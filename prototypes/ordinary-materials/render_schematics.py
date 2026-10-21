"""Render the proposed circuits. Requires Pillow, not an image-generation model."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
R=Path(__file__).resolve().parent
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'
BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
INK='#172c3b'; BLUE='#116b80'; GRAY='#526573'; ORANGE='#ad5318'

class Sheet:
    def __init__(self,title,sub,h=1280):
        self.im=Image.new('RGB',(1800,h),'#f8fafb'); self.d=ImageDraw.Draw(self.im)
        self.text(55,35,title,42,bold=True)
        self.text(55,93,sub,24,color=GRAY)
    def text(self,x,y,s,size=23,color=INK,bold=False):
        self.d.multiline_text((x,y),s,font=ImageFont.truetype(BOLD if bold else FONT,size),fill=color,spacing=7)
    def line(self,*pts,color=INK,width=4):self.d.line(pts,fill=color,width=width)
    def dot(self,x,y):self.d.ellipse((x-6,y-6,x+6,y+6),fill=BLUE)
    def box(self,x,y,w,h,title=None):
        self.d.rounded_rectangle((x,y,x+w,y+h),radius=12,fill='white',outline='#cad6dc',width=2)
        if title:self.text(x+20,y+15,title,27,bold=True)
    def ground(self,x,y):
        self.line((x,y),(x,y+12));self.line((x-18,y+12),(x+18,y+12));self.line((x-11,y+20),(x+11,y+20));self.line((x-5,y+28),(x+5,y+28))
    def resistor(self,x,y,length=90,vertical=False,label=''):
        if vertical:
            self.line((x,y),(x,y+15));self.d.rectangle((x-10,y+15,x+10,y+length-15),outline=INK,width=3);self.line((x,y+length-15),(x,y+length));self.text(x+17,y+length/2-14,label,20)
        else:
            self.line((x,y),(x+15,y));self.d.rectangle((x+15,y-10,x+length-15,y+10),outline=INK,width=3);self.line((x+length-15,y),(x+length,y));self.text(x,y-37,label,20)
    def cap(self,x,y,length=80,vertical=False,label=''):
        if vertical:
            m=y+length/2;self.line((x,y),(x,m-6));self.line((x-18,m-6),(x+18,m-6));self.line((x-18,m+6),(x+18,m+6));self.line((x,m+6),(x,y+length));self.text(x+22,m-15,label,20)
        else:
            m=x+length/2;self.line((x,y),(m-6,y));self.line((m-6,y-18),(m-6,y+18));self.line((m+6,y-18),(m+6,y+18));self.line((m+6,y),(x+length,y));self.text(x,y-38,label,20)
    def relay(self,x,y,name):
        # Logical contact unit; NC closed when coil is off. BBM required.
        self.box(x,y,225,160)
        self.text(x+15,y+13,name+' / pole 1',20,bold=True)
        self.line((x,y+85),(x+65,y+85),(x+150,y+50));self.dot(x+65,y+85)
        self.line((x+150,y+50),(x+225,y+50));self.line((x+150,y+125),(x+225,y+125))
        self.dot(x+150,y+50);self.dot(x+150,y+125)
        self.text(x+13,y+100,'COM',18);self.text(x+160,y+56,'NC',18);self.text(x+160,y+95,'NO',18)
    def save(self,name):self.im.save(R/name)

s=Sheet('01 / Homemade relay logic + one-bit memory',
        'Proposed wiring • 3 V battery • contacts drawn with coils OFF • no processor or semiconductor logic',1380)
s.box(35,150,1730,470,'NAND: two homemade relays; output Y drives a third relay K_C')
s.relay(250,270,'K_A');s.relay(790,345,'K_B')
s.line((475,320),(570,320),(570,230));s.text(525,194,'+3 V',23,color=BLUE)
s.line((475,395),(640,395),(640,430),(790,430))
s.line((1015,395),(1110,395),(1110,230));s.text(1060,194,'+3 V',23,color=BLUE)
s.line((1015,470),(1110,470),(1110,510));s.ground(1110,510)
s.line((250,355),(135,355),(135,530),(430,530));s.text(72,310,'Y',30,color=BLUE,bold=True)
s.d.rectangle((430,507,580,553),outline=INK,width=3);s.text(451,513,'K_C coil',21)
s.line((580,530),(650,530));s.ground(650,530)
s.text(1210,280,'A  B  →  Y\n0  0       1\n0  1       1\n1  0       1\n1  1       0',25)
s.text(1210,465,'K_A coil = input A\nK_B coil = input B\n1 = coil energized',23)
s.text(75,570,'K_C is the load/cascade test. Y must remain high enough to pull in K_C under load.',22,color=GRAY)

s.box(35,645,1080,405,'Memory: K_M holds itself ON after SET is released')
s.text(75,725,'+3 V',24,color=BLUE);s.line((145,740),(215,740))
s.line((215,740),(290,740));s.dot(230,740);s.dot(280,740)
s.text(198,690,'RESET (NC)',21);s.line((290,740),(360,740),(360,800))
s.line((360,800),(480,800));s.dot(480,800);s.dot(560,800);s.line((480,800),(548,775));s.line((560,800),(660,800))
s.text(460,749,'SET (NO)',21)
s.line((360,800),(360,910),(480,910));s.dot(480,910);s.dot(560,910);s.line((480,910),(548,885));s.line((560,910),(660,910),(660,800))
s.text(405,941,'K_M contact 1 (NO)',21)
s.line((660,800),(715,800));s.d.rectangle((715,775,895,825),outline=INK,width=3);s.text(740,785,'K_M coil',22);s.line((895,800),(970,800));s.ground(970,800)
s.text(75,996,'RESET opens the feed. Use contact 2 of K_M for the Q lamp.',22,color=GRAY)
s.box(1140,645,625,405,'Coils / indicators')
s.text(1170,710,'A: +3 V → toggle A → K_A coil → GND\nB: +3 V → toggle B → K_B coil → GND\nD: one 1N4007 across EVERY coil.\nD cathode (band) at coil positive.\nD anode at coil negative / GND.\n\nK_C / K_M contact 2:\nCOM = +3 V; NO → 1 kΩ → red LED → GND\nNC left unconnected. LED cathode to GND.',22)
s.box(35,1075,1730,250,'Mechanical recipe and limits')
s.text(65,1130,'Four identical homemade DPDT relays: coil + soft-iron core/yoke + return spring + two isolated SPDT contact sets.\nStart near 1,000–1,500 turns of 0.10 mm enamelled copper wire; trim winding/design to 60–120 Ω per coil.\nUse an adjustable air gap around 0.2–0.5 mm. Contacts must be break-before-make, with no NC-to-NO bridging.\nBudget 40 × 30 × 30 mm per relay; module 200 × 150 × 50 mm including 2×AA holder and controls.\nForce, pull-in voltage, bounce and durability need bench testing. Wait for contacts to settle before reading.',23)
s.save('relay-schematic.png')

s=Sheet('02 / Discrete avalanche-noise RNG prototype',
        'Three 2N3904 stages + external Pico ADC reader • nominal values • all grounds common • no guaranteed entropy',1640)
s.box(35,150,1730,320,'Noise source: reverse-biased 6.8 V Zener; noise amplitude must be measured')
s.text(65,235,'9 V\nbattery',24,color=BLUE);s.line((155,260),(200,260));s.resistor(200,260,label='100 Ω');s.line((290,260),(355,260));s.dot(355,260)
s.cap(355,260,100,True,'47 µF / 25 V');s.ground(355,360)
s.line((355,260),(600,260));s.resistor(600,260,label='470 Ω');s.line((690,260),(775,260));s.dot(775,260)
s.d.rectangle((735,310,815,380),outline=INK,width=3);s.line((775,260),(775,310));s.line((775,380),(775,410));s.ground(775,410)
s.text(850,320,'D1 BZX55C6V8\nK (band) at top; A at GND',22)
s.line((775,260),(970,260));s.cap(970,260,label='C1 100 nF');s.line((1050,260),(1115,260));s.resistor(1115,260,label='10 kΩ');s.line((1205,260),(1300,260));s.text(1315,245,'→ Q1 base',25,color=BLUE)
s.text(1170,328,'D2 across Q1 B–E:\n1N4148 anode = emitter,\ncathode (band) = base.\nLimits reverse B–E transients.',21)
s.text(65,435,'At 9 V: I_Z ≈ (9 − 6.8) / 570 = 3.9 mA. Use a 50 V nonpolar capacitor for C1.',22,color=GRAY)

s.box(35,495,1045,765,'Amplifier cell: build THREE copies, Q1 / Q2 / Q3')
s.text(75,568,'Pico 3V3 OUT',22,color=BLUE);s.line((240,583),(285,583));s.resistor(285,583,label='100 Ω');s.line((375,583),(905,583))
s.text(580,548,'VA_i (one local filter per stage)',21,color=BLUE)
s.cap(940,583,90,True,'47 µF');s.line((905,583),(940,583));s.ground(940,673)
s.text(790,725,'Also 100 nF\nVA_i to GND',20,color=GRAY)
s.line((425,583),(425,650));s.resistor(425,650,90,True,'100 kΩ');s.line((425,740),(425,825));s.dot(425,825)
s.resistor(425,825,100,True,'47 kΩ');s.ground(425,925)
s.line((650,583),(650,655));s.resistor(650,655,90,True,'4.7 kΩ');s.line((650,745),(650,785))
# Transistor: base vertical at x560, collector upper right, emitter lower right.
s.line((425,825),(560,825));s.line((560,790),(560,865));s.line((560,806),(650,760));s.line((560,845),(650,895))
s.line((635,875),(650,895),(625,893));s.text(680,805,'2N3904\nC / B / E',22)
s.line((650,895),(650,930));s.resistor(650,930,85,True,'100 Ω');s.dot(650,1015)
s.resistor(650,1015,100,True,'1 kΩ');s.ground(650,1115)
s.line((650,1015),(875,1015));s.cap(875,1015,100,True,'10 µF');s.ground(875,1115)
s.text(840,1148,'+ at upper end',19,color=GRAY)
s.line((650,760),(790,760),(790,875),(995,875));s.text(820,842,'OUT_i',23,color=BLUE)
s.cap(995,875,105,True,'470 pF');s.ground(995,980)
s.line((130,825),(425,825));s.text(75,775,'IN_i',23,color=BLUE)
s.text(75,1030,'DC target, each stage:\nVA ≈ 3.27 V\nB ≈ 0.96 V; E ≈ 0.31 V\nC ≈ 1.97 V\nCheck before connecting ADC.',23)
s.text(75,1200,'OUT1 → 100 nF → IN2; OUT2 → 100 nF → IN3.',22,color=GRAY)

s.box(1105,495,660,765,'ADC output interface')
s.text(1140,560,'JP1: OUT2 / OUT3\nUse OUT2 if OUT3 clips.',21)
s.line((1150,675),(1190,675));s.cap(1190,675,label='100 nF');s.line((1270,675),(1310,675));s.resistor(1310,675,90,label='1 kΩ');s.line((1400,675),(1540,675));s.dot(1470,675)
s.text(1525,590,'GP26 / ADC0\nPico pin 31',22,color=BLUE)
s.resistor(1470,790,90,True,'10 kΩ');s.line((1470,675),(1470,790));s.ground(1470,880)
s.line((1470,715),(1380,715),(1380,735));s.line((1470,675),(1470,715));s.cap(1380,735,110,True,'22 nF');s.ground(1380,845)
s.line((1470,675),(1470,645));s.resistor(1470,555,90,True,'10 kΩ');s.line((1470,555),(1470,535));s.text(1530,535,'3V3',21,color=BLUE)
s.text(1140,960,'Bias at ADC: 1.65 V DC.\nD3 BAT85: anode ADC, cathode 3V3.\nD4 BAT85: anode GND, cathode ADC.\nClamps omitted graphically; wire both.\n\nPico pin 36 = 3V3 OUT\nPico pin 33 = AGND / shared GND\nUSB powers Pico; 9 V powers D1 only.\nPower Pico first; disconnect 9 V first.',22)

s.box(35,1285,1730,300,'Sampling, size and validation boundary')
s.text(65,1345,'Acquire raw ADC codes at a fixed 100 ksample/s using ADC FIFO + DMA. Save raw data before any conditioning.\nDerive candidate bits only after measuring correlation and choosing a decimation interval; no fixed useful bit rate claimed.\nDemonstration debiasing: 01 → 0, 10 → 1, discard 00/11. This needs independent, identically biased input bits.\nAnalog perfboard: 70 × 50 mm. Board + Pico: about 80 × 70 mm. Enclosure + 9 V battery: about 100 × 80 × 35 mm.\nThese are layout targets, not routed PCB dimensions. DC + simplified AC checks passed; no physical build/no entropy proof.',23)
s.save('rng-schematic.png')
print('Rendered relay-schematic.png and rng-schematic.png')
