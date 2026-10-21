#!/usr/bin/env python3
"""Project-local entry point for the pinned, open source ASIC toolchain."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "toolchain.lock.json").read_text())


def execute(argv, **kwargs):
    print("+ " + shlex.join(map(str, argv)), flush=True)
    subprocess.run(list(map(str, argv)), check=True, cwd=ROOT, **kwargs)


def docker(*args):
    return ["docker", "--context", os.environ.get("CHIP_DOCKER_CONTEXT", LOCK["docker_context"]), *args]


def container(argv, *, network=False):
    (ROOT / ".tools/pdk").mkdir(parents=True, exist_ok=True)
    image = LOCK["image_digest"] or LOCK["image_tag"]
    execute(docker(
        "run", "--rm", "--init", "--network", "bridge" if network else "none",
        "--mount", f"type=bind,source={ROOT},target=/work",
        "--workdir", "/work", "--env", "PDK_ROOT=/work/.tools/pdk",
        image, *argv,
    ))


def start():
    env = os.environ.copy()
    env["PATH"] = str(ROOT / ".tools/bin") + os.pathsep + str(ROOT / ".tools/lima/bin") + os.pathsep + env["PATH"]
    binary = ROOT / ".tools/bin/colima"
    if not binary.exists():
        raise RuntimeError("Runtime missing: run python3 scripts/install-runtime.py first")
    execute([binary, "start", "chip", "--vm-type", "vz", "--mount-type", "virtiofs",
             "--mount", f"{ROOT}:w", "--cpus", "4", "--memory", "8", "--disk", "40",
             "--activate=false", "--ssh-config=false"], env=env)


def prepare():
    execute(docker("pull", LOCK["image_digest"] or LOCK["image_tag"]))
    container(["ciel", "enable", "--pdk-root", "/work/.tools/pdk", "--pdk", LOCK["pdk_family"],
               LOCK["pdk_revision"]], network=True)


def rtl():
    container(["bash", "/work/scripts/verify-rtl.sh"])


def gds(design="counter"):
    pdk = ROOT / ".tools/pdk" / LOCK["pdk"]
    if not pdk.is_symlink() or LOCK["pdk_revision"] not in pdk.readlink().parts:
        raise RuntimeError("Pinned PDK is not enabled: run python3 scripts/chip.py prepare")
    shutil.copytree(ROOT / "examples" / design, ROOT / "build" / design, dirs_exist_ok=True)
    if design == "entropy-probe":
        shutil.copy2(ROOT / "examples/ring-oscillator/ring_oscillator.v", ROOT / "build" / design)
    container(["python3", "-m", "librelane", "--pdk-root", "/work/.tools/pdk", "--pdk", LOCK["pdk"],
               "--manual-pdk", "--run-tag", "verified", "--overwrite", "--hide-progress-bar",
               f"/work/build/{design}/config.json"])


def versions():
    container(["bash", "/work/scripts/tool-versions.sh"])


def gates():
    container(["bash", "/work/scripts/verify-gates.sh"])


def check():
    """Run the legacy counter-design evidence checker, not current-chip signoff."""
    execute([sys.executable, ROOT / "scripts/check-results.py"])


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=("Scope note: 'check' (and the check step in 'verify') validates "
                "the historical counter-design build outputs only. Use 'tt-rtl' "
                "or 'tt' for the current entropy-probe Tiny Tapeout flow."),
    )
    parser.add_argument("command", choices=["start", "stop", "prepare", "versions", "rtl", "gds", "oscillator", "probe", "probe-rtl", "tt", "tt-rtl", "gates", "check", "verify", "tool"])
    parser.add_argument("args", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    if options.command == "start":
        start()
    elif options.command == "stop":
        env = os.environ.copy()
        env["PATH"] = str(ROOT / ".tools/lima/bin") + os.pathsep + env["PATH"]
        execute([ROOT / ".tools/bin/colima", "stop", "chip"], env=env)
    elif options.command == "prepare":
        prepare()
    elif options.command == "versions":
        versions()
    elif options.command == "rtl":
        rtl()
    elif options.command == "gds":
        gds()
    elif options.command == "oscillator":
        gds("ring-oscillator")
    elif options.command == "probe":
        gds("entropy-probe")
    elif options.command == "probe-rtl":
        container(["bash", "/work/scripts/verify-probe.sh"])
    elif options.command in ("tt", "tt-rtl"):
        execute([sys.executable, ROOT / "scripts/prepare-tt.py"])
        if options.command == "tt-rtl":
            container(["bash", "/work/scripts/verify-tt.sh"])
        else:
            container(["python3", "/work/scripts/measurement-flow.py", "--pdk-root", "/work/.tools/pdk", "--pdk", LOCK["pdk"],
                       "--manual-pdk", "--run-tag", "verified", "--overwrite", "--hide-progress-bar",
                       "/work/build/tinytapeout/src/config.json"])
            # Every completed physical build gets immutable images and evidence,
            # including builds whose signoff metrics fail.
            container(["env", "CHIP_ARCHIVE=1", "openroad", "-python", "/work/scripts/inspect-tt.py"])
            container(["env", "QT_QPA_PLATFORM=offscreen", "CHIP_VIEW=tt", "klayout", "-z", "-r", "/work/scripts/render-layout.py"])
            execute([sys.executable, ROOT / "scripts/render-architecture.py"])
            previous = list((ROOT / "build/iterations").glob("[0-9][0-9][0-9]-*"))
            number = max((int(p.name[:3]) for p in previous), default=-1) + 1
            name = f"{number:03d}-automatic"
            execute([sys.executable, ROOT / "scripts/snapshot-iteration.py", name])
            report = json.loads((ROOT / "build/tt-verification.json").read_text())
            if report["status"] != "PASS":
                raise RuntimeError(f"Physical checks failed; images and evidence saved in build/iterations/{name}")
    elif options.command == "gates":
        gates()
    elif options.command == "check":
        check()
    elif options.command == "verify":
        versions()
        rtl()
        gds()
        gates()
        check()
    else:
        if not options.args:
            parser.error("tool requires an executable and optional arguments")
        container(options.args)


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"Toolchain failed: {exc}", file=sys.stderr)
        sys.exit(1)
