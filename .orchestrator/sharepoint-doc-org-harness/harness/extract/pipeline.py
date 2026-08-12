from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractResult:
    path: Path
    text: str
    method: str


def extract_text(path: Path) -> ExtractResult:
    """Best-effort local extract. Docling/OCRmyPDF are optional runtime deps.

    For CI fixtures, plain text/markdown/csv are read directly. Binary Office/PDF
    uses Docling when installed; otherwise returns a minimal stub so classify can
    still run on filename + available text.
    """
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json", ".log"}:
        return ExtractResult(path, path.read_text(encoding="utf-8", errors="replace"), "raw")

    try:
        from docling.document_converter import DocumentConverter  # type: ignore

        conv = DocumentConverter()
        result = conv.convert(str(path))
        text = result.document.export_to_markdown()
        return ExtractResult(path, text, "docling")
    except Exception:
        # Optional OCR lane for PDFs when Docling unavailable
        if suffix == ".pdf":
            try:
                return _ocr_pdf_stub(path)
            except Exception:
                pass
        return ExtractResult(path, f"[unparsed binary name={path.name}]", "stub")


def _ocr_pdf_stub(path: Path) -> ExtractResult:
    """Prefer real OCRmyPDF when present; else stub."""
    try:
        import importlib

        importlib.import_module("ocrmypdf")
        # Full OCR rewrite is side-effectful; for harness classify we only need text.
        # Fall through to pypdf/pdfminer-style if available.
    except Exception:
        pass
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        parts = [(p.extract_text() or "") for p in reader.pages]
        text = "\n".join(parts).strip()
        if text:
            return ExtractResult(path, text, "pypdf")
    except Exception:
        pass
    return ExtractResult(path, f"[pdf stub name={path.name}]", "pdf-stub")
