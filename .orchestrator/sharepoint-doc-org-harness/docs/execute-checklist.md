# Operator execute checklist (live — Vince present)

Code phases P1–P5 do not run these steps. Live Desktop and taylorvalton
wait until Vince is at the machine.

1. [x] Five-file smoke in VincePersonal `00_Inbox` (not Desktop). Journal moves. `harness reverse` undoes them. (2026-08-16 run `059bb69aff1b4421a821bb0835506de0`)
2. [x] VTA redirect: `scripts/redirect-known-folders.ps1 -DryRun`, then `-Apply` only while Vince is present. (applied 2026-08-16 on VTA)
3. [x] taylorvalton: same method, applied 2026-08-16. SyncRoot is `C:\Users\taylo\Petra Hygienic Systems Int Ltd\Vince Personal - Documents` (extra-library mount of the same VincePersonal site). State: `00_Inbox\_redirect_state.json`. Old personal-OneDrive Desktop/Documents and local Downloads were not moved.
4. [x] Full drain of the Petra map (`config/drain_map.yaml`). Unique files only. Hash copies skip. Finished 2026-08-16 on VTA (`harness drain`): numbered tree + `07_Admin` unique files + Desktop/CursorInbox/Vince Backup/OLD LAPTOP + laptop leftovers. Hash copies, secrets, and code trees remain in Petra by design. Do not hide Petra nav until unique work is gone (ADR 0020).
5. [x] Mail first pass: last 90 days of attachments. 2026-08-17 Outlook COM on VTA (`vince@petrasoap.com`): 3,196 unique saved to `00_Inbox/_from_mail`; 9,706 hash copies skipped; 22,017 inline skipped; 0 secrets; 0 errors. Outlook folders unchanged. Remainder of mailbox after this writer is proven.
6. [x] First Organizer digest proven 2026-08-17/18. Proof run `0f7f643d4e1d4916b4ae5deeecf79c59` (40 files). Then mail capture `712f41a420d345e09527b8db9e03185b` (3105 moved), desktop/docs/downloads `d2220e0bb8f94baa88bc35ce8629c5d6` (1984 moved), inbox top-level `9c1878adc55e4e0289e82c2d47276a0a` (4 moved). `harness where` resolved Happy Yards. Once-daily Task Scheduler `VincePersonal-Organizer-Digest` installed 2026-08-18 on VTA; next run 2026-08-19 06:00 America/Toronto. Stay on daily until findability stays proven, then `-Mode every-4h` (06:00/10:00/14:00/18:00).
7. [ ] After unique Petra work is gone, hide the old Petra sources (`hide-petra-sources.ps1`). Never hide Vince Personal. Drain `09_Archive` + Petra root loose files first. Plan leftover VincePersonal trees with `harness fold --report …` (dry-run default, ADR 0026). `--apply` only after harvest stamp, on VTA, Vince present. Never archive `00`–`06`.

Inference stays on Dell LiteLLM `local-driver` / `local-coder`. Paid hosts stay forbidden.

Open follow-ups: TASK-1063 (every-4h after daily proof), TASK-1064 (mail remainder), TASK-1071 (relabel already-filed homes). TASK-1065, TASK-1068, and TASK-1070 (PR #32) are done.
