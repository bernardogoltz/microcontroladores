# Temperatura pela serial entre dois Arduinos, com média das 10 últimas

Trabalho 8 de Microcontroladores (2026/2) · Bernardo Ivo Goltz (202112108)

Dois Arduino Uno, programados em C++. O Arduino 1 lê um potenciômetro a cada 0,5 s, converte em temperatura de −100 °C a +250 °C e envia o valor pela serial. O Arduino 2 recebe e escreve no serial monitor a temperatura atual e a média das 10 últimas. Simulado no SimulIDE.

Os trabalhos da disciplina, com circuito, código e simulação, estão em https://github.com/bernardogoltz/microcontroladores

[Circuito SimulIDE](simulide/serial.sim1)

## Hardware

O potenciômetro é de 10 kΩ, com os extremos em 5 V e GND e o cursor em A0 do Arduino 1. O TX do Arduino 1 (pino 1) vai no RX do Arduino 2 (pino 0), e os GNDs são ligados. O TX do Arduino 2 é a saída para o serial monitor: no Uno, vai para o conversor USB-serial.

| Arduino | Pino | Função |
|---|---|---|
| 1 (sensor) | A0 | Cursor do potenciômetro |
| 1 (sensor) | D1 (TX) | Envia a temperatura ao Arduino 2 |
| 2 (monitor) | D0 (RX) | Recebe a temperatura do Arduino 1 |
| 2 (monitor) | D1 (TX) | Texto para o serial monitor |

No SimulIDE, as duas placas estão no mesmo circuito e os serial monitors das duas abrem junto. O do Arduino 1 mostra o que ele envia. O do Arduino 2 mostra no "Input" o que ele recebe e no "Output" a temperatura e a média. O AREF do Arduino 1 está em 5 V porque o ADC do SimulIDE usa esse pino como referência. Numa placa real, o AREF fica desligado. No SimulIDE o GND é comum a todo o circuito.

## Cálculos

### Serial a 9600 baud

`Serial.begin(9600)` usa 8N1. A 16 MHz, a biblioteca do Arduino liga a velocidade dupla (`U2X0` = 1):

```
UBRR0 = 16 000 000 / (8 × 9600) − 1 = 207,3 → 207
baud  = 16 000 000 / (8 × (207 + 1)) = 9615 baud (erro de +0,16 %)
```

O erro fica bem abaixo da tolerância de cerca de ±2 % do receptor com 8 bits de dados.

### Temperatura

```
T = −100 + ADC × 350 / 1023  °C
```

ADC 0 dá −100 °C e ADC 1023 dá +250 °C. A resolução é 350 / 1023 = 0,342 °C por passo do ADC, então a temperatura tem uma casa decimal. O inteiro esconderia a resolução, e a segunda casa seria ruído. A conta é feita em décimos de grau, com `long`, e arredondada:

```
T10 = (ADC × 3500 + 511) / 1023 − 1000    (−1000 a +2500)
```

`ADC × 3500` chega a 3 580 500 e não cabe num `int` de 16 bits. Somar 511, metade de 1023, arredonda para o décimo mais próximo. Exemplos: ADC 0 → −100,0 °C; ADC 511 → +74,8 °C; ADC 1023 → +250,0 °C. Não há `float`: o ATmega328P não tem ponto flutuante em hardware, e o resultado em décimos é exato.

### Leitura a cada 0,5 s

O instante da próxima leitura fica em `proxima` e é somado de 500 em 500 ms. Se uma passagem do `loop()` atrasar, a leitura seguinte não atrasa junto. Com `delay(500)`, o tempo da leitura e do envio se acumularia a cada ciclo. A comparação `(long)(millis() - proxima) >= 0` continua certa quando `millis()` volta a zero, após 49,7 dias.

### Protocolo

O Arduino 1 envia `T10` em texto com `Serial.println`, uma linha por leitura: `748` é +74,8 °C e `-466` é −46,6 °C. O fim de linha separa os valores, então o Arduino 2 se acerta sozinho se ligar no meio de uma transmissão. No máximo 7 bytes por leitura (`-1000\r\n`), cerca de 7 ms.

O Arduino 2 junta os caracteres até o `\n` e converte com `strtol`. Uma linha vazia, com algo que não seja número, longa demais ou fora de −1000 a +2500 é descartada. `Serial.parseInt()` não foi usado: ele espera até 1 s quando não chega nada e devolve 0 tanto para "0" quanto para lixo.

### Média das 10 últimas

As 10 últimas temperaturas ficam num buffer circular de 10 posições. Uma soma corrente evita somar as 10 a cada leitura: com o buffer cheio, a mais antiga sai da soma e a nova entra.

```
M10 = round(soma / n)
```

`n` é quantas temperaturas já estão guardadas. Antes de chegar a 10, a média é das `n` que existem (n = 1 a 10), e não das 10 com zeros, que errariam a média nos primeiros 5 s. A divisão inteira do C++ trunca em direção a zero, então `divArredonda` arredonda também os negativos.

