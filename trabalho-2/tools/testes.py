"""Testes da calculadora: executa o binario montado no simulador, pressiona
teclas e confere o que aparece nos displays multiplexados.

Uso: python3 tools/testes.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from avrsim import AVR, build, read_display  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODIGO = build(os.path.join(RAIZ, "src", "calculadora.asm"))

APERTO_MS = 60      # tempo com a tecla pressionada
SOLTO_MS = 60       # tempo com a tecla solta


def novo():
    avr = AVR(CODIGO)
    avr.run_ms(30)
    return avr


def tecla(avr, k):
    avr.key = k
    avr.run_ms(APERTO_MS)
    avr.key = None
    avr.run_ms(SOLTO_MS)


def digita(avr, seq):
    for k in seq:
        tecla(avr, k)
    return read_display(avr)


CASOS = [
    # (teclas, display esperado)
    ("", "00"),
    ("5", "05"),
    ("53", "53"),
    ("537", "37"),              # 3o digito continua deslocando
    ("53+", "53"),              # operador mantem o 1o numero visivel
    ("53+2", "02"),
    ("53+28", "28"),
    ("53+28=", "81"),
    ("90-45=", "45"),
    ("12-15=", "-3"),
    ("10-19=", "-9"),
    ("10-20=", "Er"),           # -10 nao cabe em 2 displays
    ("75+50=", "Er"),
    ("99+0=", "99"),
    ("50+50=", "Er"),
    ("7-7=", "00"),
    ("8+", "08"),
    ("8+=", "16"),              # sem 2o numero: usa o mesmo valor
    ("12+3=+4=", "19"),         # resultado vira 1o operando
    ("12+3=5", "05"),           # digito apos resultado inicia numero novo
    ("75+50=+3=", "03"),        # apos erro o operador e ignorado
    ("53+28C", "00"),
    ("53+28C4+4=", "08"),
    ("=", "00"),
    ("5==", "05"),
]


def teste_tecla_segurada():
    avr = novo()
    avr.key = "7"
    avr.run_ms(500)             # segurar nao repete a tecla
    avr.key = None
    avr.run_ms(60)
    return read_display(avr), "07"


def teste_repique():
    avr = novo()
    for _ in range(5):          # contato instavel de 1 ms: 5 pulsos
        avr.key = "9"
        avr.run_ms(1)
        avr.key = None
        avr.run_ms(1)
    avr.run_ms(60)
    return read_display(avr), "00"


def main():
    falhas = 0
    for seq, esperado in CASOS:
        obtido = digita(novo(), seq)
        ok = obtido == esperado
        falhas += not ok
        print(f"{'OK  ' if ok else 'FALHA'} {seq or '(nada)':<14} "
              f"-> [{obtido}] esperado [{esperado}]")
    for nome, f in (("tecla segurada", teste_tecla_segurada),
                    ("repique < 20 ms", teste_repique)):
        obtido, esperado = f()
        ok = obtido == esperado
        falhas += not ok
        print(f"{'OK  ' if ok else 'FALHA'} {nome:<14} "
              f"-> [{obtido}] esperado [{esperado}]")
    total = len(CASOS) + 2
    print(f"\n{total - falhas}/{total} testes passaram")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
