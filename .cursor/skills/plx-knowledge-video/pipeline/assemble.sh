#!/usr/bin/env bash
# Assemble per-beat composed clips (with smart zooms) + per-beat narration into
# one synced, captioned video. Each beat is extended to its narration length by
# freezing its final (clean, fully-rendered) frame, so audio and video stay in
# sync with no white load screens and no global time-stretch.
set -euo pipefail
cd "$(dirname "$0")/.."          # project root
D=demos/clips
OUT=demos/out
mkdir -p "$OUT"
PAD=0.8

python3 - <<'PY' > /tmp/_assemble_plan.sh
import json
c=json.load(open('demos/beats.json')); d=json.load(open('demos/clips/audio/durations.json'))
pad=0.8
segs=[]
texts=[]
for b in c['beats']:
    s=b['slug']; T=round(d[s]+pad,3)
    print(f"buildseg '{s}' {T}")
    segs.append(s); texts.append(b['narration'])
print("CONCAT "+" ".join(segs))
open('/tmp/_narr_all.txt','w').write(" ".join(texts))
PY

buildseg() {
  local s="$1" T="$2"
  local clip="$D/$s/final.mp4"
  local C
  C=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$clip")
  # freeze last frame to reach T (clip is shorter than narration)
  ffmpeg -y -loglevel error -i "$clip" -vf "tpad=stop_mode=clone:stop_duration=30,fps=30,scale=1600:-2,setsar=1,format=yuv420p" -t "$T" -an "$OUT/v_$s.mp4"
  # narration padded with trailing silence to exactly T
  ffmpeg -y -loglevel error -i "$D/audio/$s.mp3" -af "apad" -t "$T" -ar 44100 -ac 1 "$OUT/a_$s.wav"
  echo "seg $s -> ${T}s (clip ${C}s)"
}

CONCAT() {
  : > "$OUT/vlist.txt"; : > "$OUT/alist.txt"
  for s in "$@"; do echo "file 'v_$s.mp4'" >> "$OUT/vlist.txt"; echo "file 'a_$s.wav'" >> "$OUT/alist.txt"; done
  ( cd "$OUT" && ffmpeg -y -loglevel error -f concat -safe 0 -i vlist.txt -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p video.mp4 )
  ( cd "$OUT" && ffmpeg -y -loglevel error -f concat -safe 0 -i alist.txt -c:a pcm_s16le audio.wav )
  echo "concatenated $#"
}

source /tmp/_assemble_plan.sh
echo "video: $(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT/video.mp4")  audio: $(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT/audio.wav")"
