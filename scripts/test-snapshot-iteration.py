#!/usr/bin/env python3
"""Regression checks for archiving the current loaded/unloaded SPICE schemas."""
import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("snapshot-iteration.py")
SPEC = importlib.util.spec_from_file_location("snapshot_iteration", SCRIPT)
snapshot_iteration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot_iteration)


class SnapshotIterationTests(unittest.TestCase):
    def _row(self, stages, load):
        return {"stages": stages, "wire_load_fF_per_stage": load, "frequency_MHz": 123.0}

    def test_copies_and_records_current_loaded_and_unloaded_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "build/spice"
            output.mkdir(parents=True)
            folder = root / "snapshot"
            folder.mkdir()
            loaded = {"status": "PASS", "schema": 1,
                "loaded_cases": [self._row(stage, 1.2) for stage in (71, 95, 127)],
                "unloaded_fast_cases": [self._row(stage, 0) for stage in (71, 95, 127)]}
            unloaded = {"status": "PASS", "schema": 1,
                "cases": [self._row(stage, 0) for stage in (71, 95, 127)]}
            (output / "results.json").write_text(json.dumps(loaded))
            (output / "unloaded-results.json").write_text(json.dumps(unloaded))
            source_bytes = {"spice-results.json": (output / "results.json").read_bytes(),
                            "spice-unloaded-results.json": (output / "unloaded-results.json").read_bytes()}

            hashes = snapshot_iteration.copy_spice_reports(root, folder, [71, 95, 127])

            expected = {"spice-results.json", "spice-unloaded-results.json"}
            self.assertEqual(set(hashes), expected)
            for name in expected:
                copied = folder / name
                self.assertEqual(copied.read_bytes(), source_bytes[name])
                self.assertEqual(hashes[name], hashlib.sha256(copied.read_bytes()).hexdigest())
            self.assertEqual(json.loads((folder / "spice-results.json").read_text())["loaded_cases"][0]["wire_load_fF_per_stage"], 1.2)

    def test_does_not_accept_unloaded_generic_cases_as_loaded_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "build/spice"
            output.mkdir(parents=True)
            folder = root / "snapshot"
            folder.mkdir()
            (output / "results.json").write_text(json.dumps({"status": "PASS",
                "cases": [self._row(stage, 0) for stage in (71, 95, 127)]}))
            self.assertEqual(snapshot_iteration.copy_spice_reports(root, folder, [71, 95, 127]), {})
            self.assertFalse((folder / "spice-results.json").exists())

    def test_skips_missing_incomplete_and_invalid_loaded_reports(self):
        scenarios = ("missing", "incomplete", "invalid")
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / "build/spice"
                output.mkdir(parents=True)
                folder = root / "snapshot"
                folder.mkdir()
                source = output / "results.json"
                if scenario == "incomplete":
                    source.write_text(json.dumps({"status": "PASS",
                        "loaded_cases": [self._row(71, 1.2), self._row(95, 1.2)]}))
                elif scenario == "invalid":
                    source.write_text("{broken json")
                self.assertEqual(snapshot_iteration.copy_spice_reports(root, folder, [71, 95, 127]), {})
                self.assertFalse((folder / "spice-results.json").exists())


if __name__ == "__main__":
    unittest.main()
