#!/usr/bin/env python3
# MIT License
#
# Copyright (c) 2026 Maniek SP8KM HAMHOBBY.PL
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import argparse
import json
import math
import random
import re
import sys
import time
import wave
from array import array
from pathlib import Path

# --- Morse map (A-Z, 0-9 + kilka znaków opcjonalnych) ---
MORSE = {
    "A": ".-",    "B": "-...",  "C": "-.-.",  "D": "-..",   "E": ".",
    "F": "..-.",  "G": "--.",   "H": "....",  "I": "..",    "J": ".---",
    "K": "-.-",   "L": ".-..",  "M": "--",    "N": "-.",    "O": "---",
    "P": ".--.",  "Q": "--.-",  "R": ".-.",   "S": "...",   "T": "-",
    "U": "..-",   "V": "...-",  "W": ".--",   "X": "-..-",  "Y": "-.--",
    "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "/": "-..-.", "-": "-....-",
    "(": "-.--.",  ")": "-.--.-",
}

BANNER_A = r"""
██   ██  █████  ███    ███ ██   ██  ██████  ██████  ██████  ██    ██
██   ██ ██   ██ ████  ████ ██   ██ ██    ██ ██   ██ ██   ██  ██  ██
███████ ███████ ██ ████ ██ ███████ ██    ██ ██████  ██████    ████
██   ██ ██   ██ ██  ██  ██ ██   ██ ██    ██ ██   ██ ██   ██     ██
██   ██ ██   ██ ██      ██ ██   ██  ██████  ██████  ██████      ██
"""

SEPARATOR_RE = re.compile(r"\[(\s*)\]")


def print_banner_and_license() -> None:
    print(BANNER_A.strip("\n"))
    print("(c) 2026 Maniek SP8KM HAMHOBBY.PL — MIT License")
    print()


class ProgressBar:
    """Prosty progress bar w jednej linii (jak wget/curl)."""
    def __init__(self, total: int, label: str = "Generating", width: int = 30, interval_s: float = 0.12):
        self.total = max(1, int(total))
        self.label = label
        self.width = max(10, int(width))
        self.interval_s = interval_s
        self.done_count = 0
        self.t0 = time.time()
        self._last = 0.0

    def step(self, n: int = 1) -> None:
        self.done_count = min(self.total, self.done_count + n)
        self._render()

    def _render(self, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self._last) < self.interval_s:
            return
        self._last = now

        frac = self.done_count / self.total
        filled = int(round(frac * self.width))
        bar = "#" * filled + "-" * (self.width - filled)

        elapsed = max(0.001, now - self.t0)
        rate = self.done_count / elapsed
        eta = (self.total - self.done_count) / rate if rate > 0 else 0.0

        pct = int(frac * 100)
        sys.stdout.write(
            f"\r{self.label} [{bar}] {pct:3d}%  {self.done_count}/{self.total}  ETA {eta:5.1f}s"
        )
        sys.stdout.flush()

    def finish(self, msg: str = "OK") -> None:
        self._render(force=True)
        sys.stdout.write(f"\n{msg}\n")
        sys.stdout.flush()


def dit_time_from_speed(speed_wpm: float) -> float:
    """Czas jednego ditu w sekundach, liczony z zadanej prędkości."""
    return 1.2 / speed_wpm


def units_to_seconds(units: int, speed_wpm: float) -> float:
    """Przelicza liczbę jednostek dit na sekundy."""
    return units * dit_time_from_speed(speed_wpm)


