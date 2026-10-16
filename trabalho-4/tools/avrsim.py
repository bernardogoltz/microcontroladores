"""Montador e simulador minimos de AVR (ATmega328P) para o Trabalho 4.

Suporta apenas o subconjunto de instrucoes e diretivas usado nos trabalhos
(src/termometro.asm). O montador gera palavras de maquina reais (e um .hex
Intel), e o simulador executa essas palavras, decodificando o opcode -
portanto o que e simulado e o binario, nao o texto do fonte.

Perifericos modelados: PORTB/PORTC/PORTD, Timer0 em modo CTC com interrupcao
OCIE0A, SLEEP (modo idle), GPIOR0, o ADC de 10 bits (ADMUX, ADCSRA,
ADCL/ADCH, ADSC, ADIF, interrupcao ADIE) com tensoes definidas pelo teste,
e o teclado matricial do Trabalho 2 (PC5..PC2 / PB1..PB4).
"""

import bisect
import re
import sys

F_CPU = 16_000_000

# Simbolos de m328Pdef.inc usados no programa
M328P = {
    "pinb": 0x03, "ddrb": 0x04, "portb": 0x05,
    "pinc": 0x06, "ddrc": 0x07, "portc": 0x08,
    "pind": 0x09, "ddrd": 0x0A, "portd": 0x0B,
    "tifr0": 0x15, "gpior0": 0x1E,
    "tccr0a": 0x24, "tccr0b": 0x25, "tcnt0": 0x26, "ocr0a": 0x27,
    "smcr": 0x33, "spl": 0x3D, "sph": 0x3E, "sreg": 0x3F,
    "timsk0": 0x6E,
    "adcl": 0x78, "adch": 0x79, "adcsra": 0x7A, "adcsrb": 0x7B,
    "admux": 0x7C, "didr0": 0x7E,
    "refs1": 7, "refs0": 6, "adlar": 5,
    "aden": 7, "adsc": 6, "adate": 5, "adif": 4, "adie": 3,
    "adps2": 2, "adps1": 1, "adps0": 0,
    **{f"adc{i}d": i for i in range(6)},
    "wgm01": 1, "cs02": 2, "ocie0a": 1, "ocf0a": 1, "se": 0,
    "ramend": 0x08FF, "oc0aaddr": 0x001C, "adccaddr": 0x002A, "int_vectors_size": 52,
    **{f"p{port}{bit}": bit for port in "bcd" for bit in range(8)},
}
M328P_DEFS = {"xl": 26, "xh": 27, "yl": 28, "yh": 29, "zl": 30, "zh": 31}

# ----------------------------------------------------------------------------
# Montador
# ----------------------------------------------------------------------------

REG2 = {"add": 0x0C00, "adc": 0x1C00, "sub": 0x1800, "sbc": 0x0800,
        "and": 0x2000, "or": 0x2800, "eor": 0x2400, "mov": 0x2C00,
        "cp": 0x1400, "cpc": 0x0400, "cpse": 0x1000, "mul": 0x9C00}
IMM = {"ldi": 0xE000, "cpi": 0x3000, "subi": 0x5000, "sbci": 0x4000,
       "andi": 0x7000, "ori": 0x6000, "sbr": 0x6000}
REG1 = {"com": 0x0, "neg": 0x1, "swap": 0x2, "inc": 0x3, "asr": 0x5,
        "lsr": 0x6, "ror": 0x7, "dec": 0xA}
IOBIT = {"cbi": 0x9800, "sbic": 0x9900, "sbi": 0x9A00, "sbis": 0x9B00}
REGBIT = {"sbrc": 0xFC00, "sbrs": 0xFE00}
BRANCH = {"breq": (0xF000, 1), "brne": (0xF400, 1), "brcs": (0xF000, 0),
          "brlo": (0xF000, 0), "brcc": (0xF400, 0), "brsh": (0xF400, 0),
          "brmi": (0xF000, 2), "brpl": (0xF400, 2), "brlt": (0xF000, 4),
          "brge": (0xF400, 4)}
