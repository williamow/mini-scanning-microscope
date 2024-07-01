#script has components for both transmit and recieve interfaces; transmit is over a FTDI SPI interface, recieve is over an FTDI FIFO interface.
#each one uses a different library

import math
from pyftdi.spi import SpiController
from pyftdi.ftdi import Ftdi
import ftd2xx
import time
from matplotlib import pyplot as plt
import pickle
import numpy
np = numpy

#============================================================TX setup

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
	def write_reg(self, address, data):
		data = bytearray([address+64, data])
		slave.exchange(data, duplex=True)

	def read_reg(self, address):
		data = bytearray([address, 0])
		reg_val = slave.exchange(out=data, readlen=2, duplex=True)
		reg_val = int(reg_val[1])
		return reg_val

	def write_data(self, data):
		data = [0x3F+64+128] + data
		data = bytearray(data)
		# print(data)
		n_data = len(data)
		slave.exchange(out=data, readlen=n_data, duplex=True)

	def config(self):
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

		filt_val = 25
		LNA_val = 4
		self.write_reg(0x0F, LNA_val*32+filt_val) #reciever frequency tuning register
		for j in range(12):
			self.write_reg(0x10+j, 0) #disable all pulses to start


		self.write_reg(0x10+1, filt_val+128+64+32) #transmitted pulse center frequency
		self.write_reg(0x10+2, filt_val+128+64+32) #transmitted pulse center frequency
		self.write_reg(0x10+3, filt_val+128+64+32) #transmitted pulse center frequency
		self.write_reg(0x10+4, filt_val+128+64+32) #transmitted pulse center frequency
		self.write_reg(0x10+5, filt_val+128+64+32) #transmitted pulse center frequency

	def config_pulses(self, list_of_pulses, pulse_freq):
		#do a bulk write of the twelve pulse-parameter registers
		pulses = [0]*12
		for indx in list_of_pulses:
			pulses[indx] = pulse_freq+128+64+32
		data = [0x10+64+128] + pulses
		data = bytearray(data)
		# print(data)
		n_data = len(data)
		slave.exchange(out=data, readlen=n_data, duplex=True)


#=====================================================================RX setup

dev = ftd2xx.open(0) #open device index 0 - should be the only one since other two are set to libusbk drivers
dev.setBitMode(0x00, 0x00) #reset - ASYNC FIFO is set in EEPROM settings
dev.setUSBParameters(32768, 32768)

def fifo_rx():
    buffered = dev.getQueueStatus() #returns number of elements in the queue
    rx_buffer = dev.read(buffered)
    return rx_buffer

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
		reg_val = [int(i) for i in reg_val] #convert from byte array to list of ints
		return reg_val

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


	def read_status(self):
		time.sleep(0.05)
		fifo_rx() #clear rx buffer
		data = bytes([2, 0, 0, 2, 0, 0])
		dev.write(data)
		time.sleep(0.05)
		reg_val = fifo_rx()
		return (int(reg_val[0]), int(reg_val[2]))

	def config(self):
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
		filt_val = 25
		LNA_val = 4
		self.write_reg(0x0F, LNA_val*32+filt_val) #reciever frequency tuning register
		for j in range(4):
			self.write_reg(0x11+j, filt_val+224) #transmitted pulse center frequency

def binary_majority_vote(x):
	count1 = 0
	for i in range(8):
		count1 = count1 + (x >> i)%2
	return 1*(count1 > 4)

tx = tx_m()
rx = rx_m()

tx.config()
rx.config()

# print(rx.read_reg(0x1F))
# print(tx.read_reg(0x1F))

quality_list  =[]

