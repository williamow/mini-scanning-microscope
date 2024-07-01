module clocks(output reg clk2, output reg clk16);

	wire hfosc_clock;
	SB_HFOSC #(.CLKHF_DIV("0b00")) hfosc ( //0b00 for full 48 MHz operation, 0b01 for 24 MHz operation
	  .CLKHFPU(1'b1),
	  .CLKHFEN(1'b1),
	  .CLKHF(hfosc_clock)
	);

	//pll down to 32 MHz, which then drives the divider:
	wire clk32, locked;
	//f_out = f_in * (DIVF+1) / (2^DIVQ)
	SB_PLL40_CORE #(
		.FEEDBACK_PATH("SIMPLE"),
		.DIVR(4'b0010),		// DIVR =  2
		.DIVF(7'b0111111),	// DIVF = 63
		.DIVQ(3'b101),		// DIVQ =  5
		.FILTER_RANGE(3'b001)	// FILTER_RANGE = 1
	) uut (
		.LOCK(locked),
		.RESETB(1'b1),
		.BYPASS(1'b0),
		.REFERENCECLK(hfosc_clock),
		.PLLOUTCORE(clk32)
		);

	reg [7:0] divider;
	always @ (posedge clk32) begin 
		divider <= divider+1;
		clk2 <= divider[3];
		clk16 <= divider[0];
	end

endmodule

// module clocks(output reg clk3, output reg clk6, output reg clk24);

// 	wire hfosc_clock;
// 	SB_HFOSC #(.CLKHF_DIV("0b00")) hfosc ( //0b00 for full 48 MHz operation, 0b01 for 24 MHz operation
// 	  .CLKHFPU(1'b1),
// 	  .CLKHFEN(1'b1),
// 	  .CLKHF(hfosc_clock)
// 	);

// 	//even though we could get clock 24 directly, this way they have better phase alignment (I think?)
// 	reg [7:0] divider;
// 	always @ (posedge hfosc_clock) begin 
// 		divider <= divider+1;
// 		clk3 <= divider[3];
// 		clk6 <= divider[2];
// 		clk24 <= divider[0];
// 	end

// endmodule

// module FIFO_raw #(parameter depth=2048, parameter addr_bits=11) (input wire in_clk, input wire out_clock, input wire [7:0] IN_DATA, input wire IN_VALID, output wire IN_READY, output wire [7:0] OUT_DATA, output wire OUT_VALID, input wire OUT_READY);
// 	//FIFO made from implicit BRAM.
// 	//Input and output are on different clocks, allowing the FIFO to function as an asynchronous interface.  However if async, does not use BRAM.

// 	reg [addr_bits-1:0] wr_ptr;
// 	reg [addr_bits-1:0] rd_ptr;

// 	reg [7:0] mem[depth-1:0];

// 	assign IN_READY = ~(rd_ptr == wr_ptr+1);
// 	assign OUT_VALID = ~(rd_ptr == wr_ptr);
// 	assign OUT_DATA = mem[rd_ptr];

// 	always @ (posedge in_clk) begin
// 		if (IN_VALID && IN_READY) begin
// 			mem[wr_ptr] <= IN_DATA;
// 			wr_ptr <= wr_ptr + 1;
// 		end
// 	end

// 	always @ (posedge out_clock) begin
// 		if (OUT_VALID && OUT_READY) begin
// 			rd_ptr <= rd_ptr + 1;
// 		end
// 	end
// endmodule

module FIFO #(parameter depth=2048, parameter width=8, parameter addr_bits=11) (
	input wire in_clk, 
	input wire out_clock, 
	input wire [width-1:0] IN_DATA, 
	input wire IN_VALID, 
	output wire IN_READY, 
	output wire [width-1:0] OUT_DATA, 
	output wire OUT_VALID, 
	input wire OUT_READY);
	//FIFO made from implicit BRAM.
	//Input and output are on different clocks, allowing the FIFO to function as an asynchronous interface.  However if async, does not use BRAM.

	reg [addr_bits-1:0] wr_ptr;
	reg [addr_bits-1:0] rd_ptr;

	reg [width-1:0] mem[depth-1:0];

	assign IN_READY = ~(rd_ptr == wr_ptr+1);
	assign OUT_VALID = ~(rd_ptr == wr_ptr);
	assign OUT_DATA = mem[rd_ptr];

	always @ (posedge in_clk) begin
		if (IN_VALID && IN_READY) begin
			mem[wr_ptr] <= IN_DATA;
			wr_ptr <= wr_ptr + 1;
		end
	end

	always @ (posedge out_clock) begin
		if (OUT_VALID && OUT_READY) begin
			rd_ptr <= rd_ptr + 1;
		end
	end
endmodule

module SPI_master(tx_data, rx_data, rx_valid, clk_fast, clk_slow, CS, MOSI, MISO, SCK);
	//SR10x0 samples our data on rising edge of SCK, which is negative edge of clk48;
	//we sample SR10x0 data on falling edge of SCK, i.e. positive edge of clk48.  Since SR10x0 recieves SCK after the FPGA does, we should still see the old value.
	reg [7:0] tx_count;
	reg [6:0] tx_databuf;
	reg [7:0] rx_databuf;
	wire [7:0] tx_interface;
	assign tx_interface = {tx_data[7], tx_databuf};  //MSB is first to be shifted out, so we assign it directly instead of through the buffer
	assign rx_data = {rx_databuf[6:0], MISO}; //LSB is last to be read; therefore it is sent directly to the output byte interface
	input wire clk_slow, clk_fast, MISO;
	input wire [7:0] tx_data; //provides phase information between clk48 and clk6
	output wire [7:0] rx_data;
	output reg CS;
	output wire SCK, rx_valid, MOSI;
	// assign SCK = (SCK_phase1 == SCK_phase2) && (~CS);
	assign SCK = (clk_fast) && (~CS);

	always @ (posedge clk_slow) begin
		if (tx_count == 0) begin
			tx_count <= tx_data;
			CS <= 1; //chip select not active this cycle
		end
		else begin
			tx_count <= tx_count - 1;
			CS <= 0; //chip select active
			tx_databuf <= tx_data[6:0];
		end
	end

	assign rx_valid = ~CS;

	reg [2:0] tx_index;
	assign MOSI = tx_interface[tx_index];

	always @ (posedge clk_fast) begin
		if (CS) tx_index <= 7;
		else tx_index <= tx_index - 1;
	end

	always @ (negedge clk_fast) rx_databuf <= {rx_databuf[6:0], MISO}; //make it a shift register, not an addressed thing
endmodule

// module SPI_slave_to_FIFO(clk, tx_data, tx_valid, tx_ready, rx_data, rx_valid, rx_ready, CS, MOSI, MISO, SCK);
// 	//SPI slave is quite different than SPI master, since we need to respect the master's clock - needs an async interface
// 	//this SPI slave reads and writes to FIFO buffers.  If first byte is 0, write (this modules recieves); if first byte is 255, read (this module sends).

// 	//Maybe in the future, provide options to set the SPI mode.  For now, posedge clock sampling
// 	//MSB first
// 	input wire clk, tx_valid, rx_ready, CS, MOSI, SCK;
// 	input wire [7:0] tx_data;
// 	output wire rx_valid, tx_ready, MISO;
// 	output wire [7:0] rx_data;

// 	reg [2:0] bit_counter;
// 	reg [7:0] rx_buffer;
// 	reg [1:0] mode; //0: recieving first byte; 1: recieving data mode; 2: transmitting data mode
// 	wire [7:0] rx_word;
// 	assign rx_word = {rx_buffer[7:1], MOSI};
// 	wire end_of_byte;
// 	assign end_of_byte = (bit_counter == 7) && !CS;

// 	always @(posedge SCK, posedge CS) begin
// 		if (CS) begin
// 			bit_counter <= 0;
// 			mode <= 0;
// 		end
// 		else begin
// 			bit_counter <= bit_counter + 1;
// 			rx_buffer[7-bit_counter] <= MOSI;

// 			//transition between modes
// 			if (end_of_byte && mode == 0 && rx_word == 0) mode <= 1;
// 			if (end_of_byte && mode == 0 && rx_word == 255) mode <= 2;
// 		end

// 	end

	//since these FIFOs use a different clock for output and input, they are not placed as block ram; therefore they must be quite small to fit on chip.

// 	wire [7:0] rx_FIFO_IN_DATA, rx_FIFO_OUT_DATA;
// 	wire rx_FIFO_IN_VALID, rx_FIFO_IN_READY, rx_FIFO_OUT_VALID, rx_FIFO_OUT_READY;
// 	FIFO #(16, 4) rx_FIFO(SCK, clk, rx_FIFO_IN_DATA, rx_FIFO_IN_VALID, rx_FIFO_IN_READY, rx_FIFO_OUT_DATA, rx_FIFO_OUT_VALID, rx_FIFO_OUT_READY);
// 	//connect output of recieve FIFO to output data:
// 	assign rx_data = rx_FIFO_OUT_DATA;
// 	assign rx_valid = rx_FIFO_OUT_VALID;
// 	assign rx_FIFO_OUT_READY = rx_ready;
// 	//connect input of recieve FIFO to the recieved data:
// 	assign rx_FIFO_IN_DATA = rx_word;
// 	assign rx_FIFO_IN_VALID = end_of_byte && mode == 1;
// 	// assign ? = rx_FIFO_IN_READY;  //assume FIFO is ready;  otherwise, too bad.

// 	wire [7:0] tx_FIFO_IN_DATA, tx_FIFO_OUT_DATA;
// 	wire tx_FIFO_IN_VALID, tx_FIFO_IN_READY, tx_FIFO_OUT_VALID, tx_FIFO_OUT_READY;
// 	FIFO #(16, 4) tx_FIFO(clk, SCK, tx_FIFO_IN_DATA, tx_FIFO_IN_VALID, tx_FIFO_IN_READY, tx_FIFO_OUT_DATA, tx_FIFO_OUT_VALID, tx_FIFO_OUT_READY);
// 	//connect input of transmit FIFO to input data:
// 	assign tx_FIFO_IN_DATA = tx_data;
// 	assign tx_FIFO_IN_VALID = tx_valid;
// 	assign tx_ready = tx_FIFO_IN_READY;
// 	//connect output of transmit FIFO to MISO:
// 	assign MISO = (mode == 2) ? tx_FIFO_OUT_DATA[7-bit_counter] : ((mode == 1) ? MOSI : 0); //if writing data, return written data; during config byte, return 0
// 	// assign ? = tx_FIFO_OUT_VALID; //if data isn't valid, oh well.  to bad
// 	assign tx_FIFO_OUT_READY = end_of_byte && mode == 2; //let FIFO advance to next byte if we just completed a proper read
// endmodule

// module SPI_slave_config_byte(config_byte, CS, CS_out, MOSI, MISO, MISO_in, SCK);
// 	//this SPI slave writes to a config byte, and sends no response.  
// 	//After the config byte, control and data is transfered to another SPI interface for accessing other SPI peripheral configurations.
// 	//This is done by passing out a chip select that goes low after the first byte has been recieved.
// 	//The external MISO is also passed in so that it can be muxed into the reply of this own module.

// 	//Maybe in the future, provide options to set the SPI mode.  For now, posedge clock sampling
// 	//MSB first
// 	input wire CS, MOSI, MISO_in, SCK;
// 	output wire MISO, CS_out;
// 	output reg [7:0] config_byte;

// 	reg [2:0] bit_counter;
// 	reg [7:0] rx_buffer;
// 	reg mode; //0: recieving first byte; 1: passing signal to some other SPI
// 	wire [7:0] rx_word;
// 	assign rx_word = {rx_buffer[7:1], MOSI};
// 	wire end_of_byte;
// 	assign end_of_byte = (bit_counter == 7) && !CS;

// 	assign MISO = mode ? MISO_in : config_byte[7-bit_counter];
// 	assign CS_out = CS || ~mode;  //only in mode 1, while CS is low, will output CS be low

// 	always @(posedge SCK, posedge CS) begin
// 		if (CS) begin
// 			bit_counter <= 0;
// 			mode <= 0;
// 		end
// 		else begin
// 			bit_counter <= bit_counter + 1;
// 			rx_buffer[7-bit_counter] <= MOSI;

// 			//transition between modes
// 			if (end_of_byte && mode == 0) mode <= 1;
// 			if (end_of_byte && mode == 0) config_byte <= rx_word;
// 		end
// 	end
// endmodule

module SPI_serializer #(parameter xfer_len=4, parameter addr_bits=5) (cs, ser_out, ser_in, sck, data_in, data_out);
	//Generic SPI element. During a transfer, DI data is filled and DO data is scanned out.

	//parameter xfer_len determines the size of the max transfer length,
	//and parameter addr_bits must be sufficient to index through all bits of the max transfer length

	//external logic must be added to make actual use of DI_DATA (an action on rising CS) and to set DO_DATA before a transfer.
	//Can be used as a part in either a slave or a master.
		//for master: another bit of logic in the same system orchestrates CS to initiate transfers.
		//for slave: CS is controlled by a master SPI from somewhere else.


	input wire [(8*xfer_len-1):0] data_out; //DO is an input, because the data to be serialized is created locally;
	output reg [(8*xfer_len-1):0] data_in;
	input wire ser_in, cs, sck;
    output wire ser_out;

    //scan chain for scan_in_bits
    //syntax note:  line ends only at semicolon; no begin / end are needed since there is only one action inside each block
    always @(posedge sck)
        if (~cs) data_in <= {data_in[(8*xfer_len-2):0], ser_in};

    //output register:  content of output reg set at the end of the preceding transfer.
    reg [addr_bits:0] out_bit_counter;
    assign ser_out = data_out[out_bit_counter];

    //pointer state for serialization
    always @(posedge sck, posedge cs) begin
        if (cs) out_bit_counter <= 8*xfer_len-1; //reset to highest bit
        else out_bit_counter <= out_bit_counter-1; //MSB is shifted out first; so bit counter decrements
    end
    
endmodule
