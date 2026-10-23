#!/usr/bin/env python3
"""Extract a bounded transistor/RC clock-cone experiment from routed artifacts.

Partition A: rings, control/mux, routed clock tree, actual first divider flop.
Following partitions: adjacent mapped divider stages, replaying the preceding
partition's measured Q waveform, until the composed output is /1024.
Reports never claim whole-chip transistor extraction or entropy validation.
"""
import argparse, json, re, subprocess, sys, hashlib, math
from pathlib import Path
import chip
from evidence import sha256_file, sha256_tree, fingerprint

ROOT=chip.ROOT
FINAL=ROOT/'build/tinytapeout/src/runs/verified/final'
OUT=ROOT/'build/routed-spice'
PDK=ROOT/'.tools/pdk/sky130A'
LIBCELL=PDK/'libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice'
IMAGE='chip-ngspice:39'
POWER={'VGND':'0','VNB':'0','VPB':'vdd','VPWR':'vdd'}
# Registered one-hot ring enables plus the two source-configuration bits they compare.
CONTROL_NETS={'probe.ring_run[0]','probe.ring_run[1]','probe.ring_run[2]','probe.configuration[2]','probe.configuration[3]'}
CONTROL_FLOPS=len(CONTROL_NETS)

def norm(s): return s.replace('\\','').strip()

def cells():
    text=(FINAL/'pnl/tt_um_entropy_probe.pnl.v').read_text()
    result={}
    for kind,name,body in re.findall(r'(sky130_fd_sc_hd__\w+)\s+(\\?\S+)\s*\((.*?)\);',text,re.S):
        pins={p:norm(n) for p,n in re.findall(r'\.(\w+)\(([^)]+)\)',body)}
        result[norm(name)]={'kind':kind,'pins':pins}
    assert len(result)>300, 'Could not parse routed cells'
    return result

def parse_spef(path):
    text=path.read_text(); names={k:norm(v) for k,v in re.findall(r'^\*(\d+)\s+(\S+)$',text,re.M)}
    def resolve(s):
        return re.sub(r'\*(\d+)',lambda m:names[m[1]],norm(s))
    nets={}
    for name,total,body in re.findall(r'^\*D_NET\s+(\S+)\s+(\S+)\n(.*?)^\*END',text,re.M|re.S):
        section=None; conn=[];caps=[];res=[]
        for row in body.splitlines():
            if row in ('*CONN','*CAP','*RES'):section=row;continue
            parts=row.split()
            if not parts:continue
            if section=='*CONN' and parts[0] in ('*I','*P'):conn.append((resolve(parts[1]),parts[2]))
            elif section=='*CAP':
                assert len(parts) in (3,4),parts
                caps.append((resolve(parts[1]),resolve(parts[2]) if len(parts)==4 else '0',float(parts[-1])*1e-12))
            elif section=='*RES':res.append((resolve(parts[1]),resolve(parts[2]),float(parts[3])))
        nets[resolve(name)]={'connections':conn,'caps':caps,'resistors':res,'total_F':float(total)*1e-12}
    assert '*C_UNIT 1 PF' in text and '*R_UNIT 1 OHM' in text
    return nets

def output_pins(c):return [p for p in c['pins'] if p in ('X','Y','Q','HI','LO')]

def cone(allcells,seeds,cut=(),clocked_controls=()):
    drivers={}
    for name,c in allcells.items():
        for p in output_pins(c):drivers.setdefault(c['pins'][p],[]).append((name,p))
    selected=set();boundary={};seen=set()
    def visit(net):
        if net in ('VPWR','VGND') or net in seen:return
        seen.add(net)
        ds=drivers.get(net,[])
        assert len(ds)<=1,(net,ds)
        if net in cut or not ds:
            boundary[net]=ds[0] if ds else None;return
        name,p=ds[0];c=allcells[name]
        if re.search(r'__(df|sd|ed)',c['kind']) and not name.startswith('probe.divider.') and name not in clocked_controls:
            boundary[net]=(name,p);return
        selected.add(name)
        for pin,n in c['pins'].items():
            if pin not in POWER and pin not in output_pins(c):visit(n)
    for name in seeds:
        selected.add(name)
        for p,n in allcells[name]['pins'].items():
            if p not in POWER:visit(n)
    return selected,boundary,drivers

