module main (
	//interface to FTDI during teathered setup - slave SPI
	FTDI_cfg_cs, FTDI_mosi, FTDI_miso, FTDI_sck, 

	//interface to UWB radio, for transmitting data - master SPI
	UWB_CS, UWB_MOSI, UWB_MISO, UWB_SCK, 

	//four phase control of micromirror
	Xp, Xn, Yp, Yn,

	//interface to ADC: FPGA provides a clock, conversions come in on an 8-bit data bus
	ADC_data, ADC_clk,

	//pwm driver for setting APD bias:
	APD_pwm
	);

	//definitions for module connections
	input wire FTDI_cfg_cs, FTDI_mosi, FTDI_sck, UWB_MISO;
	output wire UWB_CS, UWB_MOSI, UWB_SCK, FTDI_miso;
	output wire Xp, Xn, Yp, Yn;
	input wire [7:0] ADC_data;
	output wire ADC_clk;
	output wire APD_pwm;

	wire FTDI_UWB_cs;
	assign FTDI_UWB_cs = 1; //for now, set to 1, which i.e. disable

	//clocks: internal oscillator and PLL are used to generate clocks at several frequencies (denoted in MHz)
	wire clk24, clk6, clk3;
	clocks the_clocks(clk3, clk6, clk24);


	//=============================================================================================================
	//SPI slave:  4-byte transfers. Byte 1 is command, byte 2 is address, byte 3-4 is data.
	wire [7:0] sl_command, sl_addr; //sl, to indicate association with slave SPI
	wire [15:0] sl_data;
	reg [31:0] sl_response;
	wire cfg_mosi; //output back to FTDI, not always connected - must be mux'd 
	SPI_serializer #(4, 5) cfg_slave(FTDI_cfg_cs, FTDI_miso, cfg_mosi, FTDI_sck, {sl_cmd, sl_addr, sl_data}, sl_response);

	//regular slave SPI: ==========================================================================================	
	//bank of config registers:
	reg [15:0] cfg_regs [15:0];

	//map config regs to their purposes:
	assign periodX = cfg_regs[0];
	assign periodY = cfg_regs[1];
	assign APD_pwm_period = cfg_regs[2][7:0];
	assign APD_pwm_duty = cfg_regs[3][7:0];
	assign SPImaster_enable = cfg_regs[4][0]; //turns UWB data writing on and off, so that it can be bypassed for initial config

	always @ (posedge FTDI_cfg_cs) begin //actions for config SPI
		case (sl_cmd)
			0:  sl_response <= {sl_cmd, sl_addr, sl_data}; //readback
			1:	cfg_regs[sl_addr] <= sl_data; //write to register
			2:  sl_response <= cfg_regs[sl_addr]; //cfg reg readback
		endcase
	end

	// simple peripheral module instantiations ===============================================================
	
	// pwm gen to drive APD bias:
	pwm_gen APD_bias(clk6, APD_pwm, APD_pwm_period, APD_pwm_duty);

	//mirror drive pattern generator:
	wire [15:0] timerX, timerY; //module outputs for phase stamping data
	wire [15:0] periodX, periodY; //frequency settings from configuration SPI
	mirror_driver md(clk6, Xp, Xn, Yp, Yn, timerX, timerY, periodX, periodY);


	//data-streaming module instantiations===============================================================
	//each module (mostly) adheres to data ready / data valid protocols for communication interfaces

	//SPI master.  Accepts bytes 1 at a time to transfer, and bytes are recieved one at a time
	wire [7:0] master_tx_data, master_rx_data; //data to be transmitted, and data just recieved, respectively
	wire master_rx_valid; //indicates when the master_rx_data is actual data 
	wire master_CS, master_MOSI, master_SCK; //SPI interface. conditionally passes thru to UWB SPI
	SPI_master master(master_tx_data, master_rx_data, master_rx_valid, clk24, clk3, master_CS, master_MOSI, UWB_MISO, master_SCK);
	
	wire [7:0] prog_to_spi, prog_from_spi, prog_data_from_FIFO;
	wire prog_FIFO_ready, prog_FIFO_valid; // ready/valid signals to grab data from the data FIFO
	uwb_data_writer prog(clk3, enable, prog_to_spi, prog_from_spi, prog_data_from_FIFO, prog_FIFO_ready, prog_FIFO_valid);
	
	//compound FIFO:  main input FIFO on a fast clock, and then a small async FIFO to match slow output clock.  'int' wires are the internal interface between these two FIFOs
	wire [7:0] compressed_IN_DATA, compressed_int_DATA, compressed_OUT_DATA;
	wire compressed_IN_VALID, compressed_IN_READY, compressed_int_VALID, compressed_int_READY, compressed_OUT_VALID, compressed_OUT_READY;
	FIFO #(8192, 13) compressed_main(clk6, clk6, compressed_IN_DATA, compressed_IN_VALID, compressed_IN_READY, compressed_int_DATA, compressed_int_VALID, compressed_int_READY);
	FIFO #(8, 3) compressed_async(clk6, clk3, compressed_int_DATA, compressed_int_VALID, compressed_int_READY, compressed_OUT_DATA, compressed_OUT_VALID, compressed_OUT_READY);

	wire [15:0] timerX, timerY;
	mirror_driver md(clk6,Xp,Xn,Yp,Yn,timerX,timerY,periodX,periodY);

	wire [7:0] fpg_data;
	wire fpg_valid, fpg_ready;
	fake_packet_gen fpg(clk6, fpg_data, fpg_valid, fpg_ready, timerX, timerY);

	//SPI connections - UWB to master, slave, and FTDI
	assign UWB_CS = FTDI_UWB_cs && master_CS; //either one pulls low
	assign UWB_SCK = (~FTDI_UWB_cs && FTDI_sck)  || (~master_CS && master_SCK);  //or of gated clocks
	assign UWB_MOSI = (~FTDI_UWB_cs && FTDI_mosi)  || (~master_CS && master_MOSI); //or of gated MOSI
	assign FTDI_miso = (~FTDI_UWB_cs && UWB_MISO)  || (~FTDI_cfg_cs && cfg_mosi); //decides which slave drives MISO

	//connect SPI master to its controlling progam:
	assign master_tx_data = prog_to_spi;
	assign prog_from_spi = master_rx_data;
	
	//connect the actual data stream FIFO to the data writer program:
	assign prog_data_from_FIFO = compressed_OUT_DATA;
	assign prog_FIFO_valid = compressed_OUT_VALID;
	assign compressed_OUT_READY = prog_FIFO_ready;

	//connect FPG data to data FIFO:
	assign compressed_IN_DATA = fpg_data;
	assign compressed_IN_VALID = fpg_valid;
	assign fpg_ready = compressed_IN_READY;