# -------- audio primitives --------
def gen_tone(
    sr: int,
    freq: float,
    duration_s: float,
    amp: float = 0.6,
    ramp_s: float = 0.005
) -> array:
    n = int(round(duration_s * sr))
    if n <= 0:
        return array('h')

    ramp = int(round(ramp_s * sr))
    ramp = min(ramp, n // 2)

    out = array('h')
    two_pi_f = 2.0 * math.pi * freq

    for i in range(n):
        t = i / sr
        x = math.sin(two_pi_f * t)

        # cosine ramp
        if ramp > 0:
            if i < ramp:
                w = 0.5 - 0.5 * math.cos(math.pi * i / ramp)
            elif i >= n - ramp:
                j = n - 1 - i
                w = 0.5 - 0.5 * math.cos(math.pi * j / ramp)
            else:
                w = 1.0
        else:
            w = 1.0

        v = int(max(-1.0, min(1.0, amp * w * x)) * 32767)
        out.append(v)

    return out


def gen_silence(sr: int, duration_s: float) -> array:
    n = int(round(duration_s * sr))
    return array('h', [0] * max(0, n))


def add_samples(dst: array, src: array) -> None:
    dst.extend(src)


# -------- CW encoder --------
def cw_emit_token(
    token: str,
    sr: int,
    freq: float,
    fwpm: float,
    amp: float = 0.6,
    ramp_s: float = 0.005
) -> array:
    """
    Nadaje token (np. "ADAM" albo "A") jako ciąg znaków Morse'a.
    Tutaj cały timing elementów liczony jest z FWPM:
    - kropka = 1 dit
    - kreska = 3 dit
    - przerwa wewnątrz litery = 1 dit
    - przerwa między literami = 3 dit
    """
    dit = dit_time_from_speed(fwpm)

    intra = 1 * dit
    dah = 3 * dit
    inter_char = 3 * dit

    out = array('h')
    token = token.upper()

    first_char = True
    for ch in token:
        code = MORSE.get(ch)
        if not code:
            add_samples(out, gen_silence(sr, inter_char))
            first_char = True
            continue

        if not first_char:
            add_samples(out, gen_silence(sr, inter_char))

        for ei, e in enumerate(code):
            add_samples(
                out,
                gen_tone(
                    sr,
                    freq,
                    dit if e == "." else dah,
                    amp=amp,
                    ramp_s=ramp_s,
                )
            )
            if ei != len(code) - 1:
                add_samples(out, gen_silence(sr, intra))

        first_char = False

    return out


# -------- parsing helpers --------
def parse_section_header(header: str) -> list[str]:
    return [t for t in header.strip().split() if t]


def parse_wordline(raw: str, y_units_per_space: int) -> tuple[list[str], list[int]]:
    """
    Rozbija linię na słowa oraz przerwy między nimi.

    Separator [  ] oznacza przerwę zależną od liczby spacji:
        gap_units = liczba_spacji * Y

    Przykłady:
        "ADAM[  ]ADAM"   -> words=["ADAM", "ADAM"], gaps=[2*Y]
        "A[   ]B[ ]C"    -> words=["A", "B", "C"], gaps=[3*Y, 1*Y]

    Zwykłe białe znaki poza separatorem traktowane są jak separator 1*Y.
    """
    parts: list[tuple[str, int | None]] = []
    pos = 0

    for m in SEPARATOR_RE.finditer(raw):
        left = raw[pos:m.start()]
        if left.strip():
            parts.append(("text", None))
            parts_text = left.strip()
            parts[-1] = (parts_text, None)

        spaces_inside = len(m.group(1))
        gap_units = spaces_inside * y_units_per_space
        parts.append(("", gap_units))
        pos = m.end()

    tail = raw[pos:]
    if tail.strip():
        parts.append((tail.strip(), None))

    words: list[str] = []
    gaps: list[int] = []

    for text, gap_units in parts:
        if gap_units is None:
            subwords = [t for t in text.split() if t]
            if not subwords:
                continue

            if not words:
                words.append(subwords[0])
            else:
                gaps.append(y_units_per_space)
                words.append(subwords[0])

            for extra in subwords[1:]:
                gaps.append(y_units_per_space)
                words.append(extra)
        else:
            if not words:
                continue
            gaps.append(gap_units)

    # normalizacja: liczba gaps ma być o 1 mniejsza niż liczba words
    if len(gaps) > max(0, len(words) - 1):
        gaps = gaps[:len(words) - 1]

    return words, gaps


def estimate_total_steps(data) -> int:
    """
    Liczymy 'kroki' tak, żeby postęp był stabilny:
    - 1 krok na sekcję (start)
    - 1 krok na token nagłówka
    - 1 krok na linię (raw entry)
    - 1 krok na każde słowo w linii
    """
    steps = 0
    for hdr, entries in data:
        steps += 1  # sekcja
        hdr_tokens = parse_section_header(hdr)
        steps += len(hdr_tokens)
        steps += len(entries)  # linie
        for raw in entries:
            words, _gaps = parse_wordline(raw, y_units_per_space=1)
            steps += len(words)
    return max(1, steps)


def _parse_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in ("true", "1", "yes", "y", "on"):
        return True
    if v in ("false", "0", "no", "n", "off"):
        return False
    raise argparse.ArgumentTypeError(
        f"niepoprawna wartość logiczna: {value!r} (użyj true/false)"
    )


# -------- build one pass and render with X/Y/Z --------
def render_one_pass(
    json_path: Path,
    sr: int,
    freq: float,
    fwpm: float,
    X: int,
    Y: int,
    Z: int,
    randomize: bool = True,
    amp: float = 0.6,
    ramp_s: float = 0.005,
    end_silence: float = 0.8,
    progress: ProgressBar | None = None,
) -> array:
    data = json.loads(json_path.read_text(encoding="utf-8"))

    sections = [(hdr, entries) for hdr, entries in data]
    if randomize:
        random.shuffle(sections)

    out = array('h')

    # X/Y/Z liczone od FWPM
    X_s = units_to_seconds(X, fwpm)
    Z_s = units_to_seconds(Z, fwpm)

    for hdr, entries in sections:
        if progress:
            progress.step(1)  # sekcja

        hdr_tokens = parse_section_header(hdr)
        for i, tok in enumerate(hdr_tokens):
            add_samples(
                out,
                cw_emit_token(
                    tok,
                    sr,
                    freq,
                    fwpm,
                    amp=amp,
                    ramp_s=ramp_s,
                )
            )
            if i == len(hdr_tokens) - 1:
                add_samples(out, gen_silence(sr, Z_s))
            else:
                add_samples(out, gen_silence(sr, X_s))
            if progress:
                progress.step(1)  # token nagłówka

        entries = list(entries)
        if randomize:
            random.shuffle(entries)

        for raw in entries:
            if progress:
                progress.step(1)  # linia

            words, gaps_units = parse_wordline(raw, y_units_per_space=Y)

            for i, w in enumerate(words):
                add_samples(
                    out,
                    cw_emit_token(
                        w,
                        sr,
                        freq,
                        fwpm,
                        amp=amp,
                        ramp_s=ramp_s,
                    )
                )

                if i == len(words) - 1:
                    add_samples(out, gen_silence(sr, Z_s))
                else:
                    gap_units = gaps_units[i] if i < len(gaps_units) else Y
                    add_samples(out, gen_silence(sr, units_to_seconds(gap_units, fwpm)))

                if progress:
                    progress.step(1)  # słowo

    add_samples(out, gen_silence(sr, end_silence))
    return out


def write_wav_mono16(path: Path, samples: array, sr: int, progress: ProgressBar | None = None) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)

        chunk = 8192
        total = len(samples)
        written = 0

        while written < total:
            end = min(total, written + chunk)
            wf.writeframesraw(samples[written:end].tobytes())
            written = end
            if progress:
                progress._render()

        wf.writeframes(b"")


