; Trabalho 5a - Brilho de um LED por PWM com valor digital de 8 bits
;
; Microcontrolador : ATmega328P @ 16 MHz
; Montador         : AVR Assembler (Microchip Studio) / avra
;
; Entrada (8 chaves DIP para o GND, pull-up interno ligado):
;    PB7..PB0 -> chaves 1..8 (chave fechada = bit 0, aberta = bit 1)
;    A porta D nao serve de entrada de 8 bits porque PD6 e a saida PWM.
;    Com o oscilador externo desligado, PB6 e PB7 sao GPIO comuns.
;
; Saida:
;    PD6 (OC0A) -> resistor de 220 R -> LED -> GND
;
; PWM:
;    Timer0 em Fast PWM de 8 bits (modo 3, TOP = 0xFF), saida nao
;    inversora em OC0A, prescaler 64:
;        f = 16 MHz / (64 * 256) = 976,6 Hz
;    Duty = (OCR0A + 1) / 256. OCR0A recebe PINB sem inverter: 0 apaga o
;    LED (sobra um pulso de 4 us por periodo, 0,4 %), 255 deixa o LED
;    aceso o tempo todo.

.include "m328Pdef.inc"

.def temp     = r16

.cseg
.org 0x0000
    rjmp reset

.org INT_VECTORS_SIZE

reset:
    ldi temp, high(RAMEND)      ; pilha no fim da SRAM
    out SPH, temp
    ldi temp, low(RAMEND)
    out SPL, temp

    ser temp                    ; DDRB = 0 desde o reset: PB0..PB7 entradas
    out PORTB, temp             ; pull-up interno nas 8 entradas
    sbi DDRD, PD6               ; PD6 (OC0A) saida

    ldi temp, (1<<COM0A1)|(1<<WGM01)|(1<<WGM00)
    out TCCR0A, temp            ; Fast PWM modo 3, nao inversora em OC0A
    ldi temp, (1<<CS01)|(1<<CS00)
    out TCCR0B, temp            ; WGM02 = 0, prescaler 64

; Copia o valor das chaves para o duty do PWM (OCR0A comeca em 0)
laco:
    in temp, PINB               ; 8 bits das chaves (fechada = 0)
    out OCR0A, temp             ; duty = (PINB + 1) / 256
    rjmp laco
