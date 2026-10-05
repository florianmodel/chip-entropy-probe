`timescale 1ns/1ps
module divider_tb;
reg raw_clock=0,reset_n=0;wire divided;
frequency_divider dut(.*);
integer i;initial begin
#1;reset_n=1;#1;reset_n=0;#1;
if(divided!==0)$fatal(1,"Divider reset");reset_n=1;
for(i=1;i<=4096;i=i+1)begin
#5;raw_clock=1;#5;raw_clock=0;#5;
// Cascaded positive-edge ripple flops cause an initial ripple on pulse 1.
if(divided !== (((i-1)/512)%2==0))$fatal(1,"Divide phase at %d",i);
end
reset_n=0;#5;if(divided!==0)$fatal(1,"Reset after activity");
$display("PASS: /1024 frequency and asynchronous divider reset");$finish;
end endmodule
