import math
from pyftdi.spi import SpiController
from pyftdi.ftdi import Ftdi
import ftd2xx
import time

#============================================================
#general info here, haha

class rxtx_SPI():
	def __init__(self, direction, verbose=False): #direction can be either 'rx' or 'tx'
		#chip select pin indices are hardcoded to pins in the following order: 0->D3, 1->D4, 2->D5, 3->D6, 4->D7 (5 Chip selects max)
		self.spi = SpiController(cs_count=2) #chip selects are on the second one, so we need at least 2.
		
		self.verbose = verbose #flag to print some extra diagnostic stuff

		## Select and configure which FTDI interface to use
		#limit which device we will conect to.  This has two purposes:
		#1) determines whether we are connecting to the RX or TX FPGA unit of the mini microscope system
		#2) prevents the library from looking at the one FTDI interface that is not on libusbK, because if it does, pyftdi may barf
		if direction == 'tx':
			Ftdi.PRODUCT_IDS = {1027:{'232h':24596,'ft232h':24596}} #0x0403:0x6014 -> default Vendor ID : Product ID for ft232h
			print(Ftdi.list_devices())
			self.spi.configure('ftdi://:232h/1')
		elif direction == 'rx':
			Ftdi.PRODUCT_IDS = {1027:{'2232h':24592,'ft2232h':24592}} #0x0403:0x6010 -> default Vendor ID : Product ID for ft2232h
			print(Ftdi.list_devices())
			self.spi.configure('ftdi://:2232h/1')
		else:
			print("The direction parameter must be either \'tx\' or \'rx\'.")
		self.direction = direction

		# Get 'port' to a specific device, and specify parameters (cs pin, bus frequency, and SPI mode)
		self.slave = self.spi.get_port(cs=1, freq=1E6, mode=1)

		#set an initial configuration for the reciever or transmitter
		self.config_byte = 1
		self.config_UWB()

	def UWB_transaction(self, payload):
		data = bytearray([self.config_byte]+payload)
		data = self.slave.exchange(data, readlen=len(payload)+1, duplex=True)
		data = [int(x) for x in data]
		return data[1:] #exlude first returned byte, which has nothing to do with the UWB transaction

	def set_config_byte(self, conf):
		ret = self.slave.exchange(bytearray([conf]), readlen=1, duplex=True)
		self.config_byte = conf
		return int(ret[0]) #should return previous config byte value

	def write_reg(self, address, data):
		cmd = [address+64, data]
		self.UWB_transaction(cmd)
		#verify data:
		if self.verbose:
			data_rx = self.read_reg(address)
			print("REG: %i: %i/%i"%(address, data, data_rx))
			if data_rx != data:
				print("register write failed")

	def read_reg(self, address):
		data = [address, 0]
		data = self.UWB_transaction(data)

		return data[1]

	def write_data(self, data):
		#since the SPI in the FPGA has a tiny FIFO, break this into 8 byte chunks
		i = 0
		datas = []
		while i<len(data): 
			datas.append(data[i,min(i+8, len(data))])
			i = i + 8

		for data in datas:
			data = [0x3F+64+128] + data
			self.UWB_transaction(data)


	def config_UWB(self, LNA_val=4,filt_val=24,pulse_freq=25,pulse_config=[1,2,3,4,5]):
		#first, set for UWB access:
		self.set_config_byte(6)

		#power cycling settings:
		self.write_reg(4, 0) #set device to only return to IDLE state between packets, rather than returning to a lower & slower power mode
		self.write_reg(5, 128) #set device to go into ACTIVE mode automatically when timer triggers
		self.write_reg(6, 0) #set timer high period to 0
		self.write_reg(7, 8) #set timer low period to 8
		self.write_reg(14, 192) #disable automatic RX buffer flushing

		self.write_reg(0x2F, 32) #set preamble to 16*2=32 clock cycles
		self.write_reg(0x2C, 128+0) #set modem to automatically transmit after waking up, and do 1.33 rate FEC

		self.write_reg(0x3C, 64) #set 64 byte packet transmission
		self.write_reg(0x3D, 64) #set 64 byte packet reception

		# self.write_reg(0x3E, 0) #set source of transmission size to reg 0x3C.  Despite what datasheet says, does not seem to do anything

		#register 1F: power status and commands: a whole bunch of details in here
		if self.direction == 'tx':
			self.write_reg(0x1F, 16) #set device to transmitter mode, and send a start transmission command
		else:
			pass #if rx, the default value of this register is good

		self.write_reg(0x0F, LNA_val*32+filt_val) #reciever frequency tuning register
		self.config_pulses(pulse_config, pulse_freq)

		#return to normal operation when done
		self.set_config_byte(1)


	def config_pulses(self, list_of_pulses, pulse_freq):
		#do a bulk write of the twelve pulse-parameter registers
		pulses = [0]*12
		for indx in list_of_pulses:
			pulses[indx] = pulse_freq+128+64+32
		data = [0x10+64+128] + pulses
		self.UWB_transaction(data)


class rx_FIFO():
	def __init__(self):
		self.dev = ftd2xx.open(0) #open device index 0 - should be the only one since other two are set to libusbk drivers
		self.dev.setBitMode(0x00, 0x00) #reset - ASYNC FIFO is set in EEPROM settings
		self.dev.setUSBParameters(32768, 32768)

	def read_data(self):
		nbuffered = self.dev.getQueueStatus() #returns number of elements in the queue
		rx_buffer = self.dev.read(nbuffered)
		return rx_buffer

	def read_data_time(self, dt):
		#reads a batch of data over a specified amount of time
		data = bytearray([])
		now = time.time()
		while time.time() < now+dt:
			data = data + self.read_data()
		return data


#if run, some tests to make sure that it is working
if __name__ == "__main__":
	#initialization function will autmatically run some tests and setup to check that it seems to be working
	rx = rxtx_SPI('rx', verbose=True)
	tx = rxtx_SPI('tx', verbose=True)
	rx_data = rx_FIFO()
	data = rx_data.read_data_time(1)
	print(len(data))
	data = [int(data[i]) for i in range(-30,-1)]
	print(data)

	rx.set_config_byte(6)
	print(rx.read_reg(0))
	print(rx.read_reg(3))
	rx.set_config_byte(1)