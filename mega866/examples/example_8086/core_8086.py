from gpio_controller import GpioController, all_earth_pins
from time import sleep
from enum import Enum
import sys

SHOW_DEBUG_PRINTS = True

# address/data pins
# Map from Mega-866 pin numbers 1-160 to address/data line number on 8086
address_pins = {
	31: 0, # AD0
    27: 1, # AD1
    25: 2, # AD2
    23: 3, # AD3
    75: 4, # AD4
    73: 5, # AD5
    71: 6, # AD6
    69: 7, # AD7
    67: 8, # AD8
    9: 9,  # AD9
    7: 10,  # AD10
    5: 11,  # AD11
    3: 12,  # AD12
    1: 13,  # AD13
    55: 14, # AD14
    53: 15, # AD15
    57: 16, # A16/S3
    59: 17, # A17/S4
    61: 18, # A18/S5
    63: 19, # A19/S6
}

DATA_PINS = frozenset([31, 27, 25, 23, 75, 73, 71, 69, 67, 9, 7, 5, 3, 1, 55, 53])

PIN_BHE = 65
PIN_RD = 13
PIN_READY = 41
PIN_INTR = 39
PIN_TEST = 37
PIN_NMI = 35
PIN_RESET = 45
PIN_CLK = 43
PIN_VCC = 49
PIN_GND1 = 51
PIN_GND2 = 47
PIN_MN_MX = 11
PIN_M_IO = 21
PIN_WR = 19
PIN_INTA = 33
PIN_ALE = 29
PIN_DT_R = 77
PIN_DEN = 79
PIN_HOLD = 15
PIN_HLDA = 17
PIN_LOCK = 19

class IoDirection(Enum):
    READ = 1
    WRITE = 2

class IoSpace(Enum):
    MEMORY = 1
    IO = 2

class IoWidth(Enum):
    WHOLE_WORD = 1
    UPPER_BYTE = 2
    LOWER_BYTE = 3

tristate_pins = set(all_earth_pins)

# Remove pins that should be always not tristated (i.e., always driven and not high-z)

for p in [PIN_READY, PIN_INTR, PIN_TEST, PIN_NMI, PIN_RESET, PIN_CLK, PIN_MN_MX, PIN_HOLD]:
    tristate_pins.remove(p)

ALWAYS_HIGH_PINS = [
    PIN_MN_MX,
    PIN_READY,
]

# Translate Mega-866 pin number to a bit for an argument to a gpio controller function
def pin(x):
    return 1 << (x - 1)


# Translate many Mega-866 pin numbers to bits for an argument to a gpio controller function
def pins(*pin_list):
    res = 0
    for p in pin_list:
        res |= pin(p)
    return res

# Take the return of gpio_controller.io_r() and get the state of the address lines of the 8086 as one 20-bit number
def get_address_pins(input_pins):
    addr = 0
    for k, v in address_pins.items():
        if input_pins & (1 << (k - 1)):
            addr |= 1 << v
    return addr


# Take the return of gpio_controller.io_r() and get the state of the data lines of the 8086 as one 20-bit number
def get_data_pins(input_pins):
    addr = 0
    for k, v in address_pins.items():
        if v < 16 and input_pins & (1 << (k - 1)):
            addr |= 1 << v
    return addr

# Take a 16-bit binary number and turn it into a pin list to feed to the `pins` function which is in turn given to gpio_controller.io_w
def number_to_data_pins_high(num):
    assert num <= 65535
    pin_list = []
    for k, v in address_pins.items():
        if num & (1 << v):
            pin_list.append(k)
    return pin_list

# Jump to 0x0:0x7c00
# ea 00 7c 00 00
#
# nop, jmp -1
# 90 eb fd

memory = {}

def init_memory():
    global memory
    memory = {
        0x7c00: 0x90,
        0x7c01: 0xeb,
        0x7c02: 0xfd,

        0xffff0: 0xea,
        0xffff1: 0x00,
        0xffff2: 0x7c,
        0xffff3: 0x00,
        0xffff4: 0x00,
    }

# 8086 reset sequnce is a series of at least 4 clock cycles while the RESET pin is held high
# Then drive the RESET pin low and a sequence of approximately 7 clock cycles is needed for some
# internal initialization that the 8086 performs. We know when the reset sequence is complete when the
# 8086 tries to fetch from 0xffff0.
# This function just sets up the mega-866 state and gets to the point of driving the RESET line low
def setup(tl866_path):
    init_memory()
    controller = GpioController(earth_serial_device=tl866_path)
    controller.init()
    controller.io_w(0)
    controller.io_tri(pins(*tristate_pins))
    controller.vdd_volt(3) # 5.1V
    controller.vdd_pins(pins(PIN_VCC))
    controller.gnd_pins(pins(PIN_GND1, PIN_GND2))
    controller.vdd_en()
    controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK))
    # Now drive RESET high and perform at least 4 clock cycles
    controller.io_w(pins(*ALWAYS_HIGH_PINS))
    controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_RESET))
    for i in range(5):
        controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_RESET, PIN_CLK))
        sleep(0.0001)
        controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_RESET))
        sleep(0.0001)
    controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_RESET, PIN_CLK))
    controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK))
    return controller

