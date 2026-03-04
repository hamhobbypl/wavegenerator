import json
import math
import random
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

# -------- Farnsworth --------
def farnsworth_scale(wpm: float, fwpm: float) -> float:
    """Skala rozciągnięcia przerw między znakami i wyrazami (Farnsworth)."""
    if fwpm >= wpm:
        return 1.0

    dit = 1.2 / wpm
    target_word_time = 60.0 / fwpm  # sekundy na słowo "PARIS"

    fixed_units = 31      # elementy + przerwy wewnątrz liter
    variable_units = 19   # przerwy między literami (12) + przerwa między wyrazami (7)

    fixed_time = fixed_units * dit
    remaining = target_word_time - fixed_time
    if remaining <= 0:
        return 1.0

    scale = remaining / (variable_units * dit)
    return max(scale, 1.0)

# -------- audio primitives --------
def gen_tone(sr: int, freq: float, duration_s: float, amp: float = 0.35, ramp_s: float = 0.005) -> array:
    """Sinus z rampą (anti-click). 16-bit mono."""
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

        # cosine ramp in/out
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

# -------- text -> CW --------
def text_to_cw_samples(
    text: str,
    sr: int,
    freq: float,
    wpm: float,
    fwpm: float,
    amp: float = 0.35,
    extra_end_silence_s: float = 0.8,
    base_line_gap_s: float = 0.12,
    wordline_extra_gap_s: float = 0.0,     # EXTRA po każdej linii słów (w sekundach)
    header_line_gap_mult: float = 2.0,     # przerwa między nagłówkiem a słowami = base_line_gap_s * mult
) -> array:
    """
    Zamiana tekstu na CW.
    - spacja ' ' => przerwa między wyrazami (7 dit * scale); wiele spacji = większa przerwa
    - przerwa między literami => 3 dit * scale
    - przerwa wewnątrz litery => 1 dit (bez scale)
    - newline => pauza:
        * domyślnie base_line_gap_s
        * jeśli linia jest nagłówkiem sekcji: base_line_gap_s * header_line_gap_mult
        * jeśli linia jest linią słów: base_line_gap_s + wordline_extra_gap_s
    """
    dit = 1.2 / wpm
    scale = farnsworth_scale(wpm, fwpm)

    intra = 1 * dit
    dah = 3 * dit
    inter_char = 3 * dit * scale
    inter_word = 7 * dit * scale

    out = array('h')
    text = text.upper()
    lines = text.splitlines()

    def is_section_header(line: str) -> bool:
        # rozpoznaj nagłówki w stylu: "A   A   A" (po formatowaniu mogą być wielokrotne spacje)
        tokens = [t for t in line.strip().split() if t]
        return len(tokens) == 3 and all(len(t) == 1 and t.isalpha() for t in tokens) and tokens[0] == tokens[1] == tokens[2]

    def is_word_line(line: str) -> bool:
        # wszystko co nie jest nagłówkiem, a ma jakieś znaki alfanumeryczne
        return (not is_section_header(line)) and any(ch.isalnum() for ch in line)

    for li, line in enumerate(lines):
        if li > 0:
            prev_line = lines[li - 1]
            # przerwa po poprzedniej linii (kontrolujemy ją tutaj)
            if is_section_header(prev_line):
                gap = base_line_gap_s * header_line_gap_mult  # 2x większa przerwa po "A A A"
            elif is_word_line(prev_line):
                gap = base_line_gap_s + wordline_extra_gap_s  # dodatkowa przerwa po każdym wierszu słów
            else:
                gap = base_line_gap_s

            add_samples(out, gen_silence(sr, gap))

        prev_was_symbol = False

        for ch in line:
            if ch == " ":
                add_samples(out, gen_silence(sr, inter_word))
                prev_was_symbol = False
                continue

            code = MORSE.get(ch)
            if not code:
                add_samples(out, gen_silence(sr, inter_char))
                prev_was_symbol = False
                continue

            if prev_was_symbol:
                add_samples(out, gen_silence(sr, inter_char))

            for ei, e in enumerate(code):
                add_samples(out, gen_tone(sr, freq, dit if e == "." else dah, amp=amp))
                if ei != len(code) - 1:
                    add_samples(out, gen_silence(sr, intra))

            prev_was_symbol = True

    add_samples(out, gen_silence(sr, extra_end_silence_s))
    return out

