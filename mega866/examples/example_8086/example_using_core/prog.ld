ENTRY(reset)

SECTIONS
{
    . = 0x400;
    .data : { *(.data) }
    .bss : { *(.bss) }

    . = 0x80000;
    .text : { *(.text) }

    ASSERT(. <= 0xffff0, "Data and code overflowed into reset vector!")
}
