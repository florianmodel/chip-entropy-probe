`timescale 1ns/1ps
module physical_tb;
reg clk=0,rst_n=0,ena=1;reg [7:0] ui_in=0,uio_in=0;
wire [7:0] uo_out,uio_out,uio_oe;
supply1 VPWR;supply0 VGND;
tt_um_entropy_probe dut(.*);
task tick;begin #10;clk=1;#10;clk=0;#10;end endtask
task read_reg(input [2:0] addr,input [7:0] expected);
begin ui_in[2:0]=addr;#1;if(uo_out!==expected)$fatal(1,"Physical register %d: got %d expected %d",addr,uo_out,expected);end endtask
task testmode(input [1:0] mode);
begin rst_n=0;tick;rst_n=1;ui_in=8'hc8;uio_in[5:4]=mode;tick;repeat(258)tick;end endtask
integer i,f;
initial begin
 tick;rst_n=1;read_reg(7,2);
 testmode(0);read_reg(2,0);read_reg(3,24);read_reg(4,0);
 testmode(1);read_reg(2,0);read_reg(3,27);read_reg(4,0);
 testmode(2);read_reg(2,128);read_reg(3,28);read_reg(4,255);
 uio_in[6]=1;testmode(3);read_reg(3,31);
 ui_in[4]=1;repeat(600)tick;read_reg(1,1);
 ena=0;tick;if(uio_oe!==0||uio_out!==0||uo_out!==0)$fatal(1,"Physical deselection");ena=1;
 // Same pre-edge sample+valid pairs as the finite PIO capture, clocked regularly.
 rst_n=0;tick;rst_n=1;ui_in=8'hc8;uio_in[5:4]=2;tick;
 f=$fopen("build/tt-rtl/physical-capture.txt","w");
 for(i=0;i<4112;i=i+1)begin
  if(^uio_out[1:0]===1'bx)$fatal(1,"Capture X");
  $fwrite(f,"%0d\n",uio_out[1:0]);tick;
 end
 $fclose(f);
 $display("PASS: complete routed functional netlist, test modes, reports and capture pairs");$finish;
end endmodule
