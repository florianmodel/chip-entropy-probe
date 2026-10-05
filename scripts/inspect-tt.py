"""Check actual mapped and routed experiment structures; preserve failed reports."""
import hashlib,json,os,re
from pathlib import Path
import odb
root=Path('/work');run=root/'build/tinytapeout/src/runs/verified';design='tt_um_entropy_probe'
m=json.loads((run/f'06-yosys-synthesis/{design}.nl.v.json').read_text())['modules'][design]
db=odb.dbDatabase.create();odb.read_db(db,str(run/f'final/odb/{design}.odb'));block=db.getChip().getBlock();scale=block.getDbUnitsPerMicron();positions={}
def cell(name,kind):
 c=m['cells'][name];i=next(x for x in block.getInsts() if x.getName().replace('\\','')==name)
 assert c['type']==i.getMaster().getName()=='sky130_fd_sc_hd__'+kind,name
 assert i.isPlaced(),name
 for port,net in {'VPWR':'VPWR','VPB':'VPWR','VGND':'VGND','VNB':'VGND'}.items():assert i.findITerm(port).getNet().getName()==net,name
 for port,bits in c['connections'].items():
  if name.startswith('probe.divider.') and port=='D':continue
  aliases=[n for n,v in m['netnames'].items() if v['bits']==bits]
  net=i.findITerm(port).getNet()
  for attempt in range(30):
   if net.getName().replace('\\','') in aliases:break
   drivers=[x for x in net.getITerms() if x.getIoType()=='OUTPUT']
   assert i.findITerm(port).getIoType()=='INPUT' and len(drivers)==1,(name,port,net.getName(),aliases)
   buffer=drivers[0].getInst()
   assert '__buf_' in buffer.getMaster().getName() or '__clkbuf_' in buffer.getMaster().getName(),(name,port,buffer.getMaster().getName())
   net=buffer.findITerm('A').getNet()
  else:raise AssertionError((name,port,'Buffer trace exceeded limit'))
 b=i.getBBox();positions[name]=[b.xMin()/scale,b.yMin()/scale,b.xMax()/scale,b.yMax()/scale];return c
lengths=sorted(int(re.search(r'ring(\d+)\.ro_gate',n)[1]) for n in m['cells'] if re.search(r'ring(\d+)\.ro_gate',n))
for n in lengths:
 base=f'probe.bank.ring{n}.';gate=cell(base+'ro_gate','nand2_1');previous=gate['connections']['Y']
 for j in range(1,n):
  inv=cell(base+f'chain[{j}].ro_inv','inv_1');assert inv['connections']['A']==previous;previous=inv['connections']['Y']
 assert gate['connections']['A']==previous
 buf=cell(base+'ro_output','buf_1');assert buf['connections']['A']==previous
for j in range(10):
 base=f'probe.divider.stage[{j}].';ff=cell(base+'ff','dfrtp_1');inv=m['cells'][base+'feedback']
 physical_ff=next(x for x in block.getInsts() if x.getName().replace('\\','')==base+'ff')
 drivers=[x for x in physical_ff.findITerm('D').getNet().getITerms() if x.getIoType()=='OUTPUT']
 assert len(drivers)==1 and drivers[0].getInst().getMaster().getName()=='sky130_fd_sc_hd__inv_1'
 physical_inv=drivers[0].getInst();net=physical_inv.findITerm('A').getNet()
 for attempt in range(30):
  if net.getName()==physical_ff.findITerm('Q').getNet().getName():break
  upstream=[x for x in net.getITerms() if x.getIoType()=='OUTPUT'];assert len(upstream)==1
  buf=upstream[0].getInst();assert '__clkbuf_' in buf.getMaster().getName() or '__buf_' in buf.getMaster().getName();net=buf.findITerm('A').getNet()
 else:raise AssertionError('Physical divider feedback broken')
 assert inv['connections']['A']==ff['connections']['Q'] and inv['connections']['Y']==ff['connections']['D']
 if j:assert ff['connections']['CLK']==m['cells'][f'probe.divider.stage[{j-1}].ff']['connections']['Q']
