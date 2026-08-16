# Mail

Outlook messages for Vince. This context exists so conversations stay mail, and only filed attachments become Documents.

## Language

**Vince**:
The one person this system serves.
_Avoid_: user, operator, customer

**VincePersonal**:
Vince’s personal SharePoint site. Filed attachments land here as Documents.
_Avoid_: OneDrive, local disk, PST, Outlook store as the file home

**Organizer**:
The automated actor allowed to file an Attachment. It places a Message in an Outlook folder only when a Correction says so.
_Avoid_: Cowork, inbox-sorter, a second Outlook taxonomy

**Message**:
An Outlook email. It is not a Document.
_Avoid_: file, document, record

**Attachment**:
A payload on a Message. It becomes a Document only after it is filed to VincePersonal.
_Avoid_: file, document (before filing)

**Vince Node**:
Vince’s private slice of Secondbrain / the knowledge graph. Mail facts that leave Outlook live only here.
_Avoid_: shared Brain, company mailbox index
