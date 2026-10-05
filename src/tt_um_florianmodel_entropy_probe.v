`default_nettype none
module tt_um_florianmodel_entropy_probe (
    input wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input wire ena, clk, rst_n
);
    wire [7:0] data;
    wire divided, sampled_bit, sample_valid, report_ready;
    resilient_probe probe (
        .clk(clk), .rst_n(rst_n), .enable(ena && ui_in[3]),
        .freeze_report(ui_in[4]), .addr(ui_in[2:0]), .data(data),
        .source_select(ui_in[7:6]), .test_select(uio_in[5:4]), .external_bit(uio_in[6]),
        .divided(divided), .sampled_bit(sampled_bit),
        .sample_valid(sample_valid), .report_ready(report_ready)
    );
    assign uo_out = ena ? data : 8'b0;
    assign uio_out = ena ? {4'b0, (divided && ui_in[5]),
                            report_ready, sample_valid, sampled_bit} : 8'b0;
    // Divided frequency diagnostic requires opt-in. Upper pins remain inputs.
    assign uio_oe = ena ? {4'b0, ui_in[5], 3'b111} : 8'b0;
    wire _unused = &{uio_in[7], uio_in[3:0], 1'b0};
endmodule
`default_nettype wire
