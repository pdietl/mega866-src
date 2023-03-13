BITS 16
CPU 8086

SECTION .reset_vectort

reset:
    jmp far start

SECTION .text

start:
    nop
    jmp start
