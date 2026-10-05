#!/usr/bin/env bash
set -euo pipefail
mkdir -p build/rtl
verilator --lint-only --Wall examples/counter/counter.v
iverilog -g2012 -s counter_tb -o build/rtl/counter.vvp examples/counter/counter.v examples/counter/counter_tb.v
vvp build/rtl/counter.vvp | tee build/rtl/test.log
yosys -p 'read_verilog examples/counter/counter.v; hierarchy -check -top counter; synth -top counter; check -assert; stat; write_json build/rtl/counter.json' > build/rtl/synthesis.log
echo "RTL simulation, lint and synthesis passed."
