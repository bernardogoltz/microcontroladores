"""Gera docs/multiplexacao.gif a partir da simulacao do binario: camera
lenta (1 quadro = 0,25 ms) da varredura dos displays.

O brilho de cada segmento e a fracao de tempo em que ele ficou aceso na
janela do quadro, calculada a partir das escritas em PORTC/PORTD feitas
pelo programa simulado.

Uso: python3 tools/gera_gif.py
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
from avrsim import AVR, F_CPU, build, enables, segment_duty  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(RAIZ, "docs")

W, H = 760, 440
BG = (20, 22, 27)
TEXT = (225, 228, 235)
MUTED = (140, 146, 160)
SEG_ON = (255, 59, 48)
SEG_OFF = (48, 26, 28)
KEY_HIT = (255, 196, 0)
TRACE = (90, 200, 120)


def fonte(nome, tam):
    for p in (f"/usr/share/fonts/liberation-sans-fonts/{nome}.ttf",
              f"/usr/share/fonts/liberation-mono-fonts/{nome}.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, tam)
    return ImageFont.load_default(tam)


F_TIT = fonte("LiberationSans-Bold", 22)
F_TXT = fonte("LiberationSans-Regular", 16)
F_SMALL = fonte("LiberationSans-Regular", 13)


def mistura(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def segmentos_poligonos(x, y, w, h, t):
    """Poligonos dos segmentos a..g de um digito com canto superior (x, y)."""
    g = 3
    m = y + h / 2

    def horiz(cy):
        return [(x + t / 2 + g, cy), (x + t + g, cy - t / 2),
                (x + w - t - g, cy - t / 2), (x + w - t / 2 - g, cy),
                (x + w - t - g, cy + t / 2), (x + t + g, cy + t / 2)]

    def vert(cx, y0, y1):
        return [(cx, y0 + t / 2 + g), (cx + t / 2, y0 + t + g),
                (cx + t / 2, y1 - t - g), (cx, y1 - t / 2 - g),
                (cx - t / 2, y1 - t - g), (cx - t / 2, y0 + t + g)]

    xl, xr = x + t / 2, x + w - t / 2
    yt, yb = y + t / 2, y + h - t / 2
    return [horiz(yt),             # a
            vert(xr, yt, m),       # b
            vert(xr, m, yb),       # c
            horiz(yb),             # d
            vert(xl, m, yb),       # e
            vert(xl, yt, m),       # f
            horiz(m)]              # g


def desenha_displays(d, x, y, duty, ganho=2.0):
    d.rounded_rectangle((x, y, x + 270, y + 210), 12, fill=(8, 8, 10))
    for i, nome in enumerate(("dezenas (PD7)", "unidades (PB0)")):
        dx = x + 25 + i * 125
        for s, poly in enumerate(segmentos_poligonos(dx, y + 22, 95, 160, 17)):
            d.polygon(poly, fill=mistura(SEG_OFF, SEG_ON, duty[i][s] * ganho))
        d.text((dx + 47, y + 196), nome, font=F_SMALL, fill=MUTED,
               anchor="mm")


def ciclos(ms):
    return int(ms * F_CPU / 1000)


def multiplexacao(codigo):
    avr = AVR(codigo)
    avr.run_ms(30)
    for k in "53+28=":
        avr.key = k
        avr.run_ms(60)
        avr.key = None
        avr.run_ms(60)

    passo = ciclos(0.25)
    janela = 40                     # 40 x 0,25 ms = 10 ms
    t_ini = avr.cycles
    avr.run_until(t_ini + passo * janela)

    def nivel(t, disp):
        estado = 0
        for te, pb, pd in avr.port_log:
            if te > t:
                break
            estado = enables(pb, pd)[disp]
        return estado

    amostras = [(nivel(t_ini + i * passo + passo // 2, 0),
                 nivel(t_ini + i * passo + passo // 2, 1))
                for i in range(janela)]

    frames = []
    for i in range(janela):
        t0 = t_ini + i * passo
        duty = segment_duty(avr.port_log, t0, t0 + passo)
        img = Image.new("RGB", (W, 370), BG)
        d = ImageDraw.Draw(img)
        d.text((24, 18), "Multiplexação em câmera lenta", font=F_TIT, fill=TEXT)
        d.text((24, 48), f"t = {i * 0.25:5.2f} ms   (1 quadro = 0,25 ms; "
               "a interrupção do Timer0 troca o display a cada 2,5 ms)",
               font=F_SMALL, fill=MUTED)
        desenha_displays(d, 30, 100, duty, ganho=1.0)

        gx, gy, gw = 340, 120, 390
        for b, nome in enumerate(("PD7 dezenas", "PB0 unidades")):
            y0 = gy + b * 80
            d.text((gx, y0 - 8), nome, font=F_SMALL, fill=MUTED)
            pts = []
            for j, a in enumerate(amostras):
                yv = y0 + 50 - a[b] * 35
                xa, xb = gx + j * gw / janela, gx + (j + 1) * gw / janela
                pts += [(xa, yv), (xb, yv)]
            d.line(pts, fill=TRACE, width=3)
        cx = gx + (i + 0.5) * gw / janela
        d.line((cx, gy, cx, gy + 140), fill=KEY_HIT, width=2)
        d.text((gx, gy + 165), "Os dois displays nunca acendem juntos.\n"
               "A 200 Hz por display, o olho vê\nos dois acesos ao mesmo tempo.",
               font=F_TXT, fill=MUTED)
        frames.append(img)
    return frames, [120] * janela


def salva(nome, frames, tempos):
    caminho = os.path.join(DOCS, nome)
    frames[0].save(caminho, save_all=True, append_images=frames[1:],
                   duration=tempos, loop=0, optimize=True)
    print(f"{caminho}: {len(frames)} quadros")


def main():
    os.makedirs(DOCS, exist_ok=True)
    codigo = build(os.path.join(RAIZ, "src", "calculadora.asm"))
    salva("multiplexacao.gif", *multiplexacao(codigo))


if __name__ == "__main__":
    main()
