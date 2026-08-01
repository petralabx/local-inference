# Contributing to petralabx/local-inference

Version: 1.1  
Effective: 2026-07-23  
Owner: PLX Repo Maintainers

> **Governance is centralized in PLX Mission Control.** This file covers
> **repo-specific** workflow only. Cross-repo rules are mandatory:
>
> | Topic | Canonical source |
> |-------|------------------|
> | Agent pillars, PR discipline, evidence | [`petralabx/PLX_MC/config/governance-contract.yaml`](https://github.com/petralabx/PLX_MC/blob/main/config/governance-contract.yaml) |
> | Compliance gate, `MC-Checkout`, risk tiers | [`petralabx/PLX_MC/docs/COLLABORATOR-SOP.md`](https://github.com/petralabx/PLX_MC/blob/main/docs/COLLABORATOR-SOP.md) |
> | Onboarding checklist | [`petralabx/PLX_MC/docs/runbooks/REPO-ONBOARDING.md`](https://github.com/petralabx/PLX_MC/blob/main/docs/runbooks/REPO-ONBOARDING.md) |
>
> See also: `docs/GOVERNANCE.md` in this repo.

---

## 1. Integration branch

| Branch | Role |
|--------|------|
| **`main`** | All feature work merges here via PR |


**Rules**

1. **Never push directly to the integration branch.** Open a PR.
2. Every PR runs the **PLX MC Compliance Gate** (`.github/workflows/plx-mc-compliance.yml`).
3. Agent-driven PRs must include `MC-Checkout: dsp_…` in the body (see COLLABORATOR-SOP).
4. Non-docs PRs need a `## Rollback Plan` section.

---

## 2. Branch naming

| Pattern | Use for |
|---------|---------|
| `feat/<area>-<slug>` | New capability |
| `fix/<area>-<slug>` | Bug fix |
| `chore/<area>-<slug>` | Tooling, deps |
| `docs/<area>-<slug>` | Documentation |
| `ci/<area>-<slug>` | GitHub Actions |

---

## 3. Commits

Use [Conventional Commits](https://www.conventionalcommits.org/) with scope. Include
Mission Control milestone IDs when applicable (`MRP-M-*`, `ERP-M-*`, etc.).

---

## 4. PR template

```markdown
## Summary
(what and why)

## Mission Control
- Milestone: … / n/a
- MC-Checkout: dsp_…   ← required for agent/task work

## Test plan
- [ ] (repo validation commands)

## Rollback Plan
(how to revert)
```

---

## 5. Validation before merge

```bash
python -m unittest discover -s tests -v
python scripts/check-brand-repo-structure.py
```

Required GitHub checks: **CI**, **PLX MC Compliance Gate**, **Compliance Gate Drift**.

---

## 6. Repo-specific notes

Python tooling repo — follow governance contract for PR discipline. Engineering
roots to preserve: `scripts/`, `litellm/`, `docs/`, `.cursor/` (see `AGENTS.md`).

---

## 7. Operator setup

Repo secrets: `PLX_MC_BASE_URL`, `COMPLIANCE_CI_TOKEN`.  
Repo variable: `COMPLIANCE_MODE` (`soft` → `hard` when ready).  
Enable branch protection on `main` — require PR + checks.

Control-plane boundaries (auth, kill switches, health, fallback): see
[`docs/runbooks/control-plane-boundaries.md`](docs/runbooks/control-plane-boundaries.md).

### Routing metadata (shadow)

`.github/workflows/mc-routing-metadata.yml` submits pull-request metadata to MC
`/api/routing/propose` via OIDC when org/repo variable
`PLX_MC_ROUTING_METADATA_ENABLED=1`. It does not check out or execute PR code.
Contract: `.github/plx-mc-routing-manifest.json`. Pilot mode is **shadow** (metrics
only; no candidate dump / deep link). Confirmation and fuzzy auto-link stay off.
Rollback: set `PLX_MC_ROUTING_METADATA_ENABLED=0` (repo override); compliance gate
remains enforced.

### Welcome to Mission Control

Colleague get-started: https://mc.plxcustomer.io/welcome  
Guide: https://github.com/petralabx/PLX_MC/blob/main/docs/runbooks/mc-for-colleagues.md
