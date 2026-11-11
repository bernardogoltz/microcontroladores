# Botão no mestre e LED no escravo pelo I2C

Trabalho 9 de Microcontroladores (2026/2) · Bernardo Ivo Goltz (202112108)

Dois Arduino Uno, programados em C++ com a biblioteca `Wire`, ligados pelo barramento I2C (TWI). O mestre lê um botão com debounce e, a cada mudança, envia um comando ao escravo: ligar o LED ao pressionar e apagar ao soltar. O escravo responde no endereço 0x08 e liga ou apaga o LED da placa (pino 13). Simulado no SimulIDE.

Os trabalhos da disciplina, com circuito, código e simulação, estão em https://github.com/bernardogoltz/microcontroladores

[Circuito SimulIDE](simulide/i2c.sim1)

## Hardware

SDA (A4) e SCL (A5) das duas placas são ligados entre si, cada linha com um resistor de pull-up de 4,7 kΩ para 5 V, e os GNDs são comuns. O TWI só puxa as linhas para 0. O nível 1 vem dos pull-ups. A `Wire` também liga os pull-ups internos de A4 e A5 (20 kΩ a 50 kΩ), fracos demais para dispensar os externos.

No mestre, o botão liga D2 ao GND, com o pull-up interno (`INPUT_PULLUP`): solto, o pino lê `HIGH`, e pressionado, `LOW`. No escravo, o LED é o da placa, no pino 13 (`LED_BUILTIN`).

| Placa | Pino | Função |
|---|---|---|
| Mestre | D2 | Botão para o GND, pull-up interno |
| Mestre e escravo | A4 (SDA) | Dados do I2C, pull-up de 4,7 kΩ |
| Mestre e escravo | A5 (SCL) | Clock do I2C, pull-up de 4,7 kΩ |
| Escravo | D13 | LED da placa |

No SimulIDE, as duas placas estão no mesmo circuito e os serial monitors das duas abrem junto. O LED da placa é o ponto amarelo ao lado do pino 13 do escravo. No SimulIDE o GND é comum a todo o circuito.

## Cálculos

### SCL de 100 kHz

`Wire.setClock(100000)` grava o divisor do TWI:

```
SCL  = F_CPU / (16 + 2 × TWBR × 4^TWPS)
TWBR = (16 000 000 / 100 000 − 16) / 2 = 72
```

com prescaler 1 (`TWPS` = 0). Esse já é o padrão da biblioteca; a chamada fica no código para deixar a frequência explícita. O escravo não gera clock: o SCL vem do mestre.

Com 4,7 kΩ, a corrente com a linha em 0 é 5 V / 4,7 kΩ ≈ 1,1 mA, abaixo dos 3 mA do modo padrão do I2C.

### Debounce

O mestre guarda a última leitura de D2 e o instante, em `millis()`, em que ela mudou. Um estado novo só é aceito depois de ficar 20 ms sem mudar, e toda oscilação do contato reinicia a espera. Não há `delay()`.

## Comandos

Endereço de 7 bits do escravo: 0x08 (`Wire.begin(0x08)` grava `TWAR` = 0x08 << 1 = 0x10). Cada comando é uma escrita de 1 byte:

```
START | endereco 0x08 + W | dado | STOP
dado = 0x01: liga o LED (botão pressionado)
dado = 0x00: apaga o LED (botão solto)
```

O mestre guarda o último comando que o escravo confirmou com ACK e só transmite quando o botão, já sem trepidação, pede outro. Segurar o botão não repete o comando. Ao ligar, o mestre envia 0x00 e deixa o LED num estado conhecido.

`Wire.endTransmission()` devolve 0 no sucesso, 2 quando o endereço fica sem ACK, 3 quando o dado fica sem ACK, 4 em outro erro e 5 em tempo esgotado. Numa falha, por exemplo com o escravo desligado, o comando é repetido 100 ms depois. `Wire.setWireTimeout(25000, true)` limita cada transmissão a 25 ms e reinicia o TWI se o barramento travar.

No escravo, `Wire.onReceive(recebe)` roda dentro da interrupção do TWI: liga ou apaga o LED e guarda o byte. A escrita na serial fica no `loop()`, fora da interrupção.

## Serial

As duas placas escrevem na serial a 9600 baud. Ao pressionar e soltar o botão:

```
Mestre                          Escravo
Mestre I2C - botao em D2, ...   Escravo I2C 0x08 - LED da placa em D13
Solto -> 0x00 (ACK)             Recebido 0x00 -> LED apagado
Pressionado -> 0x01 (ACK)       Recebido 0x01 -> LED ligado
Solto -> 0x00 (ACK)             Recebido 0x00 -> LED apagado
```

## Compilação

Cada sketch fica numa pasta com o mesmo nome, como a Arduino IDE exige. Na IDE: abrir o arquivo, escolher a placa Arduino Uno e carregar. Pelo `arduino-cli`:

```
arduino-cli compile --fqbn arduino:avr:uno --output-dir build src/mestre
arduino-cli compile --fqbn arduino:avr:uno --output-dir build src/escravo
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno src/mestre
```

O circuito carrega `../build/mestre.ino.hex` e `../build/escravo.ino.hex`.

## Código

### Mestre

[`src/mestre/mestre.ino`](src/mestre/mestre.ino)

```cpp
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
```

### Escravo

[`src/escravo/escravo.ino`](src/escravo/escravo.ino)

```cpp
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
```

## Vídeo

LINK_PENDENTE — gravar a simulação e publicar no YouTube ou no Google Drive.
