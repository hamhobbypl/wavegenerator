#!/bin/bash

WPM=23
FWPM=23
FREQ=550
RAND="true"

python3.11 generuj.py \
        --wpm $WPM \
        --fwpm $FWPM \
        --freq $FREQ \
	--random $RAND \
	--ramp 0.005 \
        -j "4-5_Liter.json" \
        -o "4-5_Liter.json.wav"