for rx_filt_freq in range(23, 27):
	for pulse_freq in range(23, 27):
		for pulse_config_indx in range(64):

			# print("Pulse position: %i"%pulse_config_indx)
			pulse_config = []
			for j in range(12): #expand to one-hot
				if (pulse_config_indx >> j)%2 == 1:
					pulse_config.append(j)
			if len(pulse_config) < 5:
				continue
			# print([pulse_config])
			# pulse_config = [1,2,3,4]
			tx.config_pulses(pulse_config, pulse_freq)
			rx.config_pulses(pulse_config, pulse_freq)
			LNA_val = 4
			rx.write_reg(0x0F, LNA_val*32+rx_filt_freq)
			# rx.config_pulses([1,2,3,4], 25)

			dropped_packets = 0.
			wrong_packets = 0.
			errors = 0.
			packet_size = 64
			npackets = 1024
			i = 0
			recieved_data = []
			transmitted_data = []
			# while (i < npackets):
			tx.write_reg(0x1F, 16)
			time.sleep(0.0001)
			tx.write_reg(0x1F, 16)
			time.sleep(0.2) #make sure interface is cleared before starting
			rx.read_data()
			for i in range(npackets):
				#check: if system is performing well, extend the experiment to more packets
				# if i == (npackets-2) and dropped_packets < 10 and npackets < 1e6:
					# npackets = npackets*2

				print("packet %i"%i, end="\r")
				rnd_data = numpy.random.randint(0, 256, size=[packet_size], dtype=np.ubyte)
				# rnd_data[0] = 255*(i%2) #alternate between leading each packet with zero and leading each packet with 255
				rnd_data = [val for val in rnd_data]
				transmitted_data = transmitted_data + rnd_data
				# tx.write_data(rnd_data)
				# tx.write_reg(0x1F, 16) #set device to transmitter mode, and send a start transmission command
				# time.sleep(0.0001)
				# tx.write_reg(0x1F, 16)
				 #set device to transmitter mode, and send a start transmission command
				# print(tx.read_reg(1))
				# print(tx.read_reg(0))
				# print(tx.read_reg(2))
				# n_rx = rx.read_reg(3) #reads number of bytes in RX FIFO
				# rssi = rx.read_reg(0x22)
				# if n_rx > 16:
				# time.sleep(0.0001)
				# return_data = []
				# for wait in range(1000):
				recieved_data = recieved_data + rx.read_data()
					# if len(return_data) >= packet_size:
						# break
				# n_rx = len(return_data)
				# return_data = [int(val) for val in return_data]
				# rssi = -1
				# if (n_rx == 0):
				# 	dropped_packets = dropped_packets + 1
				# if n_rx != packet_size:
				# 	wrong_packets = wrong_packets + 1
				
				# if n_rx == packet_size:
				# 	errors = errors + np.sum(1-1*((np.array(rnd_data)-np.array(return_data)) == 0))

				# print(rnd_data)
				# print(return_data)
				# print("")
				# i = i + 1

			time.sleep(0.2) #make sure every last bit of info makes it through the USB interface:
			recieved_data = recieved_data + rx.read_data()

			#break it into packets, check headers, etc
			recieved_amnt = len(recieved_data)/len(transmitted_data)
			# print(transmitted_data[:20])
			# print(recieved_data[:20])
			if (len(recieved_data)%packet_size == 0 and len(recieved_data) > 0):
				drop_rate = (len(transmitted_data)-len(recieved_data))/len(transmitted_data)
				recieved_data = numpy.reshape(recieved_data, [-1,packet_size])
				transmitted_data = numpy.reshape(transmitted_data, [-1,packet_size])
				# print(recieved_data.shape)
				if drop_rate == 0:
					ber = np.sum(1-1*((transmitted_data-recieved_data) == 0))/(transmitted_data.shape[0]*transmitted_data.shape[1])/8.
				else:
					#iterate through packets.  Assume at most 1 dropped packet in a row
					errors = 0
					rx_index = 0
					for tx_index in range(npackets):

						if rx_index == recieved_data.shape[1]:
							break #if rx is shorter, may need to break early

						#have to interpret first byte as all ones or all zeros, but there might be bit errors... majority vote
						new_errors  = np.sum(1.-1.*((transmitted_data[tx_index,:]-recieved_data[rx_index,:]) == 0))
						# print(transmitted_data[:,tx_index])
						# print(recieved_data[:,rx_index])
						# print(packet_size*0.9)
						if new_errors > packet_size*0.9:
							continue #assume this is the wrong packet
						# if binary_majority_vote(recieved_data[0,rx_index]) != binary_majority_vote(transmitted_data[0,tx_index]):
							# continue #don't incriment rx_index, assuming that a packet is missing in rx, then tx needs to incriment to catch up
						#otherwise, assume we are matching the correct packets
						errors = errors + new_errors
						rx_index = rx_index + 1
						
					# print(rx_index/tx_index)

					ber = errors / (recieved_data.shape[0]*recieved_data.shape[1]) / 8.
					if rx_index != recieved_data.shape[1]:
						ber = -1.
			elif len(recieved_data)%packet_size != 0:
				print("Error! Data not a mutliple of 64 bytes!")
				drop_rate = 1;
				ber = 1;
			else:
				drop_rate = 1;
				ber = 1;


				
			rssi = rx.read_reg(0x22)
			rnsi = rx.read_reg(0x23)

			print("Dropped packet rate: %.4f, bit error rate: %.4f, recieved amount: %.4f, RSSI: %i, RNSI: %i"%(drop_rate, ber, recieved_amnt, rssi, rnsi))

			quality_list.append([pulse_config, pulse_freq, rx_filt_freq, drop_rate, ber, rssi, rnsi])


#finally, when done, need to plot historgrams and save result lists to a pickle

with open('quality_results.pkl', 'wb') as f:
	pickle.dump(quality_list, f)