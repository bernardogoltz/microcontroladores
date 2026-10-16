;==============================================================================
; Trabalho 4 - Media de 4 sensores de temperatura em 2 displays de 7 segmentos
;
; Microcontrolador : ATmega328P @ 16 MHz
; Montador         : AVR Assembler (Microchip Studio) / avra
;
; Sensores (4 transmissores de temperatura, 0..5 V = 0..100 graus C):
;    ADC0 (PC0) -> sensor 1        ADC2 (PC2) -> sensor 3
;    ADC1 (PC1) -> sensor 2        ADC3 (PC3) -> sensor 4
;    Referencia AVcc (5 V), resolucao de 10 bits.
;
; Displays (catodo comum, multiplexados):
;    PD0..PD6 -> segmentos a..g (ativos em 1)
;    PD7      -> catodo do display das dezenas  (via transistor, ativo em 1)
;    PB0      -> catodo do display das unidades (via transistor, ativo em 1)
;
; Funcionamento:
;    - A cada 250 ms le os 4 canais, soma as leituras em 16 bits e divide
;      por 4 (2 deslocamentos a direita): media de 0 a 1023.
;    - Converte a media em graus: T = (media * 100 + 512) / 1024
;                                   = (media * 25 + 128) / 256
;    - 10..55 graus: mostra o valor. Abaixo de 10: "Lo". Acima de 55: "Hi".
;
; Temporizacao:
;    Timer0 em modo CTC gera interrupcao a cada 2,5 ms (400 Hz).
;    A cada interrupcao um display e aceso (200 Hz por display) e o laco
;    principal recebe um tick; a cada 100 ticks faz uma nova leitura.
;==============================================================================

.include "m328Pdef.inc"

;------------------------------------------------------------------------------
; Constantes
;------------------------------------------------------------------------------
.equ DIG_DEZ    = 7             ; PD7: habilita display das dezenas
.equ DIG_UNI    = 0             ; PB0: habilita display das unidades

.equ N_SENSORES = 4             ; ADC0..ADC3
.equ N_TICKS    = 100           ; 100 x 2,5 ms = 250 ms entre leituras
.equ ESCALA     = 25            ; media * 25 / 256 = media * 100 / 1024

.equ T_MIN      = 10            ; faixa valida, em graus C
.equ T_MAX      = 55

.equ SEG_L      = 0x38          ; d e f
.equ SEG_O      = 0x5C          ; c d e g
.equ SEG_H      = 0x76          ; b c e f g
.equ SEG_I      = 0x04          ; c

;------------------------------------------------------------------------------
; Registradores
;------------------------------------------------------------------------------
.def disp_dez = r2              ; padrao de segmentos do display das dezenas
.def disp_uni = r3              ; padrao de segmentos do display das unidades
.def mux      = r4              ; bit 0 indica qual display acender
.def temp     = r16
.def temp2    = r17
.def aux      = r18
.def canal    = r19             ; canal do ADC sendo lido
.def soma_l   = r20             ; soma das leituras / media (16 bits)
.def soma_h   = r21
.def graus    = r22             ; temperatura media em graus C
.def ticks    = r23             ; ticks ate a proxima leitura
.def adc_l    = r24             ; ultima conversao do ADC
.def adc_h    = r25

;------------------------------------------------------------------------------
; Vetores de interrupcao
;------------------------------------------------------------------------------
.cseg
.org 0x0000
    rjmp reset
.org OC0Aaddr
    rjmp isr_timer0

.org INT_VECTORS_SIZE

;------------------------------------------------------------------------------
; Inicializacao
;------------------------------------------------------------------------------
reset:
    ldi temp, high(RAMEND)      ; pilha no fim da SRAM
    out SPH, temp
    ldi temp, low(RAMEND)
    out SPL, temp

    ser temp                    ; PD0..PD6 segmentos, PD7 dezenas
    out DDRD, temp
    clr temp
    out PORTD, temp             ; displays apagados
    ldi temp, (1<<DIG_UNI)      ; PB0 saida (unidades)
    out DDRB, temp
    clr temp
    out PORTB, temp
    out DDRC, temp              ; PC0..PC3 entradas analogicas, sem pull-up
    out PORTC, temp

    ldi temp, (1<<ADC3D)|(1<<ADC2D)|(1<<ADC1D)|(1<<ADC0D)
    sts DIDR0, temp             ; desliga a entrada digital dos pinos do ADC
    ldi temp, (1<<REFS0)        ; referencia AVcc, canal 0
    sts ADMUX, temp
    ldi temp, (1<<ADEN)|(1<<ADPS2)|(1<<ADPS1)|(1<<ADPS0)
    sts ADCSRA, temp            ; ADC ligado, 16 MHz / 128 = 125 kHz

    ldi temp, (1<<WGM01)        ; Timer0 em modo CTC
    out TCCR0A, temp
    ldi temp, 155               ; 16 MHz / 256 / 156 = 400,6 Hz
    out OCR0A, temp
    ldi temp, (1<<CS02)         ; prescaler 256
    out TCCR0B, temp
    ldi temp, (1<<OCIE0A)       ; habilita interrupcao de comparacao A
    sts TIMSK0, temp

    clr mux
    clr disp_dez                ; displays apagados ate a 1a leitura
    clr disp_uni
    ldi ticks, 1                ; 1a leitura no primeiro tick
    sei

