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

# Force sRGB on every image so a CMYK source (which renders black in social
# share cards and non-color-managed browsers) can never pass through.
SRGB_PROFILE="/System/Library/ColorSync/Profiles/sRGB Profile.icc"

shopt -s nullglob nocaseglob

slugify() {
  echo "$1" | tr '[:upper:] _' '[:lower:]--' | tr -cd 'a-z0-9-' | sed -E 's/-+/-/g; s/^-|-$//g'
}

# Track slugs already emitted this run so two sources that normalize to the same
# name (e.g. "photo 1" and "photo_1", or "Sao"/"São") don't silently overwrite
# each other; a colliding slug gets a -N suffix instead. reserve_name sets the
# global RESERVED.
used=""
name_used() { case " $used " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }
reserve_name() {
  local base="$1" cand="$1" n=1
  while name_used "$cand"; do n=$((n + 1)); cand="${base}-${n}"; done
  used="$used $cand"
  [ "$cand" = "$base" ] || echo "note: slug collision, using '$cand' instead of '$base'" >&2
  RESERVED="$cand"
}

for f in "$SRC"/*.jpg "$SRC"/*.jpeg "$SRC"/*.png "$SRC"/*.tif "$SRC"/*.tiff; do
  [ -e "$f" ] || continue
  name="$(slugify "$(basename "${f%.*}")")"
  [ -n "$name" ] || { echo "skip (name slugified to empty): $f" >&2; continue; }
  reserve_name "$name"; name="$RESERVED"
  sips -s format jpeg -s formatOptions 80 -Z 2000 --matchTo "$SRGB_PROFILE" "$f" --out "$OUT/$name.jpg" >/dev/null
  sips -s format jpeg -s formatOptions 72 -Z 800  --matchTo "$SRGB_PROFILE" "$f" --out "$OUT/thumb-$name.jpg" >/dev/null
  echo "img  $OUT/$name.jpg"
done

for f in "$SRC"/*.mp4 "$SRC"/*.mov; do
  [ -e "$f" ] || continue
  name="$(slugify "$(basename "${f%.*}")")"
  [ -n "$name" ] || { echo "skip (name slugified to empty): $f" >&2; continue; }
  reserve_name "$name"; name="$RESERVED"
  ffmpeg -y -i "$f" -vf "scale='min(960,iw)':-2" -c:v libx264 -crf 30 -preset medium \
    -c:a aac -b:a 96k -movflags +faststart "$OUT/$name.mp4" </dev/null >/dev/null 2>&1
  ffmpeg -y -i "$OUT/$name.mp4" -vframes 1 -q:v 3 "$OUT/$name-poster.jpg" </dev/null >/dev/null 2>&1
  echo "vid  $OUT/$name.mp4"
done

echo "done -> $OUT"
