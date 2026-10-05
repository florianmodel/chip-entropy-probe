module entropy_probe (
    input wire clk, rst_n, enable, freeze_report,
    input wire [2:0] addr,
    output wire [7:0] data,
    output wire raw_out, sampled_bit, sample_valid, report_ready
);
    ring_oscillator osc (.enable(enable && rst_n), .raw_out(raw_out));
    entropy_monitor monitor (
        .clk(clk), .rst_n(rst_n), .enable(enable), .freeze_report(freeze_report),
        .raw_in(raw_out), .addr(addr), .data(data), .sampled_bit(sampled_bit),
        .sample_valid(sample_valid), .report_ready(report_ready)
    );
endmodule
