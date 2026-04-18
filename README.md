# 🎧 CW WAV Generator (Morse Code)

Generator plików WAV z kodem Morse’a na podstawie pliku JSON.  
Generuje realistyczny sygnał CW z pełną kontrolą timingu (FWPM), przerw (X/Y/Z) oraz parametrów audio.

---

# 🇵🇱 Polski

## 📌 Opis

Skrypt generuje plik WAV zawierający kod Morse’a na podstawie struktury JSON.  
Może działać w trybie losowym lub deterministycznym.

Obsługuje:
- alfabet A–Z i cyfry 0–9
- znaki specjalne (. , ? / - ( ))
- dynamiczne przerwy `[   ]`
- realistyczną obwiednię audio (brak kliknięć)

---

## ⚙️ Wymagania

- Python 3.8+
- brak dodatkowych bibliotek

---

## ▶️ Uruchomienie

```bash
python3 generuj.py --wpm 25 --fwpm 25 --freq 600
```

---

## 📥 Parametry

| Parametr | Opis |
|----------|------|
| `--wpm` | informacyjny |
| `--fwpm` | steruje całym timingiem CW |
| `--freq` | częstotliwość tonu (Hz) |
| `--x` | przerwa między tokenami nagłówka |
| `--y` | bazowa przerwa dla `[ ]` |
| `--z` | przerwa końcowa |
| `--random` | losowanie danych |
| `--amp` | amplituda (0–1) |
| `--ramp` | czas narastania/opadania |
| `--start-silence` | cisza na początku |
| `--end-silence` | cisza na końcu |

---

## ⏱️ Timing

```
dit = 1.2 / FWPM
```

---

## 🧩 Separator `[   ]`

```
[ ]   = 1 × Y
[  ]  = 2 × Y
[   ] = 3 × Y
```

---

## 📄 Przykład JSON

```json
[
  ["A B", [
    "ADAM[ ]ADAM",
    "TEST[  ]TEST"
  ]]
]
```

---

## 📜 Licencja

MIT License  
© 2026 Maniek SP8KM HAMHOBBY.PL

---

# 🇬🇧 English

## 📌 Description

This script generates a WAV file containing Morse code from a JSON input file.  
It supports both random and deterministic playback.

Features:
- full A–Z alphabet and digits 0–9
- special characters (. , ? / - ( ))
- dynamic spacing `[   ]`
- smooth audio envelope (no clicks)

---

## ⚙️ Requirements

- Python 3.8+
- no external dependencies

---

## ▶️ Usage

```bash
python3 generuj.py --wpm 25 --fwpm 25 --freq 600
```

---

## 📥 Parameters

| Parameter | Description |
|----------|-------------|
| `--wpm` | informational only |
| `--fwpm` | controls full CW timing |
| `--freq` | tone frequency (Hz) |
| `--x` | gap between header tokens |
| `--y` | base gap for `[ ]` |
| `--z` | final gap |
| `--random` | enable shuffle |
| `--amp` | amplitude (0–1) |
| `--ramp` | envelope time |
| `--start-silence` | silence at start |
| `--end-silence` | silence at end |

---

## ⏱️ Timing

```
dit = 1.2 / FWPM
```

---

## 🧩 `[   ]` Separator

```
[ ]   = 1 × Y
[  ]  = 2 × Y
[   ] = 3 × Y
```

---

## 📄 Example JSON

```json
[
  ["A B", [
    "ADAM[ ]ADAM",
    "TEST[  ]TEST"
  ]]
]
```

---

## 📜 License

MIT License  
© 2026 Maniek SP8KM HAMHOBBY.PL

---

# 🇩🇪 Deutsch

## 📌 Beschreibung

Dieses Skript erzeugt eine WAV-Datei mit Morsecode aus einer JSON-Datei.  
Es unterstützt sowohl zufällige als auch feste Reihenfolge.

Funktionen:
- Alphabet A–Z und Ziffern 0–9
- Sonderzeichen (. , ? / - ( ))
- dynamische Pausen `[   ]`
- weiche Tonhüllkurve (kein Klicken)

---

## ⚙️ Anforderungen

- Python 3.8+
- keine externen Bibliotheken

---

## ▶️ Nutzung

```bash
python3 generuj.py --wpm 25 --fwpm 25 --freq 600
```

---

## 📥 Parameter

| Parameter | Beschreibung |
|----------|--------------|
| `--wpm` | nur informativ |
| `--fwpm` | steuert das gesamte CW-Timing |
| `--freq` | Tonfrequenz (Hz) |
| `--x` | Pause zwischen Header-Token |
| `--y` | Basisabstand für `[ ]` |
| `--z` | Endpause |
| `--random` | Zufallsmodus |
| `--amp` | Amplitude (0–1) |
| `--ramp` | Ein-/Ausblendzeit |
| `--start-silence` | Stille am Anfang |
| `--end-silence` | Stille am Ende |

---

## ⏱️ Timing

```
dit = 1.2 / FWPM
```

---

## 🧩 `[   ]` Separator

```
[ ]   = 1 × Y
[  ]  = 2 × Y
[   ] = 3 × Y
```

---

## 📄 Beispiel JSON

```json
[
  ["A B", [
    "ADAM[ ]ADAM",
    "TEST[  ]TEST"
  ]]
]
```

---

## 📜 Lizenz

MIT License  
© 2026 Maniek SP8KM HAMHOBBY.PL