// Trabalho final - Angulo em torno do eixo X do ADXL335 (GY-61) no OLED.
// LED no D8 acende a partir de 30 graus para qualquer lado.
//
// Placa: Arduino Uno. Bibliotecas: Adafruit SSD1306 e Adafruit GFX.
// Ligacoes:
//   3.3V -> VCC do GY-61 e do OLED     GND -> GND dos dois
//   A1   -> Y do GY-61                 A2  -> Z do GY-61
//   A3   -> 3.3V (referencia)          A4/A5 -> SDA/SCL do OLED (0x3C)
//   D8   -> 220 ohm -> LED -> GND

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

const uint8_t PINO_Y = A1, PINO_Z = A2, PINO_REF = A3, LED = 8;
const float ZERO = 512;     
const float ESCALA = 102.4;  
const int LIMIAR = 30;       
const float ALFA = 0.05;     /

Adafruit_SSD1306 tela(128, 64, &Wire, -1);
float angulo = 0;
int mostrado = 0;

// Media de 16 leituras; a primeira apos trocar de canal e descartada.
float le(uint8_t pino) {
  analogRead(pino);
  unsigned int soma = 0;
  for (uint8_t i = 0; i < 16; i++) soma += analogRead(pino);
  return soma / 16.0;
}

// Le o eixo em g. Dividir pelos 3,3 V lidos em A3 tira o erro dos 5 V do USB.
float leG(uint8_t pino, float ref) {
  return (le(pino) / ref * 1024 - ZERO) / ESCALA;
}

void setup() {
  pinMode(LED, OUTPUT);
  tela.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  // Desliga os pull-ups internos (5 V) de SDA/SCL: o OLED esta em 3,3 V.
  digitalWrite(SDA, LOW);
  digitalWrite(SCL, LOW);
  tela.cp437(true);
  tela.setTextColor(SSD1306_WHITE);
  tela.setTextSize(2);
}

void loop() {
  float ref = le(PINO_REF);
  float novo = atan2(leG(PINO_Y, ref), leG(PINO_Z, ref)) * RAD_TO_DEG;
  angulo += ALFA * (novo - angulo);                         // filtro passa-baixa
  if (fabs(angulo - mostrado) > 0.8) mostrado = round(angulo);  // histerese

  digitalWrite(LED, abs(mostrado) >= LIMIAR);

  tela.clearDisplay();
  tela.setCursor(0, 24);
  tela.print(F("X  "));
  tela.print(mostrado);
  tela.write(248);  // simbolo de grau
  tela.display();

  delay(50);
}
