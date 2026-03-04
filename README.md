(c) 2026 Maniek SP8KM HAMHOBBY.PL — MIT License

usage: generuj.py [-h] [-j JSON] [-o OUT] --wpm WPM --fwpm FWPM --freq FREQ
                 [--sr SR] [--x X] [--y Y] [--z Z] [--amp AMP]
                 [--end-silence END_SILENCE]

CW WAV generator from JSON file.

Generator pliku WAV z kodem Morse'a na podstawie pliku JSON.
Program losuje sekcje i generuje sygnał CW z zadanymi przerwami.

options:
  -h, --help            show this help message and exit
  -j JSON, --json JSON  ścieżka do pliku JSON
  -o OUT, --out OUT     plik wynikowy WAV
  --wpm WPM             prędkość znaków Morse'a (WPM)
  --fwpm FWPM           prędkość Farnsworth
  --freq FREQ           częstotliwość tonu [Hz]
  --sr SR               sample rate WAV
  --x X                 przerwa między literami nagłówka
  --y Y                 przerwa po słowie
  --z Z                 przerwa po grupie słów
  --amp AMP             amplituda tonu
  --end-silence END_SILENCE
                        cisza na końcu pliku

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
    PL: częstotliwość próbkowania WAV
    EN: WAV sample rate

--x
    PL: przerwa między literami nagłówka
    EN: pause between header letters

--y
    PL: przerwa po każdym słowie
    EN: pause after each word

--z
    PL: przerwa po całej grupie słów
    EN: pause after word group

--amp
    PL: amplituda tonu (0..1)
    EN: tone amplitude (0..1)

--end-silence
    PL: cisza na końcu pliku
    EN: silence appended at end of file

PRZYKŁADY / EXAMPLES
--------------------

Minimalne użycie / minimal usage:

    python3 generuj.py --wpm 20 --fwpm 12 --freq 600

Pełna konfiguracja:

    python3 generuj.py --json lesson1.json --out lesson1.wav         --wpm 20 --fwpm 12 --freq 600         --x 1.0 --y 1.0 --z 3.0

Szybsze CW:

    python3 generuj.py --json words.json --out fast.wav         --wpm 30 --fwpm 20 --freq 700

Linux pipeline example:

    python3 generuj.py --wpm 25 --fwpm 15 --freq 650 && aplay cw_losowo.wav
