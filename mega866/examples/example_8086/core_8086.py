__all__ = ["Core8086", "IoWidth"]

from gpio_controller import GpioController, all_earth_pins
from time import sleep
from enum import Enum
import sys

class IoWidth(Enum):
    WHOLE_WORD = 1
    UPPER_BYTE = 2
    LOWER_BYTE = 3

class Core8086:
    # address/data pins
    # Map from Mega-866 pin numbers 1-160 to address/data line number on 8086
    _ADDRESS_PINS = {
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

    _DATA_PINS = frozenset([31, 27, 25, 23, 75, 73, 71, 69, 67, 9, 7, 5, 3, 1, 55, 53])

    _PIN_BHE = 65
    _PIN_RD = 13
    _PIN_READY = 41
    _PIN_INTR = 39
    _PIN_TEST = 37
    _PIN_NMI = 35
    _PIN_RESET = 45
    _PIN_CLK = 43
    _PIN_VCC = 49
    _PIN_GND1 = 51
    _PIN_GND2 = 47
    _PIN_MN_MX = 11
    _PIN_M_IO = 21
    _PIN_WR = 19
    _PIN_INTA = 33
    _PIN_ALE = 29
    _PIN_DT_R = 77
    _PIN_DEN = 79
    _PIN_HOLD = 15
    _PIN_HLDA = 17
    _PIN_LOCK = 19

    class _IoDirection(Enum):
        READ = 1
        WRITE = 2

    class _IoSpace(Enum):
        MEMORY = 1
        IO = 2


    _tristate_pins = set(all_earth_pins)

    # Remove pins that should be always not tristated (i.e., always driven and not high-z)

    for p in [_PIN_READY, _PIN_INTR, _PIN_TEST, _PIN_NMI, _PIN_RESET, _PIN_CLK, _PIN_MN_MX, _PIN_HOLD]:
        _tristate_pins.remove(p)

    _ALWAYS_HIGH_PINS = [
        _PIN_MN_MX,
        _PIN_READY,
    ]

    # 8086 reset sequnce is a series of at least 4 clock cycles while the RESET pin is held high
    # Then drive the RESET pin low and a sequence of approximately 7 clock cycles is needed for some
    # internal initialization that the 8086 performs. We know when the reset sequence is complete when the
    # 8086 tries to fetch from 0xffff0.
    # This function just sets up the mega-866 state and gets to the point of driving the RESET line low
    def __init__(self, tl866_path, mem_funcs_class, verbose=False):
        controller = GpioController(earth_serial_device=tl866_path)
        controller.init()
        controller.io_w(0)
        controller.io_tri(self._pins(*self._tristate_pins))
        controller.vdd_volt(3) # 5.1V
        controller.vdd_pins(self._pins(self._PIN_VCC))
        controller.gnd_pins(self._pins(self._PIN_GND1, self._PIN_GND2))
        controller.vdd_en()
        controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_CLK))
        # Now drive RESET high and perform at least 4 clock cycles
        controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS))
        controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_RESET))
        for i in range(5):
            controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_RESET, self._PIN_CLK))
            controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_RESET))
        controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_RESET, self._PIN_CLK))
        controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_CLK))

        self._controller = controller
        self._verbose = verbose
        self.mem_controller = mem_funcs_class


    # Translate Mega-866 pin number to a bit for an argument to a gpio controller function
    def _pin(self, x):
        return 1 << (x - 1)


    # Translate many Mega-866 pin numbers to bits for an argument to a gpio controller function
    def _pins(self, *pin_list):
        res = 0
        for p in pin_list:
            res |= self._pin(p)
        return res

    # Take the return of gpio_controller.io_r() and get the state of the address lines of the 8086 as one 20-bit number
    def _get_address_pins(self, input_pins):
        addr = 0
        for k, v in self._ADDRESS_PINS.items():
            if input_pins & (1 << (k - 1)):
                addr |= 1 << v
        return addr


    # Take the return of gpio_controller.io_r() and get the state of the data lines of the 8086 as one 20-bit number
    def _get_data_pins(self, input_pins):
        addr = 0
        for k, v in self._ADDRESS_PINS.items():
            if v < 16 and input_pins & (1 << (k - 1)):
                addr |= 1 << v
        return addr

    # Take a 16-bit binary number and turn it into a pin list to feed to the `pins` function which is in turn given to gpio_controller.io_w
    def _number_to_data_pins_high(self, num):
        assert num <= 65535
        pin_list = []
        for k, v in self._ADDRESS_PINS.items():
            if num & (1 << v):
                pin_list.append(k)
        return pin_list

    def _debug_print(self, *stuff):
        if self._verbose:
            print(*stuff)

    def run(self):
        cycle_num = 0

        # Clock is high when entering this function
        # Following the reset, the CPU will perform an initial reset sequence of approximately 7 CLK cycles, and then it will fetch the instruction at address 0xffff0

        while True:
            cycle_num += 1
            self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS))
            read_pins = self._controller.io_r()
            address = self._get_address_pins(read_pins)
            self._debug_print(f"{cycle_num:04}")
            if read_pins & self._pin(self._PIN_ALE):
                self._debug_print(f"  ALE high - latching address 0x{address:05x}")
                self._debug_print("  Beginning IO cycle")
                self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_CLK))
                self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS))

                cycle_num += 1
                self._debug_print(f"{cycle_num:04}")
                read_pins = self._controller.io_r()

                if read_pins & self._pin(self._PIN_RD) == 0:
                    self._debug_print(f"  Dir: READ")
                    io_dir = self._IoDirection.READ
                elif read_pins & self._pin(self.self._PIN_WR) == 0:
                    self._debug_print("  Dir: WRITE")
                    io_dir = self._IoDirection.WRITE
                else:
                    self._debug_print("  Error! could not determine read or write cycle!")
                    return

                if (read_pins & self._pin(self._PIN_M_IO)):
                    self._debug_print("  Space: MEMORY")
                    io_space = self._IoSpace.MEMORY
                else:
                    self._debug_print("  Space: IO")
                    io_space = self._IoSpace.IO

                bhe = (read_pins & self._pin(self._PIN_BHE)) > 0
                a0 = address & 1 > 0

                if not bhe and not a0:
                    self._debug_print("  Width: WORD")
                    io_width = IoWidth.WHOLE_WORD
                elif not bhe and a0:
                    self._debug_print("  Width: UPPER BYTE")
                    io_width = IoWidth.UPPER_BYTE
                elif bhe and not a0:
                    self._debug_print("  Width: LOWER BYTE")
                    io_width = IoWidth.LOWER_BYTE
                else:
                    self._debug_print("  Invalid state!")
                    return

                self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_CLK))
                cycle_num += 1
                self._debug_print(f"{cycle_num:04}")
                self._perform_read_write(address, direction=io_dir, space=io_space, width=io_width)
                cycle_num += 1
            else:
                self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_CLK))
                self._debug_print(f"  IDLE")

        self._controller.init()

    def _perform_read_write(self, address, direction, space, width):
        if direction == self._IoDirection.READ:
            self._controller.io_tri(self._pins(*(self._tristate_pins - self._DATA_PINS)))
            if space == self._IoSpace.MEMORY:
                data = self.mem_controller.read_memory(address, width)
            else:
                data = self.mem_controller.read_io(address, width)

            self._debug_print(f"  Writing data 0x{data:04x}")
            data_pins = self._number_to_data_pins_high(data)
            self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_CLK, *data_pins))
            self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, *data_pins))
            self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_CLK, *data_pins))
            self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, *data_pins))
            self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_CLK))
            self._controller.io_tri(self._pins(*self._tristate_pins))
        else:
            read_pins = self._controller.io_r()
            data = self._get_data_pins(read_pins)
            self._debug_print(f"  Read data 0x{data:04x}")

            if space == self._IoSpace.MEMORY:
                self.mem_controller.write_memory(address, data)
            else:
                self.mem_controller.write_io(address, data)

            self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS))
            self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_CLK))
            self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS))
            self._controller.io_w(self._pins(*self._ALWAYS_HIGH_PINS, self._PIN_CLK))

def _main():
    # Jump to 0x0:0x7c00
    # ea 00 7c 00 00
    #
    # nop, jmp -1
    # 90 eb fd

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

if __name__ == "__main__":
    _main()
