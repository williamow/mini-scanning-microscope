import math
import ftd2xx
import time
from pyftdi.spi import SpiController
from pyftdi.ftdi import Ftdi
import numpy
np = numpy

#=====================================================================RX setup
#class for accessing receiver UWB radio over FTDI FIFO interface.  In normal operation, only FIFO_RX is used to quickly receive large quatities of data;
#however direct commands to the UWB can be sent as well for configuration and debugging purposes



class rx_m():
	def write_reg(self, address, data):
		data = bytes([2, address+64, data])
		dev.write(data)

	def read_reg(self, address):
		time.sleep(0.05)
		fifo_rx() #clear rx buffer
		data = bytes([2, address, 0])
		# data = bytes(20*[0])
		dev.write(data)
		time.sleep(0.05)
		reg_val = fifo_rx()
		reg_val = [int(val) for val in reg_val]
		# print(reg_val)
		if len(reg_val) < 1:
			return -1
		else:
			return int(reg_val[-1])

	def read_data(self):
		reg_val = fifo_rx() #If data is there, should just appear!
		# reg_val = [int(i) for i in reg_val] #convert from byte array to list of ints
		return reg_val

	def read_data_time(self, dt):
		#reads a batch of data over a specified amount of time
		data = bytearray([])
		now = time.time()
		while time.time() < now+dt:
			data = data + self.read_data()
		return data

	def read_status(self):
		time.sleep(0.05)
		fifo_rx() #clear rx buffer
		data = bytes([2, 0, 0, 2, 0, 0])
		dev.write(data)
		time.sleep(0.05)
		reg_val = fifo_rx()
		return (int(reg_val[0]), int(reg_val[2]))

	def config_UWB(self, LNA_val=4,filt_val=24,pulse_freq=25,pulse_config=[1,2,3,4,5]):
		self.write_reg(4, 0) #set device to only return to IDLE state between packets, rather than returning to a lower & slower power mode, and to do so at the end of every transmission
		self.write_reg(5, 128) #set device to go into ACTIVE mode automatically when timer triggers
		self.write_reg(6, 0) #set timer high period to 0
		self.write_reg(7, 8) #set timer low period to 8
		self.write_reg(14, 192) #disable automatic RX buffer flushing

		self.write_reg(0x2F, 32) #set preamble to 32*2=64 clock cycles
		self.write_reg(0x2C, 0) #set modem to do 1.33 rate FEC

		self.write_reg(0x3D, 64) #set 64 byte packets

		#register 1F: power status and commands: a whole bunch of details in here
		# self.write_reg(0x1F, 16) #set device to transmitter mode, and send a start transmission command
		self.write_reg(0x0F, LNA_val*32+filt_val) #reciever frequency tuning register
		self.config_pulses(pulse_config, pulse_freq)

	def config_pulses(self, list_of_pulses, pulse_freq):
		#do a bulk write of the twelve pulse-parameter registers
		pulses = [0]*12
		for indx in list_of_pulses:
			pulses[indx] = pulse_freq+128+64+32
		data = [0]*20 + [13] + [0x10+64+128] + pulses #some buffer (leading zeros), then transaction size, command byte, then pulse data
		data = bytes(data)
		dev.write(data)

		#flush returned values from buffer:
		time.sleep(0.05)
		fifo_rx()


if __name__ == "__main__":
	rx = rx_m()
	rx.config()
	# time.sleep(1)

	data = read_data_time(10)
	print(len(data))
	# print(data[:64])

	#test code: finding place in data stream... well we would not have to do this if we got everything else to work just right, right?  But maybe robustness is better anyway.
	
	data2 = numpy.reshape(data[:64*100], [100,64])
	data_difference = data2[1:,:]-data2[:-1,:]
	difference_1 = (data_difference == 128)
	row_totals = numpy.sum(difference_1, axis=0)
	offset1 = numpy.argmax(row_totals)
	row_totals[offset1] = 0
	offset2 = numpy.argmax(row_totals)
	offset = min(offset1, offset2)-1

	data = data[offset:1000*64+offset]
	data = numpy.reshape(data, [1000,64])

	def printfn(x):
		return str('%03d'%x)
	numpy.set_printoptions(linewidth=4*64, formatter={'all': printfn})

	for i in range(298,305):
		print(data[i,:30])