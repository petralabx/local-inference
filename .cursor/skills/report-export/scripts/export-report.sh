#!/usr/bin/env bash
# Convert a Markdown/HTML report to PDF + Word (.docx) on macOS/Linux.
# PDF: chromium/google-chrome headless (fallback wkhtmltopdf, then LibreOffice).
# DOCX: pandoc. Usage: export-report.sh <input.md|input.html> [--outdir DIR] [--name NAME] [--share] [--no-pdf] [--no-docx]
set -euo pipefail

INPUT="${1:-}"; shift || true
[ -z "$INPUT" ] && { echo "usage: export-report.sh <input.md|.html> [--outdir DIR] [--name NAME] [--share] [--no-pdf] [--no-docx]"; exit 2; }

OUTDIR=""; NAME=""; SHARE=0; DO_PDF=1; DO_DOCX=1
while [ $# -gt 0 ]; do case "$1" in
  --outdir) OUTDIR="$2"; shift 2;;
  --name) NAME="$2"; shift 2;;
  --share) SHARE=1; shift;;
  --no-pdf) DO_PDF=0; shift;;
  --no-docx) DO_DOCX=0; shift;;
  *) echo "unknown arg: $1"; exit 2;;
esac; done

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CSS="$SKILL_DIR/assets/report.css"
INPUT="$(cd "$(dirname "$INPUT")" && pwd)/$(basename "$INPUT")"
EXT="${INPUT##*.}"; EXT="$(echo "$EXT" | tr '[:upper:]' '[:lower:]')"
[ -z "$OUTDIR" ] && OUTDIR="$(dirname "$INPUT")"; mkdir -p "$OUTDIR"
[ -z "$NAME" ] && NAME="$(basename "${INPUT%.*}")"

have(){ command -v "$1" >/dev/null 2>&1; }
ensure_pandoc(){ have pandoc && return 0; echo "pandoc missing — install with 'brew install pandoc' or your package manager."; return 1; }

HTML="$INPUT"
if [ "$EXT" = "md" ] || [ "$EXT" = "markdown" ]; then
  ensure_pandoc || exit 1
  HTML="$OUTDIR/$NAME.html"
  CSSARG=(); [ -f "$CSS" ] && CSSARG=(--css "$CSS")
  pandoc "$INPUT" -o "$HTML" --standalone --embed-resources "${CSSARG[@]}" --metadata title="$NAME"
elif [ "$EXT" != "html" ] && [ "$EXT" != "htm" ]; then
  echo "Unsupported input .$EXT (use .md or .html)"; exit 2
fi

OUTPUTS=()
if [ "$DO_PDF" = 1 ]; then
  PDF="$OUTDIR/$NAME.pdf"; URI="file://$HTML"
  BROWSER=""
  for b in google-chrome google-chrome-stable chromium chromium-browser "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"; do
    if have "$b" || [ -x "$b" ]; then BROWSER="$b"; break; fi
  done
  if [ -n "$BROWSER" ]; then
    "$BROWSER" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$PDF" "$URI" 2>/dev/null || true
  elif have wkhtmltopdf; then wkhtmltopdf "$HTML" "$PDF" || true
  elif have soffice; then soffice --headless --convert-to pdf --outdir "$OUTDIR" "$HTML" >/dev/null 2>&1 || true
  else echo "No chromium/chrome/wkhtmltopdf/soffice found; skipping PDF."; fi
  [ -f "$PDF" ] && OUTPUTS+=("$PDF")
fi

if [ "$DO_DOCX" = 1 ] && ensure_pandoc; then
  DOCX="$OUTDIR/$NAME.docx"; pandoc "$INPUT" -o "$DOCX"; [ -f "$DOCX" ] && OUTPUTS+=("$DOCX")
fi

if [ "$SHARE" = 1 ]; then
  for d in "$HOME"/OneDrive*/CursorInbox "$HOME"/CursorInbox; do
    if [ -d "$d" ]; then DEST="$d/$NAME"; mkdir -p "$DEST"; cp -f "${OUTPUTS[@]}" "$DEST"/ 2>/dev/null || true; echo "SHARED -> $DEST"; break; fi
  done
fi

echo "OUTPUTS:"; printf '  %s\n' "${OUTPUTS[@]}"
[ "${#OUTPUTS[@]}" -gt 0 ] || { echo "No outputs produced."; exit 1; }
