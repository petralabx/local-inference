from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from harness.ledger.documents import DocumentRecord

DEFAULT_BASE = "https://missioncontrol.tayloralton.com"
SOURCE_TYPE = "vince_node_document"
DOMAIN = "vince-node"


def project_document(
    rec: DocumentRecord,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> bool:
    """Project a ledger row to the Vince Node. Fail-open if Brain is down."""
    key = api_key if api_key is not None else (
        os.environ.get("VMC_API_KEY") or os.environ.get("PLX_BRAIN_API_KEY") or ""
    )
    if not key:
        return False
    root = (base_url or os.environ.get("VMC_BASE_URL") or DEFAULT_BASE).rstrip("/")
    body = {
        "title": rec.title[:300],
        "content": (
            f"sha256: {rec.sha256}\n"
            f"prefix: {rec.prefix}\n"
            f"type: {rec.doc_type}\n"
            f"date: {rec.doc_date}\n"
            f"version: {rec.version}\n"
            f"home: {rec.home}\n"
            f"path: {rec.current_path}\n"
            f"source: {rec.source}\n"
        ),
        "sourceType": SOURCE_TYPE,
        "domain": DOMAIN,
        "tags": ["vince-node", "document-ledger", rec.prefix, rec.doc_type][:20],
    }
    req = urllib.request.Request(
        root + "/api/vmc/knowledge/agent/items",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= int(resp.status) < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False
