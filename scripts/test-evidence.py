#!/usr/bin/env python3
"""Focused negative checks for provenance-bound evidence packaging."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence
import spice
import package_evidence

ROUTED_IMAGE = "sha256:test-image"


class EvidencePipelineTests(unittest.TestCase):
    def _routed_fixture(self, root):
        def write(relative, text):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            return path

        fixed_inputs = [
            "build/tinytapeout/src/runs/verified/final/pnl/tt_um_entropy_probe.pnl.v",
            "build/tinytapeout/src/runs/verified/final/gds/tt_um_entropy_probe.gds",
            "tinytapeout/src/constraints.sdc",
            ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice",
            ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib",
            ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__ff_n40C_1v95.lib",
            ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__ss_100C_1v60.lib",
            ".tools/pdk/sky130A/libs.tech/ngspice/models.spice",
            ".tools/pdk/sky130A/libs.ref/sky130_fd_pr/spice/device.spice",
        ]
        for rc in ("min", "nom", "max"):
            fixed_inputs.append(f"build/tinytapeout/src/runs/verified/final/spef/{rc}/tt_um_entropy_probe.{rc}.spef")
        for name in fixed_inputs:
            if name.endswith(".lib"):
                write(name, '''cell ("sky130_fd_sc_hd__dfrtp_1") {
                  pin ("CLK") {
                    timing () {
                      timing_type : "min_pulse_width";
                      rise_constraint (template) { index_1("0, 0.1"); values("0.8, 1.0"); }
                      fall_constraint (template) { index_1("0, 0.1"); values("0.9, 1.1"); }
                    }
                  }
                }
                ''')
            else:
                write(name, f"input {name}")
        from evidence import sha256_file, sha256_tree
        pdk = root / ".tools/pdk/sky130A"
        expected_conditions = sorted(package_evidence.ROUTED_CONDITIONS)
        case_rows, controls = [], []
        def measurement(label, condition, partition, first, last, scenario="steady", replay=None,
                        duration=250.0, ramp=5.0, enable_ramp=.1):
            rc, corner, voltage, temp, selection = condition
            stem = f"build/routed-spice/{label}"
            deck_path = write(stem + ".sp", f"deck for {label}\n")
            data_path = write(stem + ".dat", f"waveform for {label}\n")
            cells_path = write(stem + "-cells.spice", f"cells for {label}\n")
            write(stem + ".signals.json", "[]\n")
            lib_suffix = {"tt": "tt_025C_1v80", "ff": "ff_n40C_1v95", "ss": "ss_100C_1v60"}[corner]
            inputs = {
                "generator_sha256": "old-generator-is-allowed",
                "pnl_sha256": sha256_file(root / fixed_inputs[0]),
                "gds_sha256": sha256_file(root / fixed_inputs[1]),
                "spef_sha256": sha256_file(root / f"build/tinytapeout/src/runs/verified/final/spef/{rc}/tt_um_entropy_probe.{rc}.spef"),
                "model_tree_sha256": sha256_tree([pdk / "libs.tech/ngspice", pdk / "libs.ref/sky130_fd_pr/spice"]),
                "cell_library_sha256": sha256_file(root / ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"),
                "deck_sha256": sha256_file(deck_path),
                "constraints_sha256": sha256_file(root / "tinytapeout/src/constraints.sdc"),
                "tool_image_id": ROUTED_IMAGE,
                "liberty_sha256": sha256_file(root / f".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__{lib_suffix}.lib"),
            }
            if replay:
                inputs["replay_data_sha256"] = sha256_file(replay)
                replay_report = Path(str(replay).removesuffix(".dat") + ".measure.json")
                inputs["replay_measurements_sha256"] = sha256_file(replay_report)
            report = {
                "status": "PASS", "failures": [], "frequency_MHz": 200.0 if partition == "source" else 0.390625,
                "stage0_division": 2.0, "division_ratio": 2.0, "clock_cycles_after_settling": 12,
                "min_clock_high_ns": 1.0, "min_clock_low_ns": 1.0,
                "max_rise_slew_20_80_ns": .05, "max_fall_slew_20_80_ns": .06,
                "liberty_pulse_requirement_ns": .2, "input_fingerprints": inputs,
                "partition": partition, "first_stage": first, "last_stage": last,
                "parameters": {"partition": partition, "rc": rc, "corner": corner,
                    "voltage": voltage, "temp": temp, "selection": selection,
                    "ramp_ns": ramp, "enable_ramp_ns": enable_ramp, "duration_ns": duration, "scenario": scenario,
                    "first_stage": first if partition == "divider" else 1,
                    "stage_count": last-first+1 if partition == "divider" else 2,
                    "replay": str(replay) if replay else None},
            }
            if scenario != "steady":
                report["phase_measurements"] = [
                    {"status": "PASS", "failures": [], "min_clock_high_ns": 1.2,
                     "min_clock_low_ns": 1.2, "max_rise_slew_20_80_ns": .05,
                     "max_fall_slew_20_80_ns": .06} for _ in range(3)]
            report_path = write(stem + ".measure.json", json.dumps(report, indent=2) + "\n")
            return report_path, data_path, report

        for index, condition in enumerate(expected_conditions):
            rc, corner, voltage, temp, selection = condition
            base = f"{rc}-{corner}-{selection}-{voltage}-{temp}"
            refs = []
            source_path, previous_data, source_report = measurement(f"source-{base}", condition, "source", 0, 0)
            refs.append((source_path, previous_data, source_report))
            for first, last in package_evidence.ROUTED_STAGE_RANGES[1:]:
                path, previous_data, report = measurement(f"divider-{base}-{first}-{last}", condition,
                    "divider", first, last, replay=previous_data)
                refs.append((path, previous_data, report))
            measurements = [path.relative_to(root).as_posix() for path, _, _ in refs]
            final_report = refs[-1][2]
            composed = 200.0 / final_report["frequency_MHz"] * final_report["division_ratio"]
            case_rows.append({"status": "PASS_SCOPED_PARTITION_MODEL", "conditions": list(condition),
                "source_frequency_MHz": 200.0, "composed_division": composed,
                "stage_ranges": package_evidence.ROUTED_STAGE_RANGES, "measurements": measurements,
                "report_sha256": {name: sha256_file(root / name) for name in measurements}})
        for scenario in ("restart", "switch"):
            path, _, _ = measurement(f"control-{scenario}", ("nom", "tt", 1.8, 25, 0), "source", 0, 0,
                                     scenario=scenario, duration=1500.0, ramp=50.0, enable_ramp=5.0)
            controls.append({"scenario": scenario, "report": path.relative_to(root).as_posix(), "status": "PASS"})
        matrix = {"status": "PASS_SCOPED_PARTITION_MODEL", "coverage": "nine selected conditions plus controls",
            "cases": case_rows, "controls": controls, "generator_sha256": "old", "matrix_generator_sha256": "old",
            "limits": ["Partitioned source/divider waveform replay is not whole-chip simultaneous transistor simulation."]}
        write("build/routed-spice/matrix.json", json.dumps(matrix, indent=2) + "\n")
        return matrix

    def test_actual_routed_collector_accepts_complete_partitioned_matrix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._routed_fixture(root)
            proof = package_evidence.collect_routed_evidence(root, ROUTED_IMAGE)
            self.assertEqual(proof["status"], "PASS_SCOPED_PARTITION_MODEL")
            self.assertEqual(len(proof["cases"]), 9)
            self.assertEqual(len(proof["controls"]), 2)
            measurement = proof["cases"][0]["measurements"][0]
            self.assertIn("waveform", measurement["artifacts"])
            self.assertIn("cell_definitions", measurement["artifacts"])
            self.assertTrue(measurement["artifacts"]["deck"]["matches_report"])
            for control in proof["controls"]:
                phases = control["liberty_checked_phase_measurements"]
                self.assertEqual(len(phases), 3)
                self.assertGreater(phases[0]["liberty_pulse_requirement_ns"], .5)

    def test_routed_collector_checks_liberty_pulse_requirement_for_every_control_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = self._routed_fixture(root)
            control = next(c for c in matrix["controls"] if c["scenario"] == "restart")
            report_path = root / control["report"]
            report = json.loads(report_path.read_text())
            # This phase clears the old 0.5 ns experiment floor but violates the
            # slew-interpolated Liberty minimum (about 1.02 ns at this slew).
            report["phase_measurements"][0]["min_clock_high_ns"] = .9
            report_path.write_text(json.dumps(report, indent=2) + "\n")
            control["report_sha256"] = evidence.sha256_file(report_path)
            matrix_path = root / "build/routed-spice/matrix.json"
            matrix_path.write_text(json.dumps(matrix, indent=2) + "\n")
            with self.assertRaisesRegex(package_evidence.EvidenceError, "phase 0 clock pulse"):
                package_evidence.collect_routed_evidence(root, ROUTED_IMAGE)

    def test_routed_collector_rejects_incomplete_matrix_and_removes_stale_package_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._routed_fixture(root)
            matrix_path = root / "build/routed-spice/matrix.json"
            matrix = json.loads(matrix_path.read_text())
            matrix["status"] = "RUNNING_UNVERIFIED"
            matrix_path.write_text(json.dumps(matrix))
            status = package_evidence.reconcile_routed_evidence(
                root, root / "submission/evidence/routed-spice.json", ROUTED_IMAGE)
            self.assertEqual(status["status"], "absent_unverified")
            self.assertFalse((root / "submission/evidence/routed-spice.json").exists())
            self.assertIn("incomplete", status["reason"])

    def test_routed_collector_rejects_changed_summary_report_and_physical_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = self._routed_fixture(root)
            report = root / matrix["cases"][0]["measurements"][0]
            report.write_text(report.read_text() + "\n")
            with self.assertRaisesRegex(package_evidence.EvidenceError, "digest differs"):
                package_evidence.collect_routed_evidence(root, ROUTED_IMAGE)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._routed_fixture(root)
            gds = root / "build/tinytapeout/src/runs/verified/final/gds/tt_um_entropy_probe.gds"
            gds.write_text("changed GDS")
            with self.assertRaisesRegex(package_evidence.EvidenceError, "fingerprint changed"):
                package_evidence.collect_routed_evidence(root, ROUTED_IMAGE)

    def test_routed_collector_rejects_deck_that_no_longer_matches_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = self._routed_fixture(root)
            report_path = root / matrix["cases"][0]["measurements"][0]
            report = json.loads(report_path.read_text())
            deck = Path(str(report_path).removesuffix(".measure.json") + ".sp")
            deck.write_text(deck.read_text() + "* changed after simulation\n")
            with self.assertRaisesRegex(package_evidence.EvidenceError, "actual deck hash"):
                package_evidence.collect_routed_evidence(root, ROUTED_IMAGE)

    def test_routed_collector_rejects_changed_live_image_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._routed_fixture(root)
            with self.assertRaisesRegex(package_evidence.EvidenceError, "tool_image_id"):
                package_evidence.collect_routed_evidence(root, "sha256:changed-image")

    def _clocked_fixture(self, root):
        def write(relative, content):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return path

        fixed = [
            "build/tinytapeout/src/runs/verified/final/pnl/tt_um_entropy_probe.pnl.v",
            "build/tinytapeout/src/runs/verified/final/gds/tt_um_entropy_probe.gds",
            "tinytapeout/src/constraints.sdc",
            ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice",
            ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib",
            ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__ff_n40C_1v95.lib",
            ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__ss_100C_1v60.lib",
            ".tools/pdk/sky130A/libs.tech/ngspice/models.spice",
            ".tools/pdk/sky130A/libs.ref/sky130_fd_pr/spice/device.spice",
        ]
        lib = '''cell ("sky130_fd_sc_hd__dfrtp_1") {
          pin ("CLK") { timing () { timing_type : "min_pulse_width";
            rise_constraint (template) { index_1("0, 0.1"); values("0.8, 1.0"); }
            fall_constraint (template) { index_1("0, 0.1"); values("0.9, 1.1"); }
          } }
        }
        '''
        for relative in fixed:
            write(relative, lib if relative.endswith(".lib") else f"file {relative}\n")
        for rc in ("min", "nom", "max"):
            write(f"build/tinytapeout/src/runs/verified/final/spef/{rc}/tt_um_entropy_probe.{rc}.spef", f"{rc}\n")
        write("scripts/verify-clocked-switch.py", "matrix generator fixture\n")
        write("scripts/routed-spice.py", "reanalysis generator fixture\n")
        write("firmware/entropy_probe.py", "host firmware fixture\n")
        write("scripts/test-firmware.py", "host test fixture\n")
        from evidence import sha256_file, sha256_tree
        pdk = root / ".tools/pdk/sky130A"
        cases = []
        configs = [
            ("nom", "tt", 1.8, 25.0, "switch-safe", 2.0),
            ("min", "ff", 1.95, -40.0, "switch-safe", 2.0),
            ("max", "ss", 1.6, 100.0, "switch-safe", 2.0),
            ("nom", "tt", 1.8, 25.0, "switch", 1.0),
            ("nom", "tt", 1.8, 25.0, "switch", 10.0),
        ]
        for i, condition in enumerate(configs):
            rc, corner, voltage, temp, scenario, lead = condition
            label = f"clocked-{scenario}-{i}"
            stem = f"build/routed-spice/{label}"
            deck = write(stem + ".sp", f"deck {label}\n")
            write(stem + "-cells.spice", "four config cells\n")
            write(stem + ".signals.json", '["config0", "config1"]\n')
            wave = ["time config0 config1"]
            for ns in range(1501):
                bit0 = voltage if 490 <= ns < 950 else 0.0
                bit1 = voltage if ns >= 950 else 0.0
                wave.append(f"{ns * 1e-9:.12g} {bit0:.6g} {bit1:.6g}")
            write(stem + ".dat", "\n".join(wave) + "\n")
            lib_suffix = {"tt": "tt_025C_1v80", "ff": "ff_n40C_1v95", "ss": "ss_100C_1v60"}[corner]
            inputs = {
                "pnl_sha256": sha256_file(root / fixed[0]), "gds_sha256": sha256_file(root / fixed[1]),
                "spef_sha256": sha256_file(root / f"build/tinytapeout/src/runs/verified/final/spef/{rc}/tt_um_entropy_probe.{rc}.spef"),
                "model_tree_sha256": sha256_tree([pdk / "libs.tech/ngspice", pdk / "libs.ref/sky130_fd_pr/spice"]),
                "cell_library_sha256": sha256_file(root / fixed[3]), "deck_sha256": sha256_file(deck),
                "constraints_sha256": sha256_file(root / fixed[2]), "tool_image_id": ROUTED_IMAGE,
                "liberty_sha256": sha256_file(root / f".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__{lib_suffix}.lib"),
            }
            parameters = {"partition": "source", "rc": rc, "corner": corner, "voltage": voltage,
                "temp": temp, "selection": 0, "scenario": scenario, "control_model": "clocked",
                "host_period_ns": 20, "request_lead_ns": lead, "configuration_latency_ns": 1,
                "duration_ns": 1500, "ramp_ns": 50, "enable_ramp_ns": 5, "first_stage": 1,
                "stage_count": 2}
            # A failed original report remains valid provenance: packaging is
            # based on the independent, current reanalysis and raw waveform.
            original = {"status": "FAIL" if scenario == "switch-safe" else "PASS", "failures": [],
                "input_fingerprints": inputs, "parameters": parameters, "control_model": "clocked",
                "configuration_cells": ["cfg0a", "cfg0b", "cfg1a", "cfg1b"]}
            report_path = write(stem + ".measure.json", json.dumps(original, indent=2) + "\n")
            artifacts = {stem + ".sp": sha256_file(deck), stem + ".dat": sha256_file(root / (stem + ".dat")),
                stem + ".signals.json": sha256_file(root / (stem + ".signals.json")),
                stem + "-cells.spice": sha256_file(root / (stem + "-cells.spice"))}
            phase_rows = [{"status": "PASS", "failures": [], "expected_configuration": config,
                "frequency_MHz": 100.0, "stage0_division": 2.0, "min_clock_high_ns": 1.2,
                "min_clock_low_ns": 1.2, "max_rise_slew_20_80_ns": .05,
                "max_fall_slew_20_80_ns": .06} for config in range(3)]
            checked = {"status": "PASS" if scenario == "switch-safe" or lead == 2 else "FAIL",
                "phase_measurements": phase_rows}
            cases.append({"case": list(condition), "status": checked["status"],
                "simulation_report": report_path.relative_to(root).as_posix(),
                "simulation_report_sha256": sha256_file(report_path), "original_simulation_report": original,
                "reanalysis_generator_sha256": sha256_file(root / "scripts/routed-spice.py"),
                "measurements": checked, "artifact_sha256": artifacts})
        matrix = {"status": "PASS_SAFE_SWITCH_PROTOCOL", "cases": cases,
            "generator_sha256": sha256_file(root / "scripts/verify-clocked-switch.py"),
            "host_adapter_tests": {"status": "PASS",
                "firmware_sha256": sha256_file(root / "firmware/entropy_probe.py"),
                "test_sha256": sha256_file(root / "scripts/test-firmware.py")},
            "limits": ["stage-0 only"]}
        write("build/routed-spice/clocked-switch-matrix.json", json.dumps(matrix, indent=2) + "\n")
        return matrix

    def test_clocked_switch_collector_validates_and_collects_all_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._clocked_fixture(root)
            proof = package_evidence.collect_clocked_switch_evidence(root, ROUTED_IMAGE)
            self.assertEqual(proof["status"], "PASS_SAFE_SWITCH_PROTOCOL")
            self.assertEqual(len(proof["cases"]), 5)
            safe = [case for case in proof["cases"] if case["case"][4] == "switch-safe"]
            self.assertEqual([phase["observed_configuration"] for phase in safe[0]["safe_phase_validation"]], [0, 1, 2])
            self.assertEqual(proof["cases"][-1]["status"], "FAIL")

    def test_clocked_switch_collector_rejects_bad_safe_waveform_and_removes_stale_package_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = self._clocked_fixture(root)
            safe = matrix["cases"][0]
            data_path = root / next(path for path in safe["artifact_sha256"] if path.endswith(".dat"))
            rows = data_path.read_text().splitlines()
            for row_index in range(510, 810):
                parts = rows[row_index + 1].split()
                parts[1] = "0"
                rows[row_index + 1] = " ".join(parts)
            data_path.write_text("\n".join(rows) + "\n")
            safe["artifact_sha256"][str(data_path.relative_to(root))] = evidence.sha256_file(data_path)
            matrix_path = root / "build/routed-spice/clocked-switch-matrix.json"
            matrix_path.write_text(json.dumps(matrix, indent=2) + "\n")
            destination = root / "submission/evidence/clocked-switch.json"
            destination.parent.mkdir(parents=True)
            destination.write_text("stale")
            status = package_evidence.reconcile_clocked_switch_evidence(root, destination, ROUTED_IMAGE)
            self.assertEqual(status["status"], "absent_unverified")
            self.assertFalse(destination.exists())

    def test_clocked_switch_collector_rejects_changed_host_firmware(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._clocked_fixture(root)
            firmware = root / "firmware/entropy_probe.py"
            firmware.write_text(firmware.read_text() + "# changed after tests\n")
            with self.assertRaisesRegex(package_evidence.EvidenceError, "host-adapter provenance is stale"):
                package_evidence.collect_clocked_switch_evidence(root, ROUTED_IMAGE)

    def _spice_fixture(self, root):
        files = {
            "scripts/spice.py": "generator",
            ".tools/pdk/sky130A/libs.tech/ngspice/models.spice": "model",
            ".tools/pdk/sky130A/libs.ref/sky130_fd_pr/spice/device.spice": "device model",
            ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice": "cell",
        }
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        inputs = {
            "generator_sha256": evidence.sha256_file(root / "scripts/spice.py"),
            "model_tree_sha256": evidence.sha256_tree([
                root / ".tools/pdk/sky130A/libs.tech/ngspice",
                root / ".tools/pdk/sky130A/libs.ref/sky130_fd_pr/spice"]),
            "cell_library_sha256": evidence.sha256_file(
                root / ".tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"),
        }
        rows = [dict(corner=c, voltage=v, temp_C=t, stages=n, frequency_MHz=100.0)
                for c, v, t, n in sorted(package_evidence.SPICE_CASES)]
        source = root / "results.json"
        source.write_text(json.dumps({"status": "PASS", "image_id": "image:exact",
            "input_fingerprints": inputs, "frequency_limit_MHz": 500.0,
            "loaded_cases": rows}))
        return source

    def _timing_fixture(self, root):
        files = package_evidence.TIMING_FINGERPRINTS - {"toolchain.lock.json"}
        for name in files:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixture {name}")
        lock = {"image_digest": "image:exact", "librelane_version": "3.0.14", "pdk_revision": "rev"}
        (root / "toolchain.lock.json").write_text(json.dumps(lock))
        fingerprints = {name: evidence.sha256_file(root / name)
                        for name in package_evidence.TIMING_FINGERPRINTS}
        coverage = {**{f"divider_stage_{i}": True for i in range(10)},
                    "sync_meta_to_sync_sample": True, "sync_sample_to_monitor": True}
        corner = {"failures": {}, "setup_worst_slack": 0.1, "hold_worst_slack": 0.1,
                  "setup_path_count": 11, "hold_path_count": 11, "coverage": coverage,
                  "min_period_report_present": True, "pulse_width_report_present": True,
                  "pulse_period_violations": ""}
        report = {"status": "PASS", "input_fingerprints": fingerprints,
                  "tool_image": lock["image_digest"], "tool_version": lock["librelane_version"],
                  "pdk_revision": lock["pdk_revision"],
                  "corners": {name: dict(corner) for name in package_evidence.TIMING_CASES}}
        source = root / "timing.json"
        source.write_text(json.dumps(report))
        return source

    def test_actual_spice_report_validator_accepts_only_exact_covered_case_set(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._spice_fixture(root)
            valid, _ = package_evidence.validate_spice_report(
                root, source, unloaded=False, current_image_id="image:exact")
            self.assertTrue(valid)
            report = json.loads(source.read_text())
            report["loaded_cases"][0]["frequency_MHz"] = 500.01
            source.write_text(json.dumps(report))
            valid, reason = package_evidence.validate_spice_report(
                root, source, unloaded=False, current_image_id="image:exact")
            self.assertFalse(valid)
            self.assertIn("frequency", reason)

    def test_actual_spice_report_validator_rejects_duplicate_and_wrong_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._spice_fixture(root)
            report = json.loads(source.read_text())
            report["loaded_cases"][-1] = dict(report["loaded_cases"][0])
            source.write_text(json.dumps(report))
            valid, reason = package_evidence.validate_spice_report(
                root, source, unloaded=False, current_image_id="image:exact")
            self.assertFalse(valid)
            self.assertIn("duplicate", reason)
            source = self._spice_fixture(root)
            valid, reason = package_evidence.validate_spice_report(
                root, source, unloaded=False, current_image_id="image:changed")
            self.assertFalse(valid)
            self.assertIn("image identity", reason)

    def test_actual_timing_report_validator_rejects_negative_slack_and_changed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._timing_fixture(root)
            valid, _ = package_evidence.validate_timing_report(root, source)
            self.assertTrue(valid)
            report = json.loads(source.read_text())
            report["corners"][next(iter(report["corners"]))]["setup_worst_slack"] = -0.01
            source.write_text(json.dumps(report))
            valid, reason = package_evidence.validate_timing_report(root, source)
            self.assertFalse(valid)
            self.assertIn("negative", reason)
            report["corners"][next(iter(report["corners"]))]["setup_worst_slack"] = 0.1
            source.write_text(json.dumps(report))
            changed = root / "tinytapeout/src/constraints.sdc"
            changed.write_text("changed constraint")
            valid, reason = package_evidence.validate_timing_report(root, source)
            self.assertFalse(valid)
            self.assertIn("fingerprint", reason)

    def test_missing_report_removes_managed_stale_package_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "missing.json", root / "evidence/spice.json"
            destination.parent.mkdir()
            destination.write_text('{"status":"PASS","old":true}')
            result = evidence.reconcile_optional_report(source, destination, lambda _: (True, "ok"))
            self.assertEqual(result["status"], "absent_unverified")
            self.assertFalse(destination.exists())

    def test_changed_model_fingerprint_is_not_reusable(self):
        actual = {"model_tree_sha256": "old-model", "generator_sha256": "same"}
        expected = {"model_tree_sha256": "new-model", "generator_sha256": "same"}
        self.assertFalse(evidence.fingerprints_match(actual, expected))

    def test_changed_workspace_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "constraints.sdc"
            source.write_text("create_clock -period 2.0")
            fingerprints = {"constraints.sdc": evidence.sha256_file(source)}
            source.write_text("create_clock -period 1.0")
            valid, reason = evidence.validate_input_hashes(root, fingerprints, {"constraints.sdc"})
            self.assertFalse(valid)
            self.assertIn("constraints.sdc", reason)

    def test_over_limit_frequency_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "too-fast.dat"
            # Rising edges every 1 ns after 50 ns => 1000 MHz.
            data.write_text("".join(f"{t*0.5e-9} {1 if t % 2 else 0}\n" for t in range(0, 121)))
            with self.assertRaisesRegex(ValueError, "exceeds 500.0 MHz"):
                spice.parse_frequency(data, 1.0, "over-limit")

    def test_obsolete_report_is_removed_and_marked_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "legacy.json", root / "evidence/spice.json"
            source.write_text(json.dumps({"status": "PASS", "cases": []}))
            destination.parent.mkdir()
            destination.write_text("committed obsolete report")
            result = evidence.reconcile_optional_report(
                source, destination, lambda _: (False, "legacy report lacks input fingerprints"))
            self.assertEqual(result["status"], "absent_unverified")
            self.assertEqual(result["reason"], "legacy report lacks input fingerprints")
            self.assertFalse(destination.exists())

    def test_too_few_crossings_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "stopped.dat"
            data.write_text("0 0\n0.00000006 0\n0.00000007 0\n")
            with self.assertRaisesRegex(ValueError, "no sustained oscillation"):
                spice.parse_frequency(data, 1.0, "stopped")


if __name__ == "__main__":
    unittest.main()
