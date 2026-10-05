create_clock -name clk -period 20 [get_ports clk]
set_input_delay 2 -clock clk [get_ports {rst_n ena ui_in[*] uio_in[*]}]
set_output_delay 2 -clock clk [get_ports {uo_out[*] uio_out[*] uio_oe[*]}]
set_load 0.01 [get_ports {uo_out[*] uio_out[*] uio_oe[*]}]
# Break only physical RO feedback arcs; sampling is an asynchronous crossing.
foreach n {71 95 127} {
    set_disable_timing -from A -to Y [get_cells probe.bank.ring${n}.ro_gate]
    set_false_path -from [get_pins probe.bank.ring${n}.ro_output/X] -to [all_registers -data_pins]
}
set_false_path -from [get_ports {uio_in[6]}] -to [all_registers -data_pins]
# Conservative provisional 500 MHz ceiling, independently checked with SPICE.
create_clock -name ro_clock -period 2 [get_pins {probe.divider.stage[0].ff/CLK}]
for {set i 0} {$i < 10} {incr i} {
    set cell [format {probe.divider.stage[%d].ff} $i]
    create_generated_clock -name div$i -source [get_pins $cell/CLK] -divide_by 2 [get_pins $cell/Q]
    set_false_path -to [get_pins $cell/RESET_B]
}
set_false_path -from [get_clocks div9] -to [get_ports {uio_out[3]}]
