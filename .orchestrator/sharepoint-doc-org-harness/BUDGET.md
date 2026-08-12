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
| Go-ahead +$70 cap (P5 archive + P6–P8) | prior + **≤$70** | Completed under second cap; 23 tests green |

## Caps

1. Soft pause $100 — hit; waited for go-ahead.
2. Second cap **$70** (2026-08-12) — used for P5 archive polish + P6–P8.

## Status after second cap

| Done |
|------|
| P5 archive-in-place lane |
| P6 Outlook/attachments (FakeGraph + cassette) |
| P7 digest CLI + ops docs + paid-URL guard |
| P8 e2e + OSS/cutover docs + README |

**Harness phases P1–P8 complete** (fixture/fake Graph; live VTA cutover remains manual per `docs/cutover-checklist.md`). Steady-state LiteLLM **$0**.
