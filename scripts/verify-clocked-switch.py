#!/usr/bin/env python3
"""Verify the supported disable/configure/enable protocol with mapped controls.

Safe switching is required at TT/nom, FF/min and SS/max. Two nominal live-switch
alignments remain diagnostic experiments, not acceptance for live switching.
Old cut-Q failures are preserved and are not superseded by this protocol report.
"""
import argparse
import concurrent.futures
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from evidence import sha256_file
from package_evidence import _routed_current_fingerprints

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('routed',ROOT/'scripts/routed-spice.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
REPORT=r.OUT/'clocked-switch-matrix.json'
CASES=[('nom','tt',1.8,25,'switch-safe',2),('min','ff',1.95,-40,'switch-safe',2),
       ('max','ss',1.6,100,'switch-safe',2),('nom','tt',1.8,25,'switch',1),('nom','tt',1.8,25,'switch',10)]

def one(case,image_id,collect_only):
    rc,corner,voltage,temp,scenario,lead=case
    args=SimpleNamespace(partition='source',rc=rc,corner=corner,voltage=voltage,temp=temp,
        selection=0,duration_ns=1500,ramp_ns=50,enable_ramp_ns=5,scenario=scenario,
        control_model='clocked',host_period_ns=20,request_lead_ns=lead,configuration_latency_ns=1,
        first_stage=1,stage_count=2,replay=None,prepare_only=False)
    label=r.case_label(args);path=r.OUT/(label+'.measure.json')
    command=[sys.executable,str(ROOT/'scripts/routed-spice.py')]
    for key,value in vars(args).items():
        if value is not None and key!='prepare_only':command += ['--'+key.replace('_','-'),str(value)]
    valid=False
    try:
        original=json.loads(path.read_text())
        assert original['status'] in ('PASS','FAIL') and 'parameters' in original
        _routed_current_fingerprints(ROOT,original,image_id)
        assert original.get('control_model')=='clocked' and len(original['configuration_cells'])==r.CONTROL_FLOPS
        for key,value in vars(args).items():
            assert original['parameters'].get(key)==value,(key,'changed experiment')
        before=sha256_file(path.with_suffix('').with_suffix('.sp'))
        assert before==original['input_fingerprints']['deck_sha256']
        with (r.OUT/(label+'.current-prepare.log')).open('w') as log:
            result=subprocess.run(command+['--prepare-only'],stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
        assert result.returncode==0 and before==sha256_file(path.with_suffix('').with_suffix('.sp'))
        valid=True
    except (OSError,KeyError,ValueError,AssertionError):pass
    if not valid:
        if collect_only:raise RuntimeError('Missing or stale experiment: '+label)
        with (r.OUT/(label+'.runner.log')).open('w') as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
        original=json.loads(path.read_text())
        assert original['status'] in ('PASS','FAIL') and 'parameters' in original,'Simulator did not complete'
        _routed_current_fingerprints(ROOT,original,image_id)
    trace=r.read_trace(path.with_suffix('').with_suffix('.dat'))
    checked=r.analyze(trace,args,{'partition':'source'})
    # Keep original simulator/generator provenance; reanalysis gets its own hash.
    proof=dict(case=case,status=checked['status'],simulation_report=str(path.relative_to(ROOT)),
        simulation_report_sha256=sha256_file(path),original_simulation_report=original,
        reanalysis_generator_sha256=sha256_file(ROOT/'scripts/routed-spice.py'),measurements=checked,
        artifact_sha256={str(p.relative_to(ROOT)):sha256_file(p) for p in [path.with_suffix('').with_suffix('.sp'),
            path.with_suffix('').with_suffix('.dat'),path.with_suffix('').with_suffix('.signals.json'),
            r.OUT/(label+'-cells.spice')]})
    print(checked['status']+' '+label,flush=True)
    return proof

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--collect-only',action='store_true',help='Reanalyze existing matching simulations; fail if any are missing')
    args=parser.parse_args();r.OUT.mkdir(exist_ok=True,parents=True)
    report=dict(status='RUNNING_UNVERIFIED',cases=[],scope='Mapped configuration registers and routed clock/source cone; stage-0 divider only. Safe protocol is separate from live-switch diagnostics and the legacy full-divider matrix.')
    REPORT.write_text(json.dumps(report,indent=2)+'\n')
    try:
        adapter_hash=sha256_file(ROOT/'firmware/entropy_probe.py')
        adapter_test_hash=sha256_file(ROOT/'scripts/test-firmware.py')
        with (r.OUT/'clocked-switch-host-tests.log').open('w') as log:
            host_tests=subprocess.run([sys.executable,str(ROOT/'scripts/test-firmware.py')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        assert host_tests.returncode==0,'Host adapter tests failed'
        assert adapter_hash==sha256_file(ROOT/'firmware/entropy_probe.py') and adapter_test_hash==sha256_file(ROOT/'scripts/test-firmware.py')
        report['host_adapter_tests']=dict(status='PASS',firmware_sha256=adapter_hash,test_sha256=adapter_test_hash)
        image_id=subprocess.check_output(r.chip.docker('image','inspect',r.IMAGE,'--format','{{.Id}}'),text=True).strip()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures=[pool.submit(one,case,image_id,args.collect_only) for case in CASES]
            for future in concurrent.futures.as_completed(futures):
                report['cases'].append(future.result());REPORT.write_text(json.dumps(report,indent=2)+'\n')
        safe=[c for c in report['cases'] if c['case'][4]=='switch-safe']
        report['status']='PASS_SAFE_SWITCH_PROTOCOL' if len(safe)==3 and all(c['status']=='PASS' for c in safe) else 'FAIL_SAFE_SWITCH_PROTOCOL'
        report['generator_sha256']=sha256_file(Path(__file__))
        report['limits']=['Three selected PVT/RC combinations; not a full Cartesian sweep or silicon qualification.',
            'Clocked configuration and stage-0 divider simulated; downstream divider partitions are separate evidence.',
            'Do not infer that arbitrary enabled source switching is supported or that the old failed matrix passed.',
            'Ideal supply network and grounded omitted coupling; no physical entropy or hardware validation.']
    except BaseException as error:
        report.update(status='FAIL_OR_INCOMPLETE',failure=str(error));raise
    finally:REPORT.write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])
    if report['status']!='PASS_SAFE_SWITCH_PROTOCOL':raise SystemExit(1)

if __name__=='__main__':main()
