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
            # nieznany znak: mała pauza
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
    # "A A A" -> ["A","A","A"]
    return [t for t in header.strip().split() if t]

def split_wordline(raw: str) -> list[str]:
    # "ADAM[  ]ADAM[  ]ADAM" -> ["ADAM","ADAM","ADAM"]
    s = raw.replace("[  ]", " ")
    return [t for t in s.strip().split() if t]

def render_one_pass(json_path: Path, sr: int, freq: float, wpm: float, fwpm: float,
                    X: float, Y: float, Z: float,
                    amp: float = 0.35,
                    end_silence: float = 0.8) -> array:
    data = json.loads(json_path.read_text(encoding="utf-8"))

    sections = [(hdr, entries) for hdr, entries in data]
    random.shuffle(sections)  # losowa kolejność sekcji

    out = array('h')

    for hdr, entries in sections:
        # ---- nagłówek: A X A X A X ----
        hdr_tokens = parse_section_header(hdr)
        for i, tok in enumerate(hdr_tokens):
            add_samples(out, cw_emit_token(tok, sr, freq, wpm, fwpm, amp=amp))
            add_samples(out, gen_silence(sr, X))  # po każdej literze nagłówka, także po ostatniej (wg Twojego przykładu)

        # ---- linie słów w sekcji ----
        entries = list(entries)
        random.shuffle(entries)

        for raw in entries:
            words = split_wordline(raw)

            # ADAM Y ADAM Y ADAM Y
            for w in words:
                add_samples(out, cw_emit_token(w, sr, freq, wpm, fwpm, amp=amp))
                add_samples(out, gen_silence(sr, Y))  # po każdym słowie, także po ostatnim (jak w przykładzie)

            # ... Z (po całej linii słów)
            add_samples(out, gen_silence(sr, Z))

    add_samples(out, gen_silence(sr, end_silence))
    return out

def write_wav_mono16(path: Path, samples: array, sr: int):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())

def main():
    print("=== Generator CW WAV z pliku JSON (X/Y/Z w sekundach) [HAMHOBBY.PL]===")

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

    print("\nUstawienia przerw (sekundy):")
    X_in = input("przerwa pomiędzy literami nagłówka [s] (enter=1.0): ").strip()
    Y_in = input("przerwa po każdym słowie [s] (enter=1.0): ").strip()
    Z_in = input("przerwa po każdej grupie słów [s] (enter=3.0): ").strip()

    X = float(X_in) if X_in else 1.0
    Y = float(Y_in) if Y_in else 1.0
    Z = float(Z_in) if Z_in else 3.0

    samples = render_one_pass(
        json_path=json_path,
        sr=sr,
        freq=freq,
        wpm=wpm,
        fwpm=fwpm,
        X=X, Y=Y, Z=Z,
        amp=0.35,
        end_silence=0.8
    )

    write_wav_mono16(out_path, samples, sr)
    print(f"\nOK: zapisano {out_path.resolve()} (samples={len(samples)}, sr={sr})")

if __name__ == "__main__":
    main()
