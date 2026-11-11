// Trabalho 9 - Escravo I2C no endereco 0x08: liga e apaga o LED da placa
//
// Placa        : Arduino Uno (ATmega328P @ 16 MHz)
// Compilador   : Arduino IDE / arduino-cli (core arduino:avr)
//
// Ligacoes:
//    A4 (SDA) e A5 (SCL) -> SDA e SCL do mestre, pull-up de 4,7 k para 5 V
//    D13 (PB5) -> LED da placa (LED_BUILTIN)
//    GND comum
//
// Comandos recebidos (1 byte):
//    0x01 -> liga o LED
//    0x00 -> apaga o LED
//    outro valor -> ignorado
//
// onReceive roda dentro da interrupcao do TWI: so grava o comando. O loop()
// e que escreve na serial, para nao imprimir dentro da interrupcao.

#include <Wire.h>

const uint8_t ENDERECO = 0x08;
const uint8_t LIGA = 0x01;
const uint8_t APAGA = 0x00;

volatile int16_t recebido = -1;         // ultimo byte recebido (-1 = nenhum)

void recebe(int) {
  while (Wire.available()) {
    uint8_t c = Wire.read();
    if (c == LIGA || c == APAGA) {
      digitalWrite(LED_BUILTIN, c == LIGA ? HIGH : LOW);
    }
    recebido = c;
  }
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  Serial.begin(9600);
  Wire.begin(ENDERECO);                 // escravo no endereco 0x08
  Wire.onReceive(recebe);
  Serial.println("Escravo I2C 0x08 - LED da placa em D13");
}

void loop() {
  noInterrupts();
  int16_t c = recebido;
  recebido = -1;
  interrupts();
  if (c < 0) return;

  Serial.print("Recebido 0x");
  if (c < 0x10) Serial.print('0');
  Serial.print(c, HEX);
  if (c == LIGA) Serial.println(" -> LED ligado");
  else if (c == APAGA) Serial.println(" -> LED apagado");
  else Serial.println(" -> ignorado");
}
