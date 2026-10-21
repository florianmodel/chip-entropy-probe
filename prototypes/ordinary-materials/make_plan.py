"""Create a portable HTML build plan with embedded circuit drawings."""
from pathlib import Path
import base64
import json

R=Path(__file__).resolve().parent
def picture(name,alt):
    data=base64.b64encode((R/name).read_bytes()).decode()
    return f'<img alt="{alt}" src="data:image/png;base64,{data}">'

html='''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ordinary-material prototypes — relay logic and physical randomness</title>
<style>
body{font:17px/1.55 system-ui,sans-serif;color:#172c3b;background:#f6f8fa;margin:0}
main{max-width:1180px;margin:40px auto;padding:35px;background:white}
h1{font-size:38px;line-height:1.15}h2{margin-top:48px;color:#116b80}h3{margin-top:28px}
img{display:block;width:100%;height:auto;border:1px solid #dce5e9;margin:24px 0}
table{width:100%;border-collapse:collapse;margin:20px 0;font-size:16px}
td,th{padding:10px;border-bottom:1px solid #dce5e9;text-align:left;vertical-align:top}
th{background:#edf5f6}pre{background:#edf3f5;padding:18px;overflow:auto;font-size:14px}
.note{border-left:4px solid #116b80;padding:15px 20px;background:#edf5f6}
.muted{color:#526573}.grid{display:grid;grid-template-columns:1fr 1fr;gap:25px}
a{color:#116b80}li{margin:8px 0}code{font-size:.9em}
@media(max-width:700px){main{margin:0;padding:18px}.grid{display:block}h1{font-size:29px}}
@media print{main{margin:0;padding:0}body{font-size:11pt}img,table{break-inside:avoid}h2{break-before:page}}
</style><main>
<p class="muted">Build proposal · 21 October 2026 · revision 1</p>
<h1>Two prototypes made with accessible materials</h1>
<p>One demonstrates logic and memory built from homemade electromagnetic switches. The other converts avalanche noise into a measurable voltage, with a purchased Pico used as its external ADC/USB reader. Both are proposed designs; neither has been physically built.</p>
<div class="note"><strong>Scope.</strong> No custom semiconductor fabrication. The relay core needs no semiconductor logic, although purchased diodes protect its contacts and LEDs show state. The RNG analog core uses only purchased discrete semiconductors and passive components; the optional Pico reader is a modern integrated circuit board. A computer/USB supply is external. No purchases, fabrication orders or changes to the earlier ASIC design were made.</div>
<table><tr><th></th><th>Homemade relay module</th><th>Discrete noise / RNG module</th></tr>
<tr><td>Function</td><td>NAND gate, loaded output/cascade demonstration, independent one-bit memory</td><td>Physical analog noise, ADC capture, proposed bit-generation procedure</td></tr>
<tr><td>First-build budget</td><td>€20–40</td><td>€20–35 including Pico and 9 V battery</td></tr>
<tr><td>Realistic envelope</td><td>200 × 150 × 50 mm, including battery and controls</td><td>Analog board 70 × 50 mm; analog + Pico about 80 × 70 mm; enclosed with 9 V battery about 100 × 80 × 35 mm</td></tr>
<tr><td>What is verified</td><td>Ideal settled-state truth/state tables</td><td>Approximate DC bias and small-signal AC calculations</td></tr>
<tr><td>What is unresolved</td><td>Magnetic force, pull-in/release, contact bounce and lifetime</td><td>Source noise, interference, clipping, correlation, entropy and usable bit rate</td></tr></table>
<p>Costs are German small-quantity purchasing allowances with typical VAT, not a checked shopping cart. Allow another €6–15 for shipping; combine orders when possible. Tools, PC, oscilloscope and optional enclosures are excluded. Size figures are layout allowances, not measured builds, PCB layouts or physical lower bounds.</p>

<h2>1. Homemade relay logic module</h2>
<p>Build four nominally identical double-pole, double-throw (DPDT) relays: K_A and K_B implement NAND; K_C demonstrates that the result can operate another relay; K_M stores one bit using a self-hold contact. A and B are manually controlled for this first experiment. K_M is independent of the NAND circuit.</p>
<p>A NAND outputs 0 only when both inputs are 1. Replicating NAND elements supplies a universal Boolean gate family, but this four-relay module is not yet a programmable or Turing-complete computer. A later design needs sequencing, program control and extendable memory.</p>
RELAY_IMAGE
<h3>Homemade relay construction</h3>
<ol>
<li>Make a bobbin from a paper tube or plastic sleeve about 8 mm in outside diameter, around a roughly 3–4 mm soft-iron core, about 20–30 mm long. Avoid relying on stainless steel as the magnetic core. Add a bent mild-steel return yoke and a pivoting/hinged ferromagnetic armature.</li>
<li>Wind approximately 1,000–1,500 turns of 0.10 mm enamelled copper wire over a 15–20 mm winding length. Actual resistance, rather than turn count, is the electrical acceptance criterion: aim for <strong>60–120 Ω</strong> per finished coil. This often means roughly 25–55 m of wire per coil; allow 250 m for four coils and rework.</li>
<li>Use a light return spring and an adjustable released magnetic gap initially around 0.2–0.5 mm. The armature should pull in before it reaches a hard stop; adjust spring tension and gap. These are experimental starting dimensions, not a proven force design.</li>
<li>Move two electrically isolated spring contacts with the armature through an insulating plastic/paper linkage. Each pole must switch from NC to NO without connecting both. A common metal armature must not electrically join the two pole circuits. Thin phosphor-bronze/brass contact leaves, copper pads and small screws are a practical start; salvaged contact material may work better than oxidized bare copper.</li>
<li>Budget about <strong>40 × 30 × 30 mm per relay</strong>. Mount four on a 200 × 150 mm base with controls and 2×AA holder. A smaller 150 × 100 mm version is a later packaging target only if contact alignment and wiring permit it.</li>
</ol>
<p>At 3.0 V, a 60–120 Ω coil draws 25–50 mA and dissipates 75–150 mW. Four energized coils plus indicators stay near 0.2 A. Use a 0.5 A fuse in the battery feed. Fit one 1N4007 directly across each coil: cathode/band to coil positive, anode to negative. This slows release somewhat, which is acceptable for a manually operated module. Operate only from the stated low-voltage battery.</p>
<h3>Exact relay connections</h3>
<pre>Supply: 2×AA → master switch → 0.5 A fuse → VLOGIC (+3 V nominal)
All coil negatives → GND

Input A: VLOGIC → toggle A → K_A coil positive
Input B: VLOGIC → toggle B → K_B coil positive

NAND contact network (pole 1):
K_A COM → Y
K_A NC  → VLOGIC
K_A NO  → K_B COM
K_B NC  → VLOGIC
K_B NO  → GND
Y       → K_C coil positive

Memory:
VLOGIC → RESET (normally closed) → FEED
FEED → SET (normally open) → HOLD
FEED → K_M pole 1 COM
K_M pole 1 NO → HOLD
HOLD → K_M coil positive
K_M pole 1 NC unused

Indicator for each of K_C and K_M (pole 2):
COM → VLOGIC
NO → 1 kΩ resistor → red LED anode
red LED cathode → GND
NC unused

Unused poles on K_A and K_B: leave all their terminals open.</pre>
<p>Momentarily press SET: the coil closes its own parallel hold contact and stays energized after SET is released. Press RESET long enough for the armature to release, initially 0.5 s. Reset dominates while held; if SET remains pressed when RESET is released, memory sets again. This is volatile memory: loss of battery power clears it. LED Q indicates the memory state through the second pole.</p>
<h3>Materials and purchasing allowance</h3>
<table><tr><th>Item</th><th>Quantity / specification</th><th>Allowance</th></tr>
<tr><td>Enamelled copper wire</td><td>0.10 mm, approximately 250 m including rework</td><td>€8–15</td></tr>
<tr><td>Magnetic and contact parts</td><td>4 cores/yokes/armatures, spring material, 8 isolated moving contact sets, screws</td><td>€0–5 with salvage</td></tr>
<tr><td>Base, bobbins, insulation, hookup wire</td><td>Wood/card/plastic; approximately 200 × 150 mm base</td><td>€3–6</td></tr>
<tr><td>Controls</td><td>2 toggles, 1 NO SET button, 1 NC RESET button, 1 master switch</td><td>€2–4</td></tr>
<tr><td>Power</td><td>2×AA holder + two cells</td><td>€2–4</td></tr>
<tr><td>Protection / indication</td><td>4×1N4007, 2 red LEDs, 2×1 kΩ, 0.5 A fuse/holder</td><td>€1–3</td></tr>
<tr><td><strong>Planning total</strong></td><td>Rounded allowance for first build</td><td><strong>€20–40</strong></td></tr></table>
<p>Salvage can lower the cost. If building the contacts proves frustrating, substitute purchased <strong>3 V DPDT relays with comparable coil current</strong>; allow roughly €12–24 for four. Do not substitute a 5 V or 12 V coil without redesigning the supply. Purchased contacts improve repeatability but do not make the homemade version smaller retroactively.</p>
<h3>Acceptance procedure</h3>
<ol><li>Build one relay first. Measure coil resistance and verify reliable pull-in at a partly discharged battery voltage around 2.6 V; adjust the magnetic structure if it fails. Never compensate with an uncontrolled increase in supply voltage.</li>
<li>With power disconnected, verify both contact poles are isolated and NC/NO never bridge during travel. Check contact resistance repeatedly; target below 1 Ω when closed.</li>
<li>After completing four, exercise each for at least 100 operations and check for sticking, missed pulls and excessive heating. This is an initial screen, not a lifetime qualification.</li>
<li>Test all four NAND inputs with K_C connected, using the multimeter as well as its lamp. Suggested loaded-high target ≥2.5 V with fresh 3 V batteries and low ≤0.2 V. Wait initially 0.5 s after input changes; later measure bounce to determine a reasonable operating speed.</li>
<li>Test SET, hold, RESET, both pressed, and power loss on the memory circuit. NAND contact transitions can briefly glitch, so do not directly use this demonstrator as a clock or hazard-free asynchronous controller.</li></ol>

<h2>2. Small physical random-number generator</h2>
<p>A reverse-biased <strong>BZX55C6V8 Zener diode</strong> supplies avalanche noise. Three AC-coupled 2N3904 common-emitter stages amplify it; a selectable second/third-stage output feeds a 1.65 V-biased ADC input. The 6.8 V breakdown mechanism is used intentionally rather than over-stressing a transistor's base-emitter junction.</p>
<p>This revises the initial resistor-noise idea: avalanche noise is generally easier to observe with a small discrete amplifier. A pencil resistor remains an interesting experiment, but is not the proposed source in this version. An ordinary Zener's datasheet does not guarantee a minimum useful noise level, so buy several and characterize them.</p>
RNG_IMAGE
<h3>Build order and supply wiring</h3>
<ol><li>Build the three amplifier cells with the local supply filters shown. All resistors can be 1% or 5%, ¼ W. Use the manufacturer-specific C/B/E pin drawing for your exact 2N3904 batch; do not assume that every TO-92 device has the same left-to-right pinout.</li>
<li>Power the analog stages from Pico <strong>3V3 OUT, physical pin 36</strong>. Each stage gets its own 100 Ω series resistor, 47 µF and 100 nF to GND. Connect the shared ground to Pico <strong>AGND, pin 33</strong>. USB supplies the Pico.</li>
<li>Build the separate 9 V branch: battery positive → master noise switch → 100 Ω → VZ; 47 µF/25 V from VZ to GND, positive at VZ; VZ → 470 Ω → Z; Z → Zener cathode/band; Zener anode → GND. Battery negative joins shared GND. Nominal Zener dissipation is about 26 mW.</li>
<li>Connect Z through a <strong>100 nF nonpolar 50 V capacitor and 10 kΩ series resistor</strong> to Q1 base. Add the protective 1N4148 between Q1 emitter (anode) and base (cathode). That resistor and diode limit start/stop transients.</li>
<li>Connect OUT1 → 100 nF → Q2 base; OUT2 → 100 nF → Q3 base. Use a 3-pin jumper to select OUT2 or OUT3 for the ADC coupling capacitor. Never connect both outputs together.</li>
<li>Wire the ADC interface including both BAT85 clamps stated in the schematic. The two 10 kΩ bias resistors connect directly to 3V3 and GND. The 22 nF capacitor is from the ADC node to GND, after the 1 kΩ series resistor. Connect to <strong>GP26 / ADC0, physical pin 31</strong>. There is no capacitor from the ADC node to a separate stiff 1.65 V reference.</li>
<li>Power the Pico before switching on 9 V; remove 9 V before unplugging USB. Keep the 9 V source away from Pico pins and fit the coupling capacitor correctly. A metal shield can around the analog section should connect to ground at one point; insulate the board from the can.</li></ol>
<p>The analog source and amplifier contain no op-amp, comparator or logic IC. The complete USB instrument uses a Pico, so it still relies on fabricated silicon. Without it, the analog board is a noise source that can be read by an existing oscilloscope/ADC. A standalone all-discrete sampler, counter and byte interface would be a separate larger circuit.</p>
<h3>Exact component schedule</h3>
<table><tr><th>Component</th><th>Quantity / value</th><th>Connection</th></tr>
<tr><td>Q1–Q3</td><td>3×2N3904, through-hole TO-92</td><td>Three identical amplifier cells</td></tr>
<tr><td>D1</td><td>1×BZX55C6V8; buy about 5 to compare</td><td>Cathode Z; anode GND</td></tr>
<tr><td>D2</td><td>1×1N4148</td><td>Anode Q1 E; cathode Q1 B</td></tr>
<tr><td>D3, D4</td><td>2×BAT85 Schottky diodes</td><td>ADC→3V3 and GND→ADC, respectively</td></tr>
<tr><td>Base dividers</td><td>3×100 kΩ, 3×47 kΩ</td><td>VA_i→100k→B_i→47k→GND</td></tr>
<tr><td>Collector resistors</td><td>3×4.7 kΩ</td><td>VA_i to C_i</td></tr>
<tr><td>Emitter networks</td><td>3×100 Ω, 3×1 kΩ, 3×10 µF/16 V</td><td>E_i→100Ω→X_i→1k→GND; 10µF from X_i to GND (+ at X_i)</td></tr>
<tr><td>Local supply filters</td><td>3×100 Ω, 3×47 µF/16 V, 3×100 nF</td><td>3V3→100Ω→VA_i; both capacitors VA_i to GND, electrolytic + at VA_i</td></tr>
<tr><td>Collector roll-off</td><td>3×470 pF ceramic</td><td>C_i to GND</td></tr>
<tr><td>Noise supply</td><td>1×100 Ω, 1×470 Ω, 1×47 µF/25 V</td><td>As specified in supply wiring</td></tr>
<tr><td>Input protection resistor</td><td>1×10 kΩ</td><td>Between C1 and Q1 B</td></tr>
<tr><td>AC coupling</td><td>4×100 nF nonpolar, all 50 V</td><td>Source→Q1; Q1→Q2; Q2→Q3; JP1→ADC interface</td></tr>
<tr><td>ADC interface resistors</td><td>1×1 kΩ, 2×10 kΩ</td><td>Series current limit; bias divider to 3V3/GND</td></tr>
<tr><td>ADC filter</td><td>1×22 nF ceramic/film</td><td>ADC node to GND</td></tr>
<tr><td>Reader / assembly</td><td>Pico RP2040, headers, 3-pin jumper, 70×50 mm perfboard, 9 V battery/clip/switch, Micro-USB data cable</td><td>Pico may sit beside the analog board</td></tr></table>
<p><strong>Total fitted analog components:</strong> 3 transistors, 4 diodes, 24 resistors, 18 capacitors. Buy small spare quantities. Count summary: 100 Ω ×7; 470 Ω ×1; 1 kΩ ×4; 4.7 kΩ ×3; 10 kΩ ×3; 47 kΩ ×3; 100 kΩ ×3. Capacitors: 100 nF ×7; 470 pF ×3; 22 nF ×1; 10 µF ×3; 47 µF ×4.</p>
<h3>Materials budget</h3>
<table><tr><th>Item</th><th>Allowance</th></tr>
<tr><td>Transistors, Zeners, clamp diodes, including spares</td><td>€1–3</td></tr>
<tr><td>Resistors and capacitors, small packs</td><td>€4–7</td></tr>
<tr><td>Perfboard, headers, jumper, wire</td><td>€2–4</td></tr>
<tr><td>9 V battery, clip, switch</td><td>€3–5</td></tr>
<tr><td>Pico RP2040</td><td>€4.10 observed; budget €5 with headers</td></tr>
<tr><td>USB data cable and shielding material</td><td>€1–4</td></tr>
<tr><td><strong>Planning total</strong></td><td><strong>€20–35</strong> allowing pack sizes and spares</td></tr></table>
<p>As price anchors checked on 21 October 2026, BerryBase listed the Pico at €4.10 including VAT, its headers at €0.50 and a cable from €0.90. Reichelt listed a CDIL 2N3904 at €0.06 each. These do not imply that every allowance above is a live vendor quote. The board is inexpensive; tools and shipping can dominate a first order.</p>
<h3>Realistic size and layout</h3>
<p>For a hand-soldered first build, place the three amplifier cells in a row along a <strong>70 × 50 mm perfboard</strong>, with the Zener/input at one end and ADC interface at the other. Keep input/output wiring apart and decoupling close to each transistor. Put the 51 × 21 mm Pico beside it: allow about <strong>80 × 70 mm</strong> for the boards together. A <strong>100 × 80 × 35 mm enclosure allowance</strong> includes an adjacent 9 V battery, switches and insulation; verify internal fit before buying a box.</p>
<p>A later SMD analog board near 30 × 25 mm may be possible, but is not laid out here. With a stock Pico and battery, the entire instrument cannot shrink to that analog-board footprint. A socketless custom PCB using an MCU chip could shrink further, at the cost of moving away from the intended simple prototype.</p>
<h3>Bench acceptance and bit generation</h3>
<ol><li>With the source disconnected, verify collector/base/emitter voltages. Approximate nominal values per stage are C=1.97 V, B=0.96 V and E=0.31 V; ADC midpoint should be near 1.65 V. Wrong pinout, a saturated transistor or a missing ground must be fixed first.</li>
<li>Use a scope, or the Pico's raw ADC capture, to inspect the output. Start on OUT2; select OUT3 if amplitude is insufficient. An initial useful measurement target is roughly 20–300 mV RMS around the ADC midpoint, without rail clipping. This is a tuning target, not a predicted noise amplitude. If clipping persists, change all three unbypassed emitter resistors from 100 Ω to 330 Ω and recalculate/check bias and gain before proceeding.</li>
<li>Acquire <strong>raw 12-bit ADC samples at a hardware-paced 100 ksample/s</strong> with RP2040 ADC FIFO + DMA. A USB reader may stream or capture finite blocks with sequence numbers and overrun flags. A 1-million-sample capture takes about 10 seconds and 2 MB at 16-bit storage, so it cannot all reside in Pico SRAM. Use checked streaming or repeated explicitly delimited blocks; do not pretend discontinuous blocks are one uninterrupted trace. Reader firmware is a specified next implementation, not supplied or tested in this proposal.</li>
<li>Compare source-on with source disconnected and Q1 input AC-grounded through C1/10k. Inspect spectrum for 50 Hz and supply/USB peaks, histograms for clipping, lag correlation, and variation with supply, shielding, position and temperature. Noise still present without the diode may be amplifier/ADC noise or interference; it is not proof of Zener entropy.</li>
<li>For a demonstration bitstream, choose a fixed threshold from a separate calibration capture, then decimate according to observed dependence, and compare held-out samples to that threshold. Stop output on stuck signals, clipping, lost samples or a failed health check. Do not choose a threshold or bit from an adaptive PRNG.</li>
<li>Optional von Neumann demonstration: non-overlapping 01→0, 10→1, discard 00/11. Unbiased output requires the appropriate independence and equal-bias assumptions; it does not fix arbitrary correlation or create entropy. With independent fair inputs it retains ¼ of input bits, but this is not a promised throughput. A hash could make output look uniform without establishing entropy, so leave raw capture available.</li>
<li>There is <strong>no justified useful random-bit rate yet</strong>. Min-entropy estimation, restart behavior, health-test thresholds and extraction must follow source characterization. The first delivered hardware milestone would be a measurable noise source plus diagnostic bitstream, not a validated key generator. NIST SP 800-90B supplies a framework; this proposal is not a certification claim.</li></ol>

<h2>Checks performed and practical recommendation</h2>
CHECK_SUMMARY
<p>The relay module is the better first build for understanding and manufacturing a computing element. The RNG is the better first build for a compact physical experiment, but its strongest uncertainty is how much trustworthy entropy survives interference and sampling. Build one relay and one amplifier stage before purchasing or assembling the full sets.</p>
<p>Tools for the relay: multimeter, winding jig/hand drill used slowly, pliers, wire cutters, fine abrasive, small screwdriver and soldering equipment. For the RNG: multimeter, soldering equipment, PC + USB data cable; a borrowed oscilloscope is strongly useful. Tool costs are not included above.</p>
<h3>Sources and evidence</h3><ul>
<li><a href="https://web.cecs.pdx.edu/~harry/Relay/RelayPaper.htm">Harry Porter: relay computer design</a> — reference for relay logic. The proposed contacts and mechanics here are our own unbuilt design; Porter's computer also uses semiconductor RAM.</li>
<li><a href="https://www.analog.com/en/resources/design-notes/building-a-lowcost-whitenoise-generator.html">Analog Devices: low-cost white-noise generator</a> — avalanche-noise mechanism and unpredictable diode noise amplitude. Our low-frequency discrete amplifier is not a reproduction of that LNA circuit.</li>
<li><a href="https://www.vishay.com/docs/85604/bzx55.pdf">Vishay BZX55-series datasheet</a> — diode ratings; no useful noise amplitude guarantee.</li>
<li><a href="https://cdn-reichelt.de/documents/datenblatt/A100/2N3903_04-CDIL.PDF">CDIL 2N3904 datasheet</a> — electrical ratings and the actual package/pinout to consult for that vendor's part.</li>
<li><a href="https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html">Raspberry Pi Pico documentation</a> — pin functions and hardware documentation; consult RP2040 ADC/FIFO/DMA documentation when implementing capture.</li>
<li><a href="https://www.berrybase.de/raspberry-pi-pico-rp2040-mikrocontroller-board">BerryBase Pico price</a>; <a href="https://www.reichelt.de/de/de/shop/produkt/bipolartransistor_npn_40v_0_2a_0_5w_to-92-2020">Reichelt 2N3904 price</a>; <a href="https://www.berrybase.de/batteriehalter-fuer-2x-mignon-aa-mit-loetanschluss">2×AA holder, €0.39, 58×32×14.5 mm</a>; <a href="https://www.berrybase.de/lochrasterplatine-doppelseitig-5x7cm-10-stueck//">5×7 cm perfboard pack</a> — purchasing and size anchors, checked 21 October 2026.</li>
<li><a href="https://csrc.nist.gov/pubs/sp/800/90/b/final">NIST SP 800-90B</a> — entropy-source characterization and validation requirements.</li>
</ul>
<p class="muted">Companion files: check_design.py, design-checks.json, render_schematics.py, relay-schematic.png, rng-schematic.png. The HTML embeds both images and can be shared as a single file.</p>
</main></html>'''
checks=json.loads((R/'design-checks.json').read_text())
b=checks['nominal_amplifier_bias']; gain=checks['ac_gain_at_hz']['1000']
summary=f'''<div class="note">Ideal relay NAND: all four inputs correct. Memory: all eight combinations of old state / SET / RESET evaluated. Amplifier: 27 approximate bias corners (β=50/100/300; VBE=0.60/0.65/0.75 V; 3V3 supply ±5%) retained active-region headroom, minimum modeled VCE {checks['minimum_vce']:.2f} V. Nominal modeled collector current {b['ic']*1000:.3f} mA per stage; simplified finite-β hybrid-π gain from ideal Zener-node excitation to ADC is about {gain:.0f} V/V at 1 kHz with OUT3 selected. No transistor SPICE simulation, avalanche/noise simulation, parasitic analysis, ADC model or physical measurements were performed. The calculations support the chosen starting values; they establish neither entropy nor stability of the assembled high-gain circuit.</div>'''
html=html.replace('RELAY_IMAGE',picture('relay-schematic.png','Relay NAND and memory circuit schematic'))
html=html.replace('RNG_IMAGE',picture('rng-schematic.png','Discrete noise source, repeated amplifier cell and ADC interface schematic'))
html=html.replace('CHECK_SUMMARY',summary)
(R/'build-plan.html').write_text(html)
print(f'Wrote {R / "build-plan.html"}')