def build_partition(part,rc='nom',first=0,count=10,corner='tt',control_model='cut'):
    cs=cells();sp=parse_spef(FINAL/f'spef/{rc}/tt_um_entropy_probe.{rc}.spef')
    stages=list(range(first,first+count)) if part=='divider' else [0]
    seeds=[f'probe.divider.stage[{j}].ff' for j in stages]
    # Explicitly include each ring. Disabled branches remain real physical cells.
    if part=='source':seeds += [n for n in cs if n.startswith('probe.bank.ring')]
    cut_net='probe.bank.raw_out' if first==0 else f'probe.divider.q[{first-1}]'
    controls={name for name,c in cs.items() if any(c['pins'][p] in CONTROL_NETS for p in output_pins(c))} if control_model=='clocked' else set()
    if control_model=='clocked':
        assert part=='source' and len(controls)==CONTROL_FLOPS,'Clocked source requires the mapped ring_run and source-configuration flops'
        seeds+=sorted(controls)
    selected,bounds,drivers=cone(cs,seeds,{cut_net} if part=='divider' else set(),controls)
    if control_model=='clocked':assert not (CONTROL_NETS & set(bounds)),'Control flop Q must not be driven ideally'
    nets={n for name in selected for p,n in cs[name]['pins'].items() if p not in POWER}
    # Locate excluded fanout pins so their Liberty input capacitance remains
    # attached at the extracted physical terminal.
    loads={name for name,c in cs.items() if name not in selected and any(p not in POWER and p not in output_pins(c) and n in nets for p,n in c['pins'].items())}
    mapping={};serial=[0]
    def node(s):
        if s in ('0','VGND'):return '0'
        if s=='VPWR':return 'vdd'
        if s not in mapping:serial[0]+=1;mapping[s]=f'n{serial[0]}'
        return mapping[s]
    endpoints={name:{p:node(n) if n not in sp else node(name+':'+p) for p,n in c['pins'].items() if p not in POWER} for name,c in cs.items() if name in selected|loads}
    lines=[];types=set()
    library=LIBCELL.read_text()
    blocks={m[1]:(m[2].split(),m[0]) for m in re.finditer(r'^\.subckt (\S+) ([^\n]+)\n.*?^\.ends[^\n]*',library,re.M|re.S)}
    # Liberty maximum rise/fall input capacitance terminates excluded fanout.
    # Unlike an unloaded dummy cell this retains the downstream input load,
    # while avoiding simulation of unrelated state/logic beyond the cut.
    libsuffix={'tt':'tt_025C_1v80','ff':'ff_n40C_1v95','ss':'ss_100C_1v60'}[corner]
    libtext=(PDK/f'libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__{libsuffix}.lib').read_text()
    capindex=0
    for name in sorted(loads):
        c=cs[name];celltext=braced(libtext,libtext.index('cell ("'+c['kind']+'")'))
        for p,net in c['pins'].items():
            if p in POWER or p in output_pins(c) or net not in nets:continue
            pintext=braced(celltext,celltext.index('pin ("'+p+'")'))
            values=[float(x) for x in re.findall(r'\b(?:capacitance|rise_capacitance|fall_capacitance)\s*:\s*([\d.eE+-]+)',pintext)]
            assert values,(name,p,'missing termination capacitance')
            lines.append(f'Cpin{capindex} {endpoints[name][p]} 0 {max(values)*1e-12:.12g}');capindex+=1
    for i,name in enumerate(sorted(selected)):
        c=cs[name];types.add(c['kind']);ports,_=blocks[c['kind']];args=[]
        for p in ports:
            if p in POWER:args.append(POWER[p]);continue
            if p not in c['pins']:
                assert p in ('X','Y','Q','HI','LO'),(name,p,'unconnected input')
                args.append(node('unused:'+name+':'+p));continue
            n=c['pins'][p]
            if name in loads and (p in output_pins(c) or n not in nets):
                args.append(node('unused:'+name+':'+p) if p in output_pins(c) else '0')
            else:args.append(endpoints[name][p])
        lines.append('Xcell'+str(i)+' '+' '.join(args)+' '+c['kind'])
    inside_nodes={n for net in nets if net in sp for a,b,_ in sp[net]['resistors'] for n in (a,b)}
    inside_nodes|={n for net in nets if net in sp for n,_ in sp[net]['connections']}
    caps_seen=set();rctotals={'resistors':0,'capacitors':0,'coupling_to_ground_F':0.0}
    for net in sorted(nets):
        if net not in sp:continue
        for a,b,r in sp[net]['resistors']:
            # Zero-ohm extraction segments become tiny positive resistors.
            lines.append(f'Rrc{rctotals["resistors"]} {node(a)} {node(b)} {max(r,1e-6):.12g}')
            rctotals['resistors']+=1
        for a,b,c in sp[net]['caps']:
            key=(tuple(sorted((a,b))),c)
            if key in caps_seen or c==0:continue
            caps_seen.add(key)
            aa=a if a in inside_nodes else '0';bb=b if b in inside_nodes else '0'
            if (aa=='0') != (a=='0') or (bb=='0') != (b=='0'):rctotals['coupling_to_ground_F']+=c
            if aa==bb:continue
            lines.append(f'Crc{rctotals["capacitors"]} {node(aa)} {node(bb)} {c:.12g}')
            rctotals['capacitors']+=1
    # Drive cut state nets at their omitted driver's actual extracted Q node.
    ports={}
    for net,driver in bounds.items():
        point=driver[0]+':'+driver[1] if driver and net in sp else net
        ports[net]=node(point)
    observations={
        'clock':endpoints[f'probe.divider.stage[{stages[0]}].ff']['CLK'],
        'reset':endpoints[f'probe.divider.stage[{stages[0]}].ff']['RESET_B'],
        'q0':endpoints[f'probe.divider.stage[{stages[0]}].ff']['Q'],
    }
    if part=='source':
        name,p=drivers['probe.bank.raw_out'][0];observations['raw']=endpoints[name][p]
    else:observations['out']=endpoints[f'probe.divider.stage[{stages[-1]}].ff']['Q']
    if control_model=='clocked':
        for bit,net in enumerate(['probe.configuration[2]','probe.configuration[3]']):
            driver,pin=drivers[net][0];observations[f'config{bit}']=endpoints[driver][pin]
        observations['host_clock']=ports['clk']
    definitions='\n'.join(blocks[t][1] for t in sorted(types))
    return dict(lines=lines,definitions=definitions,boundaries=ports,observations=observations,
                cell_names=sorted(selected),load_cell_names=sorted(loads),rc=rctotals,
                extracted_corner=rc,partition=part,first_stage=stages[0],last_stage=stages[-1],
                cut_net=cut_net,termination_pin_capacitors=capindex,control_model=control_model,configuration_cells=sorted(controls))

