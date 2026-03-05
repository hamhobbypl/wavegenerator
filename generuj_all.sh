#!/bin/bash

WPM=23
FWPM=23
FREQ=600

for f in *.json; do
    base=$(basename "$f" .json)
    out="${base}_23.wav"

    echo "Generuję $out z $f"

    python3.11 generuj.py \
        --wpm $WPM \
        --fwpm $FWPM \
        --freq $FREQ \
        -j "$f" \
        -o "$out"

done

echo "Gotowe."
