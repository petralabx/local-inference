# SharePoint Document Organization Harness

Durable control plane for VincePersonal SharePoint + Outlook organization.

- **SoT:** VincePersonal SharePoint (not OneDrive personal library)
- **Inference (steady-state):** Dell LiteLLM only (`local-fast` / `local-primary`)
- **Safety:** wide auto + SQLite reverse journal + provenance queries
- **Spec:** see `SPEC.md` in this directory

## Quick start (dev)

```bash
cd .orchestrator/sharepoint-doc-org-harness
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Operator notes

- Single-writer scheduler: Dell-VTA
- Laptop: consume SoT + ad-hoc `harness where` queries
- Live cutover checklist lands in P7/P8 docs
