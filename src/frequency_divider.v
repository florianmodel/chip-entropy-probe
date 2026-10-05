// Diagnostic /1024 ripple divider. Its output is not an entropy stream.
module frequency_divider(input wire raw_clock, reset_n, output wire divided);
    (* keep = 1 *) wire [9:0] q, d;
    genvar i;
    generate for (i=0; i<10; i=i+1) begin: stage
        (* keep = 1, dont_touch = 1 *) sky130_fd_sc_hd__inv_1 feedback (.A(q[i]), .Y(d[i]));
        (* keep = 1, dont_touch = 1 *) sky130_fd_sc_hd__dfrtp_1 ff
            (.CLK(i==0 ? raw_clock : q[i-1]), .D(d[i]), .RESET_B(reset_n), .Q(q[i]));
    end endgenerate
    assign divided = q[9];
endmodule
