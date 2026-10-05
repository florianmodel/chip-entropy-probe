// Explicit SKY130 gates; enabled ring has an odd number of inversions.
module measurement_ring #(parameter STAGES = 71)(input wire enable, output wire raw_out);
    (* keep = 1 *) wire [STAGES-1:0] node;
    (* keep = 1, dont_touch = 1 *) sky130_fd_sc_hd__nand2_1 ro_gate
        (.A(node[STAGES-1]), .B(enable), .Y(node[0]));
    genvar i;
    generate for (i=1; i<STAGES; i=i+1) begin: chain
        (* keep = 1, dont_touch = 1 *) sky130_fd_sc_hd__inv_1 ro_inv
            (.A(node[i-1]), .Y(node[i]));
    end endgenerate
    (* keep = 1, dont_touch = 1 *) sky130_fd_sc_hd__buf_1 ro_output
        (.A(node[STAGES-1]), .X(raw_out));
endmodule

module oscillator_bank(input wire enable, input wire [1:0] select, output wire raw_out);
    wire raw71, raw95, raw127;
    measurement_ring #(.STAGES(71)) ring71 (.enable(enable && select==0), .raw_out(raw71));
    measurement_ring #(.STAGES(95)) ring95 (.enable(enable && select==1), .raw_out(raw95));
    measurement_ring #(.STAGES(127)) ring127 (.enable(enable && select==2), .raw_out(raw127));
    assign raw_out = !enable ? 1'b0 : select==0 ? raw71 : select==1 ? raw95 : select==2 ? raw127 : 1'b0;
endmodule
