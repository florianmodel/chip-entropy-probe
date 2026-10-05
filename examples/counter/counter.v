module counter (
    input wire clk,
    input wire rst_n,
    input wire enable,
    output reg [7:0] count
);
    always @(posedge clk) begin
        if (!rst_n)
            count <= 8'b0;
        else if (enable)
            count <= count + 8'd1;
    end
endmodule
