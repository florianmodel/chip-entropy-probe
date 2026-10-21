create_clock -name clk -period 20 [get_ports clk]
set_input_delay 2 -clock clk [get_ports {rst_n ena ui_in[*] uio_in[*]}]
set_output_delay 2 -clock clk [get_ports {uo_out[*] uio_out[*] uio_oe[*]}]
set_load 0.01 [get_ports {uo_out[*] uio_out[*] uio_oe[*]}]
# Break only physical RO feedback arcs; sampling is an asynchronous crossing.
foreach n {71 95 127} {
    set_disable_timing -from A -to Y [get_cells probe.bank.ring${n}.ro_gate]
}
# Only the first synchronizer data input is asynchronous. Find its driver by
# preserved net name rather than a synthesis-generated instance number. Cutting
# this endpoint covers ring and external-test inputs, without removing timing on
# sync_meta Q -> sync_sample D, monitor logic, or any divider feedback path.
set meta_q [get_pins -of_objects [get_nets probe.monitor.sync_meta] -filter {direction == output}]
if {[llength $meta_q] != 1} { error "Expected one sync_meta driver" }
set meta_cell [get_cells -of_objects $meta_q]
set meta_d [get_pins [get_full_name $meta_cell]/D]
if {[llength $meta_d] != 1} { error "Expected one first-stage synchronizer D pin" }
set_false_path -to $meta_d
# Conservative provisional 500 MHz ceiling, independently checked with SPICE.
create_clock -name ro_clock -period 2 [get_pins {probe.divider.stage[0].ff/CLK}]
for {set i 0} {$i < 10} {incr i} {
    set cell [format {probe.divider.stage[%d].ff} $i]
    create_generated_clock -name div$i -source [get_pins $cell/CLK] -divide_by 2 [get_pins $cell/Q]
    set_false_path -to [get_pins $cell/RESET_B]
}
set_false_path -from [get_clocks div9] -to [get_ports {uio_out[3]}]
