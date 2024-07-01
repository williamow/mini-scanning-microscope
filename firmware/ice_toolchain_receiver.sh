yosys -q -p 'synth_ice40 -top main -json main.json' receiver.v common_modules.v
nextpnr-ice40 --up5k --json main.json --asc main.asc --pcf pinmap_receiver.pcf --package sg48 -q
icepack main.asc main.bin
./iceprog.exe main.bin -d i:0x0403:0x6010
