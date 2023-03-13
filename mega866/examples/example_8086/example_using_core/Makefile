prog.hex: prog.elf
	ia16-elf-objcopy -I elf32-little -O ihex $< $@

prog.elf: prog.o prog.ld
	ia16-elf-gcc -T prog.ld -Wl,-Map=prog.map -nostartfiles -fno-use-cxa-atexit -Wl,--oformat=elf32-i386

prog.o: prog.asm
	nasm -f elf $< -o $@
