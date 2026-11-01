#!/bin/sh
# Master the deliverable: two-pass loudnorm to -16 LUFS integrated, true peak <= -1.5 dBTP (loudnorm aims at -1.7 for a
# 0.2 dB margin through AAC), H.264 High yuv420p BT.709 limited range at 30 fps, AAC-LC 48 kHz, AI-marking metadata.
# Writes a temp file, checks loudness / peak / size, then moves it into place (never overwrites the deliverable in place).
# The intermediate from core/render/video.mjs is limited-range BT.601 (tagged bt470bg); it is converted to BT.709 with the colorspace filter (scale= shifted the paper by 3-5 levels; measured).
# usage: sh tools/master.sh video.mp4 mix.wav out.mp4 [crf]
set -e
V=$1 A=$2 O=$3 CRF=${4:-18}
I=-16 TP=-1.7 LRA=11 MAXB=30000000
TMP="$(dirname "$O")/.$(basename "$O").tmp.mp4"
M=$(ffmpeg -hide_banner -nostats -i "$A" -af loudnorm=I=$I:TP=$TP:LRA=$LRA:print_format=json -f null - 2>&1)
g() { echo "$M" | sed -n '/{/,/}/p' | grep "\"$1\"" | sed 's/.*: "\(.*\)".*/\1/'; }
LN="loudnorm=I=$I:TP=$TP:LRA=$LRA:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true"
VF="fps=30,colorspace=all=bt709:iall=bt601-6-625:irange=tv:range=tv:fast=1,format=yuv420p,setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709"
ffmpeg -y -loglevel error -i "$V" -i "$A" -filter_complex "[0:v]$VF[v];[1:a]$LN,aresample=48000[a]" -map "[v]" -map "[a]" \
  -c:v libx264 -profile:v high -preset slow -crf "$CRF" -tune animation -r 30 -g 60 \
  -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart -shortest \
  -metadata title="ProdCraft weekly notes · wk 02 · 32 inboxes, 800 sends. Who replied?" \
  -metadata comment="Code-rendered picture and score made with an AI coding agent (lemo-opuscar toolkit); no synthetic voice, no generated footage. Facts: FACTS.md" \
  "$TMP" || { rm -f "$TMP"; echo "master.sh: ffmpeg failed" >&2; exit 1; }
R=$(ffmpeg -hide_banner -nostats -i "$TMP" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I|Peak):" | head -2)
OI=$(echo "$R" | awk '$1 == "I:" { print $2 }'); OP=$(echo "$R" | awk '$1 == "Peak:" { print $2 }')
SZ=$(stat -c %s "$TMP")
echo "master.sh: $O  I=$OI LUFS  TP=$OP dBTP  $SZ bytes"
awk -v i="$OI" -v p="$OP" -v s="$SZ" -v m="$MAXB" 'BEGIN { exit !(i + 0 < -16.5 || i + 0 > -15.5 || p + 0 > -1.5 || s + 0 > m) }' \
  && { rm -f "$TMP"; echo "master.sh: out of spec (target -16 +/- 0.5 LUFS, TP <= -1.5 dBTP, <= 30 MB)" >&2; exit 1; }
mv -f "$TMP" "$O"
