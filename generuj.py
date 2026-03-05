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

def farnsworth_scale(wpm: float, fwpm: float) -> float:
    """Rozciągnięcie przerw między literami i wyrazami do Farnsworth."""
    if fwpm >= wpm:
        return 1.0

    dit = 1.2 / wpm
    target_word_time = 60.0 / fwpm  # sekundy na "PARIS"

    fixed_units = 31
    variable_units = 19

    fixed_time = fixed_units * dit
    remaining = target_word_time - fixed_time
    if remaining <= 0:
        return 1.0

    scale = remaining / (variable_units * dit)
    return max(scale, 1.0)

# -------- audio primitives --------
def gen_tone(sr: int, freq: float, duration_s: float, amp: float = 0.35, ramp_s: float = 0.005) -> array:
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

def add_samples(dst: array, src: array):
    dst.extend(src)

# -------- CW encoder (string without spaces; we control gaps ourselves) --------
def cw_emit_token(token: str, sr: int, freq: float, wpm: float, fwpm: float, amp: float = 0.35) -> array:
    """
    Nadaje token (np. "ADAM" albo "A") jako ciąg znaków Morse'a.
    Przerwy wewnątrz litery = 1 dit (WPM)
    Przerwy między literami = 3 dit * scale (Farnsworth)
    """
    dit = 1.2 / wpm
    scale = farnsworth_scale(wpm, fwpm)

    intra = 1 * dit
    dah = 3 * dit
    inter_char = 3 * dit * scale

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
            add_samples(out, gen_tone(sr, freq, dit if e == "." else dah, amp=amp))
            if ei != len(code) - 1:
                add_samples(out, gen_silence(sr, intra))

        first_char = False

    return out

# -------- build one random pass and render with X/Y/Z --------
def parse_section_header(header: str) -> list[str]:
    return [t for t in header.strip().split() if t]

def split_wordline(raw: str) -> list[str]:
    s = raw.replace("[  ]", " ")
    return [t for t in s.strip().split() if t]

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
            steps += len(split_wordline(raw))  # słowa
    return max(1, steps)

def render_one_pass(
    json_path: Path,
    sr: int,
    freq: float,
    wpm: float,
    fwpm: float,
    X: float,
    Y: float,
    Z: float,
    amp: float = 0.35,
    end_silence: float = 0.8,
    progress: ProgressBar | None = None,
) -> array:
    data = json.loads(json_path.read_text(encoding="utf-8"))

    sections = [(hdr, entries) for hdr, entries in data]
    random.shuffle(sections)

    out = array('h')
    z_after_line = max(0.0, Z - Y)

    for hdr, entries in sections:
        if progress:
            progress.step(1)  # sekcja

        hdr_tokens = parse_section_header(hdr)
        for i, tok in enumerate(hdr_tokens):
            add_samples(out, cw_emit_token(tok, sr, freq, wpm, fwpm, amp=amp))
            add_samples(out, gen_silence(sr, Y if i == len(hdr_tokens) - 1 else X))
            if progress:
                progress.step(1)  # token nagłówka

        entries = list(entries)
        random.shuffle(entries)

        for raw in entries:
            if progress:
                progress.step(1)  # linia

            words = split_wordline(raw)
            for w in words:
                add_samples(out, cw_emit_token(w, sr, freq, wpm, fwpm, amp=amp))
                add_samples(out, gen_silence(sr, Y))
                if progress:
                    progress.step(1)  # słowo

            add_samples(out, gen_silence(sr, z_after_line))

    add_samples(out, gen_silence(sr, end_silence))
    return out

def write_wav_mono16(path: Path, samples: array, sr: int, progress: ProgressBar | None = None):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)

        # zapis w kawałkach, żeby można było odświeżać pasek
        chunk = 8192  # próbek na chunk (możesz zwiększyć)
        total = len(samples)
        written = 0

        while written < total:
            end = min(total, written + chunk)
            wf.writeframesraw(samples[written:end].tobytes())
            written = end
            if progress:
                progress._render()  # tylko odśwież (bez zwiększania kroków)

        wf.writeframes(b"")  # finalize

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

