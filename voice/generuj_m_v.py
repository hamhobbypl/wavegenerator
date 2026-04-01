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
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

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

# mapowanie znak -> nazwa pliku WAV dla trybu literowania
SPELLING_WAV = {
    **{chr(ord("A") + i): f"{chr(ord('A') + i)}.wav" for i in range(26)},
    **{str(i): f"{i}.wav" for i in range(10)},
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
    """Prosty progress bar w jednej linii."""
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
    return 1.2 / speed_wpm


def units_to_seconds(units: int, speed_wpm: float) -> float:
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


def resample_linear_mono16(samples: array, src_sr: int, dst_sr: int) -> array:
    if src_sr == dst_sr or len(samples) == 0:
        return array('h', samples)

    src_len = len(samples)
    dst_len = max(1, int(round(src_len * dst_sr / src_sr)))
    out = array('h')

    for i in range(dst_len):
        pos = i * (src_sr / dst_sr)
        left = int(math.floor(pos))
        right = min(left + 1, src_len - 1)
        frac = pos - left
        v = int(samples[left] * (1.0 - frac) + samples[right] * frac)
        out.append(v)

    return out


def wav_bytes_to_mono16(frames: bytes, sampwidth: int, channels: int) -> array:
    if sampwidth not in (1, 2):
        raise ValueError(f"Nieobsługiwana szerokość próbki WAV: {sampwidth} bajt(y)")

    if sampwidth == 1:
        raw = array('B', frames)
        mono = array('h')
        if channels == 1:
            for x in raw:
                mono.append((x - 128) << 8)
        elif channels == 2:
            for i in range(0, len(raw) - 1, 2):
                v = (((raw[i] - 128) << 8) + ((raw[i + 1] - 128) << 8)) // 2
                mono.append(v)
        else:
            raise ValueError(f"Nieobsługiwana liczba kanałów WAV: {channels}")
        return mono

    pcm = array('h')
    pcm.frombytes(frames)

    if channels == 1:
        return pcm
    if channels == 2:
        mono = array('h')
        for i in range(0, len(pcm) - 1, 2):
            mono.append((pcm[i] + pcm[i + 1]) // 2)
        return mono

    raise ValueError(f"Nieobsługiwana liczba kanałów WAV: {channels}")


def load_wav_clip_mono16(path: Path, target_sr: int) -> array:
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        src_sr = wf.getframerate()
        nframes = wf.getnframes()
        frames = wf.readframes(nframes)

    mono = wav_bytes_to_mono16(frames, sampwidth, channels)
    if src_sr != target_sr:
        mono = resample_linear_mono16(mono, src_sr, target_sr)
    return mono


# -------- CW encoder --------
def cw_emit_token(
    token: str,
    sr: int,
    freq: float,
    fwpm: float,
    amp: float = 0.6,
    ramp_s: float = 0.005
) -> array:
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


# -------- spelling encoder from letter WAV files --------
def spelling_emit_token(
    token: str,
    sr: int,
    fwpm: float,
    letters_dir: Path,
    clip_cache: dict[str, array],
    letter_gap_units: int = 1,
    missing_gap_units: int = 3,
) -> array:
    """
    Składa token z plików WAV typu A.wav, B.wav, 1.wav itd.
    """
    out = array('h')
    token = token.upper()

    letter_gap_s = units_to_seconds(letter_gap_units, fwpm)
    missing_gap_s = units_to_seconds(missing_gap_units, fwpm)

    emitted_any = False
    for idx, ch in enumerate(token):
        wav_name = SPELLING_WAV.get(ch)
        if wav_name is None:
            if emitted_any:
                add_samples(out, gen_silence(sr, missing_gap_s))
            continue

        wav_path = letters_dir / wav_name
        if not wav_path.exists():
            print(f"UWAGA: brak pliku WAV dla znaku {ch!r}: {wav_path}", file=sys.stderr)
            if emitted_any:
                add_samples(out, gen_silence(sr, missing_gap_s))
            continue

        if wav_name not in clip_cache:
            clip_cache[wav_name] = load_wav_clip_mono16(wav_path, sr)

        if emitted_any:
            add_samples(out, gen_silence(sr, letter_gap_s))

        add_samples(out, clip_cache[wav_name])
        emitted_any = True

    return out


# -------- parsing helpers --------
def parse_section_header(header: str) -> list[str]:
    return [t for t in header.strip().split() if t]


def parse_wordline(raw: str, y_units_per_space: int) -> tuple[list[str], list[int]]:
    parts: list[tuple[str, int | None]] = []
    pos = 0

    for m in SEPARATOR_RE.finditer(raw):
        left = raw[pos:m.start()]
        if left.strip():
            parts.append((left.strip(), None))

        spaces_inside = len(m.group(1))
        gap_units = spaces_inside * y_units_per_space
        parts.append(("", gap_units))
        pos = m.end()

    tail = raw[pos:]
    if tail.strip():
        parts.append((tail.strip(), None))

    words: list[str] = []
    gaps: list[int] = []
    pending_explicit_gap = False

    for text, gap_units in parts:
        if gap_units is None:
            subwords = [t for t in text.split() if t]
            if not subwords:
                continue

            for i, subword in enumerate(subwords):
                if not words:
                    words.append(subword)
                else:
                    if pending_explicit_gap and i == 0:
                        words.append(subword)
                    else:
                        gaps.append(y_units_per_space)
                        words.append(subword)

            pending_explicit_gap = False
        else:
            if not words:
                continue
            gaps.append(gap_units)
            pending_explicit_gap = True

    if len(gaps) > max(0, len(words) - 1):
        gaps = gaps[:len(words) - 1]

    return words, gaps


def estimate_total_steps(prepared_sections) -> int:
    steps = 0
    for hdr, entries in prepared_sections:
        steps += 1
        hdr_tokens = parse_section_header(hdr)
        steps += len(hdr_tokens)
        steps += len(entries)
        for raw in entries:
            words, _gaps = parse_wordline(raw, y_units_per_space=1)
            steps += len(words)
    return max(1, steps)


def prepare_sections(data, randomize: bool) -> list[tuple[str, list[str]]]:
    sections = [(hdr, list(entries)) for hdr, entries in data]
    if randomize:
        random.shuffle(sections)
        for i, (hdr, entries) in enumerate(sections):
            random.shuffle(entries)
            sections[i] = (hdr, entries)
    return sections


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
def render_one_pass_cw(
    prepared_sections,
    sr: int,
    freq: float,
    fwpm: float,
    X: int,
    Y: int,
    Z: int,
    amp: float = 0.6,
    ramp_s: float = 0.005,
    end_silence: float = 0.8,
    progress: ProgressBar | None = None,
) -> array:
    out = array('h')

    X_s = units_to_seconds(X, fwpm)
    Z_s = units_to_seconds(Z, fwpm)

    for hdr, entries in prepared_sections:
        if progress:
            progress.step(1)

        hdr_tokens = parse_section_header(hdr)
        for i, tok in enumerate(hdr_tokens):
            add_samples(out, cw_emit_token(tok, sr, freq, fwpm, amp=amp, ramp_s=ramp_s))
            if i == len(hdr_tokens) - 1:
                add_samples(out, gen_silence(sr, Z_s))
            else:
                add_samples(out, gen_silence(sr, X_s))
            if progress:
                progress.step(1)

        for raw in entries:
            if progress:
                progress.step(1)

            words, gaps_units = parse_wordline(raw, y_units_per_space=Y)

            for i, w in enumerate(words):
                add_samples(out, cw_emit_token(w, sr, freq, fwpm, amp=amp, ramp_s=ramp_s))

                if i == len(words) - 1:
                    add_samples(out, gen_silence(sr, Z_s))
                else:
                    gap_units = gaps_units[i] if i < len(gaps_units) else Y
                    add_samples(out, gen_silence(sr, units_to_seconds(gap_units, fwpm)))

                if progress:
                    progress.step(1)

    add_samples(out, gen_silence(sr, end_silence))
    return out


def render_one_pass_spelling(
    prepared_sections,
    sr: int,
    fwpm: float,
    X: int,
    Y: int,
    Z: int,
    letters_dir: Path,
    spelling_letter_gap_units: int = 1,
    end_silence: float = 0.8,
    progress: ProgressBar | None = None,
) -> array:
    out = array('h')
    clip_cache: dict[str, array] = {}

    X_s = units_to_seconds(X, fwpm)
    Z_s = units_to_seconds(Z, fwpm)

    for hdr, entries in prepared_sections:
        if progress:
            progress.step(1)

        hdr_tokens = parse_section_header(hdr)
        for i, tok in enumerate(hdr_tokens):
            add_samples(
                out,
                spelling_emit_token(
                    tok,
                    sr=sr,
                    fwpm=fwpm,
                    letters_dir=letters_dir,
                    clip_cache=clip_cache,
                    letter_gap_units=spelling_letter_gap_units,
                )
            )

            if i == len(hdr_tokens) - 1:
                add_samples(out, gen_silence(sr, Z_s))
            else:
                add_samples(out, gen_silence(sr, X_s))

            if progress:
                progress.step(1)

        for raw in entries:
            if progress:
                progress.step(1)

            words, gaps_units = parse_wordline(raw, y_units_per_space=Y)

            for i, w in enumerate(words):
                add_samples(
                    out,
                    spelling_emit_token(
                        w,
                        sr=sr,
                        fwpm=fwpm,
                        letters_dir=letters_dir,
                        clip_cache=clip_cache,
                        letter_gap_units=spelling_letter_gap_units,
                    )
                )

                if i == len(words) - 1:
                    add_samples(out, gen_silence(sr, Z_s))
                else:
                    gap_units = gaps_units[i] if i < len(gaps_units) else Y
                    add_samples(out, gen_silence(sr, units_to_seconds(gap_units, fwpm)))

                if progress:
                    progress.step(1)

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


def default_spelling_output_path(out_path: Path) -> Path:
    return out_path.with_name(f"{out_path.stem}_litery{out_path.suffix}")


def build_arg_parser() -> argparse.ArgumentParser:
    description = """
CW WAV generator from JSON file.

Generator pliku WAV z kodem Morse'a na podstawie pliku JSON.
Dodatkowo generuje drugi plik WAV z literowaniem na bazie plików A.wav, B.wav itd.
"""

    p = argparse.ArgumentParser(
        prog="generuj.py",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    p.add_argument("-j", "--json", default="plik.json",
                   help="ścieżka do pliku JSON")

    p.add_argument("-o", "--out", default="cw_losowo.wav",
                   help="plik wynikowy WAV z kodem Morse'a")

    p.add_argument("--out-spell", default=None,
                   help="plik wynikowy WAV z literowaniem; domyślnie *_litery.wav")

    p.add_argument("--letters-dir", default=None,
                   help="katalog z plikami A.wav, B.wav, ...; domyślnie katalog skryptu")

    p.add_argument("--spell-gap", type=_nonneg_int, default=1,
                   help="przerwa między literami w trybie literowania [dit units], domyślnie 1")

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
    out_spell_path = Path(args.out_spell) if args.out_spell else default_spelling_output_path(out_path)

    script_dir = Path(__file__).resolve().parent
    letters_dir = Path(args.letters_dir) if args.letters_dir else script_dir

    data = json.loads(json_path.read_text(encoding="utf-8"))
    prepared_sections = prepare_sections(data, randomize=args.random)
    total_steps = estimate_total_steps(prepared_sections)

    progress_cw = ProgressBar(total_steps, label="Generating CW", width=30, interval_s=0.12)
    samples_cw = render_one_pass_cw(
        prepared_sections=prepared_sections,
        sr=args.sr,
        freq=args.freq,
        fwpm=args.fwpm,
        X=args.x,
        Y=args.y,
        Z=args.z,
        amp=args.amp,
        ramp_s=args.ramp,
        end_silence=args.end_silence,
        progress=progress_cw,
    )
    write_wav_mono16(out_path, samples_cw, args.sr, progress=progress_cw)
    progress_cw.finish("OK: zapisano plik CW WAV.")

    progress_spell = ProgressBar(total_steps, label="Generating SPELL", width=30, interval_s=0.12)
    samples_spell = render_one_pass_spelling(
        prepared_sections=prepared_sections,
        sr=args.sr,
        fwpm=args.fwpm,
        X=args.x,
        Y=args.y,
        Z=args.z,
        letters_dir=letters_dir,
        spelling_letter_gap_units=args.spell_gap,
        end_silence=args.end_silence,
        progress=progress_spell,
    )
    write_wav_mono16(out_spell_path, samples_spell, args.sr, progress=progress_spell)
    progress_spell.finish("OK: zapisano plik WAV z literowaniem.")

    print()
    print(f"CW:        {out_path.resolve()}")
    print(f"Literowanie: {out_spell_path.resolve()}")
    print(f"Katalog liter: {letters_dir.resolve()}")
    print(f"samples_cw={len(samples_cw)}, samples_spell={len(samples_spell)}, sr={args.sr}")
    print(f"WPM={args.wpm} (informacyjnie)")
    print(f"FWPM={args.fwpm} (steruje timingiem)")
    print(f"Random={'ON' if args.random else 'OFF'}")
    print(f"freq={args.freq:.2f} Hz")
    print(f"amp={args.amp:.3f}")
    print(f"ramp={args.ramp:.6f}s")
    print(f"dit={dit_time_from_speed(args.fwpm):.6f}s")
    print(f"X={args.x} dit -> {units_to_seconds(args.x, args.fwpm):.6f}s")
    print(f"Y={args.y} dit -> {units_to_seconds(args.y, args.fwpm):.6f}s")
    print(f"Z={args.z} dit -> {units_to_seconds(args.z, args.fwpm):.6f}s")
    print(f"spell-gap={args.spell_gap} dit -> {units_to_seconds(args.spell_gap, args.fwpm):.6f}s")
    print("Przykład: [  ] = 2 * Y")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
