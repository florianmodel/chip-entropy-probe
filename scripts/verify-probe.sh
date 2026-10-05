#!/usr/bin/env bash
set -euo pipefail
mkdir -p build/probe-rtl
verilator --lint-only --Wall examples/entropy-probe/entropy_monitor.v
iverilog -g2012 -s entropy_monitor_tb -o build/probe-rtl/monitor.vvp \
    examples/entropy-probe/entropy_monitor.v examples/entropy-probe/entropy_monitor_tb.v
vvp build/probe-rtl/monitor.vvp | tee build/probe-rtl/test.log
yosys -p 'read_verilog examples/entropy-probe/entropy_monitor.v; hierarchy -check -top entropy_monitor; synth -top entropy_monitor; check -assert; stat; write_json build/probe-rtl/monitor.json' > build/probe-rtl/synthesis.log
echo 'Monitor RTL lint, simulation and synthesis passed.'
library="$PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
cell_models="$PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/verilog"
yosys -p "read_liberty -lib -ignore_miss_func $library; read_verilog examples/entropy-probe/entropy_monitor.v; synth -top entropy_monitor; dfflibmap -liberty $library; abc -liberty $library; clean; check -assert; write_verilog -noattr build/probe-rtl/monitor.nl.v" > build/probe-rtl/gate-synthesis.log
iverilog -g2012 -DFUNCTIONAL -DUNIT_DELAY= -s entropy_monitor_tb \
    -o build/probe-rtl/monitor-gates.vvp "$cell_models/primitives.v" \
    "$cell_models/sky130_fd_sc_hd.v" build/probe-rtl/monitor.nl.v \
    examples/entropy-probe/entropy_monitor_tb.v
vvp build/probe-rtl/monitor-gates.vvp | tee build/probe-rtl/gates.log