def debug_print(*stuff):
    global SHOW_DEBUG_PRINTS
    if SHOW_DEBUG_PRINTS:
        print(*stuff)

def run(controller):
    cycle_num = 0

    # Clock is high when entering this function
    # Following the reset, the CPU will perform an initial reset sequence of approximately 7 CLK cycles, and then it will fetch the instruction at address 0xffff0

    for i in range(50):
        cycle_num += 1
        controller.io_w(pins(*ALWAYS_HIGH_PINS))
        read_pins = controller.io_r()
        address = get_address_pins(read_pins)
        debug_print(f"{cycle_num:04}")
        if read_pins & pin(PIN_ALE):
            debug_print(f"  ALE high - latching address 0x{address:05x}")
            debug_print("  Beginning IO cycle")
            controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK))
            controller.io_w(pins(*ALWAYS_HIGH_PINS))

            cycle_num += 1
            debug_print(f"{cycle_num:04}")
            read_pins = controller.io_r()

            if read_pins & pin(PIN_RD) == 0:
                debug_print(f"  Dir: READ")
                io_dir = IoDirection.READ
            elif read_pins & pin(PIN_WR) == 0:
                debug_print("  Dir: WRITE")
                io_dir = IoDirection.WRITE
            else:
                debug_print("  Error! could not determine read or write cycle!")
                return

            if (read_pins & pin(PIN_M_IO)):
                debug_print("  Space: MEMORY")
                io_space = IoSpace.MEMORY
            else:
                debug_print("  Space: IO")
                io_space = IoSpace.IO

            bhe = (read_pins & pin(PIN_BHE)) > 0
            a0 = address & 1 > 0

            if not bhe and not a0:
                debug_print("  Width: WORD")
                io_width = IoWidth.WHOLE_WORD
            elif not bhe and a0:
                debug_print("  Width: UPPER BYTE")
                io_width = IoWidth.UPPER_BYTE
            elif bhe and not a0:
                debug_print("  Width: LOWER BYTE")
                io_width = IoWidth.LOWER_BYTE
            else:
                debug_print("  Invalid state!")
                return

            controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK))
            cycle_num += 1
            debug_print(f"{cycle_num:04}")
            perform_read_write(controller, address, direction=io_dir, space=io_space, width=io_width)
            cycle_num += 1
        else:
            controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK))
            debug_print(f"  IDLE")

    controller.init()

def read_memory(address, width):
    global memory
    if width == IoWidth.UPPER_BYTE or width == IoWidth.LOWER_BYTE:
        return memory.get(address, 0)
    else:
        return memory.get(address, 0) | (memory.get(address + 1, 0) << 8)

def write_memory(address, data):
    pass

def read_io(address, width):
    if width == IoWidth.UPPER_BYTE or width == IoWidth.LOWER_BYTE:
        return 0x00
    else:
        return 0x0000

def write_io(address, data):
    pass

def perform_read_write(controller, address, direction, space, width):
    if direction == IoDirection.READ:
        controller.io_tri(pins(*(tristate_pins - DATA_PINS)))
        if space == IoSpace.MEMORY:
            data = read_memory(address, width)
        else:
            data = read_io(address, width)

        print(f"  Writing data 0x{data:04x}")
        data_pins = number_to_data_pins_high(data)
        controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK, *data_pins))
        controller.io_w(pins(*ALWAYS_HIGH_PINS, *data_pins))
        controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK, *data_pins))
        controller.io_w(pins(*ALWAYS_HIGH_PINS, *data_pins))
        controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK))
        controller.io_tri(pins(*tristate_pins))
    else:
        read_pins = controller.io_r()
        data = get_data_pins(read_pins)
        print(f"  Read data 0x{data:04x}")

        if space == IoSpace.MEMORY:
            write_memory(address, data)
        else:
            write_io(address, data)

        controller.io_w(pins(*ALWAYS_HIGH_PINS))
        controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK))
        controller.io_w(pins(*ALWAYS_HIGH_PINS))
        controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK))

def main():
    controller = setup("/dev/serial/by-id/usb-ProgHQ_Open-TL866_Programmer_33144A91666856D18E6084EC-if00")
    run(controller)

if __name__ == "__main__":
    main()
