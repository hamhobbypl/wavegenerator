#!/bin/bash

BITRATE=128k

for f in *.wav; do
    base="${f%.wav}"
    out="${base}.mp3"

    echo "Konwersja $f -> $out"

    ffmpeg -loglevel error -y -i "$f" -codec:a libmp3lame -b:a $BITRATE "$out"
done

echo "Gotowe."
