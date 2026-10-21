"""Archive real layout images, source, artifacts and check status without overwriting."""
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path


def _valid_case_coverage(report, key, ring_lengths, *, loaded):
    if not isinstance(report, dict) or report.get("status") != "PASS":
        return False
    rows = report.get(key)
    if not isinstance(rows, list) or not rows:
        return False
    expected = set(ring_lengths)
    if not expected:
        return False
    observed = set()
    for row in rows:
        if not isinstance(row, dict):
            return False
        try:
            stages = int(row["stages"])
            load = float(row["wire_load_fF_per_stage"])
        except (KeyError, TypeError, ValueError):
            return False
        if stages not in expected or not (load > 0 if loaded else load == 0):
            return False
        observed.add(stages)
    return observed == expected


def copy_spice_reports(root: Path, folder: Path, ring_lengths) -> dict[str, str]:
    """Copy current-schema SPICE reports and return hashes of copied evidence.

    Loaded results use ``loaded_cases``. Their ``cases`` key is deliberately not
    consulted: that field belongs to the separate unloaded-fast report and must
    not let an unloaded-only result masquerade as loaded ring coverage.
    """
    hashes = {}
    report_paths = (
        ("results.json", "spice-results.json", "loaded_cases", True),
        ("unloaded-results.json", "spice-unloaded-results.json", "cases", False),
    )
    for source_name, target_name, case_key, loaded in report_paths:
        source = root / "build/spice" / source_name
        if not source.is_file():
            continue
        try:
            report = json.loads(source.read_text())
        except (OSError, ValueError):
            continue
        if not _valid_case_coverage(report, case_key, ring_lengths, loaded=loaded):
            continue
        destination = folder / target_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        hashes[target_name] = hashlib.sha256(destination.read_bytes()).hexdigest()
    return hashes


def main():
    root = Path(__file__).resolve().parents[1]
    name = sys.argv[1]
    assert name and "/" not in name and name[:3].isdigit()
    folder = root / "build/iterations" / name
    folder.mkdir(parents=True, exist_ok=False)
    run = root / "build/tinytapeout/src/runs/verified"
    for filename in ("architecture.png", "tt-layout.png", "tt-layout-detail.png", "tt-verification.json"):
        shutil.copy2(root / "build" / filename, folder / filename)
    report = json.loads((folder / "tt-verification.json").read_text())
    for stages in report.get("ring_lengths", []):
        path = root / f"build/tt-layout-ring-{stages}.png"
        if path.exists():
            shutil.copy2(path, folder / path.name)
    shutil.copytree(root / "tinytapeout", folder / "source/tinytapeout")
    shutil.copytree(root / "examples/resilient-probe", folder / "source/resilient-probe")
    shutil.copytree(run / "final", folder / "final")
    for filename in ("toolchain.lock.json", "tinytapeout.lock.json"):
        shutil.copy2(root / filename, folder / filename)
    shutil.copytree(root / "toolchain", folder / "source/toolchain")
    for filename in ("README.md", "CONTEXT.md"):
        shutil.copy2(root / filename, folder / filename)
    timing = root / "build/timing-review-verification.json"
    if timing.exists():
        shutil.copy2(timing, folder / "timing-review-verification.json")
    spice_hashes = copy_spice_reports(root, folder, report.get("ring_lengths", []))
    shutil.copytree(root / "scripts", folder / "source/scripts")
    shutil.copytree(root / "firmware", folder / "source/firmware",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for path in (root / "build/tt-rtl", root / "build/resilient-rtl", root / "build/tt-precheck/precheck/reports"):
        if path.exists():
            shutil.copytree(path, folder / "checks" / path.name)
    report = json.loads((folder / "tt-verification.json").read_text())
    (folder / "manifest.json").write_text(json.dumps({
        "archived_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "name": name,
        "status": report["status"],
        "gds_sha256": report["gds_sha256"],
        "png_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in folder.glob("*.png")},
        "spice_report_sha256": spice_hashes,
    }, indent=2) + "\n")
    print(folder)


if __name__ == "__main__":
    main()