def level_for(net,selection):
    if net in ('ena','rst_n'):return 1
    if net.startswith('ui_in['):
        bit=int(re.search(r'\[(\d+)\]',net)[1]);return {3:1,5:1,6:selection&1,7:(selection>>1)&1}.get(bit,0)
    if net.startswith('uio_in['):return 0
    if net.startswith('probe.ring_run['):return int(int(net[-2])==selection)
    if net in ('probe.configuration[2]','probe.configuration[3]'):return (selection>>(int(net[-2])-2))&1
    if net in ('probe.configuration[0]','probe.configuration[1]','probe.alternate'):return 0
    raise ValueError('Unspecified boundary: '+net)

def prepare(args):
    OUT.mkdir(parents=True,exist_ok=True)
    part=build_partition(args.partition,args.rc,args.first_stage,args.stage_count,args.corner,getattr(args,'control_model','cut'))
    for net in part['boundaries']:
        if net=='clk' and getattr(args,'control_model','cut')=='clocked':continue
        if net!=part['cut_net'] or args.partition=='source':level_for(net,args.selection)
    (OUT/f'{args.partition}-{args.rc}.json').write_text(json.dumps(part,indent=2)+'\n')
    print(json.dumps({k:v for k,v in part.items() if k not in ('lines','definitions','cell_names','load_cell_names')},indent=2))
    print(len(part['cell_names']),'active cells',len(part['load_cell_names']),'termination cells')
    return part

