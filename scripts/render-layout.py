"""Render real GDS using KLayout's offscreen GUI; run with klayout -z -r."""
import json
import os
from pathlib import Path
import pya

root = Path('/work')
probe = os.environ.get('CHIP_VIEW') == 'probe'
tt = os.environ.get('CHIP_VIEW') == 'tt'
folder, design, label = ('entropy-probe', 'entropy_probe', 'probe') if probe else ('ring-oscillator', 'ring_oscillator', 'oscillator')
if tt:
    folder, design, label = 'tinytapeout/src', 'tt_um_entropy_probe', 'tt'
mw = pya.Application.instance().main_window()
mw.load_layout(str(root / f'build/{folder}/runs/verified/final/gds/{design}.gds'), 1)
view = mw.current_view()
view.load_layer_props(str(root / '.tools/pdk/sky130A/libs.tech/klayout/tech/sky130A.lyp'))
view.max_hier()
view.set_config('background-color', '#101820')
view.zoom_fit()
view.save_image(str(root / f'build/{label}-layout.png'), 1200, 1200)
report = json.loads((root / f'build/{label}-verification.json').read_text())
boxes = list(report['positions_um'].values()) if probe or tt else [c['bbox_um'] for c in report['cells'].values()]
view.zoom_box(pya.DBox(min(b[0] for b in boxes)-3, min(b[1] for b in boxes)-3,
                       max(b[2] for b in boxes)+3, max(b[3] for b in boxes)+3))
view.save_image(str(root / f'build/{label}-layout-detail.png'), 1400, 700)
if tt and 'ring_lengths' in report:
    for stages in report['ring_lengths']:
        ring_boxes = [b for name,b in report['positions_um'].items() if name.startswith(f'probe.bank.ring{stages}.')]
        view.zoom_box(pya.DBox(min(b[0] for b in ring_boxes)-2,min(b[1] for b in ring_boxes)-2,
                              max(b[2] for b in ring_boxes)+2,max(b[3] for b in ring_boxes)+2))
        view.save_image(str(root / f'build/tt-layout-ring-{stages}.png'),1800,500)
pya.Application.instance().exit(0)
