# Operator execute checklist (live — Vince present)

Code phases P1–P5 do not run these steps. Live Desktop and taylorvalton
wait until Vince is at the machine.

1. [x] Five-file smoke in VincePersonal `00_Inbox` (not Desktop). Journal moves. `harness reverse` undoes them. (2026-08-16 run `059bb69aff1b4421a821bb0835506de0`)
2. [x] VTA redirect: `scripts/redirect-known-folders.ps1 -DryRun`, then `-Apply` only while Vince is present. (applied 2026-08-16 on VTA)
3. [x] taylorvalton: same method, applied 2026-08-16. SyncRoot is `C:\Users\taylo\Petra Hygienic Systems Int Ltd\Vince Personal - Documents` (extra-library mount of the same VincePersonal site). State: `00_Inbox\_redirect_state.json`. Old personal-OneDrive Desktop/Documents and local Downloads were not moved.
4. [ ] Full drain of the Petra map (`config/drain_map.yaml`). Unique files only. Hash copies skip. Started 2026-08-16 on VTA (`harness drain`). Moved unique files from `00_INBOX`, Teams, `08_Personal`, `06_Marketing`, `05_HR`, `02_Customers`, `01_Projects`, `03_Finance` (about 2,312 moved; 3 secrets skipped). Still open: `04_Operations`, `07_Admin`, Desktop, CursorInbox, Vince Backup, OLD LAPTOP FILES, leftover laptop Desktop/Documents/Downloads.
5. [ ] Mail first pass: last 90 days of attachments. Remainder after that writer is proven. Do not invent Outlook folders.
6. [ ] Once-daily Organizer until proven, then `install-organizer-cadence.ps1 -Mode every-4h` (06:00/10:00/14:00/18:00 America/Toronto).
7. [ ] After a Petra source folder is empty, remove or hide it. Do not leave a second tree.

Inference stays on Dell LiteLLM `local-driver` / `local-coder`. Paid hosts stay forbidden.
