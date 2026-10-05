"""Export the checked tile through Tiny Tapeout's custom-GDS interface."""
import hashlib,json,shutil
from pathlib import Path
import chip
root=chip.ROOT;old='tt_um_entropy_probe';new='tt_um_florianmodel_entropy_probe'
report=json.loads((root/'build/tt-verification.json').read_text());assert report['status']=='PASS'
final=root/'build/tinytapeout/src/runs/verified/final';out=root/'submission'
assert hashlib.sha256((final/f'gds/{old}.gds').read_bytes()).hexdigest()==report['gds_sha256']
chip.container(['python3','/work/scripts/export-layout.py'])
for kind,ext in [('lef','lef'),('pnl','v')]:
 target=out/('lef' if kind=='lef' else 'netlist');target.mkdir(parents=True,exist_ok=True)
 text=(final/f'{kind}/{old}.{kind+"." if kind=="pnl" else ""}{ext}').read_text()
 if kind=='lef':text=text.replace(f'MACRO {old}',f'MACRO {new}').replace(f'END {old}',f'END {new}')
 else:text=text.replace(f'module {old} ',f'module {new} ',1)
 (target/f'{new}.{ext}').write_text(text.rstrip()+"\n")
shutil.copy2(out/f'netlist/{new}.v',out/f'gds/{new}.v')
(root/'src').mkdir(exist_ok=True)
sources=('tt_um_entropy_probe.v','resilient_probe.v','measurement_monitor.v','measurement_ring.v','frequency_divider.v')
for f in sources:
 source=root/'tinytapeout/src'/f if f==sources[0] else root/'examples/resilient-probe'/f
 text=source.read_text()
 name=new+'.v' if f==sources[0] else f
 if f==sources[0]:text=text.replace('module '+old,'module '+new,1)
 (root/'src'/name).write_text(text)
info=(root/'tinytapeout/info.yaml').read_text().replace(f'top_module: "{old}"',f'top_module: "{new}"').replace(f'"{old}.v"',f'"{new}.v"')
(root/'info.yaml').write_text(info)
for source,target in [('build/tt-verification.json','physical.json'),('build/timing-review-verification.json','timing-review.json'),('build/spice/results.json','spice.json'),('build/spice/unloaded-results.json','spice-unloaded.json')]:
 if (root/source).exists():shutil.copy2(root/source,out/'evidence'/target)
for f in ('architecture.png','tt-layout.png'):
 if (root/'build'/f).exists():shutil.copy2(root/'build'/f,root/'docs'/f)
files=list((root/'examples/resilient-probe').glob('*.v'))+list((root/'tinytapeout').rglob('*.v'))+[root/'tinytapeout/src/constraints.sdc',root/'scripts/measurement-flow.py',root/'scripts/compact-rings.py',root/'toolchain.lock.json',root/'tinytapeout.lock.json']
(out/'manifest.json').write_text(json.dumps({'top_module':new,'internal_build_top':old,'author':'florianmodel','source_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'artifact_sha256':{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'},'limits':['Experimental learning/measurement chip; entropy unvalidated.','Board capture unvalidated.','Hosted precheck must pass before submission.']},indent=2)+'\n')
print('Prepared submission:',new)