NOARG = {"nop": 0x0000, "ret": 0x9508, "reti": 0x9518, "sei": 0x9478,
         "cli": 0x94F8, "sec": 0x9408, "clc": 0x9488, "sleep": 0x9588}


class AsmError(Exception):
    pass


class Assembler:
    def __init__(self):
        self.equ = dict(M328P)
        self.defs = dict(M328P_DEFS)
        self.labels = {}
        self.code = {}          # endereco de palavra -> palavra

    # -- expressoes ---------------------------------------------------------
    def value(self, expr):
        expr = expr.strip()
        names = {**self.equ, **self.labels}

        def sub(m):
            name = m.group(0).lower()
            if name in ("high", "low"):
                return name
            if name not in names:
                raise AsmError(f"simbolo indefinido: {m.group(0)}")
            return str(names[name])

        py = re.sub(r"(?<![0-9A-Za-z_])[A-Za-z_][A-Za-z0-9_]*", sub, expr)
        return int(eval(py, {"__builtins__": {}},
                        {"high": lambda v: (v >> 8) & 0xFF,
                         "low": lambda v: v & 0xFF}))

    def reg(self, tok):
        t = tok.strip().lower()
        if t in self.defs:
            return self.defs[t]
        m = re.fullmatch(r"r(\d+)", t)
        if not m or int(m.group(1)) > 31:
            raise AsmError(f"registrador invalido: {tok}")
        return int(m.group(1))

    # -- leitura do fonte ---------------------------------------------------
    @staticmethod
    def split_ops(s):
        return [p.strip() for p in s.split(",")] if s.strip() else []

    def lines(self, text):
        for n, raw in enumerate(text.splitlines(), 1):
            line = raw.split(";", 1)[0].strip()
            label = None
            m = re.match(r"([A-Za-z_][A-Za-z0-9_]*):\s*(.*)", line)
            if m:
                label, line = m.group(1).lower(), m.group(2)
            if not line:
                yield n, label, None, []
                continue
            parts = line.split(None, 1)
            yield n, label, parts[0].lower(), parts[1] if len(parts) > 1 else ""

    @staticmethod
    def size(mn, args):
        if mn in ("lds", "sts", "jmp", "call"):
            return 2
        return 1

    def assemble(self, text):
        # passo 1: enderecos dos rotulos, .equ e .def
        pc = 0
        for n, label, mn, args in self.lines(text):
            try:
                if label:
                    self.labels[label] = pc
                if mn is None:
                    continue
                pc = self.directive_pass1(mn, args, pc)
            except AsmError as e:
                raise AsmError(f"linha {n}: {e}") from None
        # passo 2: codificacao
        pc = 0
        for n, label, mn, args in self.lines(text):
            if mn is None:
                continue
            try:
                pc = self.emit(mn, args, pc)
            except AsmError as e:
                raise AsmError(f"linha {n}: {e}") from None
        return self.code

    def directive_pass1(self, mn, args, pc):
        if mn == ".equ":
            name, expr = args.split("=", 1)
            self.equ[name.strip().lower()] = self.value(expr)
        elif mn == ".def":
            name, r = args.split("=", 1)
            self.defs[name.strip().lower()] = self.reg(r)
        elif mn == ".org":
            pc = self.value(args)
        elif mn == ".db":
            pc += (len(self.split_ops(args)) + 1) // 2
        elif mn.startswith("."):
            pass
        else:
            pc += self.size(mn, args)
        return pc

    def put(self, pc, word):
        if pc in self.code:
            raise AsmError(f"sobreposicao de codigo em 0x{pc:04X}")
        self.code[pc] = word & 0xFFFF

    def emit(self, mn, a, pc):
        ops = self.split_ops(a)
        if mn in (".equ", ".def", ".include", ".cseg", ".device", ".list",
                  ".nolist"):
            return pc
        if mn == ".org":
            return self.value(a)
        if mn == ".db":
            data = [self.value(o) & 0xFF for o in ops]
            if len(data) % 2:
                data.append(0)
            for i in range(0, len(data), 2):
                self.put(pc, data[i] | (data[i + 1] << 8))
                pc += 1
            return pc

        # pseudo-instrucoes
        if mn == "clr":
            mn, ops = "eor", [ops[0], ops[0]]
        elif mn == "tst":
            mn, ops = "and", [ops[0], ops[0]]
        elif mn == "lsl":
            mn, ops = "add", [ops[0], ops[0]]
        elif mn == "rol":
            mn, ops = "adc", [ops[0], ops[0]]
        elif mn == "ser":
            mn, ops = "ldi", [ops[0], "0xFF"]
        elif mn == "cbr":
            mn, ops = "andi", [ops[0], f"~({ops[1]}) & 0xFF"]

        if mn in NOARG:
            w = NOARG[mn]
        elif mn in REG2:
            d, r = self.reg(ops[0]), self.reg(ops[1])
            w = REG2[mn] | ((r & 0x10) << 5) | (d << 4) | (r & 0x0F)
        elif mn in IMM:
            d, k = self.reg(ops[0]), self.value(ops[1])
            if d < 16:
                raise AsmError(f"{mn} exige r16..r31")
            if not -128 <= k <= 255:
                raise AsmError(f"constante fora da faixa: {k}")
            k &= 0xFF
            w = IMM[mn] | ((k & 0xF0) << 4) | ((d - 16) << 4) | (k & 0x0F)
        elif mn in REG1:
            w = 0x9400 | (self.reg(ops[0]) << 4) | REG1[mn]
        elif mn == "push":
            w = 0x920F | (self.reg(ops[0]) << 4)
        elif mn == "pop":
            w = 0x900F | (self.reg(ops[0]) << 4)
        elif mn == "lpm":
            z = ops[1].replace(" ", "").lower()
            w = 0x9000 | (self.reg(ops[0]) << 4) | {"z": 4, "z+": 5}[z]
        elif mn in ("in", "out"):
            if mn == "in":
                d, io = self.reg(ops[0]), self.value(ops[1])
            else:
                io, d = self.value(ops[0]), self.reg(ops[1])
            if not 0 <= io < 64:
                raise AsmError(f"endereco de I/O invalido para {mn}: {io}")
            w = (0xB000 if mn == "in" else 0xB800) | ((io & 0x30) << 5) \
                | (d << 4) | (io & 0x0F)
        elif mn in IOBIT:
            io, b = self.value(ops[0]), self.value(ops[1])
            if not 0 <= io < 32:
                raise AsmError(f"endereco de I/O invalido para {mn}: {io}")
            w = IOBIT[mn] | (io << 3) | b
        elif mn in REGBIT:
            w = REGBIT[mn] | (self.reg(ops[0]) << 4) | self.value(ops[1])
        elif mn in BRANCH:
            base, s = BRANCH[mn]
            k = self.value(ops[0]) - (pc + 1)
            if not -64 <= k <= 63:
                raise AsmError(f"desvio fora de alcance ({k})")
            w = base | ((k & 0x7F) << 3) | s
        elif mn in ("rjmp", "rcall"):
            k = self.value(ops[0]) - (pc + 1)
            if not -2048 <= k <= 2047:
                raise AsmError(f"desvio fora de alcance ({k})")
            w = (0xC000 if mn == "rjmp" else 0xD000) | (k & 0x0FFF)
        elif mn == "sts":
            self.put(pc, 0x9200 | (self.reg(ops[1]) << 4))
            self.put(pc + 1, self.value(ops[0]))
            return pc + 2
        elif mn == "lds":
            self.put(pc, 0x9000 | (self.reg(ops[0]) << 4))
            self.put(pc + 1, self.value(ops[1]))
            return pc + 2
        else:
            raise AsmError(f"instrucao nao suportada: {mn}")
        self.put(pc, w)
        return pc + 1


