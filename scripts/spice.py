#!/usr/bin/env python3
"""Run reproducible deterministic SKY130 oscillator corner experiments."""
import concurrent.futures,json,subprocess,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/spice';OUT.mkdir(parents=True,exist_ok=True)
IMAGE='chip-ngspice:39'
PDK='/work/.tools/pdk/sky130A'
cells=(ROOT/'.tools/pdk/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice').read_text()
(OUT/'cells.spice').write_text('\n'.join(re.search(r'(?m)^\.subckt sky130_fd_sc_hd__'+name+r'\s.*?^\.ends[^\n]*',cells,re.S|re.M)[0] for name in ('inv_1','nand2_1','buf_1','dfrtp_1')))
(OUT/'.spiceinit').write_text('set ngbehavior=hsa\nset ng_nomodcheck\n')
def case(spec,wire_load=5):
 corner,voltage,temp,stages=spec
 name=f'{corner}-{voltage}-{temp}-{stages}' + ('-unloaded' if wire_load==0 else '')
 lines=[f'SKY130 {name}: deterministic startup and frequency, NOT entropy',
 f'.lib "{PDK}/libs.tech/ngspice/sky130.lib.spice" {corner}',
 '.include "cells.spice"',
 f'.temp {temp}',f'Vpower vdd 0 PWL(0 0 5n {voltage})',
 f'Venable en 0 PWL(0 0 10n 0 10.1n {voltage})',
 f'Xgate n{stages-1} en 0 0 vdd vdd n0 sky130_fd_sc_hd__nand2_1']
 for i in range(1,stages):lines.append(f'Xi{i} n{i-1} 0 0 vdd vdd n{i} sky130_fd_sc_hd__inv_1')
 lines += [f'Xbuf n{stages-1} 0 0 vdd vdd raw sky130_fd_sc_hd__buf_1',
 # Deliberately extra loading: wire approximation per stage, plus mux and FF input load.
 *[f'Cwire{i} n{i} 0 {wire_load}f' for i in range(stages)],f'Cload raw 0 {20 if wire_load else 0}f',
 '.control','set filetype=ascii','tran 20p 200n',
 f'wrdata {name}.dat v(raw)', 'quit','.endc','.end']
 deck='\n'.join(lines)+'\n'
 sp=OUT/f'{name}.sp'
 # Same pinned models and circuit; a longer completed observation is reusable.
 def circuit(text):
  return re.sub(r'(?m)^tran .*$', 'TRAN', re.sub(r'(?m)^\.include .*$', 'PINNED_STANDARD_CELLS',text))
 cached=sp.exists() and circuit(sp.read_text())==circuit(deck) and (OUT/f'{name}.dat').exists() and 'ngspice-39 done' in (OUT/f'{name}.log').read_text()
 if not cached:sp.write_text(deck)
 cmd=['docker','--context','colima-chip','run','--rm','--network','none','--mount',f'type=bind,source={ROOT},target=/work','--workdir','/work/build/spice',IMAGE,'ngspice','-b',f'{name}.sp']
 if not cached:
  result=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  (OUT/f'{name}.log').write_text(result.stdout)
  assert result.returncode==0,(name,result.returncode,result.stdout[-1000:])
 data=[tuple(map(float,row.split())) for row in (OUT/f'{name}.dat').read_text().splitlines()]
 crossings=[]
 for (t0,v0),(t1,v1) in zip(data,data[1:]):
  if v0<voltage/2<=v1 and t0>50e-9:crossings.append(t0+(t1-t0)*(voltage/2-v0)/(v1-v0))
 assert len(crossings)>=3,(name,'no sustained oscillation',len(crossings))
 period=(crossings[-1]-crossings[0])/(len(crossings)-1)
 return dict(corner=corner,voltage=voltage,temp_C=temp,stages=stages,frequency_MHz=1e-6/period,rising_edges_after_50ns=len(crossings))
if __name__=='__main__':
 specs=[(c,v,t,n) for c in ('tt','ff','ss') for v in (1.6,1.8,1.95) for t in (-40,25,100) for n in (71,95,127)]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  rows=list(pool.map(case,specs))
 image=subprocess.check_output(['docker','--context','colima-chip','image','inspect',IMAGE,'--format','{{.Id}}'],text=True).strip()
 report=dict(status='PASS',image_id=image,cases=rows,wire_load_fF_per_stage=5,output_load_fF=20,limits=['Schematic transistor models with lumped loads, not extracted layout RC.','Deterministic transient analysis does not model or establish entropy.','PDK model corners are not a manufacturing guarantee.'])
 (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
 print(f'PASS: {len(rows)} oscillator corner cases; {min(r["frequency_MHz"] for r in rows):.1f}–{max(r["frequency_MHz"] for r in rows):.1f} MHz')