def run(args):
    clock_period=re.search(r'create_clock\s+-name\s+ro_clock\s+-period\s+([\d.]+)',(ROOT/'tinytapeout/src/constraints.sdc').read_text())
    assert clock_period and float(clock_period[1])==2.0,'Update the 500 MHz experiment envelope for the changed SDC'
    current_models=sha256_tree([PDK/'libs.tech/ngspice',PDK/'libs.ref/sky130_fd_pr/spice'])
    part=prepare(args)
    label=case_label(args)
    deckfile=OUT/f'{label}.sp';datafile=OUT/f'{label}.dat'
    ramp=args.ramp_ns*1e-9;enable=ramp+20e-9
    def pwl(points):return 'PWL('+ ' '.join(f'{t:.12g} {v:.12g}' for t,v in points)+')'
    lines=[f'Routed clock cone: {label}',f'.lib "/work/.tools/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice" {args.corner}',
           '.include "'+label+'-cells.spice"',f'.temp {args.temp}',
           'Vpower vdd 0 '+pwl([(0,0),(ramp,args.voltage)]),*part['lines']]
    replay=None
    for i,(net,n) in enumerate(sorted(part['boundaries'].items())):
        if args.partition=='divider' and net==part['cut_net']:
            if not args.replay:raise ValueError('Divider needs --replay source .dat')
            # Repeating measured settled raw waveform preserves its waveform,
            # period and voltage; only phase at replay startup is arbitrary.
            source=Path(args.replay);trace=read_trace(source)
            meta=json.loads(source.with_suffix('.measure.json').read_text())
            assert meta.get('status')=='PASS','Replay requires a passing experiment'
            assert meta.get('last_stage',0)==args.first_stage-1,'Divider partition is not adjacent to replay output'
            assert meta['parameters'].get('scenario','steady')=='steady','Only stationary source traces can be replayed'
            for key in ('rc','corner','voltage','temp','selection','ramp_ns'):
                assert meta['parameters'][key]==getattr(args,key),(key,'replay scenario mismatch')
            for key,current in [('pnl_sha256',sha256_file(FINAL/'pnl/tt_um_entropy_probe.pnl.v')),
                                ('gds_sha256',sha256_file(FINAL/'gds/tt_um_entropy_probe.gds')),
                                ('spef_sha256',sha256_file(FINAL/f'spef/{args.rc}/tt_um_entropy_probe.{args.rc}.spef')),
                                ('model_tree_sha256',current_models),
                                ('cell_library_sha256',sha256_file(LIBCELL))]:
                assert meta['input_fingerprints'][key]==current,(key,'stale replay')
            signal='q0' if meta['partition']=='source' else 'out'
            times=trace['time'];raw=trace[signal];cross=crossings(times,raw,args.voltage*.5,'rise',times[-1]*.5)
            assert len(cross)>=3,'Need settled cycles for replay'
            start,finish=cross[0],cross[-1]
            block_period=finish-start
            input_cycles=len(cross)-1
            period=block_period/input_cycles
            wave=[(t-start,v) for t,v in zip(times,raw) if start<=t<finish]
            wave=[(0,args.voltage*.5),*wave,(block_period,args.voltage*.5)]
            wave=compress_wave(wave,args.voltage*.002)
            # Keep a representative actual period, not an ideal PULSE.
            (OUT/f'{label}-replay.json').write_text(json.dumps({'source_sha256':sha256_file(source),'period_s':period,
                'train_period_s':block_period,'train_input_cycles':input_cycles,'source_measurements':meta},indent=2))
            repeats=math.ceil(32/input_cycles)
            duration=block_period*repeats+enable
            points=[(0,0),(enable-1e-10,0)]
            for cycle in range(repeats):
                points.extend((enable+cycle*block_period+t,v) for t,v in (wave if cycle==0 else wave[1:]))
            lines.append(f'Vboundary{i} {n} 0 '+pwl(points));replay=period
        elif net=='clk' and args.control_model=='clocked':
            period_ns=args.host_period_ns
            lines.append(f'Vboundary{i} {n} 0 PULSE(0 {args.voltage} 10n 0.1n 0.1n {period_ns/2-.1:g}n {period_ns:g}n)')
        else:
            high=level_for(net,args.selection)*args.voltage
            # In the cut model a ring_run flop follows enable one host clock later.
            run=net.startswith('probe.ring_run[');latency=args.host_period_ns*1e-9 if run else 0
            when=enable if net=='ui_in[3]' or run else ramp
            edge=args.enable_ramp_ns*1e-9 if net=='ui_in[3]' else 1e-10
            points=[(0,0),(max(0,when-edge),0),(when,high)]
            total=args.duration_ns*1e-9
            if args.scenario=='restart' and (net in ('ui_in[3]','rst_n') or run):
                off,on=(.35,.45) if net!='rst_n' else (.65,.70)
                if run:off,on=off+latency/total,on+latency/total
                points += [(total*off,high),(total*off+1e-10,0),(total*on,0),(total*on+1e-10,high)]
            if args.scenario=='switch' and run:
                # Registered enables: the old ring stops at the configuration
                # update and the new ring starts one host clock later.
                ring=int(net[-2]);previous=args.selection
                for fraction,sel in [(.3,1),(.6,2)]:
                    change=total*fraction+getattr(args,'configuration_latency_ns',1)*1e-9
                    if ring==previous:points += [(change,points[-1][1]),(change+1e-10,0)]
                    if ring==sel:points += [(change+latency,points[-1][1]),(change+latency+1e-10,args.voltage)]
                    previous=sel
            if args.scenario in ('switch','switch-safe') and net in ('ui_in[6]','ui_in[7]'):
                bit=0 if net=='ui_in[6]' else 1
                for fraction,sel in [(.3,1),(.6,2)]:
                    change=total*fraction
                    if args.control_model=='clocked':
                        edge_ns=10+math.ceil((args.duration_ns*fraction-10)/args.host_period_ns)*args.host_period_ns
                        change=(edge_ns-args.request_lead_ns)*1e-9
                    points += [(change,points[-1][1]),(change+1e-10,((sel>>bit)&1)*args.voltage)]
            if args.scenario=='switch-safe' and net=='ui_in[3]':
                for fraction in (.3,.6):
                    edge_ns=10+math.ceil((args.duration_ns*fraction-10)/args.host_period_ns)*args.host_period_ns
                    # Disable two whole host periods before changing request;
                    # re-enable two periods after the configuration capture.
                    off=(edge_ns-args.request_lead_ns-2*args.host_period_ns)*1e-9
                    on=(edge_ns+2*args.host_period_ns)*1e-9
                    points += [(off,high),(off+1e-10,0),(on,0),(on+1e-10,high)]
            lines.append(f'Vboundary{i} {n} 0 '+pwl(points))
    if not replay:duration=args.duration_ns*1e-9
    obs=part['observations'];signals=' '.join(f'v({n})' for n in obs.values())
    # wr_singlescale/vector names give a compact single-time-column table.
    lines+=['.options method=gear reltol=0.003 abstol=1e-12',
            '.save '+signals,
            '.control','set wr_singlescale','set wr_vecnames',
            f'tran {period/30 if replay else 50e-12:.12g} {duration:.12g}',f'wrdata {label}.dat {signals}',
            'quit','.endc','.end']
    (OUT/f'{label}-cells.spice').write_text(part['definitions'])
    (OUT/'.spiceinit').write_text('set ngbehavior=hsa\nset ng_nomodcheck\n')
    deckfile.write_text('\n'.join(lines)+'\n')
    modelhash=current_models
    inputhash=dict(generator_sha256=sha256_file(Path(__file__)),pnl_sha256=sha256_file(FINAL/'pnl/tt_um_entropy_probe.pnl.v'),
                   gds_sha256=sha256_file(FINAL/'gds/tt_um_entropy_probe.gds'),
                   spef_sha256=sha256_file(FINAL/f'spef/{args.rc}/tt_um_entropy_probe.{args.rc}.spef'),
                   model_tree_sha256=modelhash,cell_library_sha256=sha256_file(LIBCELL),
                   deck_sha256=sha256_file(deckfile),constraints_sha256=sha256_file(ROOT/'tinytapeout/src/constraints.sdc'),
                   tool_image_id=subprocess.check_output(chip.docker('image','inspect',IMAGE,'--format','{{.Id}}'),text=True).strip())
    libsuffix={'tt':'tt_025C_1v80','ff':'ff_n40C_1v95','ss':'ss_100C_1v60'}[args.corner]
    inputhash['liberty_sha256']=sha256_file(PDK/f'libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__{libsuffix}.lib')
    if args.replay:
        inputhash['replay_data_sha256']=sha256_file(Path(args.replay))
        inputhash['replay_measurements_sha256']=sha256_file(Path(args.replay).with_suffix('.measure.json'))
    if args.prepare_only:
        print('Prepared',deckfile);return
    (OUT/f'{label}.measure.json').write_text(json.dumps({'status':'RUNNING_UNVERIFIED','input_fingerprints':inputhash},indent=2))
    cmd=chip.docker('run','--rm','--network','none','--mount',f'type=bind,source={ROOT},target=/work',
                   '--workdir','/work/build/routed-spice',IMAGE,'ngspice','-b',deckfile.name)
    with (OUT/f'{label}.log').open('w') as log:
        result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:
        (OUT/f'{label}.measure.json').write_text(json.dumps({'status':'FAIL','reason':'ngspice failed','input_fingerprints':inputhash},indent=2))
        raise RuntimeError((result.returncode,OUT/f'{label}.log'))
    trace=read_trace(datafile,list(obs))
    (OUT/f'{label}.signals.json').write_text(json.dumps(list(obs)))
    measurements=analyze(trace,args,part)
    measurements.update(input_fingerprints=inputhash,partition=part['partition'],
                        first_stage=part['first_stage'],last_stage=part['last_stage'],
                        parameters=vars(args),rc_components=part['rc'],control_model=part['control_model'],configuration_cells=part['configuration_cells'],
                        active_cells=len(part['cell_names']),termination_cells=len(part['load_cell_names']),
                        termination_model='Liberty maximum rise/fall pin capacitance',
                        limitations=['Routed signal SPEF R/C plus standard-cell schematic transistors; not full transistor layout extraction.',
                                     'Supply interconnect ideal; external aggressor coupling grounded.',
                                     ('Configuration flops/clock tree simulated; monitor/interface and other omitted logic cut.' if args.control_model=='clocked' else 'Cut control-register states driven ideally.'),
                                     'Excluded fanout is terminated with Liberty maximum rise/fall pin capacitance; not whole-chip logic activity.',
                                     'Partitioned waveform replay is not simultaneous source-divider simulation.',
                                     'No physical entropy, process guarantee or hardware-validation claim.'])
    (OUT/f'{label}.measure.json').write_text(json.dumps(measurements,indent=2)+'\n')
    print(json.dumps(measurements,indent=2))
    if measurements['status']!='PASS':raise SystemExit(1)

