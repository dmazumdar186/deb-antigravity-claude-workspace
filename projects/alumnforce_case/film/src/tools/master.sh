#!/bin/sh
# Master one deliverable: two-pass loudnorm to -16 LUFS integrated, true peak <= -1.5 dBTP (one target everywhere),
# optional film grain, H.264 + AAC, BT.709 limited range. Writes to a temp file and moves it into place atomically.
# usage: sh tools/master.sh video.mp4 mix.wav out.mp4 <grain 0..> <crf>
set -e
V=$1 A=$2 O=$3 GR=${4:-0} CRF=${5:-24}
I=-16 TP=-1.7 LRA=11      # loudnorm aims 0.2 dB under the -1.5 dBTP ceiling, so the encoded AAC stays under it
TMP="$(dirname "$O")/.$(basename "$O").tmp.mp4"
M=$(ffmpeg -hide_banner -nostats -i "$A" -af loudnorm=I=$I:TP=$TP:LRA=$LRA:print_format=json -f null - 2>&1)
g() { echo "$M" | sed -n '/{/,/}/p' | grep "\"$1\"" | sed 's/.*: "\(.*\)".*/\1/'; }
LN="loudnorm=I=$I:TP=$TP:LRA=$LRA:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true"
if [ "$GR" = "0" ]; then VF="fps=24"; TUNE="-tune film"; else VF="fps=24,noise=c0s=$GR:allf=t"; TUNE="-tune grain"; fi
VF="$VF,scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p,setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709"
ffmpeg -y -loglevel error -i "$V" -i "$A" -filter_complex "[0:v]$VF[v];[1:a]$LN,aresample=48000[a]" -map "[v]" -map "[a]" \
  -c:v libx264 -preset slow -crf "$CRF" $TUNE -r 24 -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -c:a aac -b:a 192k -movflags +faststart -shortest "$TMP" || { rm -f "$TMP"; echo "master.sh: ffmpeg failed" >&2; exit 1; }
R=$(ffmpeg -hide_banner -nostats -i "$TMP" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I|Peak):" | head -2)
OI=$(echo "$R" | awk '$1 == "I:" { print $2 }'); OP=$(echo "$R" | awk '$1 == "Peak:" { print $2 }')
SZ=$(stat -c %s "$TMP")
echo "master.sh: $O  I=$OI LUFS  TP=$OP dBTP  $SZ bytes"
awk -v i="$OI" -v p="$OP" -v s="$SZ" 'BEGIN { exit !(i + 0 < -16.5 || i + 0 > -15.5 || p + 0 > -1.5 || s + 0 > 25000000) }' \
  && { rm -f "$TMP"; echo "master.sh: out of spec (target -16 +/- 0.5 LUFS, TP <= -1.5, <= 25 MB)" >&2; exit 1; }
mv -f "$TMP" "$O"
