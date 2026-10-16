"""Gera o circuito do SimulIDE (simulide/termometro.sim1).

As coordenadas dos pinos de cada componente seguem o formato do SimulIDE
1.1 (grade de 8 unidades). O ATmega328P fica espelhado (hflip) para que
PORTD fique do lado dos displays e PORTC (ADC) do lado dos sensores.

Uso: python3 tools/gera_simulide.py
"""

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "simulide", "termometro.sim1")

itens, fios = [], []
_n = [0]


def novo_id(prefixo):
    _n[0] += 1
    return f"{prefixo}-{_n[0]}"


def item(tipo, prefixo, pos, **props):
    cid = novo_id(prefixo)
    base = {"itemtype": tipo, "CircId": cid, "mainComp": "false",
            "Show_id": "false", "Show_Val": "false",
            "Pos": f"{pos[0]},{pos[1]}", "rotation": "0", "hflip": "1",
            "vflip": "1", "label": cid, "idLabPos": "-16,-24",
            "labelrot": "0", "valLabPos": "0,0", "valLabRot": "0"}
    base.update({k: str(v) for k, v in props.items()})
    itens.append(base)
    return cid


def node(pos):
    cid = novo_id("Node")
    itens.append({"itemtype": "Node", "CircId": cid, "mainComp": "false",
                  "Pos": f"{pos[0]},{pos[1]}"})
    return cid


def fio(ini, fim, pontos):
    fios.append({"itemtype": "Connector", "uid": novo_id("Connector"),
                 "startpinid": ini, "endpinid": fim,
                 "pointList": ",".join(f"{x},{y}" for x, y in pontos)})


# ----------------------------------------------------------------------------
# ATmega328P (DIP espelhado): direita = PORTD/PB0, esquerda = PORTC/AVcc
# ----------------------------------------------------------------------------
MCU = item("MCU", "mega328", (0, 0), Show_id="true", label="ATmega328P",
           idLabPos="-36,-20", Frequency="16 MHz",
           Program="../build/termometro.hex", Auto_Load="false",
           saveEepr="false", Logic_Symbol="false", Rst_enabled="false",
           Ext_Osc="false", Wdt_enabled="false", Clk_Out="false",
           SerialMon="-1", hflip="-1")
DIR = {"PORTD0": 16, "PORTD1": 24, "PORTD2": 32, "PORTD3": 40, "PORTD4": 48,
       "PORTD5": 88, "PORTD6": 96, "PORTD7": 104, "PORTB0": 112}
ESQ = {"PORTC3": 24, "PORTC2": 32, "PORTC1": 40, "PORTC0": 48,
       "PORTV1": 64, "PORTV0": 72}    # PORTV1 = AREF, PORTV0 = AVcc


def pino_mcu(nome):
    if nome in DIR:
        return f"{MCU}-{nome}", (8, DIR[nome])
    return f"{MCU}-{nome}", (-40, ESQ[nome])


# ----------------------------------------------------------------------------
# Segmentos: PD0..PD6 -> 7 x 220 R -> display de 2 digitos
# ----------------------------------------------------------------------------
RD = item("ResistorDip", "ResistorDip", (72, 40), ShowProp="Resistance",
          Resistance="220 Ω", Size="7", PullUp="false", PuVolt="5 V")
DISP = item("Seven Segment", "7Seg", (128, 40), Show_id="true",
            label="Display", idLabPos="0,-44", Color="Red",
            NumDisplays="2 _7seg", Vertical_Pins="false",
            CommonCathode="true", Threshold="2.4 V", MaxCurrent="0.006 A",
            Resistance="1 Ω")

for k, seg in enumerate("abcdefg"):
    y = 16 + 8 * k
    pin, (px, py) = pino_mcu(f"PORTD{k}")
    rl = f"{RD}-resistor{k}-ePin{2 * k}"
    rr = f"{RD}-resistor{k}-ePin{2 * k + 1}"
    if k < 5:
        fio(pin, rl, [(px, py), (56, y)])
    else:
        xj = 24 if k == 5 else 32
        fio(pin, rl, [(px, py), (xj, py), (xj, y), (56, y)])
    fio(rr, f"{DISP}-pin_{seg}", [(88, y), (104, y)])

# ----------------------------------------------------------------------------
# Habilitacao: PD7 -> 1k -> Q1 (dezenas), PB0 -> 1k -> Q2 (unidades)
# ----------------------------------------------------------------------------
RB1 = item("Resistor", "Resistor", (80, 104), Show_Val="true",
           ShowProp="Resistance", valLabPos="-12,-20",
           Resistance="1 kΩ")
Q1 = item("BJT", "Q", (128, 104), label="Q1", PNP="false", Gain="100", Vcrit="0.670736 V")
G1 = item("Ground", "Ground", (136, 144))
Q2 = item("BJT", "Q", (176, 104), label="Q2", PNP="false", Gain="100", Vcrit="0.670736 V",
          hflip="-1")
G2 = item("Ground", "Ground", (168, 144))
RB2 = item("Resistor", "Resistor", (224, 104), Show_Val="true",
           ShowProp="Resistance", valLabPos="-12,-20",
           Resistance="1 kΩ")