def to_ihex(code):
    """Gera Intel HEX a partir de {endereco de palavra: palavra}."""
    data = {}
    for addr, w in code.items():
        data[addr * 2] = w & 0xFF
        data[addr * 2 + 1] = w >> 8
    out = []
    addrs = sorted(data)
    i = 0
    while i < len(addrs):
        start = addrs[i]
        chunk = []
        while i < len(addrs) and addrs[i] == start + len(chunk) and len(chunk) < 16:
            chunk.append(data[addrs[i]])
            i += 1
        rec = [len(chunk), start >> 8, start & 0xFF, 0] + chunk
        out.append(":" + "".join(f"{b:02X}" for b in rec)
                   + f"{(-sum(rec)) & 0xFF:02X}")
    out.append(":00000001FF")
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------
# Simulador
# ----------------------------------------------------------------------------

C, Z, N, V, S, H, T, I = range(8)
IO = 0x20                       # deslocamento I/O -> espaco de dados

# Teclado: linha r ligada em PC(5-r), coluna c ligada em PB(c+1)
KEYPAD = [["7", "8", "9", None],
          ["4", "5", "6", None],
          ["1", "2", "3", "+"],
          ["C", "0", "=", "-"]]
KEY_POS = {k: (r, c) for r, row in enumerate(KEYPAD)
           for c, k in enumerate(row) if k}


