"""Small, deterministic helpers for provenance-bound generated evidence."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Iterable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_tree(paths: Iterable[Path]) -> str:
    """Hash a stable tree using root names and relative paths, not host paths."""
    digest = hashlib.sha256()
    for root in sorted(paths, key=lambda p: p.name):
        if not root.exists():
            digest.update(f"MISSING:{root.name}".encode())
            continue
        files = [root] if root.is_file() else sorted((p for p in root.rglob("*") if p.is_file()))
        for path in files:
            relative = root.name if root.is_file() else f"{root.name}/{path.relative_to(root).as_posix()}"
            digest.update(relative.encode())
            digest.update(b"\0")
            digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def fingerprints_match(actual: dict, expected: dict) -> bool:
    return bool(expected) and all(actual.get(key) == value for key, value in expected.items())


def validate_input_hashes(root: Path, fingerprints: dict, required=()) -> tuple[bool, str]:
    if not isinstance(fingerprints, dict) or not fingerprints:
        return False, "no input fingerprints"
    if not set(required).issubset(fingerprints):
        return False, "input fingerprint set is incomplete"
    for name, expected in fingerprints.items():
        path = root / name
        if not path.is_file() or sha256_file(path) != expected:
            return False, f"input fingerprint changed or missing: {name}"
    return True, "input fingerprints match current files"


def report_status(source: Path) -> dict[str, str]:
    """Describe optional generated evidence without implying validation."""
    return {"status": "available" if source.is_file() else "absent_unverified",
            "source": str(source)}


def reconcile_optional_report(source: Path, destination: Path, validator) -> dict[str, str]:
    """Copy a validated optional report or remove only its managed stale copy."""
    if source.is_file():
        ok, reason = validator(source)
    else:
        ok, reason = False, "source report missing"
    if ok:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return {"status": "available", "source": str(source), "reason": reason}
    destination.unlink(missing_ok=True)
    return {"status": "absent_unverified", "source": str(source), "reason": reason}
