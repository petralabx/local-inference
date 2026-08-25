# SharePoint Document Organization Harness

Durable control plane for VincePersonal SharePoint + Outlook organization.

- **SoT:** VincePersonal SharePoint (not OneDrive personal library)
- **Inference (steady-state):** Dell LiteLLM → Spark `local-driver` / `local-coder`
- **Safety:** wide auto + SQLite reverse journal + provenance queries
- **Spec:** `SPEC.md` · **Research:** `RESEARCH.md` · **OSS table:** `docs/oss-stack.md`

## Quick start (dev)

```bash
cd .orchestrator/sharepoint-doc-org-harness
python -m pip install -e ".[dev]"
python -m pytest -q
```

## CLI

```bash
python -m harness.cli.main version
python -m harness.cli.main digest --dry-run --report data/reports/digest.json
python -m harness.cli.main stamp --report data/reports/stamp.json --limit 20
python -m harness.cli.main fold --report data/reports/fold.json
python -m harness.cli.main where --name trafilea
python -m harness.cli.main reverse --run-id <id>
```

## Operator notes

- Single-writer scheduler: Dell-VTA (`docs/ops.md`)
- Laptop: SoT + `harness where` / reverse only
- Live cutover: `docs/cutover-checklist.md`
- Leftover-tree fold: `harness fold` is dry-run by default. `--apply` is opt-in
  hygiene after harvest stamp; never hide Vince Personal; never archive `00`–`06`.
- Promotion target: `petralabx/sharepoint-doc-org-harness` (operator creates repo)

## Phases

P1–P8 acceptance lives under `tests/test_pN_*.py`. Full suite: `python -m pytest tests/ -q`.
