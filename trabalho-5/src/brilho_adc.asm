; Trabalho 5b - Brilho de um LED por PWM controlado por potenciometro
;
; Microcontrolador : ATmega328P @ 16 MHz
; Montador         : AVR Assembler (Microchip Studio) / avra
;
; Entrada:
;    ADC0 (PC0) -> cursor de um potenciometro de 10 k (extremos em 5 V e GND)
;    Referencia AVcc (5 V), ADC a 16 MHz / 128 = 125 kHz, entrada digital
;    do PC0 desligada (DIDR0). Resultado alinhado a esquerda (ADLAR = 1):
;    ADCH tem os 8 bits mais significativos da conversao de 10 bits.
;
; Saida:
;    PD6 (OC0A) -> resistor de 220 R -> LED -> GND
;
; PWM (o mesmo do 5a):
;    Timer0 em Fast PWM de 8 bits (modo 3, TOP = 0xFF), saida nao
;    inversora em OC0A, prescaler 64:
;        f = 16 MHz / (64 * 256) = 976,6 Hz
;    Duty = (OCR0A + 1) / 256, com OCR0A = ADCH (0 V apaga, 5 V acende).

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

    sbi DDRD, PD6               ; PD6 (OC0A) saida; PC0 ja e entrada sem pull-up

    ldi temp, (1<<ADC0D)
    sts DIDR0, temp             ; desliga a entrada digital do PC0
    ldi temp, (1<<REFS0)|(1<<ADLAR)
    sts ADMUX, temp             ; referencia AVcc, alinhado a esquerda, ADC0
    ldi temp, (1<<ADEN)|(1<<ADPS2)|(1<<ADPS1)|(1<<ADPS0)
    sts ADCSRA, temp            ; ADC ligado, 16 MHz / 128 = 125 kHz

    ldi temp, (1<<COM0A1)|(1<<WGM01)|(1<<WGM00)
    out TCCR0A, temp            ; Fast PWM modo 3, nao inversora em OC0A
    ldi temp, (1<<CS01)|(1<<CS00)
    out TCCR0B, temp            ; WGM02 = 0, prescaler 64

; Converte o ADC0 e copia os 8 bits altos para o duty (OCR0A comeca em 0)
laco:
    lds temp, ADCSRA
    ori temp, (1<<ADSC)         ; inicia uma conversao
    sts ADCSRA, temp
espera_adc:
    lds temp, ADCSRA
    sbrc temp, ADSC             ; ADSC volta a 0 no fim da conversao
    rjmp espera_adc

    lds temp, ADCH              ; 8 bits mais significativos (ADLAR = 1)
    out OCR0A, temp             ; duty = (ADCH + 1) / 256
    rjmp laco
