# Live VTA cutover smoke checklist (manual)

Do not treat this as automated acceptance. Run after Graph delegated auth is ready.

1. [ ] Confirm VincePersonal sync root path in `config/local.yaml`
2. [ ] LiteLLM proxy reachable: `curl -sS http://100.103.33.54:4000/v1/models | head`
3. [ ] `python -m pytest -q` green on VTA
4. [ ] `harness digest --dry-run --report …` — inspect counts, no paid-host errors
5. [ ] Small inbox fixture (≤5 files) with `--report` (no dry-run); verify move-not-copy
6. [ ] `harness where --hash <sha>` returns the moved path
7. [ ] `harness reverse --run-id <id>` restores fixture files
8. [ ] Mail: ensure folder/rule against test mailbox; one attachment lands in inbox
9. [ ] Install Task Scheduler job per `docs/ops.md`; laptop stays query-only
10. [ ] Confirm `delete_duplicates: false` until Vince enables deletes
11. [ ] On VTA, `python -m harness.cli.main graph-login` as `vince@petrasoap.com`, then `harness stamp --limit 20` writes Party/Prefix/Home (folder walk; no FileLeafRef filter)

## Promotion to standalone repo

Target: `petralabx/sharepoint-doc-org-harness` (operator creates repo).

1. Copy `.orchestrator/sharepoint-doc-org-harness/` tree (exclude `.pytest_cache`, `data/`)
2. Keep `docs/oss-stack.md`, `SPEC.md`, `RESEARCH.md`
3. Point CI at `pytest -q` only (no GPU)
4. Do not merge unrelated `local-inference` history into the new repo
