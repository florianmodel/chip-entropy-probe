#!/usr/bin/env python3
"""Run the scoped routed-clock matrix and compose actual divider partitions.

No layout change, whole-chip transistor simulation, or entropy claim.
Usage: python3 scripts/verify-routed-spice.py [--workers 3] [--quick]
"""
import argparse, concurrent.futures, importlib.util, json, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
from evidence import sha256_file, sha256_tree

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('routed',Path(__file__).with_name('routed-spice.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
REPORT=r.OUT/'matrix.json'
IMAGE_ID=None

def invoke(common,partition='source',replay=None,first=1,count=2,scenario='steady',duration=250,ramp=5,enable_ramp=.1):
    args=SimpleNamespace(partition=partition,rc=common[0],corner=common[1],voltage=common[2],temp=common[3],
                         selection=common[4],ramp_ns=ramp,enable_ramp_ns=enable_ramp,scenario=scenario,
                         first_stage=first,stage_count=count)
    label=r.case_label(args);path=r.OUT/(label+'.measure.json')
    command=[sys.executable,str(ROOT/'scripts/routed-spice.py'),
             '--partition',partition,'--rc',args.rc,'--corner',args.corner,'--voltage',str(args.voltage),
             '--temp',str(args.temp),'--selection',str(args.selection),'--duration-ns',str(duration),
             '--ramp-ns',str(ramp),'--enable-ramp-ns',str(enable_ramp),'--scenario',scenario,
             '--first-stage',str(first),'--stage-count',str(count)]
    if replay:command += ['--replay',str(replay)]
    cache=False
    try:
        previous=json.loads(path.read_text())
        inputs=previous['input_fingerprints']
        libsuffix={'tt':'tt_025C_1v80','ff':'ff_n40C_1v95','ss':'ss_100C_1v60'}[args.corner]
        cache=(scenario=='steady' and previous['status']=='PASS'
               and inputs['pnl_sha256']==sha256_file(r.FINAL/'pnl/tt_um_entropy_probe.pnl.v')
               and inputs['gds_sha256']==sha256_file(r.FINAL/'gds/tt_um_entropy_probe.gds')
               and inputs['spef_sha256']==sha256_file(r.FINAL/f'spef/{args.rc}/tt_um_entropy_probe.{args.rc}.spef')
               and inputs['constraints_sha256']==sha256_file(ROOT/'tinytapeout/src/constraints.sdc')
               and inputs['model_tree_sha256']==sha256_tree([r.PDK/'libs.tech/ngspice',r.PDK/'libs.ref/sky130_fd_pr/spice'])
               and inputs['cell_library_sha256']==sha256_file(r.LIBCELL)
               and inputs['liberty_sha256']==sha256_file(r.PDK/f'libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__{libsuffix}.lib')
               and inputs['tool_image_id']==IMAGE_ID
               and inputs['deck_sha256']==sha256_file(path.with_suffix('').with_suffix('.sp'))
               and previous['parameters']['duration_ns']==duration)
        if replay:cache &= inputs['replay_data_sha256']==sha256_file(replay) and inputs['replay_measurements_sha256']==sha256_file(replay.with_suffix('.measure.json'))
        if cache:
            # Compare the fully regenerated deck and cell definitions. A change
            # to another partition's code need not rerun an identical circuit.
            # Keep the original simulation generator hash in the retained
            # report; never relabel an old run with the current generator hash.
            before=inputs['deck_sha256']
            with (r.OUT/(label+'.prepare.log')).open('w') as log:
                prepared=subprocess.run(command+['--prepare-only'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            cache=(prepared.returncode==0 and before==sha256_file(path.with_suffix('').with_suffix('.sp')))
            if cache:
                trace=r.read_trace(path.with_suffix('').with_suffix('.dat'))
                checked=r.analyze(trace,args,{'partition':partition})
                cache=checked['status']=='PASS'
    except (OSError,KeyError,ValueError):cache=False
    if not cache:
        with (r.OUT/(label+'.runner.log')).open('w') as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:raise RuntimeError('Partition failed: '+label+'; see .runner.log')
    report=json.loads(path.read_text());assert report['status']=='PASS'
    print(('REUSE ' if cache else 'PASS ')+label,flush=True)
    return path.with_suffix('').with_suffix('.dat'),report

def one(common):
    duration=500 if common[1]=='ss' else 250
    data,source=invoke(common,duration=duration)
    partitions=[source];measurements=[str(data.with_suffix('.measure.json').relative_to(ROOT))]
    master=source['frequency_MHz']
    for first,count in [(1,2),(3,2),(5,2),(7,2),(9,1)]:
        data,measurement=invoke(common,'divider',data,first,count,duration=duration)
        partitions.append(measurement);measurements.append(str(data.with_suffix('.measure.json').relative_to(ROOT)))
    last=partitions[-1]
    composed=master/last['frequency_MHz']*last['division_ratio']
    assert abs(composed-1024)<10.24,('composed division mismatch',composed)
    return dict(status='PASS_SCOPED_PARTITION_MODEL',conditions=common,
                source_frequency_MHz=master,composed_division=composed,measurements=measurements,
                stage_ranges=[[p['first_stage'],p['last_stage']] for p in partitions],
                report_sha256={path:sha256_file(ROOT/path) for path in measurements})

def main():
    global IMAGE_ID
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--quick',action='store_true',help='One nominal ring only; explicitly incomplete matrix')
    args=parser.parse_args();r.OUT.mkdir(parents=True,exist_ok=True)
    IMAGE_ID=subprocess.check_output(r.chip.docker('image','inspect',r.IMAGE,'--format','{{.Id}}'),text=True).strip()
    cases=[(rc,c,v,t,n) for rc,c,v,t in [('nom','tt',1.8,25),('min','ff',1.95,-40),('max','ss',1.6,100)] for n in range(3)]
    if args.quick:cases=cases[:1]
    result=dict(status='RUNNING_UNVERIFIED',coverage='quick/incomplete' if args.quick else 'nine source/PVT/RC scenarios plus controls',cases=[])
    REPORT.write_text(json.dumps(result,indent=2)+'\n')
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures=[pool.submit(one,case) for case in cases]
            for f in concurrent.futures.as_completed(futures):
                result['cases'].append(f.result());REPORT.write_text(json.dumps(result,indent=2)+'\n')
        controls=[];result['controls']=controls
        if not args.quick:
            for scenario in ('restart','switch'):
                data,measurement=invoke(('nom','tt',1.8,25,0),scenario=scenario,duration=1500,ramp=50,enable_ramp=5)
                controls.append(dict(scenario=scenario,report=str(data.with_suffix('.measure.json').relative_to(ROOT)),status=measurement['status']))
                REPORT.write_text(json.dumps(result,indent=2)+'\n')
        result.update(status='PASS_SCOPED_PARTITION_MODEL' if not args.quick else 'INCOMPLETE_QUICK_CHECK',controls=controls,
                      generator_sha256=sha256_file(ROOT/'scripts/routed-spice.py'),matrix_generator_sha256=sha256_file(Path(__file__)),
                      limits=['Nine selected PVT/RC conditions, not full Cartesian PVT or silicon qualification.',
                              '/1024 established by adjacent transistor/RC partition composition with measured-Q waveform replay.',
                              'Ideal supply network, grounded out-of-cone coupling and Liberty input-cap termination.',
                              'No entropy simulation, whole-chip simultaneous transistor simulation or fabricated-device validation.'])
    except BaseException as exc:
        result.update(status='FAIL_OR_INCOMPLETE',failure=str(exc));raise
    finally:REPORT.write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'])

if __name__=='__main__':main()
