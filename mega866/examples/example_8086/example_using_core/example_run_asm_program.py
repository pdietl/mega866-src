# Jump to 0x0:0x7c00
# ea 00 7c 00 00
#
# nop, jmp -1
# 90 eb fd

from ..core_8086 import IoWidth, Core8086

class BasicMemController:
	def __init__(self):
		self.memory = {
			0x7c00: 0x90,
			0x7c01: 0xeb,
			0x7c02: 0xfd,

			0xffff0: 0xea,
			0xffff1: 0x00,
			0xffff2: 0x7c,
			0xffff3: 0x00,
			0xffff4: 0x00,
		}

	def read_memory(self, address, width):
		if width == IoWidth.UPPER_BYTE or width == IoWidth.LOWER_BYTE:
			return self.memory.get(address, 0)
		else:
			return self.memory.get(address, 0) | (self.memory.get(address + 1, 0) << 8)

	def write_memory(self, address, data):
		pass

	def read_io(self, address, width):
		if width == IoWidth.UPPER_BYTE or width == IoWidth.LOWER_BYTE:
			return 0x00
		else:
			return 0x0000

	def write_io(self, address, data):
		pass

controller_8086 = Core8086("/dev/serial/by-id/usb-ProgHQ_Open-TL866_Programmer_33144A91666856D18E6084EC-if00", BasicMemController(), verbose=True)
controller_8086.run()
