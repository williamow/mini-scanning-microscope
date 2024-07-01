import math
from pyftdi.spi import SpiController
from pyftdi.ftdi import Ftdi
import time

#============================================================
#class for accessing transmitter UWB radio through the programmed FPGA (obviously, only when it is tethered)

spi = SpiController(cs_count=5)
#chip select pin indices are hardcoded to pins in the following order: 0->D3, 1->D4, 2->D5, 3->D6, 4->D7 (5 Chip selects max)

# Configure the first interface (IF/1) of the first FTDI device as a
# SPI master
Ftdi.PRODUCT_IDS = {1027:{'232h':24596,'ft232h':24596}}
print(Ftdi.list_devices())
spi.configure('ftdi://:232h/1')

#do a reset first
# gpio = spi.get_gpio()
# gpio.set_direction(0x30, 0x10)

# Assert GPO pin
# gpio.write(0x10)

# Get 'port' to a specific device, and specify parameters (cs pin, bus frequency, and SPI mode)
slave = spi.get_port(cs=1, freq=1E6, mode=1)

class tx_m():
	def __init__(self):
		self.config_byte = 1
		self.set_config_byte(1)


	def UWB_transaction(self, payload):
		#connects indirecty to UWB tx.  data pattern is:  [{0 for write, 255 for read} {payload into FIFO}]
		#payload into FIFO: sends to the master SPI module: format is: [{transmission length} {transmission bytes}]
		#can (should) add buffer zeros before and after a write (within the payload); 
			#they shouldn't cause actions in the master SPI, but will help alignment of data stuff

		#writes to the SPI slave FIFO buffer
		# data = [0, 0, len(payload)] + payload + [0, 0]
		# data = bytearray(data)
		# slave.exchange(data, duplex=True)

		# #reads response from the SPI slave FIFO buffer
		# data = [255] + [0]*len(payload)
		# data = bytearray(data)
		# return slave.exchange(data, readlen=len(payload)+1, duplex=True)

		data = bytearray([self.config_byte]+payload)
		return slave.exchange(data, readlen=len(payload)+1, duplex=True)

	def set_config_byte(self, conf):
		ret = slave.exchange(bytearray([conf]), readlen=1, duplex=True)
		self.config_byte = conf
		return int(ret[0]) #should return previous config byte value


	def write_reg(self, address, data):
		data = [address+64, data] #check note about data pattern above!
		self.UWB_transaction(data)

	def read_reg(self, address):
		data = [address, 0]
		data = self.UWB_transaction(data)
		return [int(x) for x in data]

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

		self.write_reg(0x3C, 64) #set 64 byte packets

		# self.write_reg(0x3E, 0) #set source of transmission size to reg 0x3C.  Despite what datasheet says, does not seem to do anything

		#register 1F: power status and commands: a whole bunch of details in here
		self.write_reg(0x1F, 16) #set device to transmitter mode, and send a start transmission command

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


#if run, some tests to make sure that it is working
if __name__ == "__main__":
	tx = tx_m()
	tx.set_config_byte(6)
	print("Reading register values:")
	tx.write_reg(14,192)
	tx.config()
	for reg in [0, 1, 2, 3, 4,5,6,7,14,16,17,18,19,20,21,22,23,24,25,26,27,0x3C]:
		reg_val = tx.read_reg(reg)
		print(reg, end="")
		print(": ", end="")
		print(reg_val)
		# print("%i: %i"%(reg, reg_val))

	print(tx.set_config_byte(1))
	print(tx.set_config_byte(1))	