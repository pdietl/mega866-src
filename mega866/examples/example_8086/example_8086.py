from gpio_controller import GpioController, all_earth_pins
from time import sleep
import sys

# address/data pins
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

PIN_BHE_S7 = 65
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

tristate_pins = set(all_earth_pins)

# Remove pins that should be always not tristated (i.e., always driven and not high-z)

for p in [PIN_READY, PIN_INTR, PIN_TEST, PIN_NMI, PIN_RESET, PIN_CLK, PIN_MN_MX, PIN_HOLD]:
    tristate_pins.remove(p)

ALWAYS_HIGH_PINS = [
    PIN_MN_MX
]

def pin(x):
    return 1 << (x - 1)


def pins(*pin_list):
    res = 0
    for p in pin_list:
        res |= pin(p)
    return res


def get_address_pins(input_pins):
    addr = 0
    for k, v in address_pins.items():
        if input_pins & (1 << (k - 1)):
            addr |= 1 << v
    return addr


def get_data_pins(input_pins):
    addr = 0
    for k, v in data_pins.items():
        if input_pins & (1 << (k - 1)):
            addr |= 1 << v
    return addr

# Jump to 0x0:0xc700
# ea 00 7c 00 00
#
# nop, jmp -1
# 90 eb fd

def init_memory():
    return {
        0x7c00: 0x90,
        0x7c01: 0xeb,
        0x7c02: 0xfd,

        0xffff0: 0xea,
        0xffff1: 0x00,
        0xffff2: 0x7c,
        0xffff3: 0x00,
        0xffff4: 0x00,
    }

def setup(tl866_path):
    controller = GpioController(earth_serial_device=tl866_path)
    controller.init()
    controller.io_w(0)
    controller.io_tri(pins(*tristate_pins))
    controller.vdd_volt(3) # 5.1V
    controller.vdd_pins(pins(PIN_VCC))
    controller.gnd_pins(pins(PIN_GND1, PIN_GND2))
    controller.vdd_en()
    sleep(0.3)
    sys.exit(0)
    controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK))
    # Now drive RESET high and perform at least 4 clock cycles
    controller.io_w(pins(*ALWAYS_HIGH_PINS))
    sleep(0.0001)
    controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_RESET))
    sleep(0.0001)
    for i in range(5):
        controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_RESET, PIN_CLK))
        sleep(0.0001)
        controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_RESET))
        sleep(0.0001)
    sleep(0.0001)
    controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_RESET, PIN_CLK))
    sleep(0.0001)
    controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK))
    sleep(0.0001)
    return controller

def run(controller):
    memory = init_memory()

    # Clock is high when entering this function
    # Following the reset, the CPU will perform an initial reset sequence of approximately 7 CLK cycles, and then it will fetch the instruction at address 0xffff0

    for i in range(50):
        controller.io_w(pins(*ALWAYS_HIGH_PINS))
        sleep(0.0001)
        controller.io_w(pins(*ALWAYS_HIGH_PINS, PIN_CLK))
        sleep(0.0001)
        read_pins = controller.io_r()
        address = get_address_pins(read_pins)
        print(f"0x{address:05x}")

    sleep(0.002)
    controller.io_w(pins(*ALWAYS_HIGH_PINS))
    controller.init()

def main():
    controller = setup("/dev/serial/by-id/usb-ProgHQ_Open-TL866_Programmer_33144A91666856D18E6084EC-if00")
    run(controller)

if __name__ == "__main__":
    main()
