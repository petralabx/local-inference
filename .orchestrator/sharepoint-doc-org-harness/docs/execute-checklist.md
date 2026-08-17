# Operator execute checklist (live — Vince present)

Code phases P1–P5 do not run these steps. Live Desktop and taylorvalton
wait until Vince is at the machine.

1. [x] Five-file smoke in VincePersonal `00_Inbox` (not Desktop). Journal moves. `harness reverse` undoes them. (2026-08-16 run `059bb69aff1b4421a821bb0835506de0`)
2. [x] VTA redirect: `scripts/redirect-known-folders.ps1 -DryRun`, then `-Apply` only while Vince is present. (applied 2026-08-16 on VTA)
3. [x] taylorvalton: same method, applied 2026-08-16. SyncRoot is `C:\Users\taylo\Petra Hygienic Systems Int Ltd\Vince Personal - Documents` (extra-library mount of the same VincePersonal site). State: `00_Inbox\_redirect_state.json`. Old personal-OneDrive Desktop/Documents and local Downloads were not moved.
4. [x] Full drain of the Petra map (`config/drain_map.yaml`). Unique files only. Hash copies skip. Finished 2026-08-16 on VTA (`harness drain`): numbered tree + `07_Admin` unique files + Desktop/CursorInbox/Vince Backup/OLD LAPTOP + laptop leftovers. Hash copies, secrets, and code trees remain in Petra by design. Do not hide Petra nav until unique work is gone (ADR 0020).
5. [x] Mail first pass: last 90 days of attachments. 2026-08-17 Outlook COM on VTA (`vince@petrasoap.com`): 3,196 unique saved to `00_Inbox/_from_mail`; 9,706 hash copies skipped; 22,017 inline skipped; 0 secrets; 0 errors. Outlook folders unchanged. Remainder of mailbox after this writer is proven.
6. [ ] Once-daily Organizer until proven, then `install-organizer-cadence.ps1 -Mode every-4h` (06:00/10:00/14:00/18:00 America/Toronto).
7. [ ] After a Petra source folder is empty, remove or hide it. Do not leave a second tree.

Inference stays on Dell LiteLLM `local-driver` / `local-coder`. Paid hosts stay forbidden.
