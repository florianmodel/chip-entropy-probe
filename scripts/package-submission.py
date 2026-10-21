"""Export the checked tile through Tiny Tapeout's custom-GDS interface."""
import hashlib,json,shutil
import os,subprocess
from pathlib import Path
import chip
from evidence import reconcile_optional_report
from package_evidence import (reconcile_clocked_switch_evidence, reconcile_routed_evidence,
                              validate_spice_report, validate_timing_report)
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
evidence_dir=out/'evidence';evidence_dir.mkdir(parents=True,exist_ok=True)
physical=json.loads((root/'build/tt-verification.json').read_text())
# These annotations were manually appended to an older report and have no
# tracked generator. Never carry them into a fresh package as verified results.
for unsupported in ('digital_checks','analog_model_checks','timing_endpoint_review'):
 physical.pop(unsupported,None)
(evidence_dir/'physical.json').write_text(json.dumps(physical,indent=2)+'\n')
def optional_report_is_fresh(source,target):
 path=root/source
 if source=='build/timing-review-verification.json':
  return validate_timing_report(root,path)
 try:
  image_id=current_spice_image_id()
 except (OSError,subprocess.CalledProcessError) as error:
  return False,f'cannot verify SPICE image identity: {error}'
 return validate_spice_report(root,path,unloaded=source.endswith('unloaded-results.json'),current_image_id=image_id)

_current_spice_image_id=None
def current_spice_image_id():
 global _current_spice_image_id
 if _current_spice_image_id is None:
  _current_spice_image_id=subprocess.check_output(['docker','--context',os.environ.get('CHIP_DOCKER_CONTEXT','colima-chip'),
   'image','inspect','chip-ngspice:39','--format','{{.Id}}'],text=True).strip()
 return _current_spice_image_id

evidence_status={'physical':{'status':'generated_current_build','source':'build/tt-verification.json'},'optional':{}}
for source,target in [('build/timing-review-verification.json','timing-review.json'),('build/spice/results.json','spice.json'),('build/spice/unloaded-results.json','spice-unloaded.json')]:
 status=reconcile_optional_report(root/source,evidence_dir/target,lambda path:optional_report_is_fresh(source,target))
 status['source']=source
 evidence_status['optional'][target]=status
try:
 evidence_status['optional']['routed-spice.json']=reconcile_routed_evidence(root,evidence_dir/'routed-spice.json',current_spice_image_id())
except (OSError,subprocess.CalledProcessError) as error:
 (evidence_dir/'routed-spice.json').unlink(missing_ok=True)
 evidence_status['optional']['routed-spice.json']={'status':'absent_unverified','source':'build/routed-spice/matrix.json','reason':f'cannot verify SPICE image identity: {error}'}
try:
 evidence_status['optional']['clocked-switch.json']=reconcile_clocked_switch_evidence(root,evidence_dir/'clocked-switch.json',current_spice_image_id())
except (OSError,subprocess.CalledProcessError) as error:
 (evidence_dir/'clocked-switch.json').unlink(missing_ok=True)
 evidence_status['optional']['clocked-switch.json']={'status':'absent_unverified','source':'build/routed-spice/clocked-switch-matrix.json','reason':f'cannot verify SPICE image identity: {error}'}
(evidence_dir/'status.json').write_text(json.dumps(evidence_status,indent=2)+'\n')
for f in ('architecture.png','tt-layout.png'):
 if (root/'build'/f).exists():shutil.copy2(root/'build'/f,root/'docs'/f)
files=list((root/'examples/resilient-probe').glob('*.v'))+list((root/'tinytapeout').rglob('*.v'))+[root/'tinytapeout/src/constraints.sdc',root/'scripts/measurement-flow.py',root/'scripts/compact-rings.py',root/'scripts/inspect-tt.py',root/'scripts/spice.py',root/'scripts/evidence.py',root/'scripts/package_evidence.py',root/'scripts/package-submission.py',root/'scripts/test-evidence.py',root/'scripts/snapshot-iteration.py',root/'scripts/test-snapshot-iteration.py',root/'scripts/export-layout.py',root/'scripts/timing-review.py',root/'scripts/routed-spice.py',root/'scripts/verify-routed-spice.py',root/'scripts/verify-clocked-switch.py',root/'scripts/test-firmware.py',root/'firmware/fixed_capture.py',root/'firmware/entropy_probe.py',root/'toolchain.lock.json',root/'tinytapeout.lock.json']
(out/'manifest.json').write_text(json.dumps({'top_module':new,'internal_build_top':old,'author':'florianmodel','source_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'artifact_sha256':{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'},'limits':['Experimental learning/measurement chip; entropy unvalidated.','Board capture unvalidated.','Hosted precheck must pass before submission.']},indent=2)+'\n')
print('Prepared submission:',new)
