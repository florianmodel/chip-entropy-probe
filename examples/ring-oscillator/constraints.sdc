# Timing graph cut only: the physical feedback wire remains connected.
# Static timing cannot predict oscillator frequency or entropy.
create_clock -name control_ref -period 20
set_input_delay 0 -clock control_ref [get_ports enable]
set_load 0.01 [get_ports raw_out]
set_disable_timing -from A -to Y [get_cells ro_gate]