def analyze(trace,args,part):
    """Recheck the full waveform, including every control phase and quiet window."""
    measurements=measure(trace,args.voltage,part['partition'],args.stage_count)
    if args.scenario!='steady':
        # Ignore transitions; demand sustained settled behavior in every phase.
        total=trace['time'][-1]
        windows=[(.10,.30),(.50,.63),(.78,1.0)] if args.scenario=='restart' else [(.08,.28),(.38,.58),(.70,1.0)]
        if args.scenario=='switch-safe':
            intervals=[]
            for fraction in (.3,.6):
                edge_ns=10+math.ceil((args.duration_ns*fraction-10)/args.host_period_ns)*args.host_period_ns
                intervals.append((edge_ns-args.request_lead_ns-2*args.host_period_ns,edge_ns+2*args.host_period_ns))
            (off1,on1),(off2,on2)=intervals
            windows=[(.08,(off1-10)/args.duration_ns),((on1+20)/args.duration_ns,(off2-10)/args.duration_ns),((on2+20)/args.duration_ns,1.)]
        phases=[]
        for a,b in windows:
            idx=[i for i,t in enumerate(trace['time']) if total*a<=t<=total*b]
            window={key:[values[i] for i in idx] for key,values in trace.items()}
            phase=measure(window,args.voltage,part['partition'],args.stage_count)
            if args.control_model=='clocked':
                expected=len(phases) if args.scenario in ('switch','switch-safe') else args.selection
                phase['expected_configuration']=expected
                for bit in (0,1):
                    values=window[f'config{bit}'];want=(expected>>bit)&1
                    if not values or (min(values)<.8*args.voltage if want else max(values)>.2*args.voltage):
                        phase['failures'].append(f'clocked configuration bit {bit} did not settle to {want}')
                phase['status']='FAIL' if phase['failures'] else 'PASS'
            phase['liberty_pulse_requirement_ns']=liberty_pulse_floor(args.corner,phase)
            if min(phase['min_clock_high_ns'],phase['min_clock_low_ns'])<phase['liberty_pulse_requirement_ns']:
                phase['failures'].append('clock width below slew-interpolated Liberty requirement')
                phase['status']='FAIL'
            phases.append(phase)
        measurements=phases[-1].copy()
        measurements['phase_measurements']=phases
        measurements['failures']=[f'phase {i}: {failure}' for i,p in enumerate(phases) for failure in p['failures']]
        if args.scenario=='restart':
            for a,b in [(.38,.44),(.68,.69)]:
                ids=[i for i,t in enumerate(trace['time']) if total*a<=t<=total*b]
                quiet={k:[v[i] for i in ids] for k,v in trace.items()}
                if crossings(quiet['time'],quiet['clock'],args.voltage/2,'rise'):
                    measurements['failures'].append('clock continues during disable/reset')
                if max(quiet['reset'],default=args.voltage)>.2*args.voltage:
                    measurements['failures'].append('divider reset not asserted while inactive')
        if args.scenario=='switch-safe':
            for fraction in (.3,.6):
                edge_ns=10+math.ceil((args.duration_ns*fraction-10)/args.host_period_ns)*args.host_period_ns
                off=edge_ns-args.request_lead_ns-2*args.host_period_ns
                on=edge_ns+2*args.host_period_ns
                ids=[i for i,t in enumerate(trace['time']) if (off+10)*1e-9<=t<=(on-2)*1e-9]
                if not ids or crossings([trace['time'][i] for i in ids],[trace['clock'][i] for i in ids],args.voltage/2,'rise'):
                    measurements['failures'].append('safe switching did not stop divider clock during disabled interval')
                if not ids or max(trace['reset'][i] for i in ids)>.2*args.voltage:
                    measurements['failures'].append('safe switching did not hold divider reset during disabled interval')
        measurements['status']='FAIL' if measurements['failures'] else 'PASS'
    pulse=liberty_pulse_floor(args.corner,measurements)
    measurements['liberty_pulse_requirement_ns']=pulse
    if min(measurements['min_clock_high_ns'],measurements['min_clock_low_ns'])<pulse:
        measurements['failures'].append('clock width below slew-interpolated Liberty requirement')
        measurements['status']='FAIL'
    return measurements

