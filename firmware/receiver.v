module main (FIFO_D, FIFO_RD, FIFO_WR, FIFO_TXE, FIFO_RXF, UWB_CS, UWB_MOSI, UWB_MISO, UWB_SCK, FTDI_CS, FTDI_MOSI, FTDI_MISO, FTDI_SCK);
	input wire FIFO_TXE, FIFO_RXF, UWB_MISO, FTDI_CS, FTDI_MOSI, FTDI_SCK;
	output wire FIFO_RD, FIFO_WR, UWB_CS, UWB_MOSI, UWB_SCK, FTDI_MISO;
	inout wire [7:0] FIFO_D;

	wire clk24, clk6, clk3;
	clocks the_clocks(clk3, clk6, clk24);
	
	wire [7:0] intf_IN_DATA, intf_OUT_DATA;
	wire intf_IN_VALID, intf_IN_READY, intf_OUT_VALID, intf_OUT_READY;
	FTDI_FIFO_ASYNC intf(clk3, intf_IN_DATA, intf_IN_VALID, intf_IN_READY, intf_OUT_DATA, intf_OUT_VALID, intf_OUT_READY, FIFO_D, FIFO_RD, FIFO_WR, FIFO_TXE, FIFO_RXF);

	wire [7:0] config_byte;
	wire slave_CS, slave_CS_out, slave_MOSI, slave_MISO, slave_MISO_in, slave_SCK;
	SPI_slave_config_byte slave(config_byte, slave_CS, slave_CS_out, slave_MOSI, slave_MISO, slave_MISO_in, slave_SCK);

	//assign meanings to the config byte
	wire enable, spi_sw, decoding;
	assign enable = config_byte[0]; //if 0, the UWB data writer turns off
	assign spi_sw = config_byte[1];//if 1, then UWB SPI connects to FTDI SPI; otherwise, UWB SPI connects to data_writer
	assign decoding = config_byte[2]; //if 1, data is decoded; if zero, data from UWB is sent directly to the FIFO link

	//connect FIFO to SPI:
	wire [7:0] master_tx_data, master_rx_data;
	wire master_rx_valid, master_CS, master_MOSI, master_MISO, master_SCK;
	SPI_master master(master_tx_data, master_rx_data, master_rx_valid, clk24, clk3, master_CS, master_MOSI, master_MISO, master_SCK);

	wire [7:0] reader_to_spi, reader_from_spi;
	wire reader_from_spi_valid;
	uwb_data_reader reader(clk3, enable, reader_to_spi, reader_from_spi, reader_from_spi_valid);

	//connect FIFO interface to SPI data:
	assign intf_IN_DATA = master_rx_data;
	assign intf_IN_VALID = reader_from_spi_valid;
	assign intf_OUT_READY = 1; //we never use data from the interface, might as well just drain data from the FIFO (tie up loose end)

	//connect spi slave to the FTDI interface
	assign slave_CS = FTDI_CS;
	assign slave_SCK = FTDI_SCK;
	assign slave_MOSI = FTDI_MOSI;
	assign FTDI_MISO = slave_MISO;

	//connect three-way switched SPI connection between UWB, FTDI, and spi master
	assign UWB_CS = spi_sw ? slave_CS_out : master_CS;
	assign UWB_SCK = spi_sw ? FTDI_SCK : master_SCK;
	assign UWB_MOSI = spi_sw ? FTDI_MOSI : master_MOSI;
	assign slave_MISO_in = UWB_MISO;
	assign master_MISO = UWB_MISO;

	//connect data reading program to the spi master module
	assign master_tx_data = reader_to_spi;
	assign reader_from_spi = master_rx_data;

endmodule

