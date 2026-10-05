#!/usr/bin/env python3
"""Route precheck subprocesses into the pinned Linux EDA container."""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
lock = json.loads((root / 'toolchain.lock.json').read_text())
command = Path(sys.argv[0]).name
if command == 'yowasp-yosys':
    command = 'yosys'  # Native pinned Yosys performs the same read_verilog syntax check.
assert command in ('magic', 'klayout', 'yosys'), command
args = [a.replace(str(root), '/work') for a in sys.argv[1:]]
cwd = str(Path.cwd().resolve()).replace(str(root), '/work')
assert cwd.startswith('/work/')
argv = ['docker', '--context', lock['docker_context'], 'run', '--rm', '--init', '--network', 'none',
        '--mount', f'type=bind,source={root},target=/work', '--workdir', cwd,
        '--env', 'PDK_ROOT=/work/.tools/pdk', '--env', 'PDK=sky130A',
        lock['image_digest'], command, *args]
sys.exit(subprocess.call(argv))