class SimError(Exception):
    pass


class AVR:
    def __init__(self, code):
        self.flash = [0xFFFF] * 16384
        for a, w in code.items():
            self.flash[a] = w
        self.mem = bytearray(0x900)
        self.pc = 0
        self.cycles = 0
        self.sleeping = False
        self.key = None             # tecla pressionada (rotulo) ou None
        self.next_cmp = None        # ciclo do proximo evento de compare
        self.port_log = []          # (ciclo, PORTB, PORTD) a cada escrita
        self.vref = 5.0             # AVcc
        self.adc_v = [0.0] * 8      # tensao (V) em cada entrada ADC0..ADC7
        self.adc_done = None        # ciclo em que a conversao atual termina
        self.adc_first = True       # 1a conversao apos ligar: 25 ciclos
        self.adc_start = 0          # ciclo em que a conversao comecou
        self.adc_log = []           # (ciclo de inicio, canal) concluidas

    # -- registradores / memoria -------------------------------------------
    def r(self, i):
        return self.mem[i]

    def w(self, i, v):
        self.mem[i] = v & 0xFF

    def flag(self, b):
        return (self.mem[IO + 0x3F] >> b) & 1

    def set_flags(self, **kw):
        s = self.mem[IO + 0x3F]
        for name, val in kw.items():
            b = "CZNVSHTI".index(name)
            s = (s | (1 << b)) if val else (s & ~(1 << b))
        self.mem[IO + 0x3F] = s & 0xFF

    def sp(self):
        return self.mem[IO + 0x3D] | (self.mem[IO + 0x3E] << 8)

    def set_sp(self, v):
        self.mem[IO + 0x3D] = v & 0xFF
        self.mem[IO + 0x3E] = (v >> 8) & 0xFF

    def push(self, v):
        sp = self.sp()
        self.mem[sp] = v & 0xFF
        self.set_sp(sp - 1)

    def pop(self):
        sp = self.sp() + 1
        self.set_sp(sp)
        return self.mem[sp]

    def push_pc(self, pc):
        self.push(pc & 0xFF)
        self.push(pc >> 8)

    def pop_pc(self):
        hi = self.pop()
        return (hi << 8) | self.pop()

    # -- perifericos -------------------------------------------------------
    def timer_period(self):
        cs = self.mem[IO + 0x25] & 7
        pre = {1: 1, 2: 8, 3: 64, 4: 256, 5: 1024}.get(cs)
        if pre is None:
            return None
        return pre * (self.mem[IO + 0x27] + 1)

    def read(self, addr):
        if addr == IO + 0x03:                       # PINB
            portb, ddrb = self.mem[IO + 0x05], self.mem[IO + 0x04]
            pins = portb                            # pull-up / saida
            if self.key:
                row, col = KEY_POS[self.key]
                portc, ddrc = self.mem[IO + 0x08], self.mem[IO + 0x07]
                rbit, cbit = 5 - row, col + 1
                row_low = (ddrc >> rbit) & 1 and not (portc >> rbit) & 1
                if row_low and not (ddrb >> cbit) & 1:
                    pins &= ~(1 << cbit)
            return pins & 0xFF
        if addr == IO + 0x06:
            return self.mem[IO + 0x08]
        if addr == IO + 0x09:
            return self.mem[IO + 0x0B]
        return self.mem[addr]

    def write(self, addr, v):
        v &= 0xFF
        if addr == 0x7A:                            # ADCSRA
            self.write_adcsra(v)
            return
        self.mem[addr] = v
        if addr in (IO + 0x05, IO + 0x0B):          # PORTB / PORTD
            self.port_log.append((self.cycles, self.mem[IO + 0x05],
                                  self.mem[IO + 0x0B]))
        elif addr == IO + 0x25:                     # TCCR0B
            p = self.timer_period()
            self.next_cmp = None if p is None else self.cycles + p
        elif addr == IO + 0x15:                     # TIFR0: escrever 1 limpa
            self.mem[addr] = 0

    # -- ADC ---------------------------------------------------------------
    ADPS = (2, 2, 4, 8, 16, 32, 64, 128)

    def write_adcsra(self, v):
        self.tick_adc()
        adif = self.mem[0x7A] & 0x10 and not v & 0x10  # escrever 1 limpa
        if not v & 0x80:                        # ADEN = 0: desliga
            self.adc_done = None
            self.adc_first = True
            v &= ~0x40
        elif v & 0x40 and self.adc_done is None:
            n = 25 if self.adc_first else 13
            self.adc_first = False
            self.adc_done = self.cycles + n * self.ADPS[v & 7]
            self.adc_start = self.cycles
        elif self.adc_done is not None:
            v |= 0x40                           # ADSC so volta a 0 no fim
        v = (v & ~0x10) | (0x10 if adif else 0)
        self.mem[0x7A] = v & 0xFF

    def adc_code(self, ch):
        if ch < 8:
            vin = self.adc_v[ch]
        elif ch == 0x0E:                        # banda de 1,1 V
            vin = 1.1
        else:                                   # GND / sensor interno
            vin = 0.0
        return max(0, min(1023, int(vin * 1024 / self.vref)))

    def tick_adc(self):
        if self.adc_done is None or self.cycles < self.adc_done:
            return
        self.adc_done = None
        admux = self.mem[0x7C]
        code = self.adc_code(admux & 0x0F)
        if admux & 0x20:                        # ADLAR: ajustado a esquerda
            code <<= 6
        self.mem[0x78] = code & 0xFF
        self.mem[0x79] = (code >> 8) & 0xFF
        self.mem[0x7A] = (self.mem[0x7A] & ~0x40) | 0x10   # ADSC=0, ADIF=1
        self.adc_log.append((self.adc_start, admux & 0x0F))

    def tick_timer(self):
        if self.next_cmp is not None and self.cycles >= self.next_cmp:
            self.mem[IO + 0x15] |= 1 << 1           # OCF0A
            self.next_cmp += self.timer_period()

    def irq(self):
        if (self.flag(I) and self.mem[IO + 0x15] & 2
                and self.mem[0x6E] & 2):
            self.mem[IO + 0x15] &= ~2
            self.sleeping = False
            self.push_pc(self.pc)
            self.set_flags(I=0)
            self.pc = 0x1C
            self.cycles += 4
        elif (self.flag(I) and self.mem[0x7A] & 0x18 == 0x18):  # ADIF+ADIE
            self.mem[0x7A] &= ~0x10
            self.sleeping = False
            self.push_pc(self.pc)
            self.set_flags(I=0)
            self.pc = 0x2A
            self.cycles += 4

    # -- execucao ----------------------------------------------------------
    def run_until(self, cycle):
        while self.cycles < cycle:
            if self.sleeping or self.idle_wait():
                events = [e for e in (self.next_cmp, self.adc_done)
                          if e is not None]
                if not events:
                    raise SimError("espera sem interrupcao possivel")
                self.cycles = max(self.cycles, min(*events, cycle))
            else:
                self.step()
            self.tick_timer()
            self.tick_adc()
            self.irq()

    def idle_wait(self):
        """Laco de espera "sbis IO, b / rjmp .-2" com o bit em 0: nada muda
        ate a proxima interrupcao, entao o tempo pode ser avancado direto."""
        op, nxt = self.flash[self.pc], self.flash[self.pc + 1]
        if (op & 0xFF00) != 0x9B00 or nxt != 0xCFFE:
            return False
        io, b = (op >> 3) & 0x1F, op & 7
        return not (self.mem[IO + io] >> b) & 1

    def run_ms(self, ms):
        self.run_until(self.cycles + int(ms * F_CPU / 1000))

    @staticmethod
    def is_two_word(op):
        return (op & 0xFC0F) == 0x9000 or (op & 0xFE0E) == 0x940C \
            or (op & 0xFE0E) == 0x940E

    def skip(self):
        self.pc += 2 if self.is_two_word(self.flash[self.pc]) else 1
        self.cycles += 1

    def step(self):
        op = self.flash[self.pc]
        self.pc += 1
        self.cycles += 1
        d5 = (op >> 4) & 0x1F
        r5 = ((op >> 5) & 0x10) | (op & 0x0F)
        dh = 16 + ((op >> 4) & 0x0F)
        k8 = ((op >> 4) & 0xF0) | (op & 0x0F)

        top6 = op & 0xFC00
        if op == 0x0000:                                    # nop
            return
        if top6 in (0x0C00, 0x1C00):                        # add / adc
            rd, rr = self.r(d5), self.r(r5)
            c = self.flag(C) if top6 == 0x1C00 else 0
            res = rd + rr + c
            r8 = res & 0xFF
            hc = ((rd & 0xF) + (rr & 0xF) + c) > 0xF
            v = bool(~(rd ^ rr) & (rd ^ r8) & 0x80)
            n = bool(r8 & 0x80)
            self.set_flags(C=res > 0xFF, Z=r8 == 0, N=n, V=v, S=n ^ v, H=hc)
            self.w(d5, r8)
            return
        if top6 == 0x9C00:                                  # mul
            res = self.r(d5) * self.r(r5)
            self.w(0, res)
            self.w(1, res >> 8)
            self.set_flags(C=res & 0x8000, Z=res == 0)
            self.cycles += 1
            return
        if top6 in (0x1800, 0x0800, 0x1400, 0x0400):         # sub sbc cp cpc
            carry = top6 in (0x0800, 0x0400)
            self.sub_flags(self.r(d5), self.r(r5), carry,
                           d5 if top6 in (0x1800, 0x0800) else None)
            return
        if top6 in (0x2000, 0x2800, 0x2400):                 # and or eor
            rd, rr = self.r(d5), self.r(r5)
            res = {0x2000: rd & rr, 0x2800: rd | rr, 0x2400: rd ^ rr}[top6]
            self.logic(d5, res)
            return
        if top6 == 0x2C00:                                  # mov
            self.w(d5, self.r(r5))
            return
        if top6 == 0x1000:                                  # cpse
            if self.r(d5) == self.r(r5):
                self.skip()
            return
        top4 = op & 0xF000
        if top4 == 0xE000:                                  # ldi
            self.w(dh, k8)
            return
        if top4 == 0x3000:                                  # cpi
            self.sub_flags(self.r(dh), k8, False, None)
            return
        if top4 in (0x5000, 0x4000):                        # subi / sbci
            self.sub_flags(self.r(dh), k8, top4 == 0x4000, dh)
            return
        if top4 in (0x7000, 0x6000):                        # andi / ori
            rd = self.r(dh)
            self.logic(dh, rd & k8 if top4 == 0x7000 else rd | k8)
            return
        if top4 in (0xC000, 0xD000):                        # rjmp / rcall
            k = op & 0x0FFF
            if k & 0x800:
                k -= 0x1000
            if top4 == 0xD000:
                self.push_pc(self.pc)
                self.cycles += 2
            else:
                self.cycles += 1
            self.pc = (self.pc + k) & 0x3FFF
            return
        if (op & 0xF800) == 0xB000 or (op & 0xF800) == 0xB800:   # in / out
            io = ((op >> 5) & 0x30) | (op & 0x0F)
            if op & 0x0800:
                self.write(IO + io, self.r(d5))
            else:
                self.w(d5, self.read(IO + io))
            return
        if (op & 0xF800) == 0xF000:                         # brbs / brbc
            s = op & 7
            k = (op >> 3) & 0x7F
            if k & 0x40:
                k -= 0x80
            want = 1 if (op & 0x0400) == 0 else 0
            if self.flag(s) == want:
                self.pc += k
                self.cycles += 1
            return
        if (op & 0xFC08) in (0xFC00, 0xFE00):               # sbrc / sbrs
            bit = (self.r(d5) >> (op & 7)) & 1
            if bit == (1 if op & 0x0200 else 0):
                self.skip()
            return
        if (op & 0xFF00) in (0x9800, 0x9A00):               # cbi / sbi
            io, b = (op >> 3) & 0x1F, op & 7
            v = self.mem[IO + io]
            v = v | (1 << b) if op & 0x0200 else v & ~(1 << b)
            self.write(IO + io, v)
            self.cycles += 1
            return
        if (op & 0xFF00) in (0x9900, 0x9B00):               # sbic / sbis
            io, b = (op >> 3) & 0x1F, op & 7
            bit = (self.read(IO + io) >> b) & 1
            if bit == (1 if op & 0x0200 else 0):
                self.skip()
            return
        if op in (0x9508, 0x9518):                          # ret / reti
            self.pc = self.pop_pc()
            self.cycles += 3
            if op == 0x9518:
                self.set_flags(I=1)
            return
        if op == 0x9478:
            self.set_flags(I=1)
            return
        if op == 0x94F8:
            self.set_flags(I=0)
            return
        if op == 0x9408:
            self.set_flags(C=1)
            return
        if op == 0x9488:
            self.set_flags(C=0)
            return
        if op == 0x9588:                                    # sleep
            if self.mem[IO + 0x33] & 1:
                self.sleeping = True
            return
        if (op & 0xFE0F) == 0x920F:                         # push
            self.push(self.r(d5))
            self.cycles += 1
            return
        if (op & 0xFE0F) == 0x900F:                         # pop
            self.w(d5, self.pop())
            self.cycles += 1
            return
        if (op & 0xFE0E) == 0x9004:                         # lpm Rd, Z(+)
            z = self.r(30) | (self.r(31) << 8)
            word = self.flash[z >> 1]
            self.w(d5, (word >> 8) if z & 1 else word & 0xFF)
            if op & 1:
                z += 1
                self.w(30, z)
                self.w(31, z >> 8)
            self.cycles += 2
            return
        if (op & 0xFE0F) == 0x9200:                         # sts
            addr = self.flash[self.pc]
            self.pc += 1
            self.write(addr, self.r(d5))
            self.cycles += 1
            return
        if (op & 0xFE0F) == 0x9000:                         # lds
            addr = self.flash[self.pc]
            self.pc += 1
            self.w(d5, self.read(addr))
            self.cycles += 1
            return
        if (op & 0xFE00) == 0x9400:                         # 1 operando
            kind = op & 0x0F
            rd = self.r(d5)
            if kind == 0x0:                                 # com
                self.logic(d5, ~rd)
                self.set_flags(C=1)
            elif kind == 0x1:                               # neg
                res = (-rd) & 0xFF
                n = bool(res & 0x80)
                v = res == 0x80
                self.set_flags(C=res != 0, Z=res == 0, N=n, V=v, S=n ^ v,
                               H=bool((res | rd) & 0x08))
                self.w(d5, res)
            elif kind == 0x2:                               # swap
                self.w(d5, ((rd << 4) | (rd >> 4)))
            elif kind in (0x3, 0xA):                        # inc / dec
                res = (rd + (1 if kind == 0x3 else -1)) & 0xFF
                n = bool(res & 0x80)
                v = rd == (0x7F if kind == 0x3 else 0x80)
                self.set_flags(Z=res == 0, N=n, V=v, S=n ^ v)
                self.w(d5, res)
            elif kind in (0x6, 0x7, 0x5):                   # lsr ror asr
                c = rd & 1
                if kind == 0x6:
                    res = rd >> 1
                elif kind == 0x7:
                    res = (rd >> 1) | (self.flag(C) << 7)
                else:
                    res = (rd >> 1) | (rd & 0x80)
                n = bool(res & 0x80)
                v = n ^ bool(c)
                self.set_flags(C=c, Z=res == 0, N=n, V=v, S=n ^ v)
                self.w(d5, res)
            else:
                raise SimError(f"opcode nao suportado 0x{op:04X}")
            return
        raise SimError(f"opcode nao suportado 0x{op:04X} em "
                       f"0x{self.pc - 1:04X}")

    def logic(self, d, res):
        res &= 0xFF
        n = bool(res & 0x80)
        self.set_flags(Z=res == 0, N=n, V=0, S=n)
        self.w(d, res)

    def sub_flags(self, rd, rr, with_carry, dest):
        c = self.flag(C) if with_carry else 0
        res = rd - rr - c
        r8 = res & 0xFF
        hc = (rd & 0xF) < (rr & 0xF) + c
        v = bool((rd ^ rr) & (rd ^ r8) & 0x80)
        n = bool(r8 & 0x80)
        z = (r8 == 0) and (self.flag(Z) if with_carry else True)
        self.set_flags(C=res < 0, Z=z, N=n, V=v, S=n ^ v, H=hc)
        if dest is not None:
            self.w(dest, r8)


