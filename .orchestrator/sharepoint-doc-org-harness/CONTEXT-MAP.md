# Context Map

Vince is one person. Filing is two related contexts. They share Vince, VincePersonal, and the Organizer. They meet when Vince is using the harness, not through a standing Work object.

## Contexts

- [Documents](./domain/documents/CONTEXT.md) — durable records in VincePersonal
- [Mail](./domain/mail/CONTEXT.md) — Outlook messages and their attachments

## Relationships

- **Mail → Documents**: an Attachment becomes a Document when it is filed to VincePersonal
- **Documents ↔ Mail**: related only while Vince is using the harness on that turn
- **Shared**: Vince, VincePersonal, Organizer, Vince Node, Correction Log, Judgement, Secret
