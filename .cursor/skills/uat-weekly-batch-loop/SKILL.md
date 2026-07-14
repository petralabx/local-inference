---
name: uat-weekly-batch-loop
description: >-
  Run one weekly PLX UAT session-batch cycle: select ≤5 batches from Open /
  In Progress / Failed Retest, get Vince's one approval, dispatch one worker
  session/PR per batch, email submitters after staging Ready, and close the
  week with WEEKLY-LOG + lessons + brain_ingest. Use when asked to run the
  weekly UAT loop, process UAT session batches, or /loop the UAT weekly cycle.
  Done only when tickets reach Resolution=Verified (submitter-driven).
---

# UAT Weekly Batch Loop

Orchestrate **one week** of UAT Feedback session batches. Per-batch fix work
belongs in **uat-feedback-batch-fix** (or paste
`.orchestrator/uat-weekly-batch-loop/BATCH-WORKER.md`).

## Policy source of truth

When the portal worktree has `.orchestrator/uat-weekly-batch-loop/SPEC.md`,
**obey it** (locked D1–D12). Do not invent policy. Prefer pasting
`WEEKLY-ORCHESTRATOR.md` from that folder over rewriting mid-run.

## When to use

- "Run the weekly UAT loop" / `/loop` the UAT weekly cycle
- Select this week's session batches and dispatch fix sessions
- Week closeout (scoreboard, lessons, brain_ingest)

## Preferences (locked defaults)

- Staging only; never `master` / production DB
- Caps: **3–5 batches/week**, **≤25 tickets**, **≤5 tickets/batch**
- Vince approves the week list **once**, then MC/cloud (or paste) **per batch**
- Email From: `cos@petrasoap.com` · To: submitters · BCC: `vince@petrasoap.com`
- URL: only `https://staging.plxcustomer.io` (never vercel.app git alias)
- Loop-complete = **Verified** only
- Retest template approved in SPEC → auto-send after merge + Vercel Ready
- Batch grouping: portal `session-groups.ts` (Open / In Progress / Failed Retest)

## Steps

1. Load memory: plx-brain `brain_search` `UAT weekly loop uat-weekly-batch-loop`;
   read `WEEKLY-LOG.md` + recent UAT bullets in `tasks/lessons.md`
2. Follow `WEEKLY-ORCHESTRATOR.md` (or this skill's steps if prompts missing)
3. Build candidate batch table; present to Vince for **one** approval; freeze list
4. Dispatch each approved batch via **uat-feedback-batch-fix** / `BATCH-WORKER.md`
5. Mid-week: help mark-ready stamp issues; never set Verified; never merge to master
6. Week closeout: scoreboard → WEEKLY-LOG → lessons → optional PROMPT-BUILDER diffs
   → **mandatory** `brain_ingest` (`projectSlug: uat-weekly-batch-loop`,
   `domain: manufacturing`, `sourceType: uat_weekly_loop`)

## Done when

- [ ] Week list Vince-approved once and frozen in WEEKLY-LOG
- [ ] Each approved batch dispatched (or deferred with reason)
- [ ] Closeout written including brain_ingest
- [ ] No ticket marked Verified by the agent
- [ ] No master push; no non-submitter email

## STOP

Critical / auth / schema / missing submitter email / same ticket Failed Retest ≥2
→ ask Vince before dispatching that batch/ticket.

## Related

- Per-batch worker: `uat-feedback-batch-fix`
- Graph send: `plx-graph-mail`
- Dual-DB schema landings: `staging-dual-db-migrate`
- SOP scenario UAT (different): `uat-runner`
