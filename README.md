(c) 2026 Maniek SP8KM HAMHOBBY.PL — MIT License

CW WAV generator from JSON file.

Generator pliku WAV z kodem Morse'a na podstawie pliku JSON.
Program może losować sekcje i wpisy albo generować dokładnie po kolei.
Kropka, kreska i X/Y/Z są liczone od FWPM.
Separator [   ] ma długość zależną od liczby spacji w środku.


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


PRZYKŁADY / EXAMPLES
--------------------

Minimalne użycie / minimal usage:

    python3 generuj.py --wpm 27 --fwpm 27 --freq 600

Losowość włączona:

    python3 generuj.py --wpm 27 --fwpm 27 --freq 600 --random true

Bez losowości:

    python3 generuj.py --wpm 27 --fwpm 27 --freq 600 --random false

Pełna konfiguracja:

    python3 generuj.py --json lesson1.json --out lesson1.wav \
        --wpm 27 --fwpm 27 --freq 600 \
        --x 7 --y 7 --z 31 --random true

Przykład separatorów:
    "ADAM[ ]ADAM"    -> przerwa 1 * Y
    "ADAM[  ]ADAM"   -> przerwa 2 * Y
    "ADAM[   ]ADAM"  -> przerwa 3 * Y

Linux pipeline example:

    python3 generuj.py --wpm 25 --fwpm 25 --freq 650 --random false && aplay cw_losowo.wav
