"""Gera o circuito do SimulIDE (simulide/calculadora.sim1).

As coordenadas dos pinos de cada componente seguem o formato do SimulIDE
1.1 (grade de 8 unidades). O ATmega328P fica espelhado (hflip) para que
PORTD fique do lado dos displays e PORTB/PORTC do lado do teclado.

Uso: python3 tools/gera_simulide.py
"""

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "simulide", "calculadora.sim1")

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
# ATmega328P (DIP espelhado): direita = PORTD/PB0, esquerda = PORTC/PB1..PB5
# ----------------------------------------------------------------------------
MCU = item("MCU", "mega328", (0, 0), Show_id="true", label="ATmega328P",
           idLabPos="-36,-20", Frequency="16 MHz",
           Program="../build/calculadora.hex", Auto_Load="false",
           saveEepr="false", Logic_Symbol="false", Rst_enabled="false",
           Ext_Osc="false", Wdt_enabled="false", Clk_Out="false",
           SerialMon="-1", hflip="-1")
DIR = {"PORTD0": 16, "PORTD1": 24, "PORTD2": 32, "PORTD3": 40, "PORTD4": 48,
       "PORTD5": 88, "PORTD6": 96, "PORTD7": 104, "PORTB0": 112}
ESQ = {"PORTC5": 8, "PORTC4": 16, "PORTC3": 24, "PORTC2": 32,
       "PORTB4": 88, "PORTB3": 96, "PORTB2": 104, "PORTB1": 112}


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
# Teclado: 4x3 (digitos, C, =) + coluna de funcoes (+, -) em botoes
#   linhas PC5..PC2, colunas PB1..PB4
# ----------------------------------------------------------------------------
KX, KY = -232, -20
KP = item("KeyPad", "KeyPad", (KX, KY), Show_id="true", label="Teclado",
          idLabPos="0,-20", Rows="4", Cols="3", Key_Labels="789456123C0=")


def pino_linha(r):
    return f"{KP}-Pin{r}", (KX + 48, KY + 8 + 16 * r)


def pino_coluna(c):
    return f"{KP}-Pin{4 + c}", (KX + 16 * c, KY + 72)


# linha r -> PC(5-r); x do degrau de cada linha
DEGRAU = {0: -64, 1: -80, 2: -96, 3: -104}
NO_PUSH = {2: -152, 3: -120}          # linha 2: "+", linha 3: "-"
nos_linha = {}
for r in range(4):
    pin_kp, (kx, ky) = pino_linha(r)
    pin_mcu, (mx, my) = pino_mcu(f"PORTC{5 - r}")
    xd = DEGRAU[r]
    if r in NO_PUSH:
        xn = NO_PUSH[r]
        n = node((xn, ky))
        nos_linha[r] = n
        fio(pin_kp, f"{n}-0", [(kx, ky), (xn, ky)])
        fio(f"{n}-1", pin_mcu, [(xn, ky), (xd, ky), (xd, my), (mx, my)])
    else:
        fio(pin_kp, pin_mcu, [(kx, ky), (xd, ky), (xd, my), (mx, my)])

# colunas 0..2 -> PB1..PB3
for c in range(3):
    pin_kp, (kx, ky) = pino_coluna(c)
    pin_mcu, (mx, my) = pino_mcu(f"PORTB{c + 1}")
    fio(pin_kp, pin_mcu, [(kx, ky), (kx, my), (mx, my)])

# coluna 3 (botoes + e -) -> PB4
PUSH = {}
for r, rot in ((2, "+"), (3, "−")):
    x = NO_PUSH[r]
    PUSH[r] = item("Push", "Push", (x, 60), rotation="90", Show_id="true",
                   label=rot, idLabPos="-22,-8", labelrot="-90",
                   Norm_Close="false", Poles="1")
n_col3 = node((-120, 88))
fio(f"{nos_linha[2]}-2", f"{PUSH[2]}-pinP0", [(-152, 20), (-152, 44)])
fio(f"{nos_linha[3]}-2", f"{PUSH[3]}-pinP0", [(-120, 36), (-120, 44)])
fio(f"{PUSH[2]}-switch0pinN", f"{n_col3}-0", [(-152, 76), (-152, 88),
                                               (-120, 88)])
fio(f"{PUSH[3]}-switch0pinN", f"{n_col3}-1", [(-120, 76), (-120, 88)])
pin_mcu, p = pino_mcu("PORTB4")
fio(f"{n_col3}-2", pin_mcu, [(-120, 88), p])

# ----------------------------------------------------------------------------
# Textos
# ----------------------------------------------------------------------------
item("TextComponent", "Text", (52, -8), Margin="0 _px", Border="0 _px",
     Color="#ffffdc", Opacity="0", Font="Helvetica [Cronyx]",
     Font_Color="#800000", Font_Size="8 _px", Fixed_Width="false",
     Text="7 x 220 Ω")
item("TextComponent", "Text", (-208, -96), Margin="6 _px", Border="1 _px",
     Color="#ffffdc", Opacity="1", Font="Helvetica [Cronyx]",
     Font_Color="#000080", Font_Size="10 _px", Fixed_Width="false",
     Text="Trabalho 2 - Calculadora com teclado matricial\n"
          "ATmega328P @ 16 MHz - displays multiplexados (Timer0, 2,5 ms)")


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
