"""Validation gates for generated evidence before it enters a package."""
from __future__ import annotations

import json
import math
from pathlib import Path
from hashlib import sha256
import re

from evidence import sha256_file, sha256_tree, validate_input_hashes

SPICE_CASES = {
    (corner, voltage, temp, stages)
    for corner in ("tt", "ff", "ss")
    for voltage in (1.6, 1.8, 1.95)
    for temp in (-40, 25, 100)
    for stages in (71, 95, 127)
}
UNLOADED_CASES = {
    ("ff", 1.95, temp, stages)
    for temp in (-40, 25, 100)
    for stages in (71, 95, 127)
}
TIMING_CASES = {
    f"{parasitic}_{process}"
    for parasitic in ("min", "nom", "max")
    for process in ("tt_025C_1v80", "ss_100C_1v60", "ff_n40C_1v95")
}
TIMING_FINGERPRINTS = {
    "tinytapeout/src/constraints.sdc",
    "tinytapeout/src/tt_um_entropy_probe.v",
    "examples/resilient-probe/resilient_probe.v",
    "examples/resilient-probe/measurement_monitor.v",
    "examples/resilient-probe/measurement_ring.v",
    "examples/resilient-probe/frequency_divider.v",
    "build/tinytapeout/src/runs/verified/final/nl/tt_um_entropy_probe.nl.v",
    "build/tinytapeout/src/runs/verified/final/gds/tt_um_entropy_probe.gds",
    "build/tinytapeout/src/runs/verified/final/spef/min/tt_um_entropy_probe.min.spef",
    "build/tinytapeout/src/runs/verified/final/spef/nom/tt_um_entropy_probe.nom.spef",
    "build/tinytapeout/src/runs/verified/final/spef/max/tt_um_entropy_probe.max.spef",
    "toolchain.lock.json",
    *{f".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__{corner}.lib"
      for corner in ("tt_025C_1v80", "ss_100C_1v60", "ff_n40C_1v95")},
}
ROUTED_CONDITIONS = {
    (rc, corner, voltage, temp, selection)
    for rc, corner, voltage, temp in (
        ("nom", "tt", 1.8, 25), ("min", "ff", 1.95, -40), ("max", "ss", 1.6, 100))
    for selection in range(3)
}
ROUTED_STAGE_RANGES = [[0, 0], [1, 2], [3, 4], [5, 6], [7, 8], [9, 9]]
ROUTED_FINGERPRINT_FIELDS = {
    "pnl_sha256", "gds_sha256", "spef_sha256", "model_tree_sha256",
    "cell_library_sha256", "deck_sha256", "constraints_sha256",
    "tool_image_id", "liberty_sha256",
}
CLOCKED_SWITCH_CASES = {
    ("nom", "tt", 1.8, 25.0, "switch-safe", 2.0),
    ("min", "ff", 1.95, -40.0, "switch-safe", 2.0),
    ("max", "ss", 1.6, 100.0, "switch-safe", 2.0),
    ("nom", "tt", 1.8, 25.0, "switch", 1.0),
    ("nom", "tt", 1.8, 25.0, "switch", 10.0),
}


class EvidenceError(ValueError):
    """A generated report cannot safely be included in the submission."""


