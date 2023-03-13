.code16
.arch i8086

.section reset

_reset:
    ljmp _start!, _start

.text

_start:
    nop
    jmp _start