endmodule

module uwb_data_writer(
	input wire clk, 
	input wire enable, //stops UWB writer to hand control over to a different SPI master
	output reg [7:0] to_spi, //bytes to transmit over SPI
	input wire [7:0] from_spi, //response recieved from SPI slave
	input wire [7:0] data_from_FIFO, //data that needs to be sent over the SPI interface
	output wire FIFO_ready, //active high indicates that this module (UWB writer) is ready to accept data
	input wire FIFO_valid //data is only available to write to the UWB if this is asserted
	);
	


	//module program: 
	//check tx_buffer space.  
	//If zero or 64 bytes used, push a 64 byte payload; then, transmit. 
	//If 128 bytes used, just transmit.  
	//(not sure if all this is quite needed - not sure if transmit command is a success every time)

	reg [7:0] PC; //kinda a program counter
	initial PC <= 195; //start the PC here

	reg [7:0] ndata;  //temporary storage of info which determines program branches

	//misc flags!
	assign FIFO_ready = (PC[7:6] == 1);//data transfers when program counter is in this range

	always @(posedge clk) begin
	
		//to_spi and from_spi program operations
		casez (PC)
			1: to_spi <= 2; //start a two-byte transfer
			2: to_spi <= 2; //command for reading usage of uwb tx buffer
			5: ndata <= from_spi; //read uwb tx buffer usage response

			20: to_spi <= 2; //start a two-byte transfer
			21: to_spi <= 31+64; //command for writing to control register
			22: to_spi <= 16; //set control register to trigger a transmission

			56: to_spi <= 2; //start a two-byte transfer
			57: to_spi <= 31+64; //command for writing to control register 0x1F
			58: to_spi <= 16; //set control register to trigger a transmission

			8'b00111110: to_spi <= 65; //a 65 byte transfer: control byte plus data
			8'b00111111: to_spi <= 63+64+128; //burst write command
			8'b01??????: to_spi <= data_from_FIFO; //burst write data

			default: to_spi <= 0;
		endcase

		//program counter control
		case (PC)
			//flow control: first thing is to check if user commands need to be processed
			0: PC <= (enable) ? 1 : 0; //only progress if enabled

			//flow control after reading ndata: do nothing, send a tx command, or load data and send a tx command
			6: PC <= (ndata <= 64 && FIFO_valid) ? 60 : 7;  //if there is space in the buffer and not enough data to transmit, just load data right away;  
			7: PC <= (ndata == 64 && FIFO_valid) ? 55 : 8; //send a tx command, then write data
			8: PC <= (ndata > 64) ? 19 : 9; //if the tx buffer is full, only send a tx command
			9: PC <= 0; //if no conditions are met, loop around and try again

			//end-of-subroutine returns
			25: PC <= 0; //loop back after a tx-command only operation
			132: PC <= 0; //loop back after finishing a bulk write
			default: PC <= PC + 1;
		endcase
	end
