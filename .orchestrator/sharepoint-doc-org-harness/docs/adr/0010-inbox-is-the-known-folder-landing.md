# Inbox is the known-folder landing

Desktop, Documents, and Downloads on VTA and taylorvalton redirect into VincePersonal `00_Inbox`. Windows cannot share one folder for all three known folders, so each gets a capture subfolder:

- `00_Inbox/_from_desktop`
- `00_Inbox/_from_documents`
- `00_Inbox/_from_downloads`

The Organizer treats those three as inbox sources and files out of them. Vince sees one inbox, not three homes. Top-level `Desktop` / `Documents` / `Downloads` in VincePersonal are rejected. Both machines use this same method (ADR 0022).
