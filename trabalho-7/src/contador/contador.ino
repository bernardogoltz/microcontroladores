// Trabalho 7 - Contador UP/DOWN com dois botoes, pull-up interno e debounce
//
// Placa        : Arduino Uno (ATmega328P @ 16 MHz)
// Compilador   : Arduino IDE / arduino-cli (core arduino:avr)
//
// Entradas (botoes para o GND, pull-up interno ligado):
//    D2 (PD2) -> botao UP   (solto = HIGH, pressionado = LOW)
//    D3 (PD3) -> botao DOWN (solto = HIGH, pressionado = LOW)
//
// Saida:
//    Serial a 9600 baud (D0 RX, D1 TX): "Contador: N" no inicio e a cada
//    alteracao do contador.
//
// Debounce:
//    Cada botao guarda a ultima leitura do pino e o instante (millis) em que
//    ela mudou. Uma leitura so e aceita depois de ficar DEBOUNCE_MS sem mudar.
//    O clique conta na transicao aceita de HIGH para LOW (ao pressionar).
//    Segurar o botao conta uma vez; soltar nao conta.

const uint8_t PINO_UP = 2;
const uint8_t PINO_DOWN = 3;
const unsigned long DEBOUNCE_MS = 50;

struct Botao {
  uint8_t pino;
  uint8_t estavel;          // estado aceito depois do debounce
  uint8_t leitura;          // ultima leitura bruta do pino
  unsigned long mudou;      // millis() da ultima mudanca da leitura
};

Botao up = {PINO_UP, HIGH, HIGH, 0};
Botao down = {PINO_DOWN, HIGH, HIGH, 0};
int contador = 0;

void iniciaBotao(Botao &b) {
  pinMode(b.pino, INPUT_PULLUP);
  b.leitura = digitalRead(b.pino);
  b.estavel = b.leitura;    // botao ja pressionado no reset nao conta
  b.mudou = millis();
}

// Retorna true uma vez por clique (borda de descida ja filtrada).
bool clicou(Botao &b) {
  uint8_t agora = digitalRead(b.pino);
  unsigned long t = millis();

  if (agora != b.leitura) {             // pino mudou: reinicia a espera
    b.leitura = agora;
    b.mudou = t;
    return false;
  }
  if (agora != b.estavel && t - b.mudou >= DEBOUNCE_MS) {
    b.estavel = agora;                  // ficou DEBOUNCE_MS sem mudar
    return agora == LOW;                // pressionou (soltar nao conta)
  }
  return false;
}

void mostraContador() {
  Serial.print("Contador: ");
  Serial.println(contador);
}

void setup() {
  Serial.begin(9600);
  iniciaBotao(up);
  iniciaBotao(down);
  mostraContador();                     // valor inicial: 0
}

void loop() {
  if (clicou(up)) {
    contador++;
    mostraContador();
  }
  if (clicou(down)) {
    contador--;
    mostraContador();
  }
}