flops=[]
for signal in ('probe.monitor.sync_meta','probe.monitor.sync_sample'):
 bits=m['netnames'][signal]['bits'];drivers=[(n,c) for n,c in m['cells'].items() if c['connections'].get('Q')==bits]
 assert len(drivers)==1 and '__dfxtp_' in drivers[0][1]['type'];flops.append(drivers[0])
assert flops[0][1]['connections']['D']==m['netnames']['probe.monitor.raw_in']['bits']
assert flops[1][1]['connections']['D']==flops[0][1]['connections']['Q']
physical_flops=[]
for signal in ('probe.monitor.sync_meta','probe.monitor.sync_sample'):
 net=block.findNet(signal);drivers=[x for x in net.getITerms() if x.getIoType()=='OUTPUT']
 assert len(drivers)==1 and '__dfxtp_' in drivers[0].getInst().getMaster().getName()
 inst=drivers[0].getInst();physical_flops.append(inst);b=inst.getBBox();positions[inst.getName()]=[b.xMin()/scale,b.yMin()/scale,b.xMax()/scale,b.yMax()/scale]
 assert inst.isPlaced()
 assert all(inst.findITerm(p).getNet().getName()==n for p,n in {'VPWR':'VPWR','VPB':'VPWR','VGND':'VGND','VNB':'VGND'}.items())
net=block.findNet('probe.monitor.sync_meta');loads=[p for p in net.getITerms() if p.getIoType()=='INPUT'];assert len(loads)==1 and loads[0].getInst().getName()==physical_flops[1].getName() and loads[0].getMTerm().getName()=='D'
metrics=json.loads((run/'final/metrics.json').read_text())
keys=['design__lint_error__count','design__inferred_latch__count','design__instance_unmapped__count','synthesis__check_error__count','design__critical_disconnected_pin__count','design__max_slew_violation__count','design__max_cap_violation__count','design__max_fanout_violation__count','route__drc_errors','route__antenna_violation__count','magic__drc_error__count','klayout__drc_error__count','magic__illegal_overlap__count','design__lvs_error__count']
failures={k:metrics.get(k) for k in keys if metrics.get(k)!=0}
for k,v in metrics.items():
 if k.startswith(('timing__setup__ws','timing__hold__ws')) and (not isinstance(v,(float,int)) or v<0):failures[k]=v
unused={p.getName() for p in block.getBTerms() if p.getIoType()=='INPUT' and p.getNet() and not p.getNet().getITerms()}
assert unused=={f'uio_in[{j}]' for j in (0,1,2,3,7)},unused
lint=(run/'01-verilator-lint/verilator-lint.log').read_text();warnings=re.findall(r'%Warning-([^:]+):[^\n]+',lint)
assert len(warnings)==20 and set(warnings)=={'PINMISSING'},(len(warnings),set(warnings))
assert all(p in {'VPWR','VGND','VPB','VNB'} for p in re.findall(r"missing pin: '([^']+)'",lint))
gds=run/f'final/gds/{design}.gds'
report=dict(status='FAIL' if failures else 'PASS',failures=failures,design=design,ring_lengths=lengths,positions_um=positions,feedback_preserved=True,divider_preserved=True,direct_two_flop_chain_preserved=True,first_stage_fanout=1,tile_um=[161,111.52],setup_slack_ns=metrics['timing__setup__ws'],hold_slack_ns=metrics['timing__hold__ws'],gds_sha256=hashlib.sha256(gds.read_bytes()).hexdigest(),checks={k:metrics.get(k) for k in keys},reviewed_unused_inputs=sorted(unused),supply_omission_warnings=len(warnings),limits=['No fabricated entropy or oscillator frequency guarantee.','Timing clocks are explicit assumptions; compare with SPICE and hardware.'])
(root/'build/tt-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],report['failures'])
if failures and os.environ.get('CHIP_ARCHIVE')!='1':raise SystemExit(1)
