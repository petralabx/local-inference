# plx-knowledge-video — reference

Templates and contracts for the Knowledge Hub package. Copy, fill from the **running
app**, and keep every file under `knowledge/<flow-slug>/`.

## `how-to.md`

YAML frontmatter, then an executive summary, then steps that mirror the video 1:1.

```markdown
---
title: <Flow name> — How-To
tags: [How-To, <Domain>, Finance, Executive, Onboarding, Business-Central]
audience: [Executive, Finance]
flow: <flow-slug>
video: ./demo.mp4
captions: ./demo.srt
status: draft            # draft | reviewed | published
source_of_truth: ./process-outline.md
updated: <YYYY-MM-DD>
---

## Executive summary

3–5 sentences: what the flow is, the controls it enforces (approvals, matching,
audit trail, system of record), and why it matters to leadership and finance.

## Steps

For each step, mirror the video exactly:

### 1. <Step name>
- **In the Portal:** <the user action>
- **System of record:** <what the backend / integration records>
- **Control & visibility:** <approval, three-way match, status, audit point>

> **Control call-out:** <the specific control this step establishes>

## Video

<video src="./demo.mp4" controls></video>
```

Only include the `Business-Central` tag (and any BC "system of record" lines) when the
running build actually performs that integration. Otherwise omit it and note the gap.

## `metadata.yml`

Lightweight, for Hub ingestion. Keep keys stable across packages.

```yaml
id: <flow-slug>
title: <Flow name> — How-To
type: how-to
domain: <e.g. Finance / Procurement>
audience: [Executive, Finance]
tags: [How-To, <Domain>, Finance, Executive, Onboarding]
assets:
  video: demo.mp4
  captions: demo.srt
  page: how-to.md
  outline: process-outline.md
duration_seconds: <int>          # from ffprobe on demo.mp4
narration:
  provider: elevenlabs           # or the local fallback actually used
  voice: <voice name/id>
  fallback_note: <present only if a non-ElevenLabs voice was used>
source:
  app: <plx-customer-portal | PLX_MC>
  base_url: <the demo.config.json baseUrl used>
  git_ref: <branch/sha filmed>
status: draft
updated: <YYYY-MM-DD>
```

## `process-outline.md`

The ordered, temporary source of truth the video mirrors. Draft it from the actual
Portal modules and any integration code — **not** from an idealized process.

```markdown
# <Flow name> — process outline

> Temporary source of truth drafted from the running app at <git_ref>. Refine with the
> process owner. Steps marked NOT IMPLEMENTED are absent in this build and are excluded
> from the video.

| # | Step | User action in Portal | System of record effect | Key controls / data / approvals | Annotation opportunity | Status |
|---|------|-----------------------|-------------------------|---------------------------------|------------------------|--------|
| 1 | ... | ... | ... | ... | zoom on ... | implemented |
| n | ... | ... | ... | ... | — | NOT IMPLEMENTED |
```

Be explicit about status per step so the outline stays honest about what can actually be
filmed today.
