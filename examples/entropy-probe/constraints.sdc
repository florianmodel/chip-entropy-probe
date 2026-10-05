create_clock -name clk -period 20 [get_ports clk]
set_input_delay 2 -clock clk [get_ports {rst_n enable freeze_report addr[*]}]
set_output_delay 2 -clock clk [get_ports {data[*] sampled_bit sample_valid report_ready}]
set_load 0.01 [get_ports {data[*] sampled_bit sample_valid report_ready raw_out}]
# These two exceptions address only the intentional asynchronous source.
# They do not remove wires or waive clocked monitor timing.
set_disable_timing -from A -to Y [get_cells osc.ro_gate]
set_false_path -from [get_pins osc.ro_output/X]
# The raw pin is an asynchronous diagnostic waveform, not clocked data.
set_false_path -to [get_ports raw_out]
