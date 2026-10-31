# Brilho de um LED por PWM

Trabalho 5 de Microcontroladores (2026/2) · Bernardo Ivo Goltz (202112108)

Controle do brilho de um LED por PWM no ATmega328P a 16 MHz, simulado no SimulIDE 1.1.0. No 5a o duty cycle vem de um valor digital de 8 bits lido em oito chaves; no 5b, de um potenciômetro lido pelo ADC.

![Brilho do LED simulado no SimulIDE: 5a com as chaves e depois 5b com o potenciômetro](docs/simulide.gif)

## 5a: brilho por valor digital

[Circuito SimulIDE](simulide/brilho_digital.sim1)

### Hardware

| Pino | Ligação |
|---|---|
| PB0–PB7 | DIP de 8 chaves para o GND, pull-up interno ligado |
| PD6 (OC0A) | resistor de 220 Ω em série com o LED, catodo no GND; osciloscópio a 200 µs/div |
| AVcc, AREF | 5 V |

Chave fechada põe o pino em 0 e chave aberta deixa o pull-up em 1. A chave da esquerda é o bit 7. O byte lido em `PINB` vai direto para `OCR0A`, sem inverter: com todas as chaves fechadas (0) o LED apaga, com todas abertas (255) ele fica aceso o tempo todo. A entrada de 8 bits é a porta B porque PD6 é a saída do PWM. No SimulIDE, com o oscilador externo desligado (`Ext_Osc="false"`), PB6 e PB7 funcionam como GPIO; numa placa com cristal, como o Arduino Uno, esses dois pinos são do cristal.

### Timer0

Fast PWM de 8 bits (modo 3, `WGM01 = WGM00 = 1`, `WGM02 = 0`), TOP = `0xFF`, saída não inversora em OC0A (`COM0A1 = 1`) e prescaler 64 (`CS01 = CS00 = 1`):

```
f_PWM = f_clk / (N × 256) = 16 000 000 / (64 × 256) = 976,6 Hz
duty  = (OCR0A + 1) / 256
```

No Fast PWM a saída sobe no início do período e desce quando o contador passa de `OCR0A`, por isso o `+ 1`. Com `OCR0A = 0` sobra um pulso de 4 µs a cada 1,024 ms (0,4 %), e o LED fica apagado na prática; com 255 ele fica aceso o período inteiro.

### Código

[`src/brilho_digital.asm`](src/brilho_digital.asm)

```asm
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
```

## 5b: brilho por potenciômetro

[Circuito SimulIDE](simulide/brilho_adc.sim1)

### Hardware

| Pino | Ligação |
|---|---|
| PC0 (ADC0) | cursor de um potenciômetro de 10 kΩ, extremos em 5 V e GND |
| PD6 (OC0A) | resistor de 220 Ω em série com o LED, catodo no GND; osciloscópio a 200 µs/div |
| AVcc, AREF | 5 V no SimulIDE; na placa, AREF só com 100 nF para o GND |

### ADC

Referência AVcc (`REFS0 = 1`), canal 0, resultado alinhado à esquerda (`ADLAR = 1`) e prescaler 128 (`ADPS2..0 = 111`), o que dá 16 MHz / 128 = 125 kHz, dentro da faixa de 50 a 200 kHz do datasheet. O buffer digital do PC0 fica desligado (`ADC0D` em `DIDR0`). Com `ADLAR = 1`, `ADCH` guarda os 8 bits mais significativos da conversão, e o programa copia esse byte para `OCR0A`: 0 V apaga o LED e 5 V o deixa aceso.

### Timer0

O mesmo do 5a: Fast PWM modo 3, TOP = `0xFF`, não inversora em OC0A, prescaler 64, 976,6 Hz.

### Código

[`src/brilho_adc.asm`](src/brilho_adc.asm)

```asm
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
```

## Vídeo

LINK_PENDENTE — gravar a simulação e publicar no YouTube ou no Google Drive.
