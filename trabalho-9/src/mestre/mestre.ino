// Trabalho 9 - Mestre I2C: botao com debounce que liga e apaga o LED do escravo
//
// Placa        : Arduino Uno (ATmega328P @ 16 MHz)
// Compilador   : Arduino IDE / arduino-cli (core arduino:avr)
//
// Ligacoes:
//    D2 (PD2) -> botao para o GND, pull-up interno (solto = HIGH)
//    A4 (SDA) e A5 (SCL) -> SDA e SCL do escravo, pull-up de 4,7 k para 5 V
//    GND comum
//
// Comandos (escrita de 1 byte no endereco 0x08, SCL de 100 kHz):
//    0x01 -> liga o LED (botao pressionado)
//    0x00 -> apaga o LED (botao solto)
//
// O comando so e enviado quando o estado do botao, ja filtrado, fica diferente
// do ultimo estado que o escravo confirmou. Se o envio falhar (escravo sem
// resposta), ele e repetido a cada 100 ms.
//
// Serial a 9600 baud: uma linha por comando enviado, com o resultado.

#include <Wire.h>

const uint8_t PINO_BOTAO = 2;
const uint8_t ENDERECO_ESCRAVO = 0x08;
const uint8_t LIGA = 0x01;
const uint8_t APAGA = 0x00;
const unsigned long DEBOUNCE_MS = 20;
const unsigned long REPETE_MS = 100;

uint8_t estavel;                        // estado aceito depois do debounce
uint8_t leitura;                        // ultima leitura bruta do pino
unsigned long mudou;                    // millis() da ultima mudanca da leitura
int enviado = -1;                       // ultimo comando confirmado (-1 = nenhum)
bool falhou = false;                    // a ultima tentativa nao teve ACK
unsigned long tentativa;                // millis() da ultima tentativa com falha

// Le o botao e devolve o estado sem trepidacao: so aceita uma leitura que
// ficou DEBOUNCE_MS sem mudar.
uint8_t botao() {
  uint8_t agora = digitalRead(PINO_BOTAO);
  unsigned long t = millis();
  if (agora != leitura) {
    leitura = agora;
    mudou = t;
  } else if (agora != estavel && t - mudou >= DEBOUNCE_MS) {
    estavel = agora;
  }
  return estavel;
}

// Envia um byte ao escravo. Retorna o codigo de endTransmission():
// 0 = ok, 2 = endereco sem ACK, 3 = dado sem ACK, 4 = outro erro, 5 = timeout.
uint8_t envia(uint8_t comando) {
  Wire.beginTransmission(ENDERECO_ESCRAVO);
  Wire.write(comando);
  return Wire.endTransmission();        // START, SLA+W, dado, STOP
}

void setup() {
  pinMode(PINO_BOTAO, INPUT_PULLUP);
  Serial.begin(9600);
  Wire.begin();                         // mestre
  Wire.setClock(100000);                // TWBR = 72, SCL de 100 kHz
  Wire.setWireTimeout(25000, true);     // nao trava se o barramento prender
  leitura = digitalRead(PINO_BOTAO);
  estavel = leitura;
  mudou = millis();
  Serial.println("Mestre I2C - botao em D2, escravo 0x08");
}

void loop() {
  uint8_t comando = (botao() == LOW) ? LIGA : APAGA;
  if (comando == enviado) return;                         // nada mudou
  if (falhou && millis() - tentativa < REPETE_MS) return; // espera para repetir

  uint8_t erro = envia(comando);
  Serial.print(comando == LIGA ? "Pressionado -> 0x01 " : "Solto -> 0x00 ");
  if (erro == 0) {
    enviado = comando;
    falhou = false;
    Serial.println("(ACK)");
  } else {
    falhou = true;
    tentativa = millis();
    Serial.print("(falha ");
    Serial.print(erro);
    Serial.println(")");
  }
}
