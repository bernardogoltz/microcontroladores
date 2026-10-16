"""Testes do termometro: executa o binario montado no simulador, aplica
tensoes conhecidas nas entradas ADC0..ADC3 e confere o que aparece nos
displays multiplexados.

Escala dos sensores: 0..5 V = 0..100 graus C (50 mV por grau).

Uso: python3 tools/testes.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from avrsim import AVR, F_CPU, build, read_display  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODIGO = build(os.path.join(RAIZ, "src", "termometro.asm"))

PERIODO_MS = 250        # intervalo entre leituras no firmware
V_POR_GRAU = 0.05


def volts(graus):
    return graus * V_POR_GRAU


def novo(temps):
    avr = AVR(CODIGO)
    aplica(avr, temps)
    return avr


def aplica(avr, temps):
    for i, t in enumerate(temps):
        avr.adc_v[i] = volts(t)


def mostra(temps, ms=300):
    avr = novo(temps)
    avr.run_ms(ms)
    return read_display(avr)


def esperado_por_codigo(codigo):
    """Modelo de referencia: media em contagens -> texto do display."""
    graus = int(codigo * 100 / 1024 + 0.5)
    if graus < 10:
        return "Lo"
    if graus > 55:
        return "Hi"
    return f"{graus:02d}"


CASOS = [
    # (descricao, temperaturas dos 4 sensores em graus C, display esperado)
    ("4 sensores iguais", (25, 25, 25, 25), "25"),
    ("4 sensores iguais", (42, 42, 42, 42), "42"),
    ("valores diferentes", (20, 30, 40, 50), "35"),
    ("valores diferentes", (12, 18, 33, 37), "25"),
    ("1 sensor fora, media ok", (0, 40, 40, 40), "30"),
    ("limite inferior", (10, 10, 10, 10), "10"),
    ("limite superior", (55, 55, 55, 55), "55"),
    ("media no limite", (5, 15, 8, 12), "10"),
    ("media no limite", (60, 50, 58, 52), "55"),
    ("abaixo da faixa", (9, 9, 9, 9), "Lo"),
    ("abaixo da faixa", (0, 0, 0, 0), "Lo"),
    ("acima da faixa", (56, 56, 56, 56), "Hi"),
    ("acima da faixa", (100, 100, 100, 100), "Hi"),
]


def teste_mudanca():
    """Muda as tensoes com o programa rodando e mede o atraso."""
    avr = novo((25, 25, 25, 25))
    avr.run_ms(1000)
    antes = read_display(avr)
    aplica(avr, (48, 50, 52, 50))
    t0 = avr.cycles
    while read_display(avr, window_ms=5) != "50":
        avr.run_ms(1)
        if avr.cycles - t0 > F_CPU:
            break
    atraso = (avr.cycles - t0) * 1000 / F_CPU
    avr.run_ms(100)
    depois = read_display(avr)
    ok = antes == "25" and depois == "50" and atraso <= PERIODO_MS + 6
    return ok, f"25 -> 50: [{antes}] -> [{depois}] em {atraso:.0f} ms"


def teste_periodo():
    """Confere a sequencia de canais (0, 1, 2, 3) e o intervalo entre
    leituras: 100 ticks de 256 x 156 ciclos = 249,6 ms."""
    avr = novo((30, 30, 30, 30))
    avr.run_ms(2000)
    log = avr.adc_log
    canais_ok = [c for _, c in log] == [0, 1, 2, 3] * (len(log) // 4)
    inicios = [t for t, c in log if c == 0]
    dts = [(b - a) * 1000 / F_CPU for a, b in zip(inicios, inicios[1:])]
    ok = (canais_ok and len(log) % 4 == 0 and len(dts) >= 7
          and all(abs(d - 249.6) < 0.01 for d in dts))
    return ok, (f"{len(log) // 4} leituras em 2 s, canais 0-1-2-3, "
                f"intervalo {min(dts):.2f}..{max(dts):.2f} ms")


def teste_varredura():
    """Todos os codigos de 0 a 1023 nos 4 canais, comparando com o modelo."""
    avr = novo((0, 0, 0, 0))
    erros = []
    vref = avr.vref
    for codigo in range(1024):
        v = (codigo + 0.5) * vref / 1024
        avr.adc_v[:4] = [v] * 4
        avr.run_ms(PERIODO_MS + 25)
        obtido = read_display(avr, window_ms=10)
        if obtido != esperado_por_codigo(codigo):
            erros.append((codigo, obtido))
    ok = not erros
    det = "1024 codigos conferidos" if ok else f"divergencias: {erros[:5]}"
    return ok, f"varredura 0..1023: {det}"


def main():
    falhas = 0
    for desc, temps, esperado in CASOS:
        obtido = mostra(temps)
        ok = obtido == esperado
        falhas += not ok
        t = " ".join(f"{x:>3}" for x in temps)
        print(f"{'OK  ' if ok else 'FALHA'} {desc:<24} {t} C "
              f"-> [{obtido}] esperado [{esperado}]")
    extras = (teste_mudanca, teste_periodo, teste_varredura)
    for f in extras:
        ok, msg = f()
        falhas += not ok
        print(f"{'OK  ' if ok else 'FALHA'} {msg}")
    total = len(CASOS) + len(extras)
    print(f"\n{total - falhas}/{total} testes passaram")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
