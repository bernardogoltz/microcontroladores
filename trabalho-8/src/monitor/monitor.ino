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
