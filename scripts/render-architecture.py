"""Render architectural diagrams from an archived/current verification report."""
import json,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[1]
folder=Path(sys.argv[1]) if len(sys.argv)>1 else root/'build'
report=json.loads((folder/'tt-verification.json').read_text())
img=Image.new('RGB',(1500,840),'#101820');d=ImageDraw.Draw(img)
font=next((str(p) for p in [Path('/System/Library/Fonts/Supplemental/Arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists()),'DejaVuSans.ttf')
f=ImageFont.truetype(font,24);title=ImageFont.truetype(font,36);small=ImageFont.truetype(font,21)
def box(rect,text,color='#194663'):
 d.rounded_rectangle(rect,radius=15,fill=color,outline='#7caac6',width=2)
 lines=text.split('\n');x=(rect[0]+rect[2])/2;y=(rect[1]+rect[3])/2
 for i,line in enumerate(lines):d.text((x,y+(i-(len(lines)-1)/2)*32),line,font=f,fill='white',anchor='mm')
def arrow(a,b):
 d.line([a,b],fill='#abd9e9',width=4)
 import math
 angle=math.atan2(b[1]-a[1],b[0]-a[0])
 points=[b]+[(b[0]-14*math.cos(angle+s),b[1]-14*math.sin(angle+s)) for s in (-.45,.45)]
 d.polygon(points,fill='#abd9e9')
d.text((60,38),'Physical entropy measurement chip',font=title,fill='white')
d.text((60,96),'Architecture overview — the physical layer PNGs show actual routed geometry.',font=small,fill='#b6c9d1')
lengths=report.get('ring_lengths',[5]);bank='Oscillator source\n'+'/'.join(map(str,lengths))+' stages\nOne enabled at a time' if len(lengths)>1 else 'Gated oscillator\n5 stages'
box((60,200,405,350),bank)
box((60,415,405,555),'Deterministic test modes\n0 / 1 / alternating / external')
box((500,240,730,400),'Source selection\nMode-change reset')
box((835,240,1110,400),'Two-flop sampler\nWarm-up validity')
box((1180,240,1440,400),'256-sample windows\nOnes / transitions\nFrozen reports')
arrow((405,275),(500,285));arrow((405,475),(500,360));arrow((730,320),(835,320));arrow((1110,320),(1180,320))
box((500,485,730,625),'Ripple divider\nFrequency / 1024')
arrow((405,325),(500,520));arrow((730,550),(830,550))
d.text((845,550),'Optional frequency output',font=small,fill='white',anchor='lm')
d.text((835,452),'Raw sample + valid + report-ready outputs',font=small,fill='#b6c9d1')
d.text((60,705),f"One SKY130 tile: 161 × 111.52 µm    |    Physical checks: {report['status']}",font=f,fill='#9fd7b0' if report['status']=='PASS' else '#edc478')
d.text((60,765),'Experimental measurement hardware. Silicon characterization is required to establish entropy.',font=small,fill='#b6c9d1')
img.save(folder/'architecture.png');print(folder/'architecture.png')
