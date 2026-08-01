---
name: plx-knowledge-video
description: Produce a PLX Knowledge Hub video package for a Portal or VMC workflow — a narrated, captioned MP4 with smart zooms and control-point annotations, a matching SRT, a How-To Markdown page, and a metadata.yml — by orchestrating the demo-studio skills with an Executive and Finance tone. Use when the user asks to record, film, publish, or refresh a Knowledge Hub how-to, onboarding, or product video for a PLX Portal or VMC flow.
---

# PLX Knowledge Video

Project wrapper around the **demo-studio** skill family (`demo-setup`, `film-demo`,
`narrate`, `sync-narration`, `produce-video`) that enforces the **PLX Knowledge Hub**
package contract, the **Executive / Finance** tone, and a control-and-visibility
annotation style. demo-studio owns the recording/zoom/caption machinery; this skill
owns *what a Knowledge Hub deliverable must be* and *how a PLX video should read*.

**Read the demo-studio stage skills — do not reimplement their machinery:**

| Stage | Skill | Owns |
|-------|-------|------|
| Orchestration | `produce-video` | A→Z chaining, silent vs narrated mode |
| Silent capture | `film-demo` (+ its `reference.md`) | camera model (`focus`/`wide`), cursor, speed-ups, guardrails, verify |
| Voice | `narrate` | ElevenLabs voice/model, script rules, credits |
| Sync + captions | `sync-narration` | faster-whisper alignment, caption burn, SRT |

If demo-studio is not installed:
`npx skills add AlexAnsart/demo-studio --skill '*' -a cursor --copy -g -y`.

## Prerequisites (verify before filming)

- Node 18+, `ffmpeg`/`ffprobe` on PATH, Playwright Chromium
  (`cd <film-demo>/scripts && npm install && npx playwright install chromium`).
- `faster-whisper` (for caption alignment): `pip install faster-whisper`.
- Narration voice: `ELEVENLABS_API_KEY` for the intended executive voice. **If the key
  is absent, stop and tell the user** — either supply the key or explicitly approve the
  best available local TTS fallback (e.g. Piper), and **note the fallback in
  `metadata.yml` and the how-to**. Never silently ship a different voice or a silent video
  when narration was requested.
- The target app must be **running and reachable** at the base URL in `demo.config.json`,
  and the exact flow must be **clickable end-to-end** in that build. If a step does not
  exist in the running app, do not stage or fake it (see Constraints).

## Required deliverable — the Knowledge Hub package

Keep every generated file under one directory: `knowledge/<flow-slug>/`.

```
knowledge/<flow-slug>/
├── demo.mp4            # narrated + burned-caption final video
├── demo.srt            # side-car captions (same timing as burned-in)
├── how-to.md           # Knowledge Hub page (frontmatter + steps)
├── metadata.yml        # Hub ingestion metadata
└── process-outline.md  # ordered source-of-truth step list this video mirrors
```

Video requirements:
- **Length 3–5 min** — tight, respectful of executive attention.
- **2–5 smart zooms** (`focus`/`wide`) on the moments that carry control: key fields,
  status changes, approval actions, and match / reconciliation indicators. Always return
  `wide` after a submit so the result is visible.
- **Visual emphasis** (highlight / circle) on approvals, control points, and any
  three-way-match or reconciliation signals — only where they actually appear in the UI.
- Captions burned in **and** exported as `demo.srt`.

## Tone (Executive + Finance)

Professional, concise, control- and visibility-oriented. Emphasise clarity,
auditability, approvals, matching/reconciliation, and system-of-record. Brief senior
operators — **avoid beginner "click here" narration**. Name the control each step
establishes (segregation of duties, approval gate, audit trail, three-way match) rather
than the mouse motion.

## Pipeline

Follow `produce-video` exactly. Voice first when narrated: write `script.md`, generate
`narration.mp3` (`narrate`), align it (faster-whisper) to size on-screen holds, record
the silent video (`film-demo`, resolve every guardrail alert), then sync + burn captions
(`sync-narration`). Finally export the SRT and write `how-to.md` + `metadata.yml`.

Export the side-car SRT from the same alignment/plan used for the burned captions so the
two never drift.

See `reference.md` for the `how-to.md` frontmatter contract and the `metadata.yml`
schema, plus the process-outline format.

### Repeatable capture pipeline (`pipeline/`)

For a reliable, one-command-per-beat capture of a **live** app, use the committed
`pipeline/` (narration-first, per-beat clean capture). It fixes the two failure modes
of naive screen-recording: it **never captures page-load white screens** (each beat is
loaded off-camera before recording) and it **passes demo-studio's compose FPS gate on
static pages** via an `activeHold` cursor drift. Each beat is recorded at its own
narration length and stitched with no global time-stretch. Full instructions,
one-time setup, and the working P2P example config are in
[`pipeline/README.md`](pipeline/README.md) (`capture-beat.mjs`, `narrate-beats.mjs`,
`assemble.sh`, `beats.example.json`, `demo.config.example.json`).

## Quality gate (self-review before delivering)

- Does the narration read for executives and finance (control/visibility, not clicks)?
- Are the real control points (approvals, matches, status transitions) the zoomed moments?
- Is the package usable in the Hub with minimal manual editing (valid frontmatter, SRT
  present, metadata complete)?
- Is `process-outline.md` accurate to the **running app**, with anything not-yet-built
  clearly marked rather than implied?
- demo-studio gates pass: `film-demo` verify `pass:true`, zero unjustified guardrail
  alerts, captions aligned to audio.

## Constraints

- **Accuracy over polish.** If a scripted beat conflicts with what the app does, change
  the script.
- **Do not invent business rules or fabricate UI.** Film only steps that exist and are
  clickable in the running build. If part of the flow is unbuilt or gated behind missing
  integration/credentials, stop and report the gap — deliver the accurate partial and say
  what is missing; never stitch or mock a step to complete the picture.
- Record against a **seeded, non-production** environment; never film real customer or
  vendor PII.
- Keep all outputs under `knowledge/<flow-slug>/` for easy review.
