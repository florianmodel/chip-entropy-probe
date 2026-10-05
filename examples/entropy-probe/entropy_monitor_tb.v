`timescale 1ns/1ps
module entropy_monitor_tb;
    reg clk = 0, rst_n = 0, enable = 0, freeze_report = 0, raw_in = 0;
    reg [2:0] addr = 0;
    wire [7:0] data;
    wire sampled_bit, sample_valid, report_ready;
    entropy_monitor dut (.*);

    reg history [0:69999];
    integer clocks = 0, generation = 0, saved_ones = 0, saved_transitions = 0;
    integer measured, start_index, ones_count, transitions_count, j, k;
    reg ready = 0;
    reg [7:0] expected;

    task tick(input reg value);
        begin
            clk = 0; raw_in = value;
            #5;
            if (!rst_n) begin
                clocks = 0; generation = 0; saved_ones = 0;
                saved_transitions = 0; ready = 0;
            end else if (!enable) begin
                clocks = 0;
            end else begin
                history[clocks] = value;
                clocks = clocks + 1;
                measured = clocks - 2;
                if (measured > 0 && measured % 256 == 0 && !freeze_report) begin
                    // Reference counts directly from the supplied input sequence.
                    start_index = measured - 256;
                    ones_count = 0; transitions_count = 0;
                    for (j = start_index; j < measured; j = j + 1) begin
                        if (history[j]) ones_count = ones_count + 1;
                        if (j > start_index && history[j] != history[j-1])
                            transitions_count = transitions_count + 1;
                    end
                    saved_ones = ones_count;
                    saved_transitions = transitions_count;
                    generation = (generation + 1) % 256;
                    ready = 1;
                end
            end
            clk = 1; #1;
            if (sample_valid !== (rst_n && enable && clocks >= 2))
                $fatal(1, "Sample validity/warmup mismatch");
            if (sampled_bit !== ((rst_n && enable && clocks >= 2) ? history[clocks-2] : 1'b0))
                $fatal(1, "Sample pipeline mismatch at clock %0d", clocks);
            if (report_ready !== ready) $fatal(1, "Ready mismatch");
            for (k = 0; k < 8; k = k + 1) begin
                addr = k[2:0]; #0.1;
                case (k)
                    0: expected = {3'b0, (ready && saved_transitions == 0),
                                   freeze_report, enable, ready, sample_valid};
                    1: expected = generation[7:0];
                    2: expected = saved_ones[7:0];
                    3: expected = {7'b0, saved_ones[8]};
                    4: expected = saved_transitions[7:0];
                    5: expected = {7'b0, saved_transitions[8]};
                    6: expected = clocks > 2 ? (clocks-2) % 256 : 0;
                    7: expected = 1;
                endcase
                if (data !== expected)
                    $fatal(1, "Register %0d mismatch at clock %0d: got %0d expected %0d", k, clocks, data, expected);
            end
            #8.2; clk = 0; #5;
        end
    endtask

    integer i;
    initial begin
        tick(0); rst_n = 1;
        repeat (3) tick(1); // Disabled source must not fill the pipeline.
        enable = 1;
        repeat (514) tick(0); // Zero windows and no boundary transition.
        repeat (514) tick(1); // Includes a full 256-one window (nine-bit count).
        for (i = 0; i < 1024; i = i + 1) tick(i % 2 != 0);
        freeze_report = 1;
        for (i = 0; i < 600; i = i + 1) tick(i % 7 < 3);
        freeze_report = 0;
        for (i = 0; i < 700; i = i + 1) tick(i % 11 == 0);
        enable = 0; repeat (5) tick(0); // Abort partial window; retain report.
        enable = 1; repeat (600) tick(1);
        rst_n = 0; tick(1); rst_n = 1;
        repeat (66000) tick(1); // Exercise report generation wraparound.
        if (generation != 1) $fatal(1, "Generation wrap coverage failed");
        $display("PASS: pipeline, windows, 9-bit counts, transitions, freeze, disable, reset and generation wrap");
        $finish;
    end
endmodule
