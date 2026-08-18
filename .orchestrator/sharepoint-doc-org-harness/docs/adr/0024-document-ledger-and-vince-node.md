# Document ledger and Vince Node projection

A Document has one identity row keyed by content hash (`sha256`). That row holds title, prefix, type, date, version, home, current path, and classify source. Mail facts may attach when the Document began as an attachment.

The move journal stays the SoT for *moves* (ADR 0005). The ledger is the SoT for *identity*. If they disagree, show Vince one diff. If he judges, Judgement wins. If he does not, the journal wins on the path and the ledger is rebuilt from the journal plus classify fields.

The Vince Node is a projection, not a second SoT. Each ledger upsert may ingest into Vince’s private Brain slice. If Brain is down, filing continues. Company Brain does not receive VincePersonal text (ADR 0003). SharePoint columns are not the SoT.

`harness where` reads the ledger first, then the journal path trail.
