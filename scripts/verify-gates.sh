#!/usr/bin/env bash
set -euo pipefail
mkdir -p build/gates
cell_models="$PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/verilog"
iverilog -g2012 -DFUNCTIONAL -DUNIT_DELAY= -s counter_tb -o build/gates/counter.vvp \
    "$cell_models/primitives.v" "$cell_models/sky130_fd_sc_hd.v" \
    build/counter/runs/verified/final/nl/counter.nl.v examples/counter/counter_tb.v
vvp build/gates/counter.vvp | tee build/gates/test.log
echo "Gate-level functional simulation passed (without SDF annotation)."
