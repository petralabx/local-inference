# Operator execute checklist (live — Vince present)

Code phases P1–P5 do not run these steps. Live Desktop and taylorvalton
wait until Vince is at the machine.

1. [x] Five-file smoke in VincePersonal `00_Inbox` (not Desktop). Journal moves. `harness reverse` undoes them. (2026-08-16 run `059bb69aff1b4421a821bb0835506de0`)
2. [x] VTA redirect: `scripts/redirect-known-folders.ps1 -DryRun`, then `-Apply` only while Vince is present. (applied 2026-08-16 on VTA)
3. [ ] taylorvalton: same script, same method, before the next save on that machine. Do not apply while Vince is away.
4. [ ] Full drain of the Petra map (`config/drain_map.yaml`). Unique files only. Hash copies skip.
5. [ ] Mail first pass: last 90 days of attachments. Remainder after that writer is proven. Do not invent Outlook folders.
6. [ ] Once-daily Organizer until proven, then `install-organizer-cadence.ps1 -Mode every-4h` (06:00/10:00/14:00/18:00 America/Toronto).
7. [ ] After a Petra source folder is empty, remove or hide it. Do not leave a second tree.

Inference stays on Dell LiteLLM `local-driver` / `local-coder`. Paid hosts stay forbidden.