pin, p = pino_mcu("PORTD7")
fio(pin, f"{RB1}-lPin", [p, (64, 104)])
fio(f"{RB1}-rPin", f"{Q1}-base", [(96, 104), (112, 104)])
fio(f"{Q1}-collector", f"{DISP}-pin_commona", [(136, 88), (136, 72)])
fio(f"{Q1}-emiter", f"{G1}-Gnd", [(136, 120), (136, 128)])
fio(f"{Q2}-collector", f"{DISP}-pin_commonb", [(168, 88), (168, 72)])
fio(f"{Q2}-emiter", f"{G2}-Gnd", [(168, 120), (168, 128)])
fio(f"{Q2}-base", f"{RB2}-lPin", [(192, 104), (208, 104)])
pin, p = pino_mcu("PORTB0")
fio(pin, f"{RB2}-rPin",
    [p, (16, 112), (16, 168), (256, 168), (256, 104), (240, 104)])

# ----------------------------------------------------------------------------
# Sensores: 4 potenciometros de 10 k entre GND e 5 V simulam os
# transmissores (0..5 V = 0..100 graus C). Cursor -> PC0..PC3 (ADC0..ADC3).
# Uma ponta de prova em cada cursor mostra a tensao.
# ----------------------------------------------------------------------------
SX0, SDX, SY = -296, 64, -40          # 1o potenciometro e espacamento
INICIAL = (2200, 2400, 2600, 2800)    # cursores: 22, 24, 26, 28 graus C
for i in range(4):
    x = SX0 + SDX * i
    pot = item("Potentiometer", "Pot", (x, SY), ShowProp="Resistance",
               Show_id="true", label=f"Sensor {i + 1}", idLabPos="-36,-60",
               Show_Val="false", Resistance="10 kΩ",
               Value_Ohm=f"{INICIAL[i]} Ω", Slider="false", Scale="1")
    vcc = item("Rail", "Rail", (x + 16, SY - 32), rotation="90",
               ShowProp="Voltage", Show_Val="false", Voltage="5 V")
    gnd = item("Ground", "Ground", (x - 16, SY + 32))
    fio(f"{vcc}-outnod", f"{pot}-PinB", [(x + 16, SY - 16), (x + 16, SY)])
    fio(f"{pot}-PinA", f"{gnd}-Gnd", [(x - 16, SY), (x - 16, SY + 16)])

    n = node((x, SY + 32))
    sonda = item("Probe", "Probe", (x + 24, SY + 16), rotation="-45",
                 Show_Val="true", valLabPos="10,-18", valLabRot="45",
                 labelrot="45", idLabPos="16,-16", ShowVolt="true",
                 Threshold="2.5 V")
    fio(f"{pot}-PinM", f"{n}-0", [(x, SY + 16), (x, SY + 32)])
    fio(f"{n}-1", f"{sonda}-inpin", [(x, SY + 32), (x + 8, SY + 32)])
    pin, (px, py) = pino_mcu(f"PORTC{i}")
    fio(f"{n}-2", pin, [(x, SY + 32), (x, py), (px, py)])

# AVcc e AREF em 5 V. No SimulIDE 1.1 o ADC com REFS = 01 (AVcc) usa a
# tensao do pino AREF como referencia: so com AVcc ligado ele le 0.
AV = item("Rail", "Rail", (-80, 72), ShowProp="Voltage", Show_Val="false",
          Voltage="5 V")
n = node((-56, 72))
fio(f"{AV}-outnod", f"{n}-0", [(-64, 72), (-56, 72)])
pin, p = pino_mcu("PORTV0")
fio(f"{n}-1", pin, [(-56, 72), p])
pin, p = pino_mcu("PORTV1")
fio(f"{n}-2", pin, [(-56, 72), (-56, 64), p])

# ----------------------------------------------------------------------------
# Textos
# ----------------------------------------------------------------------------
item("TextComponent", "Text", (52, -8), Margin="0 _px", Border="0 _px",
     Color="#ffffdc", Opacity="0", Font="Helvetica [Cronyx]",
     Font_Color="#800000", Font_Size="8 _px", Fixed_Width="false",
     Text="7 x 220 Ω")
item("TextComponent", "Text", (-296, -152), Margin="6 _px", Border="1 _px",
     Color="#ffffdc", Opacity="1", Font="Helvetica [Cronyx]",
     Font_Color="#000080", Font_Size="10 _px", Fixed_Width="false",
     Text="Trabalho 4 - Media de 4 sensores de temperatura\n"
          "ATmega328P @ 16 MHz - sensores em ADC0..ADC3 (0..5 V para 0..100 C)\n"
          "Display: media de 10 a 55 C; Lo abaixo, Hi acima")


def escapa(v):
    # o SimulIDE le "=" e quebras de linha como entidades hexadecimais
    return (v.replace("&", "&amp;").replace('"', "&quot;")
             .replace("<", "&lt;").replace(">", "&gt;")
             .replace("\n", "&#xa;").replace("=", "&#x3D;"))


def xml_item(d):
    attrs = " ".join(f'{k}="{escapa(v)}"' for k, v in d.items())
    return f"<item {attrs} />"


def main():
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    linhas = ['<circuit version="1.1.0" rev="2224" stepSize="1000000" '
              'stepsPS="1000000" NLsteps="100000" reaStep="1000000" '
              'animate="0" >', ""]
    linhas += [xml_item(d) + "\n" for d in itens + fios]
    linhas.append("</circuit>")
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    print(f"{SAIDA}: {len(itens)} componentes, {len(fios)} fios")


if __name__ == "__main__":
    main()
