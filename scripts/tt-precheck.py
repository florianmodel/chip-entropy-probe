"""Run the unmodified pinned official precheck with host geometry libraries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
stage = root / 'build/tt-precheck'
support = root / '.tools/tt-support'
shutil.copytree(support / 'precheck', stage / 'precheck', dirs_exist_ok=True)
shutil.copytree(support / 'tech', stage / 'tech', dirs_exist_ok=True)
bin_dir = stage / 'bin'
bin_dir.mkdir(parents=True, exist_ok=True)
proxy = root / 'scripts/tt-eda-proxy.py'
proxy.chmod(0o755)
for name in ('magic', 'klayout', 'yowasp-yosys'):
    path = bin_dir / name
    if not path.exists():
        path.symlink_to(proxy)
final = root / 'build/tinytapeout/src/runs/verified/final'
gds = final / 'gds/tt_um_entropy_probe.gds'
shutil.copy2(final / 'pnl/tt_um_entropy_probe.pnl.v', gds.with_suffix('.v'))
env = os.environ.copy()
env.update(PDK_ROOT=str(root / '.tools/pdk'), PDK='sky130A',
           PYTHONPATH=str(root / '.tools/tt-host-python'),
           PATH=str(bin_dir) + os.pathsep + env['PATH'])
result = subprocess.run([sys.executable, 'precheck.py', '--gds', str(gds)],
                        cwd=stage / 'precheck', env=env)
if result.returncode:
    raise SystemExit(result.returncode)
print('PASS: official Tiny Tapeout prechecks; reports in build/tt-precheck/precheck/reports')
