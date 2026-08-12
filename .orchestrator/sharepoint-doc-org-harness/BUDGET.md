---
slug: sharepoint-doc-org-harness
created: 2026-08-12T11:20:00Z
---

# Build budget

- Soft pause: **USD $100** (Cursor / frontier build agents)
- On pause: report estimated spend so far, estimate to complete remaining phases,
  wait for Vince go-ahead
- Steady-state LiteLLM: $0 token budget (local only)
- Commit + push cadence: after each phase acceptance (and mid-phase if large)

## Spend log (manual checkpoints)

| When | Est. cumulative | Note |
|------|----------------:|------|
| Budget set | $0 | Soft pause $100 |
| After P1–P3 (orchestrator-built, no phase subagents) | ~$15–25 | Discovery+research+spec earlier in session; P1–P3 coded in-session |
| After P4–P5 + soft pause | **~$85–100** | Discovery→SPEC + P1–P5 in one long session; **paused at soft limit** |

## Soft pause (2026-08-12)

**Status:** waiting for Vince go-ahead.

| Done | Remaining |
|------|-----------|
| Discovery, research, SPEC approved | — |
| P1–P3 (scaffold, journal/reverse, provenance) | — |
| P4 extract/classify + fixtures (15 tests green incl. prior) | — |
| P5 inbox move-not-copy + dedupe tombstone | P5 archive-in-place lane still thin |
| | **P6** Outlook/attachments (Graph fakes) |
| | **P7** digest job + ops docs + paid-URL guard |
| | **P8** e2e fixtures + publish prep |

**Estimate to finish remaining (P6–P8 + archive polish):** about **$60–90** more Cursor/frontier spend (mail + digest are the heavy slices). Steady-state LiteLLM stays **$0**.

**Do not continue past this pause until Vince says go.**
