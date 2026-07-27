#!/usr/bin/env bash
# Turn a folder of raw originals into web-optimized assets.
# Usage: ./optimize.sh "<source-dir>" <slug>
#
# Produces, under assets/<slug>/:
#   <name>.jpg        full view, long edge 2000px
#   thumb-<name>.jpg  grid thumb, long edge 800px
#   <name>.mp4        compressed H.264 (from mp4/mov sources)
#   <name>-poster.jpg poster frame for each video
set -euo pipefail

SRC="${1:?source dir required}"
SLUG="${2:?slug required}"
OUT="assets/$SLUG"
mkdir -p "$OUT"

shopt -s nullglob nocaseglob

slugify() {
  echo "$1" | tr '[:upper:] _' '[:lower:]--' | tr -cd 'a-z0-9-' | sed -E 's/-+/-/g; s/^-|-$//g'
}

for f in "$SRC"/*.jpg "$SRC"/*.jpeg "$SRC"/*.png "$SRC"/*.tif "$SRC"/*.tiff; do
  [ -e "$f" ] || continue
  name="$(slugify "$(basename "${f%.*}")")"
  [ -n "$name" ] || { echo "skip (name slugified to empty): $f" >&2; continue; }
  sips -s format jpeg -s formatOptions 80 -Z 2000 "$f" --out "$OUT/$name.jpg" >/dev/null
  sips -s format jpeg -s formatOptions 72 -Z 800  "$f" --out "$OUT/thumb-$name.jpg" >/dev/null
  echo "img  $OUT/$name.jpg"
done

for f in "$SRC"/*.mp4 "$SRC"/*.mov; do
  [ -e "$f" ] || continue
  name="$(slugify "$(basename "${f%.*}")")"
  [ -n "$name" ] || { echo "skip (name slugified to empty): $f" >&2; continue; }
  ffmpeg -y -i "$f" -vf "scale='min(960,iw)':-2" -c:v libx264 -crf 30 -preset medium \
    -c:a aac -b:a 96k -movflags +faststart "$OUT/$name.mp4" </dev/null >/dev/null 2>&1
  ffmpeg -y -i "$OUT/$name.mp4" -vframes 1 -q:v 3 "$OUT/$name-poster.jpg" </dev/null >/dev/null 2>&1
  echo "vid  $OUT/$name.mp4"
done

echo "done -> $OUT"