### Saída

Uma linha a cada leitura, com sinal e uma casa decimal, alinhada à direita:

```
Trabalho 8 - temperatura e media das 10 ultimas
T=  +74,8 C   Media=  +74,8 C   n=1
T=  +74,8 C   Media=  +74,8 C   n=2
...
T=  +43,7 C   Media=  +71,7 C   n=10
T=   -4,5 C   Media=  +63,8 C   n=10
```

`snprintf` monta o texto com inteiros, porque o `printf` do AVR não formata `float`. Uma linha tem até 38 bytes e leva cerca de 40 ms a 9600 baud, bem menos que os 0,5 s entre leituras.

## Compilação

Cada sketch fica numa pasta com o mesmo nome, como a Arduino IDE exige. Na IDE: abrir o arquivo, escolher a placa Arduino Uno e carregar. Pelo `arduino-cli`:

```
arduino-cli compile --fqbn arduino:avr:uno --output-dir build src/sensor
arduino-cli compile --fqbn arduino:avr:uno --output-dir build src/monitor
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno src/sensor
```

O circuito carrega `../build/sensor.ino.hex` e `../build/monitor.ino.hex`. Na placa real, os pinos 0 e 1 também estão ligados ao conversor USB-serial. Para gravar, desligue o fio entre os dois Arduinos.

## Código

### Arduino 1 — sensor

[`src/sensor/sensor.ino`](src/sensor/sensor.ino)

```cpp
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
```

### Arduino 2 — monitor

[`src/monitor/monitor.ino`](src/monitor/monitor.ino)

```cpp
// Trabalho 8 - Arduino 2 (monitor): recebe a temperatura do Arduino 1 e
// mostra no serial monitor a temperatura e a media das 10 ultimas
//
// Placa        : Arduino Uno (ATmega328P @ 16 MHz)
// Compilador   : Arduino IDE / arduino-cli (core arduino:avr)
//
// Entrada:
//    D0 (RX) <- D1 (TX) do Arduino 1, GND comum, 9600 baud 8N1
//    Uma linha por leitura: temperatura em decimos de grau e '\n'
//
// Saida:
//    D1 (TX) -> USB, serial monitor a 9600 baud, uma linha por leitura:
//       T=  +74,8 C   Media=  +74,8 C   n=1
//
// Media:
//    Buffer circular com as 10 ultimas temperaturas. Antes de ter 10, a media
//    e das n que ja chegaram (n = 1 a 10), para nao contar posicoes vazias.

const uint8_t N_MEDIA = 10;
const long T_MIN = -1000;               // -100,0 C
const long T_MAX = 2500;                // +250,0 C

long ultimas[N_MEDIA];                  // temperaturas em decimos de grau
uint8_t pos = 0;                        // proxima posicao a gravar
uint8_t n = 0;                          // quantas posicoes estao cheias
long soma = 0;                          // soma das n temperaturas guardadas

char linha[12];                         // texto recebido ate o '\n'
uint8_t tam = 0;
bool estourou = false;                  // linha maior que o buffer

// Escreve decimos de grau com sinal, 3 digitos inteiros e uma casa: "  +74,8".
void imprimeDecimos(long v) {
  char s[10];
  char sinal = v < 0 ? '-' : '+';
  if (v < 0) v = -v;
  snprintf(s, sizeof s, "%c%ld,%ld", sinal, v / 10, v % 10);
  for (uint8_t i = strlen(s); i < 7; i++) Serial.print(' ');
  Serial.print(s);
}

// Divisao arredondada para o inteiro mais proximo, tambem para negativos.
long divArredonda(long a, long b) {
  return a >= 0 ? (a + b / 2) / b : (a - b / 2) / b;
}

void guarda(long t) {
  if (n == N_MEDIA) soma -= ultimas[pos];   // sai a mais antiga
  else n++;
  ultimas[pos] = t;
  soma += t;
  pos = (pos + 1) % N_MEDIA;
}

void mostra(long t) {
  Serial.print("T=");
  imprimeDecimos(t);
  Serial.print(" C   Media=");
  imprimeDecimos(divArredonda(soma, n));
  Serial.print(" C   n=");
  Serial.println(n);
}

// Trata uma linha completa. Linha vazia, com lixo ou fora da faixa e ignorada.
void processa() {
  linha[tam] = '\0';
  char *fim;
  long t = strtol(linha, &fim, 10);
  if (tam == 0 || *fim != '\0' || t < T_MIN || t > T_MAX) return;
  guarda(t);
  mostra(t);
}

void setup() {
  Serial.begin(9600);
  Serial.println("Trabalho 8 - temperatura e media das 10 ultimas");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (!estourou) processa();
      tam = 0;
      estourou = false;
    } else if (tam < sizeof linha - 1) {
      linha[tam++] = c;
    } else {
      estourou = true;                  // descarta a linha inteira
    }
  }
}
```

## Vídeo

LINK_PENDENTE — gravar a simulação e publicar no YouTube ou no Google Drive.
