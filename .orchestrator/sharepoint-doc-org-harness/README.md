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
python -m harness.cli.main graph-login
python -m harness.cli.main relabel --report data/reports/relabel.json --limit 20
python -m harness.cli.main stamp --report data/reports/stamp.json --limit 20
python -m harness.cli.main inventory --report data/reports/inventory.json --root "<leftover-root>"
python -m harness.cli.main sync-audit --dry-run
python -m harness.cli.main where --name trafilea
python -m harness.cli.main reverse --run-id <id>
```

`inventory` is report-only: it classifies leftover local files (`candidate-to-consume`,
`skip-code`, `skip-secret`, `already-in-VincePersonal`) and writes JSON for a later
digest/fold. It does not copy or upload. Pass `--root` (repeatable) and/or
`--roots-file config/inventory_roots.example.yaml` for the machine you are on.
Do not scan real VTA paths from a Cloud Agent VM. Code trees, secrets, and
`local-inference-canonical` stay off SharePoint. Never hide Vince Personal.

`sync-audit` is report-only (no upload, rename, or stamp). Dry-run walks local +
SharePoint folder-by-folder and writes `data/reports/sync-audit.json`. The cloud
VM cannot see VTA OneDrive; run the live audit on Dell-VTA.

## Operator notes

- Single-writer scheduler: Dell-VTA (`docs/ops.md`)
- Laptop: SoT + `harness where` / reverse only
- Live cutover: `docs/cutover-checklist.md`
- Promotion target: `petralabx/sharepoint-doc-org-harness` (operator creates repo)

## Phases

P1–P8 acceptance lives under `tests/test_pN_*.py`. Full suite: `python -m pytest tests/ -q`.
