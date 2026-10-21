"""Engineering checks, not SPICE/noise simulation or hardware validation.

Run with a Python containing numpy. All values match build-plan.html.
"""
import json
import itertools
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent

def bias(beta=100, vbe=.65, supply=3.3):
    # Three identical stages, each with its own 100-ohm supply filter.
    va = supply
    for _ in range(100):
        rth = 100_000 * 47_000 / 147_000
        ie = (va * 47 / 147 - vbe) / (1100 + rth / (beta + 1))
        ib = ie / (beta + 1)
        ic = ie - ib
        va = supply - 100 * (ic + (va - (vbe + 1100 * ie)) / 100_000)
    vb = vbe + 1100 * ie
    return dict(beta=beta, vbe=vbe, supply=supply, va=va,
                vb=vb, ve=1100*ie, vc=va-4700*ic, ic=ic,
                vce=va-4700*ic-1100*ie)

def ac(freq, b):
    # Hybrid-pi model, finite beta. No Early effect, junction capacitance,
    # wiring parasitics, avalanche noise model or supply coupling.
    # Per stage nodes: base, collector, emitter, bypass junction.
    # ADC node=12, after output coupling/series resistor node=13.
    n=15; a=np.zeros((n,n),complex); z=np.zeros(n,complex)
    w=2j*np.pi*freq
    def adm(i,j,y):
        if i is not None: a[i,i]+=y
        if j is not None: a[j,j]+=y
        if i is not None and j is not None: a[i,j]-=y; a[j,i]-=y
    for k in range(3):
        base,col,em,by=[4*k+t for t in range(4)]
        adm(base,None,1/100_000+1/47_000)
        adm(col,None,1/4700+w*470e-12)
        adm(em,by,1/100)
        adm(by,None,1/1000+w*10e-6)
        gm=b['ic']/.02585
        adm(base,em,gm/b['beta'])
        a[col,base]+=gm; a[col,em]-=gm
        a[em,base]-=gm; a[em,em]+=gm
        if k:
            adm(4*(k-1)+1,base,w*100e-9)
        else:
            # Ideal excitation at Zener cathode, through C1 and 10k.
            adm(14,None,w*100e-9); z[14]+=w*100e-9
            adm(14,base,1/10_000)
    adm(9,13,w*100e-9)
    adm(13,12,1/1000)
    adm(12,None,1/10_000+1/10_000+w*22e-9)
    return abs(np.linalg.solve(a,z)[12])

truth=[]
for A,B in itertools.product([0,1],repeat=2):
    # COM A = Y; NC A = V+; NO A = COM B; NC B = V+; NO B = GND.
    y = 1 if not A else (1 if not B else 0)
    assert y == (not(A and B))
    truth.append(dict(A=A,B=B,Y=y))
memory=[]
for old,reset,set_ in itertools.product([0,1],repeat=3):
    # RESET pressed opens upstream supply; reset has priority.
    new=int(not reset and (set_ or old))
    memory.append(dict(old=old,reset_pressed=reset,set_pressed=set_,new=new))

corners=[bias(beta,vbe,v) for beta,vbe,v in
         itertools.product([50,100,300],[.60,.65,.75],[3.135,3.3,3.465])]
assert all(x['ic']>0 and x['vce']>.5 for x in corners)
nom=bias()
result=dict(status='analytical checks only; no bench validation',
            relay_nand=truth,relay_memory=memory,
            nominal_amplifier_bias=nom,
            dc_corner_count=len(corners),minimum_vce=min(x['vce'] for x in corners),
            ac_gain_at_hz={str(f):ac(f,nom) for f in [10,100,300,1000,3000,10000,50000]},
            zener_current_estimate_A=(9-6.8)/(100+470),
            relay_coil_current_A=[3/120,3/60],
            relay_coil_dissipation_W=[9/120,9/60],
            limitations=['Constant VBE corner approximation; finite-beta hybrid-pi AC model',
                        'No avalanche entropy model or output bit-rate prediction',
                        'No relay force, bounce, contact-resistance or lifetime validation',
                        'No parasitics, transistor fT, supply feedback or ADC sample/hold model'])
(ROOT/'design-checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