def _workspace_path(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise EvidenceError(f"expected a workspace-relative artifact path: {relative}")
    path = root / candidate
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise EvidenceError(f"artifact path escapes workspace: {relative}") from error
    if not path.is_file():
        raise EvidenceError(f"required routed artifact missing: {relative}")
    return path


def _routed_current_fingerprints(root: Path, report: dict, current_image_id: str) -> dict:
    inputs = report.get("input_fingerprints")
    if not isinstance(inputs, dict) or not ROUTED_FINGERPRINT_FIELDS.issubset(inputs):
        raise EvidenceError("routed measurement lacks required input fingerprints")
    parameters = report.get("parameters", {})
    rc, corner = parameters.get("rc"), parameters.get("corner")
    if rc not in ("min", "nom", "max") or corner not in ("tt", "ff", "ss"):
        raise EvidenceError("routed measurement has invalid RC/process parameters")
    try:
        current_models = sha256_tree([
            root / ".tools/pdk/sky130A/libs.tech/ngspice",
            root / ".tools/pdk/sky130A/libs.ref/sky130_fd_pr/spice"])
        current = {
            "pnl_sha256": sha256_file(_workspace_path(root, "build/tinytapeout/src/runs/verified/final/pnl/tt_um_entropy_probe.pnl.v")),
            "gds_sha256": sha256_file(_workspace_path(root, "build/tinytapeout/src/runs/verified/final/gds/tt_um_entropy_probe.gds")),
            "spef_sha256": sha256_file(_workspace_path(root, f"build/tinytapeout/src/runs/verified/final/spef/{rc}/tt_um_entropy_probe.{rc}.spef")),
            "model_tree_sha256": current_models,
            "cell_library_sha256": sha256_file(_workspace_path(root, ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice")),
            "constraints_sha256": sha256_file(_workspace_path(root, "tinytapeout/src/constraints.sdc")),
            "tool_image_id": current_image_id,
        }
        suffix = {"tt": "tt_025C_1v80", "ff": "ff_n40C_1v95", "ss": "ss_100C_1v60"}[corner]
        current["liberty_sha256"] = sha256_file(_workspace_path(
            root, f".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__{suffix}.lib"))
    except OSError as error:
        raise EvidenceError(f"cannot hash routed input: {error}") from error
    for key, digest in current.items():
        if inputs.get(key) != digest:
            raise EvidenceError(f"routed input fingerprint changed: {key}")
    return current


def _measurement_artifacts(root: Path, report_path: Path, report_sha: str | None,
                           current_image_id: str) -> dict:
    try:
        report_rel = report_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise EvidenceError("measurement report is outside the workspace") from error
    report_file = _workspace_path(root, report_rel)
    report_bytes = report_file.read_bytes()
    actual_report_sha = sha256(report_bytes).hexdigest()
    if report_sha is not None and actual_report_sha != report_sha:
        raise EvidenceError(f"measurement report digest differs from matrix: {report_rel}")
    try:
        report = json.loads(report_bytes)
    except (OSError, ValueError) as error:
        raise EvidenceError(f"invalid measurement JSON: {report_rel}: {error}") from error
    if not isinstance(report, dict) or report.get("status") != "PASS" or report.get("failures") != []:
        raise EvidenceError(f"measurement report is not a clean PASS: {report_rel}")
    inputs = report.get("input_fingerprints", {})
    current = _routed_current_fingerprints(root, report, current_image_id)
    stem = report_rel.removesuffix(".measure.json")
    deck_rel, data_rel = stem + ".sp", stem + ".dat"
    cells_rel, signals_rel = stem + "-cells.spice", stem + ".signals.json"
    deck = _workspace_path(root, deck_rel)
    if inputs.get("deck_sha256") != sha256_file(deck):
        raise EvidenceError(f"actual deck hash does not match measurement: {report_rel}")
    data = _workspace_path(root, data_rel)
    cells = _workspace_path(root, cells_rel)
    signals = _workspace_path(root, signals_rel)
    parameters = report.get("parameters", {})
    if report.get("partition") == "divider":
        replay = parameters.get("replay")
        if not replay:
            raise EvidenceError(f"divider report has no replay waveform: {report_rel}")
        replay_path = Path(replay)
        if replay_path.is_absolute():
            try:
                replay_rel = replay_path.resolve().relative_to(root.resolve()).as_posix()
            except ValueError as error:
                raise EvidenceError(f"replay waveform is outside workspace: {report_rel}") from error
        else:
            replay_rel = replay_path.as_posix()
        replay_file = _workspace_path(root, replay_rel)
        replay_report = _workspace_path(root, replay_rel.removesuffix(".dat") + ".measure.json")
        if (inputs.get("replay_data_sha256") != sha256_file(replay_file) or
                inputs.get("replay_measurements_sha256") != sha256_file(replay_report)):
            raise EvidenceError(f"replay waveform fingerprint mismatch: {report_rel}")
    return {
        "path": report_rel,
        "sha256": actual_report_sha,
        "report": report,
        "input_fingerprints": inputs,
        "current_inputs_verified": current,
        "metrics": {key: report.get(key) for key in (
            "frequency_MHz", "stage0_division", "division_ratio", "clock_cycles_after_settling",
            "min_clock_high_ns", "min_clock_low_ns", "max_rise_slew_20_80_ns",
            "max_fall_slew_20_80_ns", "liberty_pulse_requirement_ns", "first_stage", "last_stage")},
        "artifacts": {
            "deck": {"path": deck_rel, "sha256": sha256_file(deck), "matches_report": True},
            "waveform": {"path": data_rel, "sha256": sha256_file(data)},
            "cell_definitions": {"path": cells_rel, "sha256": sha256_file(cells)},
            "signal_list": {"path": signals_rel, "sha256": sha256_file(signals)},
        },
    }


def _braced(text: str, start: int) -> str:
    begin = text.index("{", start)
    depth, end = 1, begin + 1
    while depth:
        if end >= len(text):
            raise ValueError("unterminated Liberty group")
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
        end += 1
    return text[begin + 1:end - 1]


def _liberty_pulse_floor(root: Path, corner: str, measurements: dict) -> float:
    """Interpolate the dfrtp CLK min-pulse constraint at the measured worst slew."""
    suffix = {"tt": "tt_025C_1v80", "ff": "ff_n40C_1v95", "ss": "ss_100C_1v60"}.get(corner)
    if suffix is None:
        raise EvidenceError(f"unsupported control Liberty corner: {corner}")
    liberty = _workspace_path(
        root, f".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__{suffix}.lib")
    try:
        text = liberty.read_text()
        cell_start = text.index('cell ("sky130_fd_sc_hd__dfrtp_1")')
        cell = _braced(text, cell_start)
        clk_start = cell.index('pin ("CLK")')
        clk = _braced(cell, clk_start)
        rise_slew = _number(measurements.get("max_rise_slew_20_80_ns"))
        fall_slew = _number(measurements.get("max_fall_slew_20_80_ns"))
        if rise_slew is None or fall_slew is None or rise_slew < 0 or fall_slew < 0:
            raise ValueError("missing or invalid clock slew")
        slew = max(rise_slew, fall_slew)
        requirements = []
        for match in re.finditer(r"timing\s*\([^)]*\)\s*\{", clk):
            timing = _braced(clk, match.start())
            if '"min_pulse_width"' not in timing:
                continue
            for table in re.finditer(r"(?:rise|fall)_constraint\s*\([^)]*\)\s*\{", timing):
                values = _braced(timing, table.start())
                xs = list(map(float, re.search(r'index_1\("([^\"]+)"\)', values)[1].split(",")))
                ys = list(map(float, re.search(r'values\("([^\"]+)"\)', values)[1].split(",")))
                if len(xs) != len(ys) or len(xs) < 2 or slew > xs[-1]:
                    raise ValueError("slew outside Liberty characterization")
                value = ys[0]
                for x0, x1, y0, y1 in zip(xs, xs[1:], ys, ys[1:]):
                    if x0 <= slew <= x1:
                        value = y0 + (y1 - y0) * (slew - x0) / (x1 - x0)
                        break
                requirements.append(value)
        if not requirements:
            raise ValueError("missing CLK min-pulse-width tables")
        requirement = max(requirements)
        if not math.isfinite(requirement) or requirement < 0:
            raise ValueError("invalid interpolated CLK pulse requirement")
        return requirement
    except (OSError, ValueError, TypeError, AttributeError, IndexError, ZeroDivisionError) as error:
        raise EvidenceError(f"cannot validate control Liberty pulse requirement: {error}") from error


def collect_routed_evidence(root: Path, current_image_id: str) -> dict:
    matrix_path = _workspace_path(root, "build/routed-spice/matrix.json")
    matrix_sha = sha256_file(matrix_path)
    try:
        matrix = json.loads(matrix_path.read_bytes())
    except (OSError, ValueError) as error:
        raise EvidenceError(f"invalid routed matrix: {error}") from error
    if not isinstance(matrix, dict) or matrix.get("status") != "PASS_SCOPED_PARTITION_MODEL":
        raise EvidenceError("routed matrix is missing, incomplete or failed: " + (str(matrix.get("status")) + "; " + str(matrix.get("failure", "")) if isinstance(matrix, dict) else "invalid matrix"))
    cases = matrix.get("cases")
    if not isinstance(cases, list) or len(cases) != 9:
        raise EvidenceError("routed matrix must contain all nine source/PVT/RC conditions")
    observed = set()
    collected_cases = []
    for case in cases:
        try:
            condition = (case["conditions"][0], case["conditions"][1], float(case["conditions"][2]),
                         float(case["conditions"][3]), int(case["conditions"][4]))
        except (KeyError, IndexError, TypeError, ValueError):
            raise EvidenceError("malformed routed matrix condition")
        if condition in observed:
            raise EvidenceError(f"duplicate routed matrix condition: {condition}")
        observed.add(condition)
        if condition not in ROUTED_CONDITIONS or case.get("status") != "PASS_SCOPED_PARTITION_MODEL":
            raise EvidenceError(f"unexpected or failed routed matrix case: {condition}")
        if case.get("stage_ranges") != ROUTED_STAGE_RANGES:
            raise EvidenceError(f"partition composition is incomplete: {condition}")
        if _number(case.get("source_frequency_MHz")) is None or _number(case.get("source_frequency_MHz")) <= 0:
            raise EvidenceError(f"invalid source frequency in routed case: {condition}")
        composed = _number(case.get("composed_division"))
        if composed is None or abs(composed - 1024.0) > 10.24:
            raise EvidenceError(f"composed division is outside the /1024 tolerance: {condition}")
        reports = case.get("measurements")
        report_hashes = case.get("report_sha256", {})
        expected_count = len(ROUTED_STAGE_RANGES)
        if not isinstance(reports, list) or len(reports) != expected_count or set(report_hashes) != set(reports):
            raise EvidenceError(f"routed case report list/hash map is incomplete: {condition}")
        measurements = []
        for index, report_rel in enumerate(reports):
            report_file = _workspace_path(root, report_rel)
            proof = _measurement_artifacts(root, report_file, report_hashes[report_rel], current_image_id)
            report = proof["report"]
            expected_partition = "source" if index == 0 else "divider"
            expected_first, expected_last = ROUTED_STAGE_RANGES[index]
            if (report.get("partition") != expected_partition or report.get("first_stage") != expected_first or
                    report.get("last_stage") != expected_last):
                raise EvidenceError(f"measurement partition does not match matrix stage range: {report_rel}")
            params = report.get("parameters", {})
            pvt = (params.get("rc"), params.get("corner"), _number(params.get("voltage")),
                   _number(params.get("temp")), params.get("selection"))
            if pvt != condition or params.get("scenario") != "steady":
                raise EvidenceError(f"measurement condition does not match matrix: {report_rel}")
            if index == 0:
                if abs(float(report.get("frequency_MHz", 0)) - float(case["source_frequency_MHz"])) > 1e-6:
                    raise EvidenceError(f"source frequency differs from report: {report_rel}")
            if index == expected_count - 1:
                ratio = _number(report.get("division_ratio"))
                frequency = _number(report.get("frequency_MHz"))
                if ratio is None or ratio <= 0 or frequency is None or frequency <= 0:
                    raise EvidenceError(f"final divider measurement lacks division data: {report_rel}")
                measured_composition = float(case["source_frequency_MHz"]) / frequency * ratio
                if abs(measured_composition - composed) > 1e-6:
                    raise EvidenceError(f"reported composed ratio disagrees with source/final measurements: {condition}")
            measurements.append(proof)
        collected_cases.append({"conditions": list(condition), "source_frequency_MHz": case["source_frequency_MHz"],
                                "composed_division": case["composed_division"],
                                "stage_ranges": case["stage_ranges"], "measurements": measurements})
    if observed != ROUTED_CONDITIONS:
        raise EvidenceError("routed matrix condition set is incomplete")
    controls = matrix.get("controls")
    if not isinstance(controls, list) or {control.get("scenario") for control in controls if isinstance(control, dict)} != {"restart", "switch"} or len(controls) != 2:
        raise EvidenceError("routed matrix must include passing restart and switch controls")
    collected_controls = []
    for control in controls:
        if not isinstance(control, dict) or control.get("status") != "PASS":
            raise EvidenceError("restart/switch control is not PASS")
        report_rel = control.get("report")
        proof = _measurement_artifacts(root, _workspace_path(root, report_rel), control.get("report_sha256"), current_image_id)
        report = proof["report"]
        params = report.get("parameters", {})
        scenario = control["scenario"]
        if (report.get("partition") != "source" or params.get("scenario") != scenario or
                params.get("rc") != "nom" or params.get("corner") != "tt" or
                _number(params.get("voltage")) != 1.8 or _number(params.get("temp")) != 25.0 or
                params.get("selection") != 0 or _number(params.get("duration_ns")) != 1500.0 or
                _number(params.get("ramp_ns")) != 50.0 or _number(params.get("enable_ramp_ns")) != 5.0):
            raise EvidenceError(f"control report does not match its scenario: {report_rel}")
        phases = report.get("phase_measurements")
        if not isinstance(phases, list) or len(phases) != 3 or any(
                not isinstance(phase, dict) or phase.get("status") != "PASS" or phase.get("failures") != []
                for phase in phases):
            raise EvidenceError(f"control report lacks three passing phases: {report_rel}")
        checked_phases = []
        for index, phase in enumerate(phases):
            required = _liberty_pulse_floor(root, params.get("corner"), phase)
            high, low = _number(phase.get("min_clock_high_ns")), _number(phase.get("min_clock_low_ns"))
            if high is None or low is None or high < required or low < required:
                raise EvidenceError(
                    f"control phase {index} clock pulse is below slew-interpolated Liberty requirement: {report_rel}")
            checked_phases.append({**phase, "liberty_pulse_requirement_ns": required})
        collected_controls.append({"scenario": scenario, "status": "PASS", "measurement": proof,
                                   "liberty_checked_phase_measurements": checked_phases})
    if sha256_file(matrix_path) != matrix_sha:
        raise EvidenceError("routed matrix changed during collection")
    return {
        "schema": 1,
        "status": "PASS_SCOPED_PARTITION_MODEL",
        "scope": "Nine selected PVT/RC scenarios, each composed from adjacent transistor/RC partitions; plus restart and switch controls. Not whole-chip simultaneous transistor simulation or silicon qualification.",
        "actual_image_id": current_image_id,
        "matrix": {"path": "build/routed-spice/matrix.json", "sha256": matrix_sha,
                   "generator_sha256": matrix.get("matrix_generator_sha256"),
                   "experiment_generator_sha256": matrix.get("generator_sha256"),
                   "coverage": matrix.get("coverage"), "report": matrix},
        "cases": collected_cases,
        "controls": collected_controls,
        "limitations": matrix.get("limits", []),
    }


def reconcile_routed_evidence(root: Path, destination: Path, current_image_id: str) -> dict:
    try:
        proof = collect_routed_evidence(root, current_image_id)
    except (EvidenceError, OSError, ValueError, TypeError, KeyError, AttributeError, IndexError) as error:
        destination.unlink(missing_ok=True)
        return {"status": "absent_unverified", "source": "build/routed-spice/matrix.json", "reason": str(error)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(proof, indent=2) + "\n")
    return {"status": "available_scoped_partition_model", "source": "build/routed-spice/matrix.json",
            "sha256": sha256_file(destination)}


def _clocked_signal_trace(root: Path, report_rel: str, artifacts: dict):
    data_rel = next((name for name in artifacts if name.endswith(".dat")), None)
    signals_rel = next((name for name in artifacts if name.endswith(".signals.json")), None)
    if not data_rel or not signals_rel:
        raise EvidenceError("clocked report lacks waveform or signal-list artifact")
    labels = json.loads(_workspace_path(root, signals_rel).read_text())
    if not isinstance(labels, list) or "config0" not in labels or "config1" not in labels:
        raise EvidenceError("clocked waveform does not expose both configuration registers")
    rows = _workspace_path(root, data_rel).read_text().splitlines()
    columns = [[] for _ in range(len(labels) + 1)]
    try:
        for row in rows[1:]:
            values = list(map(float, row.split()))
            if len(values) != len(columns):
                raise ValueError("waveform column count mismatch")
            for col, value in zip(columns, values):
                col.append(value)
    except (ValueError, TypeError) as error:
        raise EvidenceError(f"invalid clocked waveform for {report_rel}: {error}") from error
    if not columns[0] or any(not math.isfinite(value) for col in columns for value in col):
        raise EvidenceError(f"empty or non-finite clocked waveform: {report_rel}")
    return columns[0], columns[1:], labels


def _clocked_switch_windows(duration_ns: float, lead_ns: float, period_ns: float = 20.0):
    intervals = []
    for fraction in (.3, .6):
        edge_ns = 10 + math.ceil((duration_ns * fraction - 10) / period_ns) * period_ns
        intervals.append((edge_ns - lead_ns - 2 * period_ns, edge_ns + 2 * period_ns))
    (off1, on1), (off2, on2) = intervals
    return [(.08, (off1 - 10) / duration_ns),
            ((on1 + 20) / duration_ns, (off2 - 10) / duration_ns),
            ((on2 + 20) / duration_ns, 1.)]


def _validate_clocked_safe_phases(root: Path, phases: list, times: list, values: list, labels: list,
                                  voltage: float, corner: str, duration_ns: float, lead_ns: float):
    if len(phases) != 3:
        raise EvidenceError("safe switch reanalysis must contain exactly three phases")
    label_index = {name: index for index, name in enumerate(labels)}
    total = times[-1]
    checked = []
    for index, phase in enumerate(phases):
        if not isinstance(phase, dict) or phase.get("status") != "PASS" or phase.get("failures") != []:
            raise EvidenceError(f"safe switch phase {index} did not pass reanalysis")
        if phase.get("expected_configuration") != index:
            raise EvidenceError(f"safe switch phase {index} has incorrect expected configuration")
        frequency = _number(phase.get("frequency_MHz"))
        ratio = _number(phase.get("stage0_division"))
        high, low = _number(phase.get("min_clock_high_ns")), _number(phase.get("min_clock_low_ns"))
        if (frequency is None or not 0 < frequency <= 500 or ratio is None or abs(ratio - 2.0) > .02 or
                high is None or low is None or high < .5 or low < .5):
            raise EvidenceError(f"safe switch phase {index} violates frequency/division/pulse limits")
        requirement = _liberty_pulse_floor(root, corner, phase)
        if high < requirement or low < requirement:
            raise EvidenceError(f"safe switch phase {index} is below its slew-interpolated Liberty pulse requirement")
        fraction_start, fraction_end = _clocked_switch_windows(duration_ns, lead_ns)[index]
        selected = [row for row, time in enumerate(times) if total * fraction_start <= time <= total * fraction_end]
        if not selected:
            raise EvidenceError(f"safe switch phase {index} has no waveform samples")
        config = 0
        for bit in (0, 1):
            observed = [values[label_index[f"config{bit}"]][row] for row in selected]
            want = (index >> bit) & 1
            failed = min(observed) < .8 * voltage if want else max(observed) > .2 * voltage
            if failed:
                raise EvidenceError(f"safe switch phase {index} waveform did not settle configuration bit {bit}")
            config |= want << bit
        checked.append({**phase, "observed_configuration": config,
                        "liberty_pulse_requirement_ns": requirement})
    return checked


def collect_clocked_switch_evidence(root: Path, current_image_id: str) -> dict:
    matrix_path = _workspace_path(root, "build/routed-spice/clocked-switch-matrix.json")
    matrix_sha = sha256_file(matrix_path)
    try:
        matrix = json.loads(matrix_path.read_bytes())
    except (OSError, ValueError) as error:
        raise EvidenceError(f"invalid clocked switch matrix: {error}") from error
    if not isinstance(matrix, dict) or matrix.get("status") != "PASS_SAFE_SWITCH_PROTOCOL":
        raise EvidenceError("clocked switch matrix is missing or incomplete")
    matrix_generator = sha256_file(_workspace_path(root, "scripts/verify-clocked-switch.py"))
    reanalysis_generator = sha256_file(_workspace_path(root, "scripts/routed-spice.py"))
    if matrix.get("generator_sha256") != matrix_generator:
        raise EvidenceError("clocked switch matrix generator fingerprint is stale")
    host_tests = matrix.get("host_adapter_tests")
    if not isinstance(host_tests, dict) or host_tests.get("status") != "PASS":
        raise EvidenceError("clocked switch matrix lacks passing host-adapter tests")
    for key, relative in (("firmware_sha256", "firmware/entropy_probe.py"),
                          ("test_sha256", "scripts/test-firmware.py")):
        if host_tests.get(key) != sha256_file(_workspace_path(root, relative)):
            raise EvidenceError(f"clocked switch host-adapter provenance is stale: {key}")
    cases = matrix.get("cases")
    if not isinstance(cases, list) or len(cases) != 5:
        raise EvidenceError("clocked switch matrix must contain exactly five cases")
    observed, collected = set(), []
    for proof in cases:
        try:
            case = proof["case"]
            condition = (case[0], case[1], float(case[2]), float(case[3]), case[4], float(case[5]))
        except (KeyError, IndexError, TypeError, ValueError):
            raise EvidenceError("malformed clocked switch case")
        if condition in observed or condition not in CLOCKED_SWITCH_CASES:
            raise EvidenceError(f"duplicate or unexpected clocked switch case: {condition}")
        observed.add(condition)
        safe = condition[4] == "switch-safe"
        permitted_statuses = ("PASS",) if safe else ("PASS", "FAIL")
        if proof.get("status") not in permitted_statuses:
            raise EvidenceError(f"clocked switch case did not complete: {condition}")
        if proof.get("reanalysis_generator_sha256") != reanalysis_generator:
            raise EvidenceError(f"clocked switch reanalysis generator fingerprint is stale: {condition}")
        report_rel = proof.get("simulation_report")
        report_path = _workspace_path(root, report_rel)
        report_sha = sha256_file(report_path)
        if report_sha != proof.get("simulation_report_sha256"):
            raise EvidenceError(f"clocked source report digest changed: {report_rel}")
        try:
            original = json.loads(report_path.read_bytes())
        except (OSError, ValueError) as error:
            raise EvidenceError(f"invalid original clocked report {report_rel}: {error}") from error
        if original != proof.get("original_simulation_report") or original.get("status") not in ("PASS", "FAIL"):
            raise EvidenceError(f"clocked original simulation provenance is invalid: {report_rel}")
        current = _routed_current_fingerprints(root, original, current_image_id)
        params = original.get("parameters", {})
        rc, corner, voltage, temp, scenario, lead = condition
        expected = {"partition": "source", "rc": rc, "corner": corner, "voltage": voltage, "temp": temp,
            "selection": 0, "scenario": scenario, "control_model": "clocked", "host_period_ns": 20.0,
            "request_lead_ns": lead, "configuration_latency_ns": 1.0, "duration_ns": 1500.0,
            "ramp_ns": 50.0, "enable_ramp_ns": 5.0, "first_stage": 1, "stage_count": 2}
        if any(params.get(key) != value for key, value in expected.items()):
            raise EvidenceError(f"clocked simulation parameters changed: {condition}")
        if original.get("control_model") != "clocked" or len(original.get("configuration_cells", [])) != 4:
            raise EvidenceError(f"clocked simulation lacks four mapped configuration flops: {condition}")
        measurements = proof.get("measurements")
        expected_status = "PASS" if safe else proof.get("status")
        if (not isinstance(measurements, dict) or measurements.get("status") != expected_status or
                proof.get("status") != expected_status):
            raise EvidenceError(f"clocked reanalysis status is inconsistent: {condition}")
        artifacts = proof.get("artifact_sha256")
        if not isinstance(artifacts, dict) or len(artifacts) != 4:
            raise EvidenceError(f"clocked case artifact map is incomplete: {condition}")
        verified_artifacts = {}
        for relative, digest in artifacts.items():
            actual = sha256_file(_workspace_path(root, relative))
            if actual != digest:
                raise EvidenceError(f"clocked case artifact changed: {relative}")
            verified_artifacts[relative] = actual
        deck_rel = next((name for name in artifacts if name.endswith(".sp")), None)
        if not deck_rel or original.get("input_fingerprints", {}).get("deck_sha256") != verified_artifacts[deck_rel]:
            raise EvidenceError(f"clocked current deck hash does not match original report: {condition}")
        if safe:
            times, values, labels = _clocked_signal_trace(root, report_rel, artifacts)
            phase_proof = _validate_clocked_safe_phases(root, measurements.get("phase_measurements", []),
                times, values, labels, voltage, corner, 1500.0, lead)
        else:
            phase_proof = measurements.get("phase_measurements")
            if not isinstance(phase_proof, list) or len(phase_proof) != 3:
                raise EvidenceError(f"live-switch diagnostic is incomplete: {condition}")
        collected.append({"case": list(condition), "status": proof["status"],
            "simulation_report": {"path": report_rel, "sha256": report_sha, "original_status": original["status"],
                "original_report": original, "current_inputs_verified": current},
            "reanalysis_generator_sha256": proof["reanalysis_generator_sha256"],
            "measurements": measurements, "safe_phase_validation": phase_proof if safe else None,
            "artifacts": verified_artifacts})
    if observed != CLOCKED_SWITCH_CASES:
        raise EvidenceError("clocked switch matrix case set is incomplete")
    if sha256_file(matrix_path) != matrix_sha:
        raise EvidenceError("clocked switch matrix changed during collection")
    return {"schema": 1, "status": "PASS_SAFE_SWITCH_PROTOCOL",
        "scope": "Three clocked safe-switch PVT scenarios plus two nominal live-switch diagnostics; stage-0 divider only. Not full-chip simulation or silicon qualification.",
        "actual_image_id": current_image_id,
        "matrix": {"path": "build/routed-spice/clocked-switch-matrix.json", "sha256": matrix_sha,
            "generator_sha256": matrix["generator_sha256"], "report": matrix},
        "cases": collected, "limits": matrix.get("limits", [])}


def reconcile_clocked_switch_evidence(root: Path, destination: Path, current_image_id: str) -> dict:
    try:
        proof = collect_clocked_switch_evidence(root, current_image_id)
    except (EvidenceError, OSError, ValueError, TypeError, KeyError, AttributeError, IndexError) as error:
        destination.unlink(missing_ok=True)
        return {"status": "absent_unverified", "source": "build/routed-spice/clocked-switch-matrix.json",
                "reason": str(error)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(proof, indent=2) + "\n")
    return {"status": "available_safe_switch_protocol", "source": "build/routed-spice/clocked-switch-matrix.json",
            "sha256": sha256_file(destination)}


def _load_pass(source: Path):
    try:
        report = json.loads(source.read_text())
    except (OSError, ValueError) as error:
        return None, f"invalid report: {error}"
    if not isinstance(report, dict) or report.get("status") != "PASS":
        return None, "report is not PASS"
    return report, ""


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def validate_spice_report(root: Path, source: Path, *, unloaded: bool,
                          current_image_id: str) -> tuple[bool, str]:
    report, reason = _load_pass(source)
    if report is None:
        return False, reason
    if report.get("image_id") != current_image_id:
        return False, "SPICE container image identity changed"
    try:
        expected_hashes = {
            "generator_sha256": sha256_file(root / "scripts/spice.py"),
            "model_tree_sha256": sha256_tree([
                root / ".tools/pdk/sky130A/libs.tech/ngspice",
                root / ".tools/pdk/sky130A/libs.ref/sky130_fd_pr/spice"]),
            "cell_library_sha256": sha256_file(root / ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"),
        }
    except OSError as error:
        return False, f"SPICE model input unavailable: {error}"
    actual_hashes = report.get("input_fingerprints", {})
    if any(actual_hashes.get(key) != value for key, value in expected_hashes.items()):
        return False, "SPICE generator or model inputs changed"
    limit = _number(report.get("frequency_limit_MHz"))
    if limit != 500.0:
        return False, "missing 500 MHz limit assertion"
    rows = report.get("cases") if unloaded else report.get("loaded_cases")
    expected = UNLOADED_CASES if unloaded else SPICE_CASES
    if not isinstance(rows, list) or len(rows) != len(expected):
        return False, f"expected {len(expected)} {'unloaded' if unloaded else 'loaded'} corner measurements"
    observed = set()
    for row in rows:
        try:
            key = (row["corner"], float(row["voltage"]), int(row["temp_C"]), int(row["stages"]))
        except (KeyError, TypeError, ValueError):
            return False, "malformed SPICE measurement"
        frequency = _number(row.get("frequency_MHz"))
        if key in observed:
            return False, "duplicate SPICE corner measurement"
        observed.add(key)
        if frequency is None or not (0 < frequency <= limit):
            return False, f"frequency missing or outside (0, {limit:g}] MHz"
    if observed != expected:
        return False, "SPICE corner tuples are incomplete or unexpected"
    return True, "fresh PASS report with complete corner coverage"


def validate_timing_report(root: Path, source: Path) -> tuple[bool, str]:
    report, reason = _load_pass(source)
    if report is None:
        return False, reason
    matched, reason = validate_input_hashes(root, report.get("input_fingerprints", {}), TIMING_FINGERPRINTS)
    if not matched:
        return False, reason
    try:
        lock = json.loads((root / "toolchain.lock.json").read_text())
    except (OSError, ValueError) as error:
        return False, f"toolchain lock unavailable: {error}"
    if (report.get("tool_image") != lock.get("image_digest") or
            report.get("tool_version") != lock.get("librelane_version") or
            report.get("pdk_revision") != lock.get("pdk_revision")):
        return False, "timing report tool or PDK identity changed"
    corners = report.get("corners", {})
    if not isinstance(corners, dict) or set(corners) != TIMING_CASES:
        return False, "timing report does not contain all nine required corners"
    required_paths = {*(f"divider_stage_{stage}" for stage in range(10)),
                      "sync_meta_to_sync_sample", "sync_sample_to_monitor"}
    for name, result in corners.items():
        if not isinstance(result, dict):
            return False, f"malformed timing corner: {name}"
        setup = _number(result.get("setup_worst_slack"))
        hold = _number(result.get("hold_worst_slack"))
        coverage = result.get("coverage", {})
        setup_count = _number(result.get("setup_path_count"))
        hold_count = _number(result.get("hold_path_count"))
        if (result.get("failures") or setup is None or setup < 0 or hold is None or hold < 0 or
                setup_count is None or setup_count <= 0 or hold_count is None or hold_count <= 0 or
                not isinstance(coverage, dict) or
                not required_paths.issubset(coverage) or any(coverage[path] is not True for path in required_paths) or
                result.get("min_period_report_present") is not True or
                result.get("pulse_width_report_present") is not True or
                result.get("pulse_period_violations") != ""):
            return False, f"timing corner failed, is incomplete, or has negative/non-finite slack: {name}"
    return True, "fresh PASS report with complete nine-corner timing coverage"
