# Leftover-tree fold is dry-run hygiene after harvest stamp

Vince locked leftover-tree fold as hygiene **after** harvest stamp, not as the
search architecture. SharePoint All-tab ranking of leftover piles
(`Documents`, `Misc`, `General_Docs`, `Open Orders / Happy Valley`) above real
invoices is a stamp/index problem first. Folding those trees is a later cleanup.

`harness fold` lists leftover trees versus taxonomy `00_Inbox`–`06_Reference`,
estimates file counts, and proposes destinations with the existing classifier
order (correction_rule → heuristic → LLM). It does not move files unless
`--apply` is passed. `--apply` stays off in the live default.

Skip code trees and secrets. Never hide Vince Personal. Never archive `00`–`06`
as cleanup — archived SharePoint data drops out of the Copilot semantic index
(ADR 0025). Nested leftover piles inside the homes (`04_Admin/Documents`,
`04_Admin/General_Docs`, `05_Personal/Misc`, `01_Clients_Projects/Petra`) fold
into other live `00`–`06` destinations, not `_Archive`.