module FTDI_FIFO_ASYNC(clk, IN_DATA, IN_VALID, IN_READY, OUT_DATA, OUT_VALID, OUT_READY, FIFO_D, FIFO_RD, FIFO_WR, FIFO_TXE, FIFO_RXF);
	inout wire [7:0] FIFO_D; //bidirectional data interface to FTDI
	input wire FIFO_TXE; // when FTDI is not ready, goes high (inverse ready signal)
	input wire FIFO_RXF; // when FTDI has data, goes low (inverse valid signal)
	output wire FIFO_RD; //puts new data from FTDI onto bus when driven low, FTDI releases bus when driven high
	output wire FIFO_WR; //FTDI samples data (reads in data) on falling edge

	input wire clk, IN_VALID, OUT_READY;
	input wire [7:0] IN_DATA;
	output wire [7:0] OUT_DATA;
	output wire IN_READY, OUT_VALID;

	wire [7:0] to_ftdi_IN_DATA, to_ftdi_OUT_DATA;
	wire to_ftdi_IN_VALID, to_ftdi_IN_READY, to_ftdi_OUT_VALID, to_ftdi_OUT_READY;
	FIFO #(8192, 13) to_ftdi(clk, clk, to_ftdi_IN_DATA, to_ftdi_IN_VALID, to_ftdi_IN_READY, to_ftdi_OUT_DATA, to_ftdi_OUT_VALID, to_ftdi_OUT_READY);

	wire [7:0] from_ftdi_IN_DATA, from_ftdi_OUT_DATA;
	wire from_ftdi_IN_VALID, from_ftdi_IN_READY, from_ftdi_OUT_VALID, from_ftdi_OUT_READY;
	FIFO #(512, 9) from_ftdi(clk, clk, from_ftdi_IN_DATA, from_ftdi_IN_VALID, from_ftdi_IN_READY, from_ftdi_OUT_DATA, from_ftdi_OUT_VALID, from_ftdi_OUT_READY);

	//FIFO_D needs to be a tri-state.  Maybe this implicit tri-state will work
	assign FIFO_D = FIFO_RD ? to_ftdi_OUT_DATA : 8'bZZZZZZZZ;

	//control signals between FTDI FIFO and FPGA buffer FIFOs:
	assign to_ftdi_OUT_READY = TX_go; //if we are transmitting, then then the FTDI must be ready
	assign from_ftdi_IN_DATA = FIFO_D;
	assign from_ftdi_IN_VALID = RX_go && ~FIFO_RXF; //if we are reading from FTDI, then data must be valid

	// end
	assign FIFO_WR = ~clk && TX_go && to_ftdi_OUT_VALID;  //if we are not writing, the write clock should be held low; if we are writing, the write clock should go high, then low @ posedge of system clock since FTDI reads on negative edge
	assign FIFO_RD = clk || ~RX_go || ~from_ftdi_IN_READY;  //if we are not reading, the read clock should be held high through a cycle;  if we are reading, then pass the clock

	//two status bits to determine what we do next:
	reg RX_go, TX_go;
	always @ (posedge clk) begin
		//conditions for a read from FTDI: did not read last cycle, FTDI is valid, and FPGA FIFO is ready
		if (~FIFO_RXF && from_ftdi_IN_READY) begin
			RX_go <= 1;
			TX_go <= 0;
		end
		//conditions for a write to FTDI: FTDI is ready and FPGA has valid data
		else if (~FIFO_TXE && to_ftdi_OUT_VALID) begin
			RX_go <= 0;
			TX_go <= 1;
		end
		//no transaction next edge
		else begin
			RX_go <= 0;
			TX_go <= 0;
		end
	end

	//simple connections from internal FIFOs to module ports:
	assign IN_READY = to_ftdi_IN_READY;
	assign OUT_DATA = from_ftdi_OUT_DATA;
	assign OUT_VALID = from_ftdi_OUT_VALID;
	assign to_ftdi_IN_DATA = IN_DATA;
	assign to_ftdi_IN_VALID = IN_VALID;
	assign from_ftdi_OUT_READY = OUT_READY;
endmodule

module uwb_data_reader(input wire clk, input wire en, output reg [7:0] to_spi, input wire [7:0] from_spi, output reg from_spi_valid);

	//FSM state.  starting at zero, low values control a request that asks for amount of available data.
	//in higher values, data is read back from module using a burst read.  the FSM is returned to zero when the burst ends.

	reg [7:0] PC; //kinda a program counter
	initial PC <= 0; //start the PC here

	reg [7:0] ndata;  //temporary storage of info which determines program branches

	always @(posedge clk) begin
	
		//to_spi and from_spi program operations
		casez (PC)
			0: from_spi_valid <= 0;  //this happens to be where we end up at the end of a transfer, so we can reset the valid flag here.
			1: to_spi <= 2; //start a two-byte transfer
			2: to_spi <= 3; //command for reading usage of uwb tx buffer
			5: ndata <= from_spi; //read uwb tx buffer usage response

			7: to_spi <= 1 + ndata;  //ndata+1 sized spi transfer
			8: to_spi <= 63+128; //burst read command
			10: from_spi_valid <= 1;

			default: to_spi <= 0;
		endcase

		//program counter control
		case (PC)
			//flow control: first thing is to check if user commands need to be processed
			0: PC <= (en) ? 1 : 0; //only progress if enabled

			//flow control after reading ndata: read ndata amount of bytes
			6: PC <= (ndata == 0) ? 0 : 7;  //if there is no data, return to program begining

			//return to zero after burst read is done, or incriment PC
			default: PC <= (PC == ndata+9) ? 0: PC + 1; //if this is ndata+9, then the next will be ndata+10 -> 0 will reset from_spi_valid.
		endcase

	end
endmodule