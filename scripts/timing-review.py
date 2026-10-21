#!/usr/bin/env python3
"""Run routed/extracted setup, hold, pulse-width and period checks at 9 corners."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "toolchain.lock.json").read_text())
BUILD = ROOT / "build"
RUN = BUILD / "tinytapeout/src/runs/verified/final"
WORK = BUILD / "timing-review"
REPORT = BUILD / "timing-review-verification.json"
DESIGN = "tt_um_entropy_probe"
NETLIST = RUN / f"nl/{DESIGN}.nl.v"
GDS = RUN / f"gds/{DESIGN}.gds"
SDC = ROOT / "tinytapeout/src/constraints.sdc"

CORNER_DATA = {
    "tt_025C_1v80": {"lib": "tt_025C_1v80", "spef": ("min", "nom", "max")},
    "ss_100C_1v60": {"lib": "ss_100C_1v60", "spef": ("min", "nom", "max")},
    "ff_n40C_1v95": {"lib": "ff_n40C_1v95", "spef": ("min", "nom", "max")},
}
ANALYSES = ("min", "nom", "max")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_coverage_names():
    names = [f"divider_stage_{i}" for i in range(10)]
    names.extend(("sync_meta_to_sync_sample", "sync_sample_to_monitor"))
    return names


def tcl_for(liberty: Path, spef: Path) -> str:
    """Produce a self-contained OpenSTA script using the current tracked SDC."""
    lines = [
        f"read_liberty /work/{liberty.relative_to(ROOT).as_posix()}",
        f"read_verilog /work/{NETLIST.relative_to(ROOT).as_posix()}",
        f"link_design {DESIGN}",
        f"read_sdc /work/{SDC.relative_to(ROOT).as_posix()}",
        "set_propagated_clock [all_clocks]",
        f"read_spef /work/{spef.relative_to(ROOT).as_posix()}",
        "puts {TIMING_REVIEW_SETUP_BEGIN}",
        "report_checks -path_delay max -group_path_count 1 -digits 6",
        "puts {TIMING_REVIEW_SETUP_END}",
        "puts {TIMING_REVIEW_HOLD_BEGIN}",
        "report_checks -path_delay min -group_path_count 1 -digits 6",
        "puts {TIMING_REVIEW_HOLD_END}",
        "puts {TIMING_REVIEW_PULSE_PERIOD_VIOLATIONS_BEGIN}",
        "report_check_types -violators -min_pulse_width -min_period -digits 6",
        "puts {TIMING_REVIEW_PULSE_PERIOD_VIOLATIONS_END}",
        "puts {TIMING_REVIEW_MIN_PERIOD_BEGIN}",
        "report_clock_min_period -clocks [all_clocks]",
        "puts {TIMING_REVIEW_MIN_PERIOD_END}",
        "puts {TIMING_REVIEW_PULSE_WIDTH_BEGIN}",
        "report_pulse_width_checks -verbose -digits 6",
        "puts {TIMING_REVIEW_PULSE_WIDTH_END}",
    ]
    for i in range(10):
        name = f"divider_stage_{i}"
        cell = f"probe.divider.stage[{i}].ff"
        lines.extend([
            f"puts {{TIMING_REVIEW_COVERAGE_BEGIN_{name}}}",
            f"report_checks -path_delay max -from [get_pins {{{cell}/Q}}] "
            f"-to [get_pins {{{cell}/D}}] -group_path_count 1 -digits 6",
            f"puts {{TIMING_REVIEW_COVERAGE_END_{name}}}",
        ])
    lines.extend([
        "set sync_meta_q [get_pins -of_objects [get_nets {probe.monitor.sync_meta}] "
        "-filter {direction == output}]",
        "set sync_sample_d [get_pins -of_objects [get_nets {probe.monitor.sync_meta}] "
        "-filter {direction == input}]",
        "if {[llength $sync_meta_q] != 1} { error {Expected one sync_meta Q driver} }",
        "if {[llength $sync_sample_d] != 1} { error {Expected one sync_sample D load} }",
        "puts {TIMING_REVIEW_COVERAGE_BEGIN_sync_meta_to_sync_sample}",
        "report_checks -path_delay max -from $sync_meta_q -to $sync_sample_d "
        "-group_path_count 1 -digits 6",
        "puts {TIMING_REVIEW_COVERAGE_END_sync_meta_to_sync_sample}",
        "set sync_sample_q [get_pins -of_objects [get_nets {probe.monitor.sync_sample}] "
        "-filter {direction == output}]",
        "if {[llength $sync_sample_q] != 1} { error {Expected one sync_sample Q driver} }",
        "puts {TIMING_REVIEW_COVERAGE_BEGIN_sync_sample_to_monitor}",
        "report_checks -path_delay max -from $sync_sample_q "
        "-to [all_registers -data_pins] -group_path_count 1 -digits 6",
        "puts {TIMING_REVIEW_COVERAGE_END_sync_sample_to_monitor}",
    ])
    return "\n".join(lines) + "\n"


def _section(log: str, begin: str, end: str) -> str | None:
    start = log.find(begin)
    finish = log.find(end, start + len(begin)) if start >= 0 else -1
    if start < 0 or finish < 0:
        return None
    return log[start + len(begin):finish]


def parse_log(log: str) -> dict:
    """Extract check status and explicit path-query coverage from an OpenSTA log."""
    invalid_object = re.findall(
        r"(?im)^.*(?:not a valid (?:start point|endpoint|object)|"
        r"no objects? matched|no pins? matched|no cells? matched|"
        r"no clocks? matched|can't find|couldn't find).*$", log)
    opensta_errors = re.findall(r"(?im)^.*(?:\bError:|invalid command name).*$", log)
    setup = _section(log, "TIMING_REVIEW_SETUP_BEGIN", "TIMING_REVIEW_SETUP_END")
    hold = _section(log, "TIMING_REVIEW_HOLD_BEGIN", "TIMING_REVIEW_HOLD_END")
    violations = _section(log, "TIMING_REVIEW_PULSE_PERIOD_VIOLATIONS_BEGIN",
                          "TIMING_REVIEW_PULSE_PERIOD_VIOLATIONS_END")
    min_period = _section(log, "TIMING_REVIEW_MIN_PERIOD_BEGIN", "TIMING_REVIEW_MIN_PERIOD_END")
    pulse = _section(log, "TIMING_REVIEW_PULSE_WIDTH_BEGIN", "TIMING_REVIEW_PULSE_WIDTH_END")

    def slacks(section):
        if section is None:
            return []
        return [{"value": float(value), "status": status.upper()}
                for value, status in re.findall(
                    r"([-+]?\d+(?:\.\d+)?)\s+slack\s+\((MET|VIOLATED)\)", section, re.I)]

    coverage = {}
    for name in expected_coverage_names():
        body = _section(log, f"TIMING_REVIEW_COVERAGE_BEGIN_{name}",
                        f"TIMING_REVIEW_COVERAGE_END_{name}")
        coverage[name] = bool(body and "Startpoint:" in body and "Endpoint:" in body
                              and "No paths found" not in body)

    period_rows = []
    if min_period is not None:
        period_rows = [{"clock": clock, "period_min": float(period),
                        "fmax_mhz": (None if fmax.lower() == "inf" else float(fmax))}
                       for clock, period, fmax in re.findall(
                           r"(?m)^\s*(\S+)\s+period_min\s*=\s*([\d.]+)\s+fmax\s*=\s*([\d.]+|inf)\s*$",
                           min_period, re.I)]
    pulse_width_checks = (re.findall(r"(?m)^\s*Check:\s*(\S+)", pulse)
                          if pulse is not None else [])

    return {
        "setup_slacks": slacks(setup),
        "hold_slacks": slacks(hold),
        "setup_hold_sections_present": setup is not None and hold is not None,
        "pulse_period_violations": (violations or "").strip(),
        "pulse_period_violation_section_present": violations is not None,
        "min_period_rows": period_rows,
        "min_period_report_present": bool(period_rows),
        "pulse_width_check_count": len(pulse_width_checks),
        "pulse_width_check_types": sorted(set(pulse_width_checks)),
        "pulse_width_report_present": bool(pulse_width_checks),
        "coverage": coverage,
        "invalid_object_warnings": invalid_object,
        "opensta_errors": opensta_errors,
    }


def collect_inputs() -> dict[str, str]:
    pdk_lib_dir = ROOT / ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib"
    inputs = [
        SDC,
        ROOT / "tinytapeout/src/tt_um_entropy_probe.v",
        ROOT / "examples/resilient-probe/resilient_probe.v",
        ROOT / "examples/resilient-probe/measurement_monitor.v",
        ROOT / "examples/resilient-probe/measurement_ring.v",
        ROOT / "examples/resilient-probe/frequency_divider.v",
        ROOT / "scripts/timing-review.py",
        NETLIST,
        GDS,
        *(RUN / f"spef/{analysis}/{DESIGN}.{analysis}.spef" for analysis in ANALYSES),
        *(pdk_lib_dir / f"sky130_fd_sc_hd__{corner['lib']}.lib"
          for corner in CORNER_DATA.values()),
        ROOT / "toolchain.lock.json",
    ]
    absent = [str(path.relative_to(ROOT)) for path in inputs if not path.is_file()]
    if absent:
        raise FileNotFoundError("Required timing inputs are absent: " + ", ".join(absent))
    return {path.relative_to(ROOT).as_posix(): sha256(path) for path in sorted(set(inputs))}


def corner_definitions():
    lib_dir = ROOT / ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib"
    for analysis in ANALYSES:
        for proc, details in CORNER_DATA.items():
            name = f"{analysis}_{proc}"
            liberty = lib_dir / f"sky130_fd_sc_hd__{details['lib']}.lib"
            spef_analysis = analysis
            spef = RUN / f"spef/{spef_analysis}/{DESIGN}.{spef_analysis}.spef"
            yield name, proc, analysis, liberty, spef


def make_report(corners: dict, input_fingerprints: dict, failures: list[str]) -> dict:
    return {
        "status": "PASS" if not failures else "FAIL",
        "analysis": "static timing on one routed/extracted layout; not oscillator frequency or silicon evidence",
        "tool_image": LOCK.get("image_digest") or LOCK["image_tag"],
        "tool_version": LOCK.get("librelane_version"),
        "pdk": LOCK.get("pdk"),
        "pdk_revision": LOCK.get("pdk_revision"),
        "corner_coverage": sorted(corners),
        "corners": corners,
        "input_fingerprints": input_fingerprints,
        "failures": failures,
    }


def run() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    corners = {}
    failures = []
    try:
        input_fingerprints = collect_inputs()
    except (OSError, ValueError) as error:
        report = make_report(corners, {}, [str(error)])
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2) + "\n")
        print(error, file=sys.stderr)
        return 1

    for name, proc, analysis, liberty, spef in corner_definitions():
        tcl = WORK / f"{name}.tcl"
        log_path = WORK / f"{name}.log"
        tcl.write_text(tcl_for(liberty, spef))
        command = [sys.executable, str(ROOT / "scripts/chip.py"), "tool", "sta",
                   "-no_splash", "-exit", f"/work/{tcl.relative_to(ROOT).as_posix()}"]
        completed = subprocess.run(command, cwd=ROOT, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = completed.stdout
        log_path.write_text(output)
        parsed = parse_log(output)
        expected = set(expected_coverage_names())
        coverage_ok = set(k for k, value in parsed["coverage"].items() if value) == expected
        setup_ok = bool(parsed["setup_slacks"]) and all(
            x["status"] == "MET" and x["value"] >= 0 for x in parsed["setup_slacks"])
        hold_ok = bool(parsed["hold_slacks"]) and all(
            x["status"] == "MET" and x["value"] >= 0 for x in parsed["hold_slacks"])
        no_pulse_or_period_violations = not parsed["pulse_period_violations"]
        corner_failures = []
        if completed.returncode:
            corner_failures.append(f"STA exited {completed.returncode}")
        if not parsed["setup_hold_sections_present"] or not setup_ok:
            corner_failures.append("missing or negative setup slack")
        if not hold_ok:
            corner_failures.append("missing or negative hold slack")
        if not parsed["min_period_report_present"]:
            corner_failures.append("missing minimum-period report")
        if not parsed["pulse_width_report_present"]:
            corner_failures.append("missing pulse-width report")
        if not parsed["pulse_period_violation_section_present"]:
            corner_failures.append("missing pulse/period violation report section")
        if not no_pulse_or_period_violations:
            corner_failures.append("minimum pulse-width or period violation")
        if parsed["opensta_errors"]:
            corner_failures.append("OpenSTA reported an error")
        if parsed["invalid_object_warnings"]:
            corner_failures.append("invalid SDC/query object warning")
        if not coverage_ok:
            corner_failures.append("divider feedback or synchronizer path query missing")
        corner = {
            "process_corner": proc,
            "parasitic_corner": analysis,
            "setup_worst_slack": min((x["value"] for x in parsed["setup_slacks"]), default=None),
            "hold_worst_slack": min((x["value"] for x in parsed["hold_slacks"]), default=None),
            "setup_path_count": len(parsed["setup_slacks"]),
            "hold_path_count": len(parsed["hold_slacks"]),
            "min_period_report_present": parsed["min_period_report_present"],
            "min_period_rows": parsed["min_period_rows"],
            "pulse_width_report_present": parsed["pulse_width_report_present"],
            "pulse_width_check_count": parsed["pulse_width_check_count"],
            "pulse_width_check_types": parsed["pulse_width_check_types"],
            "pulse_period_violations": parsed["pulse_period_violations"],
            "coverage": parsed["coverage"],
            "invalid_object_warnings": parsed["invalid_object_warnings"],
            "opensta_errors": parsed["opensta_errors"],
            "log": log_path.relative_to(ROOT).as_posix(),
            "failures": corner_failures,
        }
        corners[name] = corner
        failures.extend(f"{name}: {failure}" for failure in corner_failures)
        print(f"{name}: {'PASS' if not corner_failures else 'FAIL'}; "
              f"setup={corner['setup_worst_slack']} hold={corner['hold_worst_slack']}")

    report = make_report(corners, input_fingerprints, failures)
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Wrote {REPORT.relative_to(ROOT)}: {report['status']}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run())
