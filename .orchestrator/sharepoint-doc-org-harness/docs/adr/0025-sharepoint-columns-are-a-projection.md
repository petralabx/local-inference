# SharePoint Title and Party/Prefix/Home are a ledger projection

Amended 2026-08-25.

The Document ledger remains the identity SoT (ADR 0024). SharePoint list-item
Title and the three Vince Personal site columns are a **projection** of that
ledger so All-tab search and Copilot can rank the readable title, not the law
filename.

## Column contract (locked)

| Display name | Internal name (stable) | Crawled property |
| --- | --- | --- |
| Party | `OrganizerParty` | `ows_OrganizerParty` |
| Prefix | `OrganizerPrefix` | `ows_OrganizerPrefix` |
| Home | `OrganizerHome` | `ows_OrganizerHome` |

They are **site columns** on Vince Personal, added to the default Document
content type, and **indexed** (SharePoint indexed column) so list views survive
5k. They are never library-local. The Organizer stamps list-item **Title** to
the peeled readable title (no date, no PREFIX, no `_vNN`). It does not rename
the native Title field.

Do not create Term store or Syntex models. Do not customize ranking models. Do
not enable SharePoint Autofill / Copilot-in-SharePoint autofill on
`OrganizerParty`, `OrganizerPrefix`, or `OrganizerHome` — those values are
ledger projections. Autofill, if ever used, would be a separate Summary-style
column only. See [Set up and manage autofill columns](https://learn.microsoft.com/en-us/microsoft-365/documentprocessing/autofill-setup).

Python stamps Graph listItem fields when online and still writes Office/PDF
Title/Subject/Keywords on the sync-root when Graph is offline. A tenant-admin
search-schema mapping is required before the columns become refiners; the
harness cannot finish that step. See `docs/ops.md`.

## Copilot and search (do not weaken)

Microsoft Copilot’s semantic index uses library column metadata plus Title when
a library or folder is attached. Folder names are not Copilot classification.
Party/Prefix/Home plus the stamped Title are that signal.

- [Semantic indexing for Microsoft Copilot](https://learn.microsoft.com/en-us/microsoftsearch/semantic-index-for-copilot)
  (page `updated_at` 2026-08-18): scoped library/folder queries incorporate
  column metadata; the SharePoint site must remain searchable; **Archived
  SharePoint Data** is not supported at user or tenant index.
- Vince Personal must stay searchable: Site settings → Search and offline
  availability → **Allow this site to appear in search results = Yes**. If it
  is No, both Microsoft Search and the semantic index drop the site. Same
  exclusion path is documented on the Copilot page and on
  [Enable content on a site to be searchable](https://learn.microsoft.com/en-us/sharepoint/make-site-content-searchable).
- Do not archive `00`–`06` homes as cleanup. Archived SharePoint data is not
  in the semantic index ([Copilot supported content types](https://learn.microsoft.com/en-us/microsoftsearch/semantic-index-for-copilot#supported-content-types);
  [Archive FAQ: archived content is not used by Copilot](https://learn.microsoft.com/en-us/microsoft-365/archive/archive-faq)).