def _positive_float(value: str) -> float:
    try:
        f = float(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"niepoprawna liczba: {value!r}") from e
    if f <= 0:
        raise argparse.ArgumentTypeError("wartość musi być > 0")
    return f


def _nonneg_float(value: str) -> float:
    try:
        f = float(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"niepoprawna liczba: {value!r}") from e
    if f < 0:
        raise argparse.ArgumentTypeError("wartość musi być >= 0")
    return f


def _nonneg_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"niepoprawna liczba całkowita: {value!r}") from e
    if n < 0:
        raise argparse.ArgumentTypeError("wartość musi być >= 0")
    return n


def build_arg_parser() -> argparse.ArgumentParser:
    description = """
CW WAV generator from JSON file.

Generator pliku WAV z kodem Morse'a na podstawie pliku JSON.
Program może losować sekcje i wpisy albo generować dokładnie po kolei.
Kropka, kreska i X/Y/Z są liczone od FWPM.
Separator [   ] ma długość zależną od liczby spacji w środku.
"""

    epilog = """
PARAMETRY / PARAMETERS
----------------------

--wpm
    PL: parametr informacyjny / kompatybilnościowy
    EN: informational / compatibility parameter

--fwpm
    PL: prędkość, od której liczony jest cały timing CW
        (kropka, kreska, przerwy oraz X/Y/Z)
    EN: speed used for the entire CW timing
        (dot, dash, gaps, and X/Y/Z)

--freq
    PL: częstotliwość tonu CW w Hz
    EN: CW tone frequency in Hz

--sr
    PL: częstotliwość próbkowania WAV, domyślne 44100Hz
    EN: WAV sample rate, default 44100Hz

--x
    PL: przerwa między tokenami nagłówka w jednostkach dit, domyślne 7
    EN: pause between header tokens in dit units, default 7

--y
    PL: bazowa przerwa na jedną spację w separatorze [ ]
        domyślnie 7
        np.:
            [ ]   = 1 * Y
            [  ]  = 2 * Y
            [   ] = 3 * Y
    EN: base pause per one space inside [ ], default 7

--z
    PL: przerwa po ostatnim tokenie nagłówka oraz po ostatnim słowie w linii
        w jednostkach dit, domyślne 31
    EN: pause after the last header token and after the last word in a line
        in dit units, default 31

--random
    PL: włącza lub wyłącza losowanie sekcji i wpisów
        true  = losowo
        false = po kolei z pliku JSON
    EN: enables or disables shuffling of sections and entries
        true  = random
        false = in file order

--amp
    PL: amplituda tonu (0..1), domyślnie 0.6
    EN: tone amplitude (0..1), default 0.6

--ramp
    PL: czas narastania/opadania obwiedni tonu [s], domyślnie 0.005
    EN: rise/fall envelope time [s], default 0.005

--end-silence
    PL: cisza na końcu pliku [s], domyślne 0.8s
    EN: silence appended at end of file [s], default 0.8s


UWAGI / NOTES
-------------

1 jednostka = 1 dit = 1.2 / FWPM sekundy

Przykład dla FWPM=12:
    1 dit = 0.100000 s

Układ przerw:
    - w nagłówku: tokeny rozdzielane są X, a po ostatnim tokenie jest Z
    - w linii:
        separator [ ]   daje 1 * Y
        separator [  ]  daje 2 * Y
        separator [   ] daje 3 * Y
      a po ostatnim słowie jest Z

Separator słów w JSON:
    Skrypt obsługuje znaczniki:
        [ ]
        [  ]
        [   ]
    oraz inne warianty z dowolną liczbą spacji w środku nawiasów.

Uwaga:
    W tej wersji WPM nie steruje już timingiem elementów.
    Cały timing jest liczony od FWPM.

Ramp / envelope:
    --ramp steruje łagodnym wejściem i zejściem tonu.
    Typowe wartości:
        0.003  = szybszy atak
        0.005  = standard
        0.008  = łagodniejszy atak
        0.010  = bardzo miękki atak

PRZYKŁADY / EXAMPLES
--------------------

Minimalne użycie / minimal usage:

    python3 generuj.py --wpm 27 --fwpm 27 --freq 600

Łagodniejsza rampa:

    python3 generuj.py --wpm 27 --fwpm 27 --freq 550 --amp 0.6 --ramp 0.008

Losowość włączona:

    python3 generuj.py --wpm 27 --fwpm 27 --freq 600 --random true

Bez losowości:

    python3 generuj.py --wpm 27 --fwpm 27 --freq 600 --random false

Pełna konfiguracja:

    python3 generuj.py --json lesson1.json --out lesson1.wav \
        --wpm 27 --fwpm 27 --freq 600 \
        --x 7 --y 7 --z 31 --random true --amp 0.6 --ramp 0.008

Przykład separatorów:
    "ADAM[ ]ADAM"    -> przerwa 1 * Y
    "ADAM[  ]ADAM"   -> przerwa 2 * Y
    "ADAM[   ]ADAM"  -> przerwa 3 * Y

Linux pipeline example:

    python3 generuj.py --wpm 25 --fwpm 25 --freq 550 --amp 0.6 --ramp 0.008 --random false && aplay cw_losowo.wav
"""

    p = argparse.ArgumentParser(
        prog="generuj.py",
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    p.add_argument("-j", "--json", default="plik.json",
                   help="ścieżka do pliku JSON")

    p.add_argument("-o", "--out", default="cw_losowo.wav",
                   help="plik wynikowy WAV")

    p.add_argument("--wpm", type=_positive_float, required=True,
                   help="parametr informacyjny/kompatybilnościowy")

    p.add_argument("--fwpm", type=_positive_float, required=True,
                   help="prędkość używana do całego timingu CW")

    p.add_argument("--freq", type=_positive_float, required=True,
                   help="częstotliwość tonu [Hz]")

    p.add_argument("--sr", type=int, default=44100,
                   help="sample rate WAV")

    p.add_argument("--x", type=_nonneg_int, default=7,
                   help="przerwa między tokenami nagłówka [dit units]")

    p.add_argument("--y", type=_nonneg_int, default=7,
                   help="bazowa przerwa na jedną spację w separatorze [ ] [dit units]")

    p.add_argument("--z", type=_nonneg_int, default=31,
                   help="przerwa po ostatnim tokenie nagłówka i po ostatnim słowie w linii [dit units]")

    p.add_argument("--random", type=_parse_bool, default=True,
                   help="losowość: true = włączona, false = wyłączona")

    p.add_argument("--amp", type=_nonneg_float, default=0.6,
                   help="amplituda tonu")

    p.add_argument("--ramp", type=_nonneg_float, default=0.005,
                   help="czas narastania/opadania tonu [s]")

    p.add_argument("--end-silence", type=_nonneg_float, default=0.8,
                   help="cisza na końcu pliku")

    return p


def main(argv: list[str] | None = None) -> int:
    print_banner_and_license()

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    json_path = Path(args.json)
    if not json_path.exists():
        parser.error(f"Nie znaleziono pliku JSON: {json_path.resolve()}")

    if args.sr <= 0:
        parser.error("--sr musi być > 0")
    if args.amp > 1.0:
        parser.error("--amp musi być w zakresie 0..1")

    out_path = Path(args.out)

    data_for_steps = json.loads(json_path.read_text(encoding="utf-8"))
    total_steps = estimate_total_steps(data_for_steps)

    progress = ProgressBar(total_steps, label="Generating WAVE", width=30, interval_s=0.12)

    samples = render_one_pass(
        json_path=json_path,
        sr=args.sr,
        freq=args.freq,
        fwpm=args.fwpm,
        X=args.x,
        Y=args.y,
        Z=args.z,
        randomize=args.random,
        amp=args.amp,
        ramp_s=args.ramp,
        end_silence=args.end_silence,
        progress=progress,
    )

    write_wav_mono16(out_path, samples, args.sr, progress=progress)
    progress.finish("OK: zapisano plik WAV.")

    print(f"Plik: {out_path.resolve()}")
    print(f"samples={len(samples)}, sr={args.sr}")
    print(f"WPM={args.wpm} (informacyjnie)")
    print(f"FWPM={args.fwpm} (steruje całym timingiem)")
    print(f"Random={'ON' if args.random else 'OFF'}")
    print(f"freq={args.freq:.2f} Hz")
    print(f"amp={args.amp:.3f}")
    print(f"ramp={args.ramp:.6f}s")
    print(f"dit={dit_time_from_speed(args.fwpm):.6f}s")
    print(f"X={args.x} dit -> {units_to_seconds(args.x, args.fwpm):.6f}s")
    print(f"Y={args.y} dit na 1 spację w separatorze [ ] -> {units_to_seconds(args.y, args.fwpm):.6f}s")
    print(f"Z={args.z} dit -> {units_to_seconds(args.z, args.fwpm):.6f}s")
    print("Przykład: [  ] = 2 * Y")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
