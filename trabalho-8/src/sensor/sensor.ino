// Trabalho 8 - Arduino 1 (sensor): le a temperatura no potenciometro a cada
// 0,5 s e envia o valor ao Arduino 2 pela serial
//
// Placa        : Arduino Uno (ATmega328P @ 16 MHz)
// Compilador   : Arduino IDE / arduino-cli (core arduino:avr)
//
// Entrada:
//    A0 (PC0) -> cursor do potenciometro de 10 k (extremos em 5 V e GND)
//
// Saida:
//    D1 (TX) -> D0 (RX) do Arduino 2, GND comum, 9600 baud 8N1
//
// Temperatura:
//    O ADC de 10 bits (0 a 1023) e escalado para -100 a +250 graus C:
//       T = -100 + ADC * 350 / 1023
//    A conta e feita em decimos de grau, com inteiros e arredondada:
//       T10 = (ADC * 3500 + 511) / 1023 - 1000     (-1000 a +2500)
//
// Protocolo:
//    Uma linha de texto por leitura, com T10 em decimos de grau e '\n' no fim.
//    Exemplo: 748 = +74,8 C ; -466 = -46,6 C
//
// Tempo:
//    millis() marca a proxima leitura. O instante e somado de 500 em 500 ms,
//    entao o atraso de uma passagem nao se acumula nas seguintes.

const uint8_t PINO_POT = A0;
const unsigned long PERIODO_MS = 500;

unsigned long proxima;

// Converte a leitura do ADC em decimos de grau Celsius, arredondando.
long decimos(int adc) {
  return ((long)adc * 3500L + 511L) / 1023L - 1000L;
}

void setup() {
  Serial.begin(9600);
  proxima = millis();
}

void loop() {
  if ((long)(millis() - proxima) >= 0) {
    proxima += PERIODO_MS;
    int adc = analogRead(PINO_POT);
    Serial.println(decimos(adc));
  }
}