def build_arg_parser() -> argparse.ArgumentParser:

    description = """
CW WAV generator from JSON file.

Generator pliku WAV z kodem Morse'a na podstawie pliku JSON.
Program losuje sekcje i generuje sygnał CW z zadanymi przerwami.
"""

    epilog = """
PARAMETRY / PARAMETERS
----------------------

--wpm
    PL: prędkość znaków Morse'a w słowach na minutę
    EN: Morse character speed in words per minute

--fwpm
    PL: prędkość Farnsworth (wolniejsze odstępy między znakami)
    EN: Farnsworth speed (slower spacing between characters)

--freq
    PL: częstotliwość tonu CW w Hz
    EN: CW tone frequency in Hz

--sr
    PL: częstotliwość próbkowania WAV, domyślne 44100Hz
    EN: WAV sample rate, default 44100Hz

--x
    PL: przerwa między literami nagłówka, domyślne 0.5s
    EN: pause between header letters, default 0.5s

--y
    PL: przerwa po każdym słowie, domyślne 1.0s
    EN: pause after each word, default 1.0s

--z
    PL: przerwa po całej grupie słów, domyślne 3.0s
    EN: pause after word group, default 3.0s

--amp
    PL: amplituda tonu (0..1) domyślne 0.35
    EN: tone amplitude (0..1) default 0.35

--end-silence
    PL: cisza na końcu pliku [s] domyślne 0.8s
    EN: silence appended at end of file [s] default 0.8s


PRZYKŁADY / EXAMPLES
--------------------

Minimalne użycie / minimal usage:

    python3 generuj.py --wpm 20 --fwpm 12 --freq 600

Pełna konfiguracja:

    python3 generuj.py --json lesson1.json --out lesson1.wav \
        --wpm 20 --fwpm 12 --freq 600 \
        --x 1.0 --y 1.0 --z 3.0

Szybsze CW:

    python3 generuj.py --json words.json --out fast.wav \
        --wpm 30 --fwpm 20 --freq 700

Linux pipeline example:

    python3 generuj.py --wpm 25 --fwpm 15 --freq 650 && aplay cw_losowo.wav
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
                   help="prędkość znaków Morse'a (WPM)")

    p.add_argument("--fwpm", type=_positive_float, required=True,
                   help="prędkość Farnsworth")

    p.add_argument("--freq", type=_positive_float, required=True,
                   help="częstotliwość tonu [Hz]")

    p.add_argument("--sr", type=int, default=44100,
                   help="sample rate WAV")

    p.add_argument("--x", type=_nonneg_float, default=0.5,
                   help="przerwa między literami nagłówka")

    p.add_argument("--y", type=_nonneg_float, default=1.0,
                   help="przerwa po słowie")

    p.add_argument("--z", type=_nonneg_float, default=3.0,
                   help="przerwa po grupie słów")

    p.add_argument("--amp", type=_nonneg_float, default=0.35,
                   help="amplituda tonu")

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

    # pre-scan JSON do policzenia kroków (dla paska postępu)
    data_for_steps = json.loads(json_path.read_text(encoding="utf-8"))
    total_steps = estimate_total_steps(data_for_steps)

    progress = ProgressBar(total_steps, label="Generating WAVE", width=30, interval_s=0.12)

    samples = render_one_pass(
        json_path=json_path,
        sr=args.sr,
        freq=args.freq,
        wpm=args.wpm,
        fwpm=args.fwpm,
        X=args.x, Y=args.y, Z=args.z,
        amp=args.amp,
        end_silence=args.end_silence,
        progress=progress,
    )

    write_wav_mono16(out_path, samples, args.sr, progress=progress)
    progress.finish("OK: zapisano plik WAV.")

    print(f"Plik: {out_path.resolve()}")
    print(f"samples={len(samples)}, sr={args.sr}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())