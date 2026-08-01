# adversarial-review-loop — reference

Wiring for the universal loop in [SKILL.md](SKILL.md). Keep `SKILL.md` portable;
the subagent names, severity mapping, and per-repo gates live here.

## 1. Reviewer wiring (independent, read-only)

The reviewer must be independent of the builder. Resolve it by role and run it
read-only against the diff. Options, in order of preference:

1. **Codex-class subagent (general review).** Launch a `Task` subagent whose model
   is a Codex-family model (resolve the best available Codex-class slug at runtime
   from the project model-override file — do not hardcode it here). Set
   `readonly: true`. Prompt it to return severity-ranked findings only; it must not
   author the fix.
2. **`review-bugbot`** — for a Bugbot-style review of local changes. Single-shot,
   read-only. See [review-bugbot](../review-bugbot/SKILL.md).
3. **`review-security`** — for security-sensitive / production-critical changes;
   pair with `strict_approve: true`. See [review-security](../review-security/SKILL.md).
4. **`auditor` / `validator` subagents** — adversarial, read-only verifiers already
   defined in `.claude/agents/`; useful when the change is research/trading code.

Independence rule: the reviewer's model family MUST differ from the builder's. If
the builder is a Claude-family model, the Codex-class reviewer satisfies
independence; if the builder is Codex-class, route the reviewer to a different
family. If you cannot get an independent reviewer, hard-stop
(`reviewer_unavailable` / `reviewer_same_family_as_builder`).

## 2. Severity threshold mapping

Normalize each reviewer's output to one scale so `threshold` is comparable:

| Normalized | Meaning | bugbot/security ~ | Action at `threshold: medium` |
|---|---|---|---|
| critical | exploitable / data-loss / breaks prod | "critical" / P0 | must fix |
| high | likely bug, security weakness, contract break | "high" / P1 | must fix |
| medium | correctness/maintainability risk | "medium" / P2 | may remain (= threshold) |
| low | style, nit, optional improvement | "low" / nit | may remain |

`threshold` names the highest severity allowed to remain UNFIXED. Anything strictly
above the chosen line is blocking (so at `threshold: medium`, only `high` and
`critical` block). With `strict_approve: true`, even a clean at-or-below-threshold
result requires an explicit reviewer APPROVE.

## 3. Per-repo build/verify gate

The builder's `verify()` and the PR gate use each repo's own canonical gate
(commands verified 2026-06-19):

| Repo | Gate command | Notes |
|---|---|---|
| agentic-swarm / VMC | `./scripts/wterm-preflight.sh --mode pre-push` | canonical commit/push gate — see [wterm-preflight](../wterm-preflight/SKILL.md) |
| plx-customer-portal | from `portal/`: `npm run typecheck && npm run lint && npm run test && npm run audit:hygiene` | Vitest (`vitest run`); `audit:hygiene` = `scripts/audit-module-coverage.sh`; target the `staging` branch only (PRs to `master` need explicit approval); DB steps require `bash scripts/assert-staging-context.sh` first |
| clawdbot | `pnpm build && pnpm lint && pnpm test` | TS/pnpm; keep `pnpm-lock.yaml` in sync |
| mrp-project | `npm install && npm test` | — |

Self-locate the repo root (`VMC_REPO_ROOT` → `git rev-parse --show-toplevel` →
`pwd`) so the same skill works unmodified across checkouts and boxes. Run the gate
from the directory each command expects (e.g. `portal/` for plx-customer-portal).

## 4. PR keep-green across rounds

Between review rounds the PR can drift (base moves, CI flakes, new comments). Use
[babysit](../babysit/SKILL.md) to triage comments, resolve clear conflicts, and
fix CI so each re-review runs against a green PR. Do not let a red PR be reviewed —
the reviewer's findings get polluted by unrelated breakage.

## 5. Evidence bundle layout

```text
.orchestrator/review-<slug>/
├── PARAMS.md            # task, thinking, max_iter, threshold, strict_approve
├── state.yaml           # resumable state (branch, pr, iteration, verdict)
├── rounds/<k>/
│   ├── findings.json    # normalized severity-ranked findings
│   ├── fix.diff
│   └── verify.log       # gate exit codes after the fix
└── REPORT.md            # final verdict + every finding's final status + PR link
```

## 6. Worked example

```text
PARAMS: task="add rate-limit to /api/foo", thinking="think hard", max_iter=5,
        threshold=medium, strict_approve=true   # prod-critical route
builder (Claude-family): plan -> implement -> wterm-preflight pre-push green -> open PR #1234

round 1: reviewer=Codex-class subagent (read-only) ->
         [high] missing 429 on burst, [medium] no per-IP key, [low] magic number
         blocking = {high, medium} -> fix both -> push -> CI green
round 2: reviewer -> [low] magic number only
         strict_approve=true and verdict!=APPROVE -> continue (do NOT stop yet)
round 3: builder addresses the low nit -> push -> reviewer -> APPROVE
         -> return APPROVED(pr=#1234, iteration=3)
```

If round 5 had been reached with the high finding still open, the result is
`NOT_APPROVED(reason="max_iter reached", remaining=[high ...])` — reported as a
non-approval, never as approved.
