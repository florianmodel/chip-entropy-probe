#!/usr/bin/env python3
"""Fail on missing evidence or failed checks and write a concise verification report."""
import json
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
run = ROOT / "build/counter/runs/verified"
metrics_path = run / "final/metrics.json"
metrics = json.loads(metrics_path.read_text())
zero_checks = [
    "design__lint_error__count", "design__lint_warning__count",
    "design__inferred_latch__count", "design__instance_unmapped__count",
    "synthesis__check_error__count", "design__disconnected_pin__count",
    "design__max_slew_violation__count", "design__max_cap_violation__count",
    "design__max_fanout_violation__count", "route__drc_errors",
    "route__antenna_violation__count", "magic__drc_error__count",
    "klayout__drc_error__count", "magic__illegal_overlap__count",
    "design__lvs_error__count",
]
failures = []
for key in zero_checks:
    if metrics.get(key) != 0:
        failures.append(f"{key} must be zero; got {metrics.get(key)!r}")
for prefix in ("timing__setup__ws", "timing__hold__ws"):
    values = {k: v for k, v in metrics.items() if k == prefix or k.startswith(prefix + "__corner:")}
    if prefix not in values or any(not isinstance(v, (int, float)) or v < 0 for v in values.values()):
        failures.append(f"Missing or failing {prefix} timing evidence")
for path in (ROOT / "build/rtl/test.log", ROOT / "build/gates/test.log"):
    if not path.exists() or "PASS:" not in path.read_text():
        failures.append(f"Missing passing simulation: {path}")
flow_log = run / "flow.log"
if not flow_log.exists() or "Flow complete." not in flow_log.read_text():
    failures.append("Missing complete physical-flow log")
gds = run / "final/gds/counter.gds"
if not gds.exists() or gds.stat().st_size == 0:
    failures.append("Missing nonempty GDS layout")
if failures:
    raise SystemExit("Verification failed:\n" + "\n".join(failures))
report = {
    "status": "PASS",
    "design": "counter",
    "toolchain": json.loads((ROOT / "toolchain.lock.json").read_text()),
    "clock_period_ns": 20,
    "setup_slack_ns": metrics["timing__setup__ws"],
    "hold_slack_ns": metrics["timing__hold__ws"],
    "zero_error_checks": {key: metrics[key] for key in zero_checks},
    "gds_bytes": gds.stat().st_size,
    "gds_sha256": hashlib.sha256(gds.read_bytes()).hexdigest(),
    "limits": ["Standalone macro, not a complete Tiny Tapeout submission", "Gate simulation is functional, without SDF timing annotation", "No physical randomness or TRNG security tested"],
}
(ROOT / "build/verification.json").write_text(json.dumps(report, indent=2) + "\n")
lines = [
    "# Toolchain verification: PASS", "",
    "The eight-bit counter passed RTL and gate-level functional simulation, lint,",
    "synthesis, placement, routing, timing checks, Magic and KLayout DRC, and Netgen LVS.", "",
    "| Check | Result |", "| --- | --- |",
    "| Clock period | 20 ns (50 MHz) |",
    f"| Worst setup slack | {report['setup_slack_ns']:.3f} ns |",
    f"| Worst hold slack | {report['hold_slack_ns']:.3f} ns |",
    "| Magic / KLayout DRC errors | 0 / 0 |",
    "| LVS errors | 0 |", "| Routing / antenna errors | 0 / 0 |",
    f"| GDS size | {report['gds_bytes']:,} bytes |", "",
    f"GDS SHA-256: `{report['gds_sha256']}`", "",
    "Evidence: `build/verification.json`, `build/tool-versions.txt`,",
    "`build/rtl/test.log`, `build/gates/test.log`, and",
    "`build/counter/runs/verified/final/metrics.json`.", "",
    "## Limits", "",
    *[f"- {limit}." for limit in report["limits"]], "",
]
(ROOT / "build/verification.md").write_text("\n".join(lines))
print("PASS: simulation, physical checks and timing; report saved to build/verification.md")
