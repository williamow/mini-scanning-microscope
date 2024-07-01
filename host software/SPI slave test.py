#script has components for both transmit and recieve interfaces; transmit is over a FTDI SPI interface, recieve is over an FTDI FIFO interface.
#each one uses a different library

import math
from pyftdi.spi import SpiController
from pyftdi.ftdi import Ftdi
import time
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

#test write operation
data = bytearray([0, 1, 2, 3, 4, 5])
data = slave.exchange(out=data, readlen=len(data), duplex=True)
data = [int(x) for x in data] #list conversion
print(data)
data = bytearray([0, 11, 12, 13, 14, 15])
data = slave.exchange(out=data, readlen=len(data), duplex=True)
data = [int(x) for x in data] #list conversion
print(data)

data = bytearray([255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
data = slave.exchange(out=data, readlen=len(data), duplex=True)
data = [int(x) for x in data] #list conversion
print(data)

data = bytearray([255, 1, 2, 3, 4, 5, 11, 12, 13, 14, 15])
data = slave.exchange(out=data, readlen=len(data), duplex=True)
data = [int(x) for x in data] #list conversion
print(data)