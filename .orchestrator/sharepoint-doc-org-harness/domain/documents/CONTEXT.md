# Documents

Durable records that live in VincePersonal. This context exists so every save has one home and a history.

## Language

**Vince**:
The one person this system serves.
_Avoid_: user, operator, customer

**VincePersonal**:
Vince’s personal SharePoint site. It is the only store for Documents.
_Avoid_: OneDrive, local disk, personal drive, cache

**Organizer**:
The automated actor allowed to change a Document’s location or name. Installing its daily job is Vince evoking it.
_Avoid_: Cowork, M365 Auto, COS as a second writer

**Secret**:
A credential or key. It is never a Document and never enters VincePersonal or the Vince Node.
_Avoid_: file, document, attachment (when it is a key)

**Document**:
A durable business or personal record whose bytes live in VincePersonal and whose history can be asked about. Its filename is a readable title. Date, type, and version live in the journal.
_Avoid_: file (the bytes), item, attachment (that is Mail until filed), record

**Save Path**:
The one place Vince is shown when he saves. It is VincePersonal. Other roots may exist as hidden pipes.
_Avoid_: This PC, Desktop, OneDrive as a visible home

**Vince Node**:
Vince’s private slice of Secondbrain / the knowledge graph. Vince may open it beside company PLX. No other person, and no agent Vince did not evoke, can read or write it.
_Avoid_: shared Brain, company graph, tenant-wide index

**Correction**:
A learned rule about how Vince files, taken from his overrides. The Organizer applies Corrections before it guesses.
_Avoid_: prompt, memory, vibe

**Correction Log**:
The inspectable, append-only store of Corrections. It is the lesson. The Vince Node holds a projection.
_Avoid_: model weights, chat memory, Brain-only memory

**Judgement**:
Vince’s choice when the journal and the Vince Node disagree. If he does not choose, the journal stands.
_Avoid_: merge, consensus, majority
