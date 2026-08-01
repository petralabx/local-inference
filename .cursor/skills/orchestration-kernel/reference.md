# Orchestration Kernel — Reference

Detailed expansion for the shared contracts defined in [SKILL.md](SKILL.md).

## 1. Role Resolution Contract

### 1.1 Role table (canonical)

| Role | Selection criteria | Primary surfaces |
|---|---|---|
| planner | highest-capability reasoning model with strong long-context quality | research synthesis, spec decomposition, escalation reframing |
| builder | strongest coding model at balanced reliability and throughput | implementation and fix loops |
| mechanical | fastest low-cost model with stable formatting/tooling behavior | inventories, manifests, structured updates |
| critic/auditor | independent-capability model from a different family than builder | adversarial review, contradiction checks, reject authority |

### 1.2 Resolution order (canonical)

1. **Pinned override file** for this run (if provided).
2. **Runtime best-available resolution** by role criteria.
3. **Human gate confirmation** before freeze.
4. Freeze role->model map in run artifact (`SPEC.md` model plan or equivalent).

Never encode concrete slugs in skill prose. Run-specific artifacts are allowed.

## 2. Canonical Scope Checker

Single owner: `project-orchestrator/scripts/scope-check.sh`.

Expected behavior:
- Input: `owns` (required), `forbidden` (optional), and changed files.
- Reject when any changed file:
  - matches forbidden, or
  - does not match any owns glob.
- Exit contract:
  - `0`: clean
  - `2`: violations
  - `64`: usage error

Other skills must reference this script path instead of cloning it.

## 3. Edge Contracts

### 3.1 Edge 1 — Researcher -> Orchestrator

Producer artifact: `.orchestrator/<slug>/RESEARCH.md`.

Consumer behavior in orchestrator Stage 1:
- if present: seed direction, trade-offs, and criteria from research
- if absent: preserve existing no-research flow

### 3.2 Edge 2 — Orchestrator -> Hardener

Handoff occurs after integration branch is verified.

Required handoff payload:
- integration branch name
- approved `SPEC.md` path
- success-criteria check status summary
- phase evidence locations (`patch.diff`, `NOTES.md`, `commands.log`, optional `BLOCKER.md`)
- integration verification evidence (`verify.log` and criteria checklist)
- explicit hardening target (near-perfect convergence without scope creep)

### 3.3 Edge 3 — Hardener -> Re-Spec / Re-Research

Trigger: high-impact finding requires design shift beyond approved spec.

Escalation routing:
- re-spec needed -> `project-orchestrator`
- additional discovery needed -> `project-researcher`

Escalation payload:
- finding taxonomy + severity
- blocked-by-spec explanation
- attempted fixes and why insufficient
- failing command evidence and regression/baseline deltas
- explicit decision request (re-spec question or research question)

## 4. Drift + Stop Contract

### 4.1 Shared detectors

- **scope drift**: ownership or forbidden violation
- **plan drift**: implementation diverges from approved contract
- **evidence drift**: green claim lacks command evidence

### 4.2 Shared hard-stop payload

```yaml
stop_reason: <code>
phase_or_loop: <id>
attempt: <n>
failed_checks:
  - command: <command>
    exit_code: <non-zero>
evidence_paths:
  - <path>
next_action: <specific next step>
```

Stop means halt-and-report, not "best effort complete".

## 5. Evidence Bundle Shape

```text
.orchestrator/<slug>/
├── RESEARCH.md?               # present when researcher ran
├── SPEC.md
├── P1/..Pn/
│   ├── patch.diff
│   ├── NOTES.md
│   ├── commands.log
│   └── BLOCKER.md?
├── integration/
│   ├── verify.log
│   └── success-criteria.md
├── hardener/
│   ├── baseline.env?
│   ├── current.env?
│   ├── REPORT.md?
│   └── BLOCKER.md?
└── REPORT.md
```

Exact per-skill additions are allowed, but this core shape should remain stable.
