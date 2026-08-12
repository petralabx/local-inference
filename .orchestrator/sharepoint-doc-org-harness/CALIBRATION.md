---
slug: sharepoint-doc-org-harness
created: 2026-08-12T11:12:00Z
source: discovery+research
---

# Calibration — SharePoint Document Organization Harness

## Intent

Replace the failing Claude Cowork control plane with a first-class durable
Python harness that keeps VincePersonal SharePoint + Outlook organized under
wide auto, with reverse + knowledge-graph provenance, using local LiteLLM only
after cutover.

## Constraints (pinned)

- SoT: VincePersonal SharePoint (sync root + Graph). Not OneDrive personal SoT.
- Hosts: Dell-VTA single-writer; laptop consumer / ad-hoc agents.
- Local-only inference post-build: Dell proxy aliases only.
- OSS wrap-first (Docling, fclones, OCRmyPDF, msgraph-sdk-python; journal+graph).
- Email: Outlook folders/rules + attachments → SharePoint.
- Exclude code/repos from filing.
- Historical active reorg: 12 months; older → archive-in-place.

## Success (pinned)

1. Provenance query: “where did former path/name X go?”
2. Inbox drain to ≤100 active items after cutover digests
3. Near-zero drift (no copy/`_vNN` stacks; no client-folder fragmentation)

## Non-goals (pinned)

- Paperless/TagSpaces/Karakeep as runtime SoT
- Paid cloud LLM tokens for steady-state
- Team SharePoint sites
- Gated crawl/walk/run as steady-state safety

## Delivery home

New package path in this workspace for phased build:
`.orchestrator/sharepoint-doc-org-harness/harness/` (publishable later to
`petralabx/sharepoint-doc-org-harness`). Do not put product code in
`litellm/` or other local-inference roots.
