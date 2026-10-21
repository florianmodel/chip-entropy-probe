#!/usr/bin/env python3
"""Run provenance-bound schematic SKY130 oscillator corner experiments.

These are deterministic transistor-model experiments with lumped loads. They
are not extracted-layout simulation and do not establish entropy quality.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from evidence import fingerprint, sha256_file, sha256_tree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/spice"
IMAGE = "chip-ngspice:39"
CONTEXT = os.environ.get("CHIP_DOCKER_CONTEXT", "colima-chip")
PDK_ROOT = ROOT / ".tools/pdk/sky130A"
CONTAINER_PDK_ROOT = Path("/work/.tools/pdk/sky130A")
CELL_LIBRARY = PDK_ROOT / "libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"
MODEL_ROOT = PDK_ROOT / "libs.tech/ngspice"
DEVICE_MODELS = PDK_ROOT / "libs.ref/sky130_fd_pr/spice"
FREQUENCY_LIMIT_MHZ = 500.0


def specs():
    loaded = [(c, v, t, n, 5) for c in ("tt", "ff", "ss")
              for v in (1.6, 1.8, 1.95) for t in (-40, 25, 100)
              for n in (71, 95, 127)]
    # Preserve the established unloaded-fast experiment: three temperatures
    # and three ring lengths at the fastest voltage/process corner.
    unloaded = [("ff", 1.95, t, n, 0) for t in (-40, 25, 100)
                for n in (71, 95, 127)]
    return loaded, unloaded


def write_cell_definitions():
    source = CELL_LIBRARY.read_text()
    names = ("inv_1", "nand2_1", "buf_1", "dfrtp_1")
    definitions = []
    for name in names:
        match = re.search(r"(?m)^\.subckt sky130_fd_sc_hd__" + name + r"\s.*?^\.ends[^\n]*", source, re.S | re.M)
        if not match:
            raise RuntimeError(f"missing cell definition: {name}")
        definitions.append(match[0])
    (OUT / "cells.spice").write_text("\n".join(definitions) + "\n")
    (OUT / ".spiceinit").write_text("set ngbehavior=hsa\nset ng_nomodcheck\n")


def deck_for(spec):
    corner, voltage, temp, stages, wire_load = spec
    name = f"{corner}-{voltage}-{temp}-{stages}" + ("-unloaded" if wire_load == 0 else "")
    lines = [f"SKY130 {name}: deterministic startup and frequency, NOT entropy",
             f'.lib "{CONTAINER_PDK_ROOT.as_posix()}/libs.tech/ngspice/sky130.lib.spice" {corner}',
             '.include "cells.spice"', f".temp {temp}",
             f"Vpower vdd 0 PWL(0 0 5n {voltage})",
             f"Venable en 0 PWL(0 0 10n 0 10.1n {voltage})",
             f"Xgate n{stages-1} en 0 0 vdd vdd n0 sky130_fd_sc_hd__nand2_1"]
    for i in range(1, stages):
        lines.append(f"Xi{i} n{i-1} 0 0 vdd vdd n{i} sky130_fd_sc_hd__inv_1")
    lines += [f"Xbuf n{stages-1} 0 0 vdd vdd raw sky130_fd_sc_hd__buf_1",
              *[f"Cwire{i} n{i} 0 {wire_load}f" for i in range(stages)],
              f"Cload raw 0 {20 if wire_load else 0}f", ".control",
              "set filetype=ascii", "tran 20p 200n", f"wrdata {name}.dat v(raw)",
              "quit", ".endc", ".end"]
    return name, "\n".join(lines) + "\n"


def parse_frequency(data_path: Path, voltage: float, name: str) -> dict:
    data = [tuple(map(float, row.split())) for row in data_path.read_text().splitlines() if row.strip()]
    crossings = []
    for (t0, v0), (t1, v1) in zip(data, data[1:]):
        if v0 < voltage / 2 <= v1 and t0 > 50e-9:
            crossings.append(t0 + (t1 - t0) * (voltage / 2 - v0) / (v1 - v0))
    if len(crossings) < 3:
        raise ValueError(f"{name}: no sustained oscillation ({len(crossings)} rising edges after 50ns)")
    period = (crossings[-1] - crossings[0]) / (len(crossings) - 1)
    frequency = 1e-6 / period
    if frequency > FREQUENCY_LIMIT_MHZ:
        raise ValueError(f"{name}: {frequency:.3f} MHz exceeds {FREQUENCY_LIMIT_MHZ:.1f} MHz limit")
    return {"frequency_MHz": frequency, "rising_edges_after_50ns": len(crossings)}


def case(spec, *, image_id: str, model_hash: str, cell_hash: str):
    corner, voltage, temp, stages, wire_load = spec
    name, deck = deck_for(spec)
    sp, data, log = (OUT / f"{name}.{ext}" for ext in ("sp", "dat", "log"))
    meta = OUT / f"{name}.provenance.json"
    identity = {"schema": 1, "deck_sha256": fingerprint(deck),
                "generator_sha256": sha256_file(Path(__file__)),
                "model_tree_sha256": model_hash, "cell_library_sha256": cell_hash,
                "container_image_id": image_id,
                "parameters": {"corner": corner, "voltage_V": voltage, "temperature_C": temp,
                               "stages": stages, "wire_load_fF_per_stage": wire_load,
                               "output_load_fF": 20 if wire_load else 0,
                               "transient_step_s": 20e-12, "duration_s": 200e-9,
                               "frequency_limit_MHz": FREQUENCY_LIMIT_MHZ}}
    cache_valid = False
    try:
        cache_valid = (json.loads(meta.read_text()) == identity and sp.read_text() == deck
                       and data.is_file() and "ngspice-39 done" in log.read_text())
    except (OSError, json.JSONDecodeError):
        pass
    if not cache_valid:
        sp.write_text(deck)
        cmd = ["docker", "--context", CONTEXT, "run", "--rm", "--network", "none",
               "--mount", f"type=bind,source={ROOT},target=/work", "--workdir", "/work/build/spice",
               IMAGE, "ngspice", "-b", f"{name}.sp"]
        result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log.write_text(result.stdout)
        if result.returncode:
            raise RuntimeError(f"{name}: ngspice failed ({result.returncode}): {result.stdout[-1000:]}")
        meta.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n")
    measured = parse_frequency(data, voltage, name)
    return {"corner": corner, "voltage": voltage, "temp_C": temp, "stages": stages,
            "wire_load_fF_per_stage": wire_load, **measured,
            "cache": "reused" if cache_valid else "simulated"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    write_cell_definitions()
    image_id = subprocess.check_output(
        ["docker", "--context", CONTEXT, "image", "inspect", IMAGE, "--format", "{{.Id}}"],
        text=True).strip()
    model_hash = sha256_tree([MODEL_ROOT, DEVICE_MODELS])
    cell_hash = sha256_file(CELL_LIBRARY)
    loaded, unloaded = specs()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(lambda s: case(s, image_id=image_id, model_hash=model_hash,
                                            cell_hash=cell_hash), loaded + unloaded))
    report = {"status": "PASS", "schema": 1, "image_id": image_id,
              "input_fingerprints": {"model_tree_sha256": model_hash,
                                     "cell_library_sha256": cell_hash,
                                     "generator_sha256": sha256_file(Path(__file__))},
              "scope": "Schematic transistor-model transient with lumped per-stage and output loads; not extracted layout RC.",
              "entropy_claim": "None. Deterministic simulation does not model or establish entropy.",
              "frequency_limit_MHz": FREQUENCY_LIMIT_MHZ,
              "loaded_cases": [r for r in rows if r["wire_load_fF_per_stage"]],
              "unloaded_fast_cases": [r for r in rows if not r["wire_load_fF_per_stage"]]}
    (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "unloaded-results.json").write_text(json.dumps({
        "status": "PASS", "schema": 1, "image_id": image_id,
        "input_fingerprints": report["input_fingerprints"],
        "scope": report["scope"], "entropy_claim": report["entropy_claim"],
        "frequency_limit_MHz": FREQUENCY_LIMIT_MHZ,
        "cases": report["unloaded_fast_cases"]}, indent=2) + "\n")
    frequencies = [r["frequency_MHz"] for r in rows]
    print(f"PASS: {len(loaded)} loaded + {len(unloaded)} unloaded schematic cases; "
          f"{min(frequencies):.1f}–{max(frequencies):.1f} MHz (limit {FREQUENCY_LIMIT_MHZ:g} MHz)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SPICE evidence generation failed: {exc}", file=sys.stderr)
        raise