def case_label(args):
    label=f'{args.partition}-{args.rc}-{args.corner}-{args.selection}-{args.voltage:g}-{args.temp:g}-{args.ramp_ns:g}-{args.scenario}-en{args.enable_ramp_ns:g}'
    if args.scenario=='switch' and getattr(args,'configuration_latency_ns',1)!=1:label+=f'-cfg{args.configuration_latency_ns:g}'
    if getattr(args,'control_model','cut')=='clocked':label+=f'-clocked-p{args.host_period_ns:g}-lead{args.request_lead_ns:g}'
    if args.partition=='divider':label+=f'-stages{args.first_stage}-{args.first_stage+args.stage_count-1}'
    return label

def braced(text,start):
    begin=text.index('{',start);depth=1;end=begin+1
    while depth:
        if text[end]=='{':depth+=1
        elif text[end]=='}':depth-=1
        end+=1
    return text[begin+1:end-1]

def liberty_pulse_floor(corner,measurements):
    filename={'tt':'tt_025C_1v80','ff':'ff_n40C_1v95','ss':'ss_100C_1v60'}[corner]
    text=(PDK/f'libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__{filename}.lib').read_text()
    cell=braced(text,text.index('cell ("sky130_fd_sc_hd__dfrtp_1")'))
    clk=braced(cell,cell.index('pin ("CLK")'))
    slew=max(measurements['max_rise_slew_20_80_ns'],measurements['max_fall_slew_20_80_ns'])
    requirements=[]
    for match in re.finditer(r'timing\s*\([^)]*\)\s*\{',clk):
        timing=braced(clk,match.start())
        if '"min_pulse_width"' not in timing:continue
        for table in re.finditer(r'(?:rise|fall)_constraint\s*\([^)]*\)\s*\{',timing):
            values=braced(timing,table.start())
            xs=list(map(float,re.search(r'index_1\("([^\"]+)"\)',values)[1].split(',')))
            ys=list(map(float,re.search(r'values\("([^\"]+)"\)',values)[1].split(',')))
            assert len(xs)==len(ys)
            assert slew<=xs[-1],('clock slew beyond Liberty characterization',slew,xs[-1])
            value=ys[0]
            for a,b,ya,yb in zip(xs,xs[1:],ys,ys[1:]):
                if a<=slew<=b:value=ya+(yb-ya)*(slew-a)/(b-a);break
            requirements.append(value)
    assert requirements,'Missing clock min-pulse-width tables'
    # Use worse rise/fall requirement for both polarities; conservative.
    return max(requirements)