# ----------------------------------------------------------------------------
# Leitura dos displays a partir do historico das portas
# ----------------------------------------------------------------------------

SEG_CHARS = {0x3F: "0", 0x06: "1", 0x5B: "2", 0x4F: "3", 0x66: "4",
             0x6D: "5", 0x7D: "6", 0x07: "7", 0x7F: "8", 0x6F: "9",
             0x40: "-", 0x79: "E", 0x50: "r", 0x00: " ",
             0x38: "L", 0x5C: "o", 0x76: "H", 0x04: "i"}


def enables(pb, pd):
    """(dezenas, unidades) habilitados: PD7 e PB0."""
    return (pd >> 7) & 1, pb & 1


def segment_duty(log, t0, t1):
    """Fracao do tempo [t0, t1) em que cada segmento de cada display ficou
    aceso. Retorna (duty_dezenas[7], duty_unidades[7])."""
    duty = [[0.0] * 7, [0.0] * 7]
    times = [e[0] for e in log]
    i = bisect.bisect_right(times, t0)
    j = bisect.bisect_left(times, t1)
    state = log[i - 1][1:] if i else (0, 0)
    events = [(t0, *state)] + log[i:j] + [(t1, 0, 0)]
    for (ta, pb, pd), (tb, _, _) in zip(events, events[1:]):
        dt = tb - ta
        for disp, on in enumerate(enables(pb, pd)):
            if on:
                for s in range(7):
                    if (pd >> s) & 1:
                        duty[disp][s] += dt
    span = t1 - t0
    return [[v / span for v in d] for d in duty]


def read_display(avr, window_ms=20):
    """Texto mostrado nos 2 displays nos ultimos window_ms (multiplexados)."""
    t1 = avr.cycles
    t0 = t1 - int(window_ms * F_CPU / 1000)
    text = ""
    for d in segment_duty(avr.port_log, t0, t1):
        pattern = sum(1 << s for s in range(7) if d[s] > 0.25)
        text += SEG_CHARS.get(pattern, "?")
    return text


def build(asm_path):
    with open(asm_path, encoding="utf-8") as f:
        return Assembler().assemble(f.read())


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "src/termometro.asm"
    out = sys.argv[2] if len(sys.argv) > 2 else "build/termometro.hex"
    code = build(src)
    with open(out, "w") as f:
        f.write(to_ihex(code))
    print(f"{out}: {len(code)} palavras ({len(code) * 2} bytes)")
