(c) 2026 Maniek SP8KM HAMHOBBY.PL — MIT License

usage: generuj.py [-h] [-j JSON] [-o OUT] --wpm WPM --fwpm FWPM --freq FREQ
                 [--sr SR] [--x X] [--y Y] [--z Z] [--amp AMP]
                 [--end-silence END_SILENCE]

CW WAV generator from JSON file.

Generator pliku WAV z kodem Morse'a na podstawie pliku JSON.
Program losuje sekcje i generuje sygnał CW z zadanymi przerwami.
Kropka, kreska i X/Y/Z są liczone od FWPM.

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
    PL: przerwa po słowach wewnątrz linii w jednostkach dit, domyślne 21
    EN: pause between words inside a line in dit units, default 21

--z
    PL: przerwa po ostatnim tokenie nagłówka oraz po ostatnim słowie w linii
        w jednostkach dit, domyślne 31
    EN: pause after the last header token and after the last word in a line
        in dit units, default 31

--amp
    PL: amplituda tonu (0..1), domyślne 0.35
    EN: tone amplitude (0..1), default 0.35

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
    - w linii: słowa rozdzielane są Y, a po ostatnim słowie jest Z

Uwaga:
    W tej wersji WPM nie steruje już timingiem elementów.
    Cały timing jest liczony od FWPM.


PRZYKŁADY / EXAMPLES
--------------------

Minimalne użycie / minimal usage:

    python3 generuj.py --wpm 27 --fwpm 27 --freq 600

Pełna konfiguracja:

    python3 generuj.py --json lesson1.json --out lesson1.wav \
        --wpm 27 --fwpm 27 --freq 600 \
        --x 7 --y 21 --z 31

Wolniejsze ćwiczenie:

    python3 generuj.py --json words.json --out slow.wav \
        --wpm 25 --fwpm 10 --freq 700 \
        --x 7 --y 21 --z 31
    python3 generuj.py --json words.json --out fast.wav  --wpm 30 --fwpm 20 --freq 700
