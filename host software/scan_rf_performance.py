import mini_uScope_reciever
import mini_uScope_transmitter
import math
import numpy
import pickle

rx = mini_uScope_reciever.rx_m()
tx = mini_uScope_transmitter.tx_m()

tx.config_UWB()
rx.config_UWB()

results_list = []

capture_time = 0.2 #determines how long we measure data; should be 1.5 M bytes per second
clocks_per_packet = 256
timerX_period = 996
timerY_period = 1000

for LNA_val in [4]:
	for filt_freq in range(24, 25):
		for pulse_freq in range(25, 26):
			for pulse_config_indx in range(64):
				
				pulse_config = []
				for j in range(12): #expand to one-hot
					if (pulse_config_indx >> j)%2 == 1:
						pulse_config.append(j)
				if len(pulse_config) < 6:
					continue

				tx.config_UWB(LNA_val,filt_freq,pulse_freq,pulse_config)
				tx.set_config_byte(1) #config for testing
				rx.config_UWB(LNA_val,filt_freq,pulse_freq,pulse_config)

				result = {'LNA': LNA_val, 'filt_freq': filt_freq, 'pulse_freq': pulse_freq, 'BER': 1, 'PER': 1, 'RSSI': 63, 'pulse_config': pulse_config,}
				#recieve data and check for errors and missing packets

				data = rx.read_data_time(capture_time)
				print(len(data))

				#if less than half the expected data, just call it a failure:
				if len(data) < capture_time*0.75e6*0.5:
					results_list.append(result)
					print(result)
					continue

				#finds offset of packet edges in data stream, assumes a minimal amount of data has been recorded
				data2 = numpy.reshape(data[:64*100], [100,64])
				data_difference = data2[1:,:]-data2[:-1,:]
				difference_1 = 1.*(data_difference == 1) #looking incriments in the high byte of the timer indicators
				row_totals = numpy.sum(difference_1, axis=0)
				print(row_totals)
				offset1 = numpy.argmax(row_totals)
				row_totals[offset1] = 0
				offset2 = numpy.argmax(row_totals)
				if abs(offset1 - offset2) == 2:
					offset = min(offset1, offset2)
				else:
					offset = max(offset1, offset2) #the alignment wraps around at index 64

				#re-organize data according to offset
				data = data[offset:]
				npackets = math.floor(len(data)/64)
				data = data[:npackets*64]
				data = numpy.reshape(data, [npackets,64])

				#print data (usually commented out)
				def printfn(x):
					return str('%03d'%x)
				numpy.set_printoptions(linewidth=4*64, formatter={'all': printfn})

				for i in range(298,305):
					print(data[i,:30])


				#combine 16 byte data from first two rows:
				timerX = data[:,1] + data[:,0]*256
				timerY = data[:,3] + data[:,2]*256

				#payload part of the data
				data = data[:,4:]

				gt = numpy.linspace(4,63,60) #what the artificial payload is supposed to be
				gt = numpy.expand_dims(gt, axis=0) #add a 1-sized dimension at the beginning so it can be broadcast subtracted

				error = data - gt;
				nerrors = numpy.sum(1.*(error != 0))

				BER = nerrors / npackets / 60. / 8.
				result['BER'] = round(BER, 5)

				#counting dropped packets is a little harder... have to look at timer data, which may not be faithful anyway
				nexttimerX = (timerX + clocks_per_packet)%timerX_period;#predict what the next one should be
				nexttimerY = (timerY + clocks_per_packet)%timerY_period;
				Xwrong = 1.*(nexttimerX[:-1] != timerX[1:])
				Ywrong = 1.*(nexttimerY[:-1] != timerY[1:])
				both_wrong = Xwrong*Ywrong;

				print(nexttimerX[0:20])
				print(timerX[1:21])
				print(nexttimerY[0:20])
				print(timerY[1:21])
				print(both_wrong[0:20])

				Nwrong = numpy.sum(1.*(both_wrong==1))
				PER = Nwrong/npackets
				result['PER'] = round(PER, 5) #packet error rate - actually not a very exact measurement, oh well.

				result['RSSI'] = rx.read_reg(0x22)

				results_list.append(result)
				print(result)

with open('rf_performance_scan_results.pkl', 'wb') as f:
	pickle.dump(results_list, f)