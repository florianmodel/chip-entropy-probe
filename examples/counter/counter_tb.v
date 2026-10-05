`timescale 1ns/1ps
module counter_tb;
    reg clk = 0;
    reg rst_n = 0;
    reg enable = 0;
    wire [7:0] count;
    integer expected = 0;
    integer i;
    counter dut (.clk(clk), .rst_n(rst_n), .enable(enable), .count(count));
    always #5 clk = ~clk;
    task tick;
        begin
            @(posedge clk);
            if (!rst_n) expected = 0;
            else if (enable) expected = (expected + 1) % 256;
            #1;
            if (count !== expected[7:0]) $fatal(1, "count mismatch: got %d expected %d", count, expected);
            @(negedge clk);
        end
    endtask
    initial begin
        tick();
        rst_n = 1;
        enable = 1;
        for (i = 0; i < 260; i = i + 1) tick();
        enable = 0;
        repeat (5) tick();
        rst_n = 0;
        tick();
        rst_n = 1;
        enable = 1;
        repeat (3) tick();
        $display("PASS: reset, increment, wraparound, hold, reset again and restart");
        $finish;
    end
endmodule
