# Delegated MSAL device-code on VTA is the Graph write path

Decided 2026-08-25.

Vince Personal list-item stamps (`Title`, `OrganizerParty`, `OrganizerPrefix`,
`OrganizerHome`) use **delegated** Microsoft Graph as `vince@petrasoap.com`.
The writer machine is Dell-VTA. The live client satisfies
`GraphDriveClient` and is constructed only when a token can be acquired
silently or via an explicit login.

## Decision

1. **MSAL public-client device-code** for the first interactive login on VTA
   (`harness graph-login`). The token cache lives in
   `data/msal_graph_cache.bin` (untracked). Later stamp / digest / relabel
   runs use silent MSAL refresh. Scheduled jobs never start device-code
   unless `HARNESS_GRAPH_INTERACTIVE=1`.
2. **Existing Windows Graph session** may be reused when Azure CLI on VTA is
   already signed in as the same UPN. That is a convenience, not a second
   SoT and not a pasted token.
3. The public client defaults to Microsoft Graph Command Line Tools
   (`14d82eec-204b-4c2f-b7e8-296a70dab67e`). Override `graph.client_id` if
   the tenant blocks that first-party app. Still delegated. Still no secret.
4. Offline / missing cache keeps `FakeGraphDriveClient` for tests and
   `graph=None` + `GraphOfflineError` for live jobs. Office/PDF embeds still
   write.

## Rejected

- **App-only / client-secret.** PLX_Forms and other tenant apps are
  read-biased. Site-column and list-item writes are Vince’s delegated
  consent, not a new daemon principal.
- **Pasting an access token** into chat, env files committed to git, or an
  agent prompt.
- **Scraping browser cookies** from another machine. A Cloud Agent VM does
  not inherit Vince’s SharePoint session.
- **Unindexed `$filter=FileLeafRef`** on the Documents library. The library
  is over the 5k view threshold; that filter throttles. Backfill walks
  `00`–`06` folders and resolves items by drive path or per-folder
  `/children`. Leftover root trees are not folded by stamp.

## Scope

- Site: `https://petrasoap.sharepoint.com/sites/VincePersonal`
- Library: default Documents / Shared Documents
- Content type: Document `0x0101`
- Scopes: `Sites.ReadWrite.All` (delegated)

See `docs/ops.md` for login + stamp commands.
