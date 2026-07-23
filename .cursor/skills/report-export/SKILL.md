---
name: report-export
description: >-
  Convert a Markdown or HTML report into a polished, shareable PDF and Word
  (.docx) file, and optionally copy it to OneDrive/SharePoint for non-technical
  colleagues. Use when the user wants to download, export, send, or share an
  analysis/report/quote as a PDF, Word document, or other non-technical format,
  or mentions PDF, .docx, "save as", "shareable", or "send to colleagues".
---

# Report Export (PDF + Word)

Turn a report you've drafted into files anyone can open and share. PDF is
produced with **headless Microsoft Edge/Chrome** (no LaTeX needed); Word
(`.docx`) is produced with **pandoc**. Optionally copies outputs into the
operator's **OneDrive `CursorInbox`** so they sync to SharePoint for sharing.

## When to use

- "Can I get this as a PDF / Word doc?" · "Make it shareable / downloadable."
- "Send this to colleagues who aren't technical."
- Any analysis, quote, audit, or summary that should leave the chat as a file.

## Quick start

1. Author the report as a single **Markdown** file (best Word output) or a
   self-contained **HTML** file (best PDF fidelity — full control of layout).
   For Markdown, the bundled `assets/report.css` gives a clean printed look.
2. Run the bundled script (resolve its absolute path from this skill's folder):

```powershell
# Windows (PowerShell)
& "<skill-dir>/scripts/export-report.ps1" -InputPath "report.md" -Share
```

```bash
# macOS / Linux
"<skill-dir>/scripts/export-report.sh" report.md --share
```

3. Report the output file paths back to the user as clickable links, and (if
   `-Share`/`--share`) tell them the OneDrive/SharePoint copy is ready.

### Options

| Flag | Meaning |
|---|---|
| `-InputPath` / first arg | `.md` or `.html` source (required) |
| `-OutDir` / `--outdir` | output folder (default: input's folder) |
| `-Name` / `--name` | output base filename (default: input name) |
| `-Share` / `--share` | also copy outputs to OneDrive `CursorInbox/<name>/` |
| `-Pdf:$false` / `--no-pdf` | skip the PDF |
| `-Docx:$false` / `--no-docx` | skip the Word doc |

The script **auto-installs pandoc** (winget on Windows) if missing, and locates
Edge or Chrome automatically for the PDF.

## Authoring tips

- **Tables, headings, and lists** convert cleanly to both PDF and Word. Avoid
  relying on CSS-only visual tricks if the Word version must match the PDF.
- For a branded, paginated PDF, write **HTML** with inline `<style>` including
  `@page { size: Letter; margin: 16mm; }` and `page-break-before` on major
  sections. See `assets/report.css` for a reusable base.
- Mark drafts **"Confidential — Indicative / Not a binding quote"** when the
  report contains pricing or estimates.
- Keep it scannable for non-technical readers: executive summary first, then
  tables, then assumptions/caveats.

## What it produces

For `report.md` → `report.pdf`, `report.docx` (and `report.html` when the source
was Markdown). With sharing on, copies land in
`~/OneDrive*/CursorInbox/<name>/`.

## Prerequisites (handled automatically)

- **pandoc** — for `.docx` (and Markdown→HTML). Auto-installed via `winget`
  (`JohnMacFarlane.Pandoc`, user scope) on Windows; on macOS/Linux install with
  `brew install pandoc` / the distro package manager if the script reports it
  missing.
- **Edge or Chrome** — for PDF via `--headless --print-to-pdf`. Pre-installed on
  Windows. On Linux a `chromium`/`google-chrome` binary (or `wkhtmltopdf`, or
  LibreOffice `soffice`) is used as fallback.

## Notes

- No LaTeX is required or installed — PDF goes through the browser print engine.
- If only an editable Word file is needed and pandoc is unavailable, any `.html`
  report opens directly in Microsoft Word (File → Open → Save As `.docx`).
- Scripts are idempotent and safe to re-run.
