"""Stage canonical sources and pinned Tiny Tapeout one-tile physical inputs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
lock = json.loads((root / 'tinytapeout.lock.json').read_text())
for folder, ref in lock['repositories'].items():
    path = root / '.tools' / folder
    if not path.exists():
        subprocess.run(['git', 'clone', 'https://github.com/TinyTapeout/' + ref['repo'] + '.git', str(path)], check=True)
        subprocess.run(['git', '-C', str(path), 'checkout', '--detach', ref['commit']], check=True)
    actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
    assert actual == ref['commit'], (folder, actual)
stage = root / 'build/tinytapeout'
shutil.copytree(root / 'tinytapeout', stage, dirs_exist_ok=True)
sources = ('tt_um_entropy_probe.v', 'resilient_probe.v', 'measurement_monitor.v', 'measurement_ring.v', 'frequency_divider.v')
for source in sources[1:]:
    shutil.copy2(root / 'examples/resilient-probe' / source, stage / 'src' / source)
support = root / '.tools/tt-support'
template = root / '.tools/ttsky-template'
def_file = support / 'tech/sky130A/def/tt_block_1x1_pg.def'
shutil.copy2(def_file, stage / 'src/tile.def')
# Same per-project merge as Project.create_user_config in pinned tt-support.
config = json.loads((template / 'src/config.json').read_text())
config.pop('//', None)
config.update({
    'DESIGN_NAME': 'tt_um_entropy_probe',
    'VERILOG_FILES': ['dir::' + name for name in sources],
    'DIE_AREA': [0, 0, 161.00, 111.52], 'FP_DEF_TEMPLATE': 'dir::tile.def',
    'VDD_PIN': 'VPWR', 'GND_PIN': 'VGND', 'RT_MAX_LAYER': 'met4',
    'RSZ_DONT_TOUCH_RX': r'^probe\.(bank\..*ro_.*|divider\..*)',
    'PNR_SDC_FILE': 'dir::constraints.sdc', 'SIGNOFF_SDC_FILE': 'dir::constraints.sdc',
    'RUN_KLAYOUT_DRC': True,
})
(stage / 'src/config.json').write_text(json.dumps(config, indent=2) + '\n')
(stage / 'staging.json').write_text(json.dumps({
    'lock': lock, 'def_sha256': hashlib.sha256(def_file.read_bytes()).hexdigest(),
    'sources_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [(stage/'src'/source) for source in sources]}
}, indent=2) + '\n')
print('Staged one-tile Tiny Tapeout layout inputs in', stage)
