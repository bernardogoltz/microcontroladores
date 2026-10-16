"""Gera o circuito do SimulIDE (simulide/termometro.sim1).

As coordenadas dos pinos de cada componente seguem o formato do SimulIDE
1.1 (grade de 8 unidades), conferidas nos exemplos que acompanham o
programa. O ATmega328P fica espelhado (hflip) para que PORTD fique do lado
dos displays e PORTC/PORTB do lado dos sensores e da chave.

Uso: python3 tools/gera_simulide.py
"""

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "simulide", "termometro.sim1")

# Posicao inicial de cada potenciometro (Value_Ohm de 10 kOhm)
POT_OHM = (2500, 5000, 7500)

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


def terra(pino, p, pos_terra):
    """Liga o pino ao GND colocado em pos_terra (pino Gnd 16 acima)."""
    g = item("Ground", "Ground", pos_terra)
    gx, gy = pos_terra
    pontos = [p]
    for q in ((gx, p[1]), (gx, gy - 16)):
        if q != pontos[-1]:
            pontos.append(q)
    fio(pino, f"{g}-Gnd", pontos)


def texto(pos, txt, tam=9, cor="#000080", borda=0):
    item("TextComponent", "Text", pos, Margin=f"{3 if borda else 0} _px",
         Border=f"{borda} _px", Color="#ffffdc", Opacity="1" if borda else "0",
         Font="Helvetica [Cronyx]", Font_Color=cor, Font_Size=f"{tam} _px",
         Fixed_Width="false", Text=txt)


# ----------------------------------------------------------------------------
# ATmega328P (DIP espelhado): direita = PORTD/PB0, esquerda = PORTC/PB1..PB5
# ----------------------------------------------------------------------------
MCU = item("MCU", "mega328", (0, 0), Show_id="true", label="ATmega328P",
           idLabPos="-36,-20", Frequency="16 MHz",
           Program="../build/termometro.hex", Auto_Load="false",
           saveEepr="false", Logic_Symbol="false", Rst_enabled="false",
           Ext_Osc="false", Wdt_enabled="false", Clk_Out="false",
           SerialMon="-1", hflip="-1")
DIR = {"PORTD0": 16, "PORTD1": 24, "PORTD2": 32, "PORTD3": 40, "PORTD4": 48,
       "PORTD5": 88, "PORTD6": 96, "PORTD7": 104, "PORTB0": 112}
ESQ = {"PORTC5": 8, "PORTC4": 16, "PORTC3": 24, "PORTC2": 32, "PORTC1": 40,
       "PORTC0": 48, "PORTV1": 64, "PORTV0": 72, "PORTB5": 80,
       "PORTB4": 88, "PORTB3": 96, "PORTB2": 104, "PORTB1": 112}


def pino_mcu(nome):
    if nome in DIR:
        return f"{MCU}-{nome}", (8, DIR[nome])
    return f"{MCU}-{nome}", (-40, ESQ[nome])


# ----------------------------------------------------------------------------
# Segmentos: PD0..PD6 -> 7 x 220 R -> display de 3 digitos
# ----------------------------------------------------------------------------
RD = item("ResistorDip", "ResistorDip", (72, 40), ShowProp="Resistance",
          Resistance="220 Ω", Size="7", PullUp="false", PuVolt="5 V")
