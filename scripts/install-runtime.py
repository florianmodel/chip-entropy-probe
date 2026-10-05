#!/usr/bin/env python3
"""Install checksum-verified official macOS ARM64 Colima and Lima releases."""
import hashlib
import json
from pathlib import Path
import platform
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "toolchain.lock.json").read_text())
if platform.system() != "Darwin" or platform.machine() != "arm64":
    raise RuntimeError("This runtime installer targets Apple Silicon macOS")
downloads = ROOT / ".tools/downloads"
downloads.mkdir(parents=True, exist_ok=True)
(ROOT / ".tools/bin").mkdir(parents=True, exist_ok=True)
(ROOT / ".tools/lima").mkdir(parents=True, exist_ok=True)


def download(url, path):
    print(f"Downloading {url}", flush=True)
    with urllib.request.urlopen(url) as response, path.open("wb") as destination:
        while block := response.read(1024 * 1024):
            destination.write(block)


def verify(path, expected):
    with path.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
    if actual != expected:
        raise RuntimeError(f"Checksum mismatch for {path.name}: {actual}")


colima_name = "colima-Darwin-arm64"
colima_url = f"https://github.com/abiosoft/colima/releases/download/v{LOCK['colima_version']}/{colima_name}"
colima_archive = downloads / colima_name
colima_checksum = downloads / "colima.sha256sum"
download(colima_url, colima_archive)
download(colima_url + ".sha256sum", colima_checksum)
verify(colima_archive, LOCK["colima_sha256"])
verify(colima_archive, colima_checksum.read_text().split()[0])

lima_name = f"lima-{LOCK['lima_version']}-Darwin-arm64.tar.gz"
lima_url = f"https://github.com/lima-vm/lima/releases/download/v{LOCK['lima_version']}/"
lima_archive = downloads / "lima.tar.gz"
lima_checksums = downloads / "lima.sha256sums"
download(lima_url + lima_name, lima_archive)
download(lima_url + "SHA256SUMS", lima_checksums)
expected = next(line.split()[0] for line in lima_checksums.read_text().splitlines() if line.endswith(lima_name))
verify(lima_archive, LOCK["lima_sha256"])
verify(lima_archive, expected)
(ROOT / ".tools/bin/colima").write_bytes(colima_archive.read_bytes())
(ROOT / ".tools/bin/colima").chmod(0o755)
with tarfile.open(lima_archive) as archive:
    archive.extractall(ROOT / ".tools/lima", filter="data")
print("Runtime installed and verified. Requires an existing Docker CLI.")
