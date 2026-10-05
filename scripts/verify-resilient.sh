#!/usr/bin/env bash
set -euo pipefail
mkdir -p build/resilient-rtl
verilator --lint-only --Wall examples/resilient-probe/measurement_monitor.v
iverilog -g2012 -s measurement_monitor_tb -o build/resilient-rtl/monitor.vvp \
    examples/resilient-probe/measurement_monitor.v examples/resilient-probe/measurement_monitor_tb.v
vvp build/resilient-rtl/monitor.vvp | tee build/resilient-rtl/test.log
yosys -p 'read_verilog examples/resilient-probe/measurement_monitor.v; hierarchy -check -top measurement_monitor; synth -top measurement_monitor; check -assert; stat; write_json build/resilient-rtl/monitor.json' > build/resilient-rtl/synthesis.log
echo 'Monitor RTL lint, simulation and synthesis passed.'
library="$PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
cell_models="$PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/verilog"
yosys -p "read_liberty -lib -ignore_miss_func $library; read_verilog examples/resilient-probe/measurement_monitor.v; synth -top measurement_monitor; dfflibmap -liberty $library; abc -liberty $library; clean; check -assert; write_verilog -noattr build/resilient-rtl/monitor.nl.v" > build/resilient-rtl/gate-synthesis.log
iverilog -g2012 -DFUNCTIONAL -DUNIT_DELAY= -s measurement_monitor_tb \
    -o build/resilient-rtl/monitor-gates.vvp "$cell_models/primitives.v" \
    "$cell_models/sky130_fd_sc_hd.v" build/resilient-rtl/monitor.nl.v \
    examples/resilient-probe/measurement_monitor_tb.v
vvp build/resilient-rtl/monitor-gates.vvp | tee build/resilient-rtl/gates.log
