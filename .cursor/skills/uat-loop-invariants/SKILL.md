---
name: uat-loop-invariants
description: >-
  Frozen pass/fail gates for the PLX UAT weekly session-batch loop (V0 week-list,
  V2 PR stamp, V4 mail, V5 smoke, V6 no agent-Verified, V9 week closeout) plus
  independent verify (fresh subagent, score > 8) and OUTPUT/MEMORY artifacts.
  Use before Vince approves the week list, before merge/email, and at week
  closeout. Never "fix" by rewriting policy. Policy: SPEC.md when present.
---

# UAT Loop Invariants

Frozen validators for the weekly UAT batch loop. **Fail closed.** Do not weaken
caps, URL rules, or Verified ownership to make a run look green.

## When to use

- Before presenting the week batch list to Vince (**V0**)
- Before merge / before retest email (**V2 / V4 / V5 / V6**)
- At week closeout (**V9**)
- Anytime the user says “validate the UAT loop”, “run uat-loop-invariants”, or
  the orchestrator/worker checklist calls for a gate

## Policy source

Prefer `.orchestrator/uat-weekly-batch-loop/SPEC.md` (D1–D12). If missing, use
the locked defaults in skills `uat-weekly-batch-loop` and `uat-feedback-batch-fix`.

## Gate catalog (v1)

| ID | Name | When | Skill helpers |
|---|---|---|---|
| **V0** | Week list legal | Pre-Vince approval | this skill |
| **V1** | Diagnosis card | Pre-PR | worker / `root-cause-debugger` |
| **V2** | PR stamp + mark-ready dry-run | Pre-merge | `babysit` UAT-PR profile |
| **V3** | Staging Ready | Pre-email | `loop` Ready watcher / Vercel |
| **V4** | Mail validate | Pre-send | `plx-graph-mail` mode=`validate` |
| **V5** | Batch smoke | Post-Ready | `plx-portal-agent-access` batch smoke |
| **V6** | No agent-Verified | Post-worker | this skill |
| **V9** | Week closeout complete | Week end | this skill + OUTPUT/MEMORY + brain_ingest |
| **IV** | Independent verify | End of batch + week | Fresh subagent; score > 8; `INDEPENDENT-VERIFIER.md` |

(V7 schema STOP → `staging-dual-db-migrate` + Vince; V8 adversarial review optional for Critical/High.)

---

## V0 — Week list legal

```text
UAT_V0: OK|FAIL
```

Pass only if all true:

1. Batch count ∈ **1..5** (or 0 with explicit empty-week note)
2. Total tickets **≤ 25**
3. Each batch **≤ 5** tickets
4. Every ticket resolution ∈ {Open, In Progress, Failed Retest} (case-insensitive)
5. No undeclared Critical / auth / schema STOP tickets slipped in without Vince flag
6. Failed Retest ≥2 same-ticket cases are flagged for Vince, not silently queued

---

## V1 — Diagnosis card (spot-check)

```text
UAT_V1: OK|FAIL
```

PR/session must include: ranked hypotheses, files to inspect, smallest fix,
verification plan; `[NEEDS INFO]` called out. Fail if coding started with none.

---

## V2 — Delegate to babysit UAT-PR

Run `babysit` UAT-PR profile; require `UAT_PR_VALIDATE: OK`.

---

## V3 — Staging Ready

```text
UAT_V3: OK|FAIL
```

Evidence: Vercel staging deployment Ready for the merge SHA **or** mark-ready
workflow success. Base URL checks use only `https://staging.plxcustomer.io`.

Optional: arm `/loop` to wake on Ready rather than blind polling.

---

## V4 — Delegate to plx-graph-mail validate

Require `MAIL_VALIDATE: OK` before any send.

---

## V5 — Delegate to portal-agent-access batch smoke

Require `BATCH_SMOKE: OK` or `SKIP` with Vince/WEEKLY-LOG reason. Prefer OK
before email when pageUrls exist.

---

## V6 — No agent-Verified

```text
UAT_V6: OK|FAIL
```

After worker actions, no ticket in the batch may have been set to **Verified**
by the agent. Expected post-fix states: Ready for UAT / UATn (or prior state
if blocked). Fail if agent PATCHed Verified.

---

## V9 — Week closeout

```text
UAT_V9: OK|FAIL
```

Pass only if:

1. `WEEKLY-LOG.md` has this week’s section + scoreboard fields
2. Approved batch list frozen
3. Per-dispatched batch row present (or deferred with reason)
4. Reusable failures appended to `tasks/lessons.md` when applicable
5. **OUTPUT-WEEK.md** + **MEMORY-WEEK.md** exist under `runs/{{WEEK_ID}}/`
6. **brain_ingest** of MEMORY done (`projectSlug: uat-weekly-batch-loop`,
   `domain: manufacturing`, `sourceType: uat_weekly_loop`) — record title/id
7. No master push; no non-submitter email claimed

V9 alone does **not** mark the week done — see **IV** below.

---

## IV — Independent verify (fresh subagent)

```text
INDEPENDENT_VERIFY: score=<1-10> pass=YES|NO
```

- Must run in a **separate Task/subagent** with a **fresh context** (not the builder).
- Prefer `readonly: true` + different model family when available.
- Prompt: `.orchestrator/uat-weekly-batch-loop/INDEPENDENT-VERIFIER.md`
- **`pass: YES` only if `score > 8`**. Score ≤ 8 → run not done.
- Builder **must not** self-score.
- Applies to **each batch run** and the **week closeout**.

Also require per-batch:

1. `runs/{{WEEK_ID}}/OUTPUT-{{BATCH_ID}}.md`
2. `runs/{{WEEK_ID}}/MEMORY-{{BATCH_ID}}.md` + brain_ingest of MEMORY

---

## Composite reports

**Pre-approval:** `UAT_V0`  
**Pre-email bundle:** `UAT_V2` + `UAT_V3` + `UAT_V4` (+ `UAT_V5` when runnable) + `UAT_V6`  
**Batch done:** V1–V6 + OUTPUT/MEMORY + ingest + **IV score > 8**  
**Week end:** `UAT_V9` + OUTPUT-WEEK/MEMORY-WEEK + ingest + **IV score > 8**

Never report FAIL as OK. Never regenerate policy to match a bad run. Never self-score IV.

## Related

- `uat-weekly-batch-loop` · `uat-feedback-batch-fix`
- `plx-graph-mail` · `babysit` · `plx-portal-agent-access`
- `session-brain` · `PROMPT-BUILDER` · SPEC.md §15–§16 · `INDEPENDENT-VERIFIER.md`
