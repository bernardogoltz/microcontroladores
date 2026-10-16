"""Testes do termometro: executa o binario montado no simulador, coloca
leituras conhecidas em cada canal do ADC, muda a chave seletora e confere o
que aparece nos 3 displays multiplexados.

Uso: python3 tools/testes.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from avrsim import (AVR, F_CPU, Assembler, enables,  # noqa: E402
                    read_display)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(RAIZ, "src", "termometro.asm"), encoding="utf-8") as f:
    ASM = Assembler()
    CODIGO = ASM.assemble(f.read())

LEITURA_MS = 50         # intervalo entre leituras do firmware
ESPERA_MS = 70          # uma leitura completa + margem

falhas = 0
total = 0


def confere(nome, obtido, esperado):
    global falhas, total
    total += 1
    ok = obtido == esperado
    falhas += not ok
    print(f"{'OK  ' if ok else 'FALHA'} {nome:<34} -> [{obtido}] "
          f"esperado [{esperado}]")


def esperado_c(adc):
    """Temperatura esperada: ADC * 120 / 1023 arredondado (meio para cima)."""
    return (adc * 120 + 511) // 1023


def texto(t):
    return f"{t:>3}"


def novo(adc=(0, 0, 0), chave=(0,)):
    avr = AVR(CODIGO)
    avr.adc[:3] = adc
    avr.switch = set(chave)
    avr.run_ms(ESPERA_MS)
    return avr


def teste_valores():
    print("-- conversao e formato (canal ADC0)")
    casos = [
        (0, "fundo inferior"), (1023, "fundo de escala"), (512, "meio"),
        (4, "0,47 C arredonda para 0"), (5, "0,59 C arredonda para 1"),
        (8, "0,94 C arredonda para 1"), (9, "1,06 C arredonda para 1"),
        (17, "1,99 C arredonda para 2"), (85, "9,97 C: aparece a dezena"),
        (852, "99,94 C: aparece a centena"), (1018, "119,41 C"),
        (1019, "119,53 C arredonda para 120"), (256, "30,03 C"),
    ]
    for adc, desc in casos:
        avr = novo(adc=(adc, 0, 0))
        confere(f"ADC {adc:4} ({desc})", read_display(avr),
                texto(esperado_c(adc)))


def teste_canais():
    print("-- 3 canais diferentes, trocando a chave")
    adc = (256, 640, 1000)                  # 30, 75 e 117 C
    avr = novo(adc=adc, chave=(0,))
    for ch in (0, 1, 2, 1, 0, 2):
        avr.switch = {ch}
        avr.run_ms(ESPERA_MS)
        confere(f"chave em ADC{ch} (ADC = {adc[ch]})", read_display(avr),
                texto(esperado_c(adc[ch])))
    canais = sorted({c for _, c, _ in avr.conversions})
    confere("canais convertidos (MUX)", canais, [0, 1, 2])


def teste_invalida():
    print("-- combinacao invalida da chave")
    avr = novo(adc=(256, 640, 1000))
    for chave, desc in ((set(), "nenhuma fechada"), ({0, 1}, "ADC0+ADC1"),
                        ({1, 2}, "ADC1+ADC2"), ({0, 1, 2}, "todas")):
        avr.switch = chave
        avr.run_ms(ESPERA_MS)
        confere(f"chave invalida ({desc})", read_display(avr), "---")
    avr.switch = {1}
    avr.run_ms(ESPERA_MS)
    confere("volta para ADC1", read_display(avr), " 75")


def teste_tensao_variando():
    print("-- mudanca de tensao durante a execucao (ADC0)")
    avr = novo()
    for v in (0.0, 2.5, 4.0, 5.0, 1.0, 0.04):
        avr.set_volts(0, v)
        avr.run_ms(ESPERA_MS)
        adc = avr.adc[0]
        confere(f"{v:4.2f} V -> ADC {adc}", read_display(avr),
                texto(esperado_c(adc)))


def teste_tempo_resposta():
    print("-- tempos")
    avr = novo(adc=(1023, 0, 0))
    inicio = [t for t, _, _ in avr.conversions]
    avr.run_ms(500)
    tempos = [t for t, _, _ in avr.conversions]
    dt = {round((b - a) * 1000 / F_CPU, 3) for a, b in zip(tempos, tempos[1:])}
    confere("intervalo entre leituras (ms)", sorted(dt), [50.0])
    confere("1a leitura apos o reset (ms)",
            round(inicio[0] * 1000 / F_CPU, 1), 2.0)

    # a cada interrupcao exatamente um display fica habilitado
    t0 = avr.cycles - int(0.1 * F_CPU)
    trocas = []
    for t, pb, pd in avr.port_log:
        on = enables(pb, pd)
        if sum(on) > 1:
            confere("dois displays acesos ao mesmo tempo", True, False)
            return
        if t >= t0 and sum(on) == 1:
            if not trocas or trocas[-1][1] != on:
                trocas.append((t, on))
    trocas = trocas[1:]                     # 1o: display ja aceso em t0
    periodos = {round((b[0] - a[0]) * 1000 / F_CPU, 2)
                for a, b in zip(trocas, trocas[1:])}
    confere("tempo de cada display aceso (ms)", sorted(periodos), [2.0])
    ordem = [on.index(1) for _, on in trocas[:6]]
    confere("ordem de varredura", len(set(ordem[:3])), 3)

    # resposta a troca da chave: ate uma leitura (50 ms) + conversao
    avr.adc[1] = 512
    avr.switch = {1}
    t_troca = avr.cycles
    while read_display(avr, 6) != " 60":
        avr.run_ms(1)
        if avr.cycles - t_troca > 0.2 * F_CPU:
            break
    ms = (avr.cycles - t_troca) * 1000 / F_CPU
    confere(f"troca da chave visivel em {ms:.0f} ms (<= 56)", ms <= 56, True)


def teste_rotina_converte():
    """Executa so a rotina 'converte' do binario para os 1024 valores."""
    print("-- rotina converte isolada, ADC = 0..1023")
    erros = []
    entrada = ASM.labels["converte"]
    for adc in range(1024):
        avr = AVR(CODIGO)
        avr.set_sp(0x08FF)
        avr.push_pc(0x3FFF)                 # retorno para um endereco marca
        avr.pc = entrada
        avr.w(24, adc & 0xFF)
        avr.w(25, adc >> 8)
        while avr.pc != 0x3FFF:
            avr.step()
        if avr.r(16) != esperado_c(adc) or avr.r(1) != 0:
            erros.append(adc)
    confere("valores que conferem", f"{1024 - len(erros)}/1024", "1024/1024")


def main():
    teste_valores()
    teste_canais()
    teste_invalida()
    teste_tensao_variando()
    teste_tempo_resposta()
    teste_rotina_converte()
    print(f"\n{total - falhas}/{total} testes passaram")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