def compress_wave(points,tolerance):
    """Piecewise-linear simplification bounded at every original sample."""
    if len(points)<=2:return points
    a,b=points[0],points[-1]
    distances=[abs(v-(a[1]+(b[1]-a[1])*(t-a[0])/(b[0]-a[0]))) for t,v in points]
    i=max(range(len(points)),key=distances.__getitem__)
    if distances[i]<=tolerance:return [a,b]
    return compress_wave(points[:i+1],tolerance)[:-1]+compress_wave(points[i:],tolerance)

def read_trace(path,labels=None):
    lines=Path(path).read_text().splitlines()
    if labels is None:labels=json.loads(Path(path).with_suffix('.signals.json').read_text())
    columns=[[] for _ in range(len(labels)+1)]
    for row in lines[1:]:
        values=list(map(float,row.split()));assert len(values)==len(columns),(len(values),len(columns))
        for c,v in zip(columns,values):c.append(v)
    return dict(zip(['time',*labels],columns))

def crossings(t,v,threshold,direction,start=0):
    out=[]
    for i in range(1,len(t)):
        if t[i-1]<start:continue
        a,b=v[i-1],v[i]
        if (a<threshold<=b) if direction=='rise' else (a>threshold>=b):
            out.append(t[i-1]+(t[i]-t[i-1])*(threshold-a)/(b-a))
    return out

