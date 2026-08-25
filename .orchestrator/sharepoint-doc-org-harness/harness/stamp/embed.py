from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from harness.actions.drain import is_secret_file

OOXML_SUFFIXES = {".docx", ".xlsx", ".pptx"}
PDF_SUFFIXES = {".pdf"}
# Never rewrite keys/code/secrets even if someone asks for Title.
SKIP_REWRITE_SUFFIXES = {
    ".pem",
    ".key",
    ".pfx",
    ".p12",
    ".cer",
    ".crt",
    ".p7b",
    ".p7c",
    ".asc",
}

CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CORE_CT = "application/vnd.openxmlformats-package.core-properties+xml"
CORE_REL = "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"


def can_embed(path: Path) -> bool:
    if is_secret_file(path):
        return False
    suffix = path.suffix.lower()
    if suffix in SKIP_REWRITE_SUFFIXES:
        return False
    return suffix in OOXML_SUFFIXES or suffix in PDF_SUFFIXES


def write_embedded_properties(
    path: Path,
    *,
    title: str,
    subject: str,
    keywords: str,
) -> dict[str, Any]:
    """Write Office/PDF Title/Subject/Keywords. Never rewrite secrets/code."""
    if not path.is_file() or is_secret_file(path):
        return {"written": False, "reason": "secret_or_missing"}
    suffix = path.suffix.lower()
    if suffix in SKIP_REWRITE_SUFFIXES:
        return {"written": False, "reason": "secret_suffix"}
    try:
        if suffix in OOXML_SUFFIXES:
            _write_ooxml_core(path, title=title, subject=subject, keywords=keywords)
            return {"written": True, "format": suffix.lstrip(".")}
        if suffix in PDF_SUFFIXES:
            return _write_pdf_info(path, title=title, subject=subject, keywords=keywords)
    except Exception as exc:
        return {"written": False, "reason": type(exc).__name__}
    return {"written": False, "reason": "unsupported"}


def _write_ooxml_core(path: Path, *, title: str, subject: str, keywords: str) -> None:
    if not zipfile.is_zipfile(path):
        raise ValueError("not_ooxml_zip")
    with zipfile.ZipFile(path, "r") as zin:
        names = set(zin.namelist())
        payload = {name: zin.read(name) for name in names}

    payload["docProps/core.xml"] = _core_xml(title=title, subject=subject, keywords=keywords)
    payload["[Content_Types].xml"] = _ensure_core_content_type(
        payload.get("[Content_Types].xml") or _default_content_types()
    )
    payload["_rels/.rels"] = _ensure_core_rel(payload.get("_rels/.rels") or _default_rels())

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in payload.items():
            zout.writestr(name, data)
    path.write_bytes(buffer.getvalue())


def _core_xml(*, title: str, subject: str, keywords: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<cp:coreProperties xmlns:cp="{CP_NS}" xmlns:dc="{DC_NS}" '
        f'xmlns:dcterms="{DCTERMS_NS}" xmlns:xsi="{XSI_NS}">'
        f"<dc:title>{escape(title)}</dc:title>"
        f"<dc:subject>{escape(subject)}</dc:subject>"
        f"<cp:keywords>{escape(keywords)}</cp:keywords>"
        "</cp:coreProperties>"
    ).encode("utf-8")


def _ensure_core_content_type(raw: bytes) -> bytes:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return raw
    for override in root.findall(f"{{{CT_NS}}}Override"):
        if override.attrib.get("PartName") == "/docProps/core.xml":
            return raw
    ET.SubElement(
        root,
        f"{{{CT_NS}}}Override",
        {"PartName": "/docProps/core.xml", "ContentType": CORE_CT},
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _ensure_core_rel(raw: bytes) -> bytes:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return raw
    for rel in root.findall(f"{{{RELS_NS}}}Relationship"):
        if rel.attrib.get("Type") == CORE_REL:
            return raw
    used = {rel.attrib.get("Id", "") for rel in root.findall(f"{{{RELS_NS}}}Relationship")}
    rid = "rIdCore"
    n = 1
    while rid in used:
        n += 1
        rid = f"rIdCore{n}"
    ET.SubElement(
        root,
        f"{{{RELS_NS}}}Relationship",
        {"Id": rid, "Type": CORE_REL, "Target": "docProps/core.xml"},
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _default_content_types() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        b'<Default Extension="xml" ContentType="application/xml"/>'
        b"</Types>"
    )


def _default_rels() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b"</Relationships>"
    )


def _write_pdf_info(path: Path, *, title: str, subject: str, keywords: str) -> dict[str, Any]:
    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore
    except Exception:
        return {"written": False, "reason": "pypdf_missing"}
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        return {"written": False, "reason": type(exc).__name__}
    writer = PdfWriter()
    writer.append(reader)
    writer.add_metadata(
        {
            "/Title": title,
            "/Subject": subject,
            "/Keywords": keywords,
        }
    )
    buffer = io.BytesIO()
    writer.write(buffer)
    path.write_bytes(buffer.getvalue())
    return {"written": True, "format": "pdf"}


def read_ooxml_core(path: Path) -> dict[str, str]:
    """Test helper: read Title/Subject/Keywords from an OOXML package."""
    with zipfile.ZipFile(path, "r") as zin:
        raw = zin.read("docProps/core.xml")
    root = ET.fromstring(raw)
    title = root.findtext(f"{{{DC_NS}}}title") or ""
    subject = root.findtext(f"{{{DC_NS}}}subject") or ""
    keywords = root.findtext(f"{{{CP_NS}}}keywords") or ""
    return {"title": title, "subject": subject, "keywords": keywords}


def minimal_docx_bytes(*, body: str = "fixture") -> bytes:
    """A tiny OOXML zip so tests can stamp without Word."""
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{body}</w:t></w:r></w:p></w:body></w:document>"
    ).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        zout.writestr("[Content_Types].xml", _default_content_types())
        zout.writestr("_rels/.rels", _default_rels())
        zout.writestr("word/document.xml", document)
    return buffer.getvalue()
