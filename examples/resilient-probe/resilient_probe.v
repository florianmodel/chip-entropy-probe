module resilient_probe (
    input wire clk, rst_n, enable, freeze_report, external_bit,
    input wire [1:0] source_select, test_select,
    input wire [2:0] addr,
    output wire [7:0] data,
    output wire divided, sampled_bit, sample_valid, report_ready
);
    reg [3:0] configuration;
    reg alternate;
    wire [3:0] requested = {source_select, test_select};
    // Any configuration change invalidates acquisition and aborts its partial
    // window on the next clock edge. Completed reports retain their provenance.
    wire active = enable && rst_n && configuration == requested;
    wire ring_active = active && configuration[3:2] != 3;
    wire ring_wave;
    wire test_wave = configuration[1:0]==0 ? 1'b0 : configuration[1:0]==1 ? 1'b1 :
                     configuration[1:0]==2 ? alternate : external_bit;
    wire source_wave = configuration[3:2]==3 ? test_wave : ring_wave;
    always @(posedge clk) begin
        if (!rst_n) begin configuration <= 0; alternate <= 0; end
        else begin configuration <= requested; alternate <= !alternate; end
    end
    oscillator_bank bank (.enable(ring_active), .select(configuration[3:2]), .raw_out(ring_wave));
    frequency_divider divider (.raw_clock(ring_wave), .reset_n(ring_active), .divided(divided));
    measurement_monitor monitor (
        .clk(clk), .rst_n(rst_n), .enable(active), .freeze_report(freeze_report),
        .raw_in(source_wave), .configuration(configuration), .addr(addr), .data(data),
        .sampled_bit(sampled_bit), .sample_valid(sample_valid), .report_ready(report_ready)
    );
endmodule