DISP = item("Seven Segment", "7Seg", (128, 40), Show_id="true",
            label="Temperatura (ºC)", idLabPos="0,-44", Color="Red",
            NumDisplays="3 _7seg", Vertical_Pins="false",
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
# Habilitacao: PD7 -> Q1 (centenas), PB0 -> Q2 (dezenas), PB1 -> Q3
# (unidades), cada um com 1 kOhm na base. Catodos comuns em x = 136/168/200.
# ----------------------------------------------------------------------------
def resistor(pos, rot="0"):
    return item("Resistor", "Resistor", pos, Show_Val="true",
                ShowProp="Resistance", valLabPos="-12,-20",
                Resistance="1 kΩ", rotation=rot)


def bjt(pos, rotulo, flip="1"):
    return item("BJT", "Q", pos, label=rotulo, Show_id="true",
                idLabPos="-4,-28" if flip == "1" else "-12,-28",
                PNP="false", Gain="100", Vcrit="0.670736 V", hflip=flip)


# Q1: centenas
RB1 = resistor((80, 104))
Q1 = bjt((128, 104), "Q1")
pin, p = pino_mcu("PORTD7")
fio(pin, f"{RB1}-lPin", [p, (64, 104)])
fio(f"{RB1}-rPin", f"{Q1}-base", [(96, 104), (112, 104)])
fio(f"{Q1}-collector", f"{DISP}-pin_commona", [(136, 88), (136, 72)])
terra(f"{Q1}-emiter", (136, 120), (136, 144))

# Q2: dezenas (mais abaixo, coletor sobe ate o catodo do meio)
RB2 = resistor((112, 176))
Q2 = bjt((160, 176), "Q2")
pin, p = pino_mcu("PORTB0")
fio(pin, f"{RB2}-lPin", [p, (16, 112), (16, 176), (96, 176)])
fio(f"{RB2}-rPin", f"{Q2}-base", [(128, 176), (144, 176)])
fio(f"{Q2}-collector", f"{DISP}-pin_commonb", [(168, 160), (168, 72)])
terra(f"{Q2}-emiter", (168, 192), (168, 216))

# Q3: unidades (espelhado, base pela direita)
Q3 = bjt((208, 104), "Q3", flip="-1")
RB3 = resistor((248, 104))
fio(f"{Q3}-collector", f"{DISP}-pin_commonc", [(200, 88), (200, 72)])
terra(f"{Q3}-emiter", (200, 120), (200, 144))
fio(f"{Q3}-base", f"{RB3}-lPin", [(224, 104), (232, 104)])
pin, p = pino_mcu("PORTB1")
fio(pin, f"{RB3}-rPin",
    [p, (-56, 112), (-56, 240), (288, 240), (288, 104), (264, 104)])


# ----------------------------------------------------------------------------
# Sensores: 3 potenciometros de 10 kOhm entre 5 V e GND, cursor no ADC.
#   Potenciometro com rotation -90: PinB em cima (0,-16), PinA embaixo
#   (0,+16), cursor PinM a direita (+16,0). Uma ponta de prova mostra a
#   tensao de cada canal.
# ----------------------------------------------------------------------------
POT_X = {0: -328, 1: -232, 2: -136}
POT_Y = -40
ADC_Y = {0: 48, 1: 40, 2: 32}
for ch in range(3):
    x = POT_X[ch]
    texto((x - 36, POT_Y - 96), f"Sensor {ch}\nADC{ch} (PC{ch})", tam=9,
          cor="#000080")
    rail = item("Rail", "Rail", (x, POT_Y - 48), rotation="90",
                Show_Val="false", ShowProp="Voltage", Voltage="5 V")
    pot = item("Potentiometer", "Pot", (x, POT_Y), rotation="-90",
               ShowProp="Resistance", label=f"Sensor {ch}",
               Show_Val="false", Resistance="10 kΩ",
               Value_Ohm=f"{POT_OHM[ch]} Ω", Slider="false", Scale="1")
    fio(f"{rail}-outnod", f"{pot}-PinB", [(x, POT_Y - 32), (x, POT_Y - 16)])
    terra(f"{pot}-PinA", (x, POT_Y + 16), (x, POT_Y + 40))
    xv = x + 32
    n = node((xv, POT_Y))
    fio(f"{pot}-PinM", f"{n}-0", [(x + 16, POT_Y), (xv, POT_Y)])
    pin, (mx, my) = pino_mcu(f"PORTC{ch}")
    fio(f"{n}-1", pin, [(xv, POT_Y), (xv, ADC_Y[ch]), (mx, my)])
    pr = item("Probe", "Probe", (xv + 24, POT_Y - 40), rotation="-45",
              Show_Val="true", valLabPos="18,-10", valLabRot="45",
              ShowVolt="true", Threshold="2.5 V", labelrot="45")
    fio(f"{n}-2", f"{pr}-inpin", [(xv, POT_Y), (xv, POT_Y - 24),
                                  (xv + 8, POT_Y - 24)])

# AVcc e AREF em 5 V (referencia do ADC)
rail = item("Rail", "Rail", (-80, 72), Show_Val="true", ShowProp="Voltage",
            valLabPos="-28,-8", Voltage="5 V")
pin, p = pino_mcu("PORTV0")
n = node((-48, 72))
fio(f"{rail}-outnod", f"{n}-0", [(-64, 72), (-48, 72)])
fio(f"{n}-1", pin, [(-48, 72), p])
pin, p = pino_mcu("PORTV1")
fio(f"{n}-2", pin, [(-48, 72), (-48, 64), p])


# ----------------------------------------------------------------------------
# Chave seletora: DIP de 3 vias exclusivo (so uma fechada por vez), comum no
# GND. Via k (canal ADCk) -> PB(4-k), com pull-up interno.
# ----------------------------------------------------------------------------
SW_X, SW_Y = -96, 112
SW = item("SwitchDip", "Chave", (SW_X, SW_Y), label="Canal", Size="3",
          Exclusive="true", CommonPin="true", State="1")
texto((SW_X - 60, SW_Y + 8), "Chave\nseletora", tam=8, cor="#000080")
for k in range(3):
    pin, (mx, my) = pino_mcu(f"PORTB{4 - k}")
    fio(f"{SW}-switch{k}-pinN", pin, [(SW_X + 16, SW_Y - 24 + 8 * k),
                                      (mx, my)])
    texto((SW_X - 52, SW_Y - 30 + 8 * k), f"ADC{k}", tam=7, cor="#404040")
terra(f"{SW}-switch0-pinP", (SW_X - 8, SW_Y - 24), (SW_X - 24, SW_Y + 8))


# ----------------------------------------------------------------------------
# Titulo
# ----------------------------------------------------------------------------
texto((-336, -208), "Trabalho 3 - Termômetro de 3 canais (0 a 120 ºC)\n"
      "ATmega328P @ 16 MHz - ADC0..ADC2, chave seletora, "
      "3 displays multiplexados", tam=10, borda=1)


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
