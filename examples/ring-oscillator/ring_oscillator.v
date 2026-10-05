// Physical experiment: digital simulation cannot establish jitter or entropy.
module ring_oscillator(input wire enable, output wire raw_out);
    (* keep = 1 *) wire ro0, ro1, ro2, ro3, ro4;
    // NAND plus four inverters gives five inversions when enabled.
    (* keep = 1, dont_touch = 1 *) sky130_fd_sc_hd__nand2_1 ro_gate
        (.A(ro4), .B(enable), .Y(ro0));
    (* keep = 1, dont_touch = 1 *) sky130_fd_sc_hd__inv_1 ro_inv1 (.A(ro0), .Y(ro1));
    (* keep = 1, dont_touch = 1 *) sky130_fd_sc_hd__inv_1 ro_inv2 (.A(ro1), .Y(ro2));
    (* keep = 1, dont_touch = 1 *) sky130_fd_sc_hd__inv_1 ro_inv3 (.A(ro2), .Y(ro3));
    (* keep = 1, dont_touch = 1 *) sky130_fd_sc_hd__inv_1 ro_inv4 (.A(ro3), .Y(ro4));
    (* keep = 1, dont_touch = 1 *) sky130_fd_sc_hd__buf_1 ro_output (.A(ro4), .X(raw_out));
endmodule
