yosys -q -p 'synth_ice40 -top main -json main.json' transmitter.v common_modules.v
nextpnr-ice40 --up5k --json main.json --asc main.asc --pcf pinmap_transmitter.pcf --package sg48 -q
rm main.json
icepack main.asc main.bin
rm main.asc
./iceprog.exe main.bin -S -d i:0x0403:0x6014
rm main.bin