;------------------------------------------------------------------------------
; Laco principal: espera o tick do Timer0 e, a cada N_TICKS ticks, le os
; sensores, calcula a media e atualiza os displays.
;------------------------------------------------------------------------------
laco:
    sbis GPIOR0, 0              ; espera o tick sinalizado pela interrupcao
    rjmp laco
    cbi GPIOR0, 0

    dec ticks
    brne laco
    ldi ticks, N_TICKS

    rcall le_sensores           ; soma = media das 4 leituras (0..1023)
    rcall converte              ; graus = temperatura em graus C (0..100)
    rcall mostra_temperatura
    rjmp laco

;------------------------------------------------------------------------------
; Interrupcao do Timer0 (2,5 ms): multiplexacao dos displays
;------------------------------------------------------------------------------
isr_timer0:
    push temp
    in temp, SREG
    push temp

    cbi PORTD, DIG_DEZ          ; apaga os dois displays antes de trocar
    cbi PORTB, DIG_UNI

    sbrs mux, 0
    rjmp isr_dezenas
    out PORTD, disp_uni         ; bit 7 = 0: dezenas continuam apagadas
    sbi PORTB, DIG_UNI
    rjmp isr_fim
isr_dezenas:
    out PORTD, disp_dez
    sbi PORTD, DIG_DEZ
isr_fim:
    inc mux
    sbi GPIOR0, 0               ; sinaliza o tick para o laco principal

    pop temp
    out SREG, temp
    pop temp
    reti

;------------------------------------------------------------------------------
; le_sensores: le ADC0..ADC3 e deixa a media em soma_h:soma_l
;------------------------------------------------------------------------------
le_sensores:
    clr soma_l
    clr soma_h
    clr canal
le_proximo:
    mov temp, canal
    rcall le_adc                ; adc_h:adc_l = leitura do canal (0..1023)
    add soma_l, adc_l           ; soma em 16 bits: no maximo 4 x 1023 = 4092
    adc soma_h, adc_h
    inc canal
    cpi canal, N_SENSORES
    brne le_proximo

    lsr soma_h                  ; media = soma / 4
    ror soma_l
    lsr soma_h
    ror soma_l
    ret

;------------------------------------------------------------------------------
; le_adc: converte o canal em temp e devolve o resultado em adc_h:adc_l
;------------------------------------------------------------------------------
le_adc:
    ori temp, (1<<REFS0)        ; referencia AVcc + canal
    sts ADMUX, temp
    lds temp, ADCSRA
    ori temp, (1<<ADSC)         ; inicia a conversao
    sts ADCSRA, temp
espera_adc:
    lds temp, ADCSRA            ; ADSC volta a 0 no fim (13 ciclos de ADC)
    sbrc temp, ADSC
    rjmp espera_adc
    lds adc_l, ADCL             ; ADCL antes de ADCH
    lds adc_h, ADCH
    ret

;------------------------------------------------------------------------------
; converte: graus = (media * 25 + 128) / 256, com media em soma_h:soma_l
;   media * 25 = soma_l * 25 + (soma_h * 25) * 256  (cabe em 16 bits)
;   O byte alto do produto e a parte inteira; o bit 7 do byte baixo arredonda.
;------------------------------------------------------------------------------
converte:
    ldi temp, ESCALA
    mul soma_l, temp            ; r1:r0 = soma_l * 25
    mov aux, r0
    mov graus, r1
    mul soma_h, temp            ; r0 = soma_h * 25 (soma_h <= 3)
    add graus, r0
    clr r1
    sbrc aux, 7                 ; fracao >= 0,5: arredonda para cima
    inc graus
    ret

;------------------------------------------------------------------------------
; mostra_temperatura: escreve graus nos buffers dos displays,
;   ou "Lo" / "Hi" fora da faixa T_MIN..T_MAX
;------------------------------------------------------------------------------
mostra_temperatura:
    cpi graus, T_MIN
    brlo mostra_baixo
    cpi graus, T_MAX + 1
    brsh mostra_alto

    mov temp2, graus
    rcall div10                 ; aux = dezenas, temp2 = unidades
    mov temp, aux
    rcall segmentos
    mov disp_dez, temp
    mov temp, temp2
    rcall segmentos
    mov disp_uni, temp
    ret

mostra_baixo:
    ldi temp, SEG_L
    ldi temp2, SEG_O
    rjmp mostra_texto
mostra_alto:
    ldi temp, SEG_H
    ldi temp2, SEG_I
mostra_texto:
    mov disp_dez, temp
    mov disp_uni, temp2
    ret

;------------------------------------------------------------------------------
; div10: temp2 = temp2 mod 10, aux = temp2 / 10
;------------------------------------------------------------------------------
div10:
    clr aux
div10_laco:
    cpi temp2, 10
    brlo div10_fim
    subi temp2, 10
    inc aux
    rjmp div10_laco
div10_fim:
    ret

;------------------------------------------------------------------------------
; segmentos: converte o digito em temp (0..9) no padrao de 7 segmentos
;------------------------------------------------------------------------------
segmentos:
    ldi ZH, high(tabela_7seg*2)
    ldi ZL, low(tabela_7seg*2)
    add ZL, temp
    ldi temp, 0
    adc ZH, temp
    lpm temp, Z
    ret

;------------------------------------------------------------------------------
; Tabela em memoria de programa
;------------------------------------------------------------------------------
tabela_7seg:            ;  0     1     2     3     4     5     6     7     8     9
    .db                  0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F