# -------- building one random pass --------
def format_section_header(header: str, gap_spaces: int) -> str:
    tokens = header.strip().split()
    return (" " * gap_spaces).join(tokens)

def build_random_pass_text(json_path: Path, header_gap_spaces: int = 3) -> str:
    data = json.loads(json_path.read_text(encoding="utf-8"))

    sections = [(hdr, entries) for hdr, entries in data]
    random.shuffle(sections)  # losowa kolejność sekcji; usuń jeśli chcesz A..Z

    lines = []
    for hdr, entries in sections:
        # nagłówek sekcji z dłuższymi przerwami (wiele spacji)
        lines.append(format_section_header(hdr, header_gap_spaces))

        # słowa w sekcji
        entries = list(entries)
        random.shuffle(entries)
        for s in entries:
            lines.append(s.replace("[  ]", " "))

        # pusta linia między sekcjami (będzie potraktowana jak zwykła linia)
        lines.append("")

    return "\n".join(lines)

# -------- WAV writer --------
def write_wav_mono16(path: Path, samples: array, sr: int):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())

def main():
    print("=== Generator CW WAV z pliku JSON (sekcje A A A, ... ) ===")

    json_file = input("Ścieżka do pliku JSON [plik.json]: ").strip() or "plik.json"
    json_path = Path(json_file)
    if not json_path.exists():
        raise SystemExit(f"Nie znaleziono pliku: {json_path.resolve()}")

    wpm = float(input("WPM (prędkość znaków, np. 20): ").strip())
    fwpm = float(input("FWPM (Farnsworth, np. 12): ").strip())
    freq = float(input("Częstotliwość tonu [Hz] (np. 600): ").strip())

    sr_in = input("Sample rate [Hz] (enter=44100): ").strip()
    sr = int(sr_in) if sr_in else 44100

    out_name = input("Nazwa pliku WAV (enter=cw_losowo.wav): ").strip() or "cw_losowo.wav"
    out_path = Path(out_name)

    # --- ustawienia nagłówków sekcji ---
    header_gap_spaces_in = input("Ile 'długich przerw' (spacji) między literami nagłówka (enter=2): ").strip()
    header_gap_spaces = int(header_gap_spaces_in) if header_gap_spaces_in else 2

    # --- dodatkowa przerwa po każdej linii słów (sekundy) ---
    wordline_extra_gap_in = input("Dodatkowa przerwa po KAŻDYM wierszu słów [s] (enter=0.5): ").strip()
    wordline_extra_gap_s = float(wordline_extra_gap_in) if wordline_extra_gap_in else 0.5

    # --- bazowa przerwa między liniami (sekundy) ---
    base_line_gap_in = input("Bazowa przerwa między liniami [s] (enter=0.3): ").strip()
    base_line_gap_s = float(base_line_gap_in) if base_line_gap_in else 0.3

    # 1) zbuduj jeden losowy przebieg całego materiału
    text = build_random_pass_text(json_path=json_path, header_gap_spaces=header_gap_spaces)

    # 2) wygeneruj próbki CW
    samples = text_to_cw_samples(
        text=text,
        sr=sr,
        freq=freq,
        wpm=wpm,
        fwpm=fwpm,
        amp=0.35,
        extra_end_silence_s=0.8,
        base_line_gap_s=base_line_gap_s,
        wordline_extra_gap_s=wordline_extra_gap_s,
        header_line_gap_mult=2.0,  # 2x większa przerwa po nagłówku
    )

    # 3) zapisz WAV
    write_wav_mono16(out_path, samples, sr)
    print(f"OK: zapisano {out_path.resolve()} (samples={len(samples)}, sr={sr})")

if __name__ == "__main__":
    main()
