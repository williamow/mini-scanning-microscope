#script has components for both transmit and recieve interfaces; transmit is over a FTDI SPI interface, recieve is over an FTDI FIFO interface.
#each one uses a different library

import math
from pyftdi.spi import SpiController
from pyftdi.ftdi import Ftdi
import ftd2xx
import time
from matplotlib import pyplot as plt
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

	def config(self):
		#power cycling settings:
		self.write_reg(4, 0) #set device to only return to IDLE state between packets, rather than returning to a lower & slower power mode
		self.write_reg(5, 128) #set device to go into ACTIVE mode automatically when timer triggers
		self.write_reg(6, 0) #set timer high period to 0
		self.write_reg(7, 8) #set timer low period to 8
		self.write_reg(14, 192) #disable automatic RX buffer flushing

		self.write_reg(0x2F, 64) #set preamble to 16*2=32 clock cycles
		self.write_reg(0x2C, 128) #set modem to automatically transmit after waking up

		#register 1F: power status and commands: a whole bunch of details in here
		self.write_reg(0x1F, 16) #set device to transmitter mode, and send a start transmission command

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
		dev.write(data)
		time.sleep(0.05)
		reg_val = fifo_rx()
		return int(reg_val[1])

	def read_status(self):
		time.sleep(0.05)
		fifo_rx() #clear rx buffer
		data = bytes([2, 0, 0, 2, 0, 0])
		dev.write(data)
		time.sleep(0.05)
		reg_val = fifo_rx()
		return (int(reg_val[0]), int(reg_val[2]))

	def config(self):
		self.write_reg(4, 0) #set device to only return to IDLE state between packets, rather than returning to a lower & slower power mode
		self.write_reg(5, 128) #set device to go into ACTIVE mode automatically when timer triggers
		self.write_reg(6, 0) #set timer high period to 0
		self.write_reg(7, 8) #set timer low period to 8
		self.write_reg(14, 192) #disable automatic RX buffer flushing

		self.write_reg(0x2F, 64) #set preamble to 16*2=32 clock cycles
		# self.write_reg(0x2C, 128) #set modem to automatically transmit after waking up

		#register 1F: power status and commands: a whole bunch of details in here
		# self.write_reg(0x1F, 16) #set device to transmitter mode, and send a start transmission command


tx = tx_m()
rx = rx_m()

tx.config()
rx.config()

print(rx.read_reg(0x1F))
print(tx.read_reg(0x1F))

#sweep through transmission parameters to find optimum operating frequency
rssi_values = numpy.zeros([8, 32]) + 64 #max actual value is 63, indicating weakest signal, so default for no recieved signal is 64
for i in range(256):

	lna_val = math.floor(i/32.)
	filt_val = i%32
	print("LNA: %i filt: %i"%(math.floor(i/32.), i%32))

	rx.write_reg(0x0F, i) #reciever frequency tuning register
	for j in range(4):
		tx.write_reg(0x11+j, filt_val+224) #transmitted pulse center frequency

	for j in range(16):
		tx.write_reg(0x3F, i) #write a byte to the TX FIFO
	tx.write_reg(0x1F, 16) #set device to transmitter mode, and send a start transmission command
	# print(rx.read_status())
	n_rx = rx.read_reg(3) #reads number of bytes in RX FIFO
	print("recieved %i bytes"%n_rx)
	for j in range(n_rx): #clear reading buffer
		rx.read_reg(0x3F)
	if n_rx > 0:
		rssi = rx.read_reg(0x22)
		rssi_values[lna_val, filt_val] = rssi
		print("RSSI: %i"%rssi)

plt.figure()
plt.imshow(rssi_values)

for i in range(8):
    for j in range(32):
        plt.text(j, i, rssi_values[i, j],
                       ha="center", va="center", color="w")

plt.ylabel("LNA value")
plt.xlabel("filt value")

plt.show()