// Measurement logic only. No entropy estimate, conditioning or security claim.
module entropy_monitor (
    input wire clk, rst_n, enable, freeze_report, raw_in,
    input wire [2:0] addr,
    output reg [7:0] data,
    output wire sampled_bit, sample_valid,
    output reg report_ready
);
    // Keep the first stage's fanout restricted to the second stage.
    (* async_reg = "true", keep = 1 *) reg sync_meta, sync_sample;
    reg [1:0] warmup;
    reg [7:0] progress, generation;
    reg [8:0] ones, transitions, report_ones, report_transitions;
    reg previous;
    wire [8:0] next_ones = ones + {8'b0, sync_sample};
    wire [8:0] next_transitions = transitions +
        {8'b0, ((progress != 0) && (sync_sample != previous))};

    assign sample_valid = rst_n && enable && warmup[1];
    assign sampled_bit = sample_valid && sync_sample;

    // No reset/enable mux between the synchronizer stages. Validity masks
    // startup data until two enabled clock edges have filled the pipeline.
    always @(posedge clk) begin
        sync_meta <= raw_in;
        sync_sample <= sync_meta;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            warmup <= 0;
            progress <= 0; generation <= 0; ones <= 0; transitions <= 0;
            report_ones <= 0; report_transitions <= 0; previous <= 0;
            report_ready <= 0;
        end else if (!enable) begin
            warmup <= 0;
            progress <= 0; ones <= 0; transitions <= 0; previous <= 0;
            // Keep the last completed report when acquisition is disabled.
        end else begin
            warmup <= {warmup[0], 1'b1};
            if (warmup[1]) begin
                previous <= sync_sample;
                if (progress == 8'hff) begin
                    progress <= 0; ones <= 0; transitions <= 0;
                    if (!freeze_report) begin
                        report_ones <= next_ones;
                        report_transitions <= next_transitions;
                        generation <= generation + 8'd1;
                        report_ready <= 1;
                    end
                end else begin
                    progress <= progress + 8'd1;
                    ones <= next_ones;
                    transitions <= next_transitions;
                end
            end
        end
    end

    always @* begin
        case (addr)
            3'd0: data = {3'b0, (report_ready && report_transitions == 0),
                          freeze_report, enable, report_ready, sample_valid};
            3'd1: data = generation;
            3'd2: data = report_ones[7:0];
            3'd3: data = {7'b0, report_ones[8]};
            3'd4: data = report_transitions[7:0];
            3'd5: data = {7'b0, report_transitions[8]};
            3'd6: data = progress;
            3'd7: data = 8'h01; // Interface version.
        endcase
    end
endmodule
