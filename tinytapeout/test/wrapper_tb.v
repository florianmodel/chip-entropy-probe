`timescale 1ns/1ps
// Deterministic stand-in; this makes no claim about physical entropy.
module oscillator_bank(input wire [2:0] enable,output wire raw_out);
 reg stimulus=0;
 integer rises=0,falls=0;
 realtime last_fall=0,min_off=1e9;
 always @(enable) if(enable!==0 && enable!==3'b001 && enable!==3'b010 && enable!==3'b100) $fatal(1,"Ring enables not one-hot: %b",enable);
 always @(posedge (|enable)) begin rises=rises+1; if($realtime-last_fall<min_off) min_off=$realtime-last_fall; end
 always @(negedge (|enable)) begin falls=falls+1; last_fall=$realtime; end
 assign raw_out=(|enable) ? stimulus : 0;
endmodule
module wrapper_tb;
 reg clk=0,rst_n=0,ena=1;
 reg [7:0] ui_in=0,uio_in=0;
 wire [7:0] uo_out,uio_out,uio_oe;
 tt_um_entropy_probe dut(.*);
 task tick;
 begin
 #5;clk=1;#5;clk=0;#5;
 if(uio_oe !== (ena ? (ui_in[5]?8'h0f:8'h07):0)) $fatal(1,"Output enable");
 if(uio_out[7:4]!==0) $fatal(1,"Reserved output");
 if(!ena && (uo_out!==0 || uio_out!==0)) $fatal(1,"Deselection");
 end endtask
 task read_reg(input [2:0] address,input [7:0] expected);
 begin ui_in[2:0]=address;#1;
 if(uo_out!==expected) $fatal(1,"Register %0d got %0d expected %0d",address,uo_out,expected);
 end endtask
 task mode(input [1:0] source,input [1:0] testmode);
 begin
 ui_in[7:6]=source;uio_in[5:4]=testmode;#1;
 if(uio_out[1]!==0) $fatal(1,"Mode change must invalidate immediately");
 tick; read_reg(6,0);repeat(source==3 ? 258 : 259)tick;
 end endtask
 integer i;
 initial begin
 tick;rst_n=1;read_reg(7,2);
 ui_in[3]=1; mode(3,0);
 read_reg(1,1);read_reg(2,0);read_reg(3,24);read_reg(4,0);
 mode(3,1);read_reg(1,2);read_reg(2,0);read_reg(3,27);read_reg(4,0);
 mode(3,2);read_reg(1,3);read_reg(2,128);read_reg(3,28);read_reg(4,255);
 uio_in[6]=1;mode(3,3);read_reg(1,4);read_reg(3,31);
 ui_in[4]=1; repeat(600)tick;read_reg(1,4);read_reg(3,31);
 ui_in[4]=0;repeat(256)tick;read_reg(1,5);
 // Changing physical source length also aborts partial windows.
 for(i=0;i<3;i=i+1)begin
 dut.probe.bank.stimulus=i%2;mode(i,0);
 read_reg(3, (i<<3) | (i%2));
 end
 // Glitches between clock edges on selection and test pins must not touch a running ring.
 mode(0,0);i=dut.probe.bank.rises;
 if(dut.probe.bank.enable!==3'b001) $fatal(1,"Ring 0 not running");
 #1;uio_in[5:4]=2;#1;uio_in[5:4]=0;ui_in[7:6]=1;#1;ui_in[7:6]=0;#1;ui_in[3]=0;#1;ui_in[3]=1;tick;
 if(dut.probe.bank.rises!==i || dut.probe.bank.enable!==3'b001) $fatal(1,"Pin glitch restarted ring");
 // A sustained test-mode pin change aborts the window but leaves the ring running.
 uio_in[5:4]=1;repeat(3)tick;
 if(dut.probe.bank.rises!==i || dut.probe.bank.enable!==3'b001) $fatal(1,"Test pins restarted ring");
 uio_in[5:4]=0;repeat(3)tick;
 // A selection change leaves all rings off for at least one clock period (15 ns here).
 dut.probe.bank.min_off=1e9;ui_in[7:6]=2;repeat(3)tick;
 if(dut.probe.bank.enable!==3'b100 || dut.probe.bank.min_off<15) $fatal(1,"Switch off time %0t",dut.probe.bank.min_off);
 // ena and rst_n stop the ring immediately, without a clock edge.
 ena=0;#1;if(dut.probe.bank.enable!==0) $fatal(1,"ena must stop ring without clock");ena=1;repeat(3)tick;
 rst_n=0;#1;if(dut.probe.bank.enable!==0) $fatal(1,"rst_n must stop ring without clock");tick;rst_n=1;ui_in[7:6]=0;repeat(3)tick;
 ena=0;repeat(3)tick;ena=1;ui_in[3]=0;tick;
 if(uio_out[1:0]!==0) $fatal(1,"Disabled sample validity");
 rst_n=0;tick;rst_n=1;read_reg(1,0);
 $display("PASS: registered ring enables, source changes, test modes, report provenance, reset, freeze and TT pins");$finish;
 end
endmodule
