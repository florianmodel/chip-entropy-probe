"""Archive real layout images, source, artifacts and check status without overwriting."""
import datetime,hashlib,json,shutil,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];name=sys.argv[1]
assert name and '/' not in name and name[:3].isdigit()
folder=root/'build/iterations'/name
folder.mkdir(parents=True,exist_ok=False)
run=root/'build/tinytapeout/src/runs/verified'
for f in ('architecture.png','tt-layout.png','tt-layout-detail.png','tt-verification.json'):
 shutil.copy2(root/'build'/f,folder/f)
report=json.loads((folder/'tt-verification.json').read_text())
for stages in report.get('ring_lengths',[]):
 p=root/f'build/tt-layout-ring-{stages}.png'
 if p.exists():shutil.copy2(p,folder/p.name)
shutil.copytree(root/'tinytapeout',folder/'source/tinytapeout')
shutil.copytree(root/'examples/resilient-probe',folder/'source/resilient-probe')
shutil.copytree(run/'final',folder/'final')
for f in ('toolchain.lock.json','tinytapeout.lock.json'):shutil.copy2(root/f,folder/f)
shutil.copytree(root/'toolchain',folder/'source/toolchain')
for f in ('README.md','CONTEXT.md'):shutil.copy2(root/f,folder/f)
if (root/'build/timing-review-verification.json').exists():shutil.copy2(root/'build/timing-review-verification.json',folder/'timing-review-verification.json')
if (root/'build/spice/results.json').exists():
 spice=json.loads((root/'build/spice/results.json').read_text())
 if {r['stages'] for r in spice['cases']}==set(report.get('ring_lengths',[])):
  shutil.copy2(root/'build/spice/results.json',folder/'spice-results.json')
if (root/'build/spice/unloaded-results.json').exists():shutil.copy2(root/'build/spice/unloaded-results.json',folder/'spice-unloaded-results.json')
shutil.copytree(root/'scripts',folder/'source/scripts')
shutil.copytree(root/'firmware',folder/'source/firmware',ignore=shutil.ignore_patterns('__pycache__'))
for path in (root/'build/tt-rtl',root/'build/resilient-rtl',root/'build/tt-precheck/precheck/reports'):
 if path.exists():shutil.copytree(path,folder/'checks'/path.name)
report=json.loads((folder/'tt-verification.json').read_text())
(folder/'manifest.json').write_text(json.dumps({'archived_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'name':name,'status':report['status'],'gds_sha256':report['gds_sha256'],'png_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.png')}},indent=2)+'\n')
print(folder)
