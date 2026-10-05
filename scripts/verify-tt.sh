#!/usr/bin/env bash
set -euo pipefail
mkdir -p build/tt-rtl
models="$PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/verilog"
iverilog -g2012 -DFUNCTIONAL -DUNIT_DELAY= -s wrapper_tb -o build/tt-rtl/wrapper.vvp \
 "$models/primitives.v" "$models/sky130_fd_sc_hd.v" \
 tinytapeout/src/tt_um_entropy_probe.v examples/resilient-probe/resilient_probe.v \
 examples/resilient-probe/measurement_monitor.v examples/resilient-probe/frequency_divider.v tinytapeout/test/wrapper_tb.v
vvp build/tt-rtl/wrapper.vvp | tee build/tt-rtl/test.log
iverilog -g2012 -DFUNCTIONAL -DUNIT_DELAY= -s divider_tb -o build/tt-rtl/divider.vvp \
 "$models/primitives.v" "$models/sky130_fd_sc_hd.v" \
 examples/resilient-probe/frequency_divider.v tinytapeout/test/divider_tb.v
vvp build/tt-rtl/divider.vvp | tee build/tt-rtl/divider.log
yosys -Q -p 'read_verilog -lib tinytapeout/src/tt_um_entropy_probe.v; hierarchy -top tt_um_entropy_probe; write_json build/tt-rtl/ports.json' > build/tt-rtl/ports.log
python3 - <<'PY'
import json
p = json.load(open('build/tt-rtl/ports.json'))['modules']['tt_um_entropy_probe']['ports']
expected = {'ui_in': ('input',8), 'uo_out': ('output',8), 'uio_in': ('input',8),
            'uio_out': ('output',8), 'uio_oe': ('output',8),
            'ena': ('input',1), 'clk': ('input',1), 'rst_n': ('input',1)}
assert set(p) == set(expected)
for name, (direction, size) in expected.items():
    assert p[name]['direction'] == direction and len(p[name]['bits']) == size
print('PASS: exact Tiny Tapeout top-level port signature')
PY
