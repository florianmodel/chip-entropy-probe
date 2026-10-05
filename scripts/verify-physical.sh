#!/usr/bin/env bash
set -euo pipefail
models="$PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/verilog"
iverilog -g2012 -DFUNCTIONAL -DUNIT_DELAY= -DUSE_POWER_PINS -s physical_tb \
 -o build/tt-rtl/physical.vvp "$models/primitives.v" "$models/sky130_fd_sc_hd.v" \
 build/tinytapeout/src/runs/verified/final/pnl/tt_um_entropy_probe.pnl.v tinytapeout/test/physical_tb.v
vvp build/tt-rtl/physical.vvp | tee build/tt-rtl/physical.log
