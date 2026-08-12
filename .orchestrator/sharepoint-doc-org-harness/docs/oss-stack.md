# OSS adopt / wrap / reject

Mirrored from `RESEARCH.md` for packaging and promotion.

| Project | License | Decision | Role |
|---------|---------|----------|------|
| docling-project/docling | MIT | **Adopt / wrap** | Primary extract |
| ocrmypdf/OCRmyPDF | MPL-2.0 | **Wrap** | Scan PDF lane |
| paperless-ngx/paperless-ngx | GPL-3.0 | **Reject (runtime)** | Patterns only |
| pkolaczk/fclones | MIT | **Wrap** | Byte-identical dedupe |
| pauldreik/rdfind | GPL-style | **Reject (primary)** | Prefer fclones on Windows |
| microsoftgraph/msgraph-sdk-python | MIT | **Adopt** | Graph mail + drive IDs |
| microsoftgraph/msgraph-sdk-dotnet | MS | **Reject (primary)** | Python stack preferred |
| apache/tika | Apache-2.0 | **Wrap (fallback)** | Exotic MIME |
| neo4j / memgraph | various | **Defer** | NetworkX + SQLite first |
| qdrant / lancedb | various | **Optional later** | Semantic search |
| tagspaces/tagspaces | AGPL | **Reject (runtime)** | UX ideas only |
| karakeep | various | **Reject (runtime)** | Not SoT |

SharePoint (VincePersonal) remains the sole document SoT.