endmodule

module fake_packet_gen(clk, data_out, valid, ready, timerX, timerY);
	input wire clk, ready;
	output wire valid;
	output reg [7:0] data_out;
	input wire [15:0] timerX, timerY;


	reg [13:0] counter;
	wire [5:0] byte_counter; //which byte in each packet
	wire [7:0] packet_counter; //counts which packet we are making
	assign byte_counter = counter[5:0];
	assign packet_counter = counter[13:6];

	initial counter <= 0;

	always @(*) begin
		case (byte_counter)
			0: data_out = timerX[15:8];
			1: data_out = timerX[7:0];
			2: data_out = timerY[15:8];
			3: data_out = timerY[7:0];
			default: data_out = byte_counter;
		endcase
	end
	
	assign valid = (counter[7:6] == 0) ? 1 : 0;//valid only 1 half of the time

	always @(posedge clk) counter <= counter + 1;
endmodule

module pwm_gen(
	input wire clk,
	output wire out,
	input wire [7:0] total_period,
	input wire [7:0] high_period
	);
	// by specifying both the total period and the high period,
	// many more levels are acheivable without sacraficing frequency

	reg [7:0] counter;

	assign out = (counter > high_period) ? 0 : 1;

	always @(posedge clk)
		if (counter == high_period) counter <= 0;
		else counter <= counter + 1;
endmodule

module mirror_driver(
	clk,
	Xp, Xn, Yp, Yn, //control signals to mirror
	timerX, timerY,  //output state of timers to be encoded into data stream
	periodX, periodY //period settings
	);

	input wire [15:0] periodY, periodX;

	input wire clk;
	output wire Xp, Xn, Yp, Yn;

	output reg [15:0] timerX, timerY;

	//conditionally wire output drives based on timer values
	assign Xp = (timerX > periodX/2) ? 1:0;
	assign Xn = (timerX > periodX/2) ? 0:1;
	assign Yp = (timerY > periodY/2) ? 1:0;
	assign Yn = (timerY > periodY/2) ? 0:1;

	initial begin
		timerX = 0;
		timerY = 0;
	end

	//two timers with slightly different periods, to create beat frequency (scanning frame rate)
	always @ (posedge clk) begin
		
		if (timerX == periodX) timerX <= 0; //period of timerX
		else timerX <= timerX + 1;

		if (timerY == periodY) timerY <= 0; //period of timerY
		else timerY <= timerY + 1;
	end
endmodule