def measure(trace,voltage,partition,stage_count=10):
    t=trace['time'];v=trace['clock'];start=t[-1]*.5
    rise=crossings(t,v,voltage/2,'rise',start);fall=crossings(t,v,voltage/2,'fall',start)
    failures=[]
    if len(rise)<5:failures.append('absent sustained clock')
    period=(rise[-1]-rise[0])/(len(rise)-1) if len(rise)>1 else math.inf
    frequency=1/period
    if not 0<frequency<=500e6:failures.append('clock exceeds 500 MHz timing envelope')
    high=[next((f-r for f in fall if f>r),math.inf) for r in rise[:-1]]
    low=[next((r-f for r in rise if r>f),math.inf) for f in fall[:-1]]
    # Additional experiment floor; run() also checks the slew-interpolated
    # Liberty requirement on every measured phase.
    if high and min(high)<.5e-9:failures.append('clock high width below 0.5 ns experiment floor')
    if low and min(low)<.5e-9:failures.append('clock low width below 0.5 ns experiment floor')
    q0=crossings(t,trace['q0'],voltage/2,'rise',start)
    ratio0=(q0[-1]-q0[0])/(len(q0)-1)/period if len(q0)>1 else None
    if ratio0 is None or abs(ratio0-2)>.02:failures.append('first stage does not divide by 2')
    result=dict(status='FAIL' if failures else 'PASS',failures=failures,frequency_MHz=frequency/1e6,
                min_clock_high_ns=min(high,default=math.inf)*1e9,
                min_clock_low_ns=min(low,default=math.inf)*1e9,
                stage0_division=ratio0,clock_cycles_after_settling=len(rise))
    for direction in ('rise','fall'):
        c20=crossings(t,v,voltage*.2,direction,start)
        c80=crossings(t,v,voltage*.8,direction,start)
        first,last=(c20,c80) if direction=='rise' else (c80,c20)
        slews=[next((end-begin for end in last if end>begin),math.inf) for begin in first[:-1]]
        result[f'max_{direction}_slew_20_80_ns']=max(slews,default=math.inf)*1e9
    if partition=='divider':
        q9=crossings(t,trace['out'],voltage/2,'rise',t[-1]*.05)
        ratio=(q9[-1]-q9[0])/(len(q9)-1)/period if len(q9)>1 else None
        result['division_ratio']=ratio
        edges=crossings(t,v,voltage/2,'rise')
        intervals=[sum(a<=e<b for e in edges) for a,b in zip(q9,q9[1:])]
        result['clock_edges_per_output_period']=intervals
        expected=2**stage_count
        if len(intervals)<2 or ratio is None or abs(ratio-expected)>.02 or any(n!=expected for n in intervals):
            failures.append(f'insufficient settled /{expected} observations or misdivision')
    result['status']='FAIL' if failures else 'PASS'
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--partition',choices=['source','divider'],default='source')
    p.add_argument('--rc',choices=['min','nom','max'],default='nom')
    p.add_argument('--corner',choices=['tt','ff','ss'],default='tt')
    p.add_argument('--voltage',type=float,default=1.8)
    p.add_argument('--temp',type=float,default=25)
    p.add_argument('--selection',type=int,choices=range(3),default=0)
    p.add_argument('--ramp-ns',type=float,default=5)
    p.add_argument('--enable-ramp-ns',type=float,default=.1)
    p.add_argument('--duration-ns',type=float,default=500)
    p.add_argument('--replay')
    p.add_argument('--first-stage',type=int,default=1)
    p.add_argument('--stage-count',type=int,default=2)
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--scenario',choices=['steady','restart','switch','switch-safe'],default='steady')
    p.add_argument('--configuration-latency-ns',type=float,default=1,help='Cut-model delay from request to configuration update in switch experiment; not a synchronous control model')
    p.add_argument('--control-model',choices=['cut','clocked'],default='cut')
    p.add_argument('--host-period-ns',type=float,default=20)
    p.add_argument('--request-lead-ns',type=float,default=2,help='Request transition before the targeted host rising edge')
    args=p.parse_args()
    if args.control_model=='clocked' and args.partition!='source':p.error('Clocked control model applies to source partition')
    if not 0<args.request_lead_ns<args.host_period_ns or args.host_period_ns<20:p.error('Use host period >=20 ns and request lead strictly inside a period')
    if args.scenario=='switch-safe' and args.control_model!='clocked':p.error('Safe switching requires clocked controls')
    if not 0<=args.first_stage<10 or not 1<=args.stage_count<=10-args.first_stage:p.error('invalid divider stage range')
    required={'tt':(1.8,25),'ff':(1.95,-40),'ss':(1.6,100)}[args.corner]
    if (args.voltage,args.temp)!=required:
        p.error('Pulse checking requires the characterized voltage/temperature pair '+str(required))
    if args.partition=='divider' and args.scenario!='steady':p.error('Replay partition currently checks steady division only')
    if args.scenario=='switch' and args.selection!=0:p.error('switch scenario starts at selection zero')
    if args.scenario=='switch' and not 0<=args.configuration_latency_ns<args.duration_ns*.08:
        p.error('configuration latency must be nonnegative and settle before the measured phase')
    run(args)

if __name__=='__main__':main()
