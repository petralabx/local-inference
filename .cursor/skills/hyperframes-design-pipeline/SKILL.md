---
name: hyperframes-design-pipeline
description: Create, ingest, polish, validate, and render HyperFrames motion-design prototypes. Use when the user mentions HyperFrames, Claude Design, animated UI concepts, motion studies, product launch videos, design ideation ZIPs, UI/UX walkthroughs, or converting visual ideas into Cursor-polished HTML/CSS/GSAP compositions.
---

# HyperFrames Design Pipeline

## When To Use

Use this skill for motion-first design artifacts:

- HyperFrames compositions, videos, launch teasers, social reels, UI walkthroughs, motion studies, animated design prototypes.
- Claude Design handoffs, especially ZIPs containing `index.html`, `preview.html`, `README.md`, `DESIGN.md`, and assets.
- Cursor-only generation of a first draft when the user wants to skip Claude Design.
- Polishing animation timing, scene visibility, shader transitions, pacing, typography, and readability.

Do not use HyperFrames as the production app framework. For real app UI, treat the composition as a reference and implement production code in the host app's normal stack.

## Operating Modes

### 1. Claude Design Handoff

When the user has or wants a Claude Design draft:

1. Ask Claude Design to produce a ZIP with `index.html`, `preview.html`, `README.md`, `DESIGN.md`, and local assets.
2. In Cursor, unpack or inspect the uploaded draft.
3. Verify it is plain HTML + CSS + GSAP, not React/Babel.
4. Run validation and preview commands from the project folder:

```bash
npx hyperframes doctor
npx hyperframes lint
npx hyperframes preview
```

5. Polish only after lint passes or after structural errors are fixed.
6. Render only after preview has been checked:

```bash
npx hyperframes render index.html -o output.mp4
```

### 2. Cursor-Only Draft

When creating the composition entirely in Cursor:

1. Gather subject, audience, aspect ratio, duration, brand/source direction, and target use.
2. If the brief is sparse and lacks attachments, brand direction, style, or "surprise me", ask one concrete clarifying question.
3. Create a self-contained HyperFrames folder with:
   - `index.html`
   - `preview.html`
   - `README.md`
   - `DESIGN.md`
   - optional `assets/`
4. Choose the smallest scene count that tells the story.
5. Validate with lint, preview, then render if requested.

### 3. Portal/UI Translation

When the output should influence a production app:

1. Keep HyperFrames files as design artifacts unless the user asks to integrate.
2. Extract reusable decisions: layout hierarchy, type scale, color tokens, transition timing, empty/loading states, chart motion, microinteractions.
3. Rebuild production UI in the repo's native framework and components.
4. Do not import HyperFrames runtime into the app unless explicitly requested and reviewed as a product feature.

## Composition Rules

Follow these invariants:

- Plain HTML, CSS, and GSAP only.
- No React, JSX, Babel, `setTimeout`, `setInterval`, `requestAnimationFrame`, unseeded `Math.random()`, `Date.now()`, or `repeat: -1`.
- Every scene uses `class="scene clip"` and has required `data-*` attributes.
- Every scene contains a `.scene-content` wrapper.
- Non-anchor scenes use explicit `tl.set(..., { autoAlpha: 1 })` and `tl.set(..., { autoAlpha: 0 })` toggles.
- Shader anchor scenes use `style="opacity:0;"`; non-anchor scenes use `style="visibility:hidden;"`.
- The first anchor scene in each shader group is explicitly shown with `tl.set("#sN", { opacity: 1 }, startTime)`.
- Scene windows tile end-to-end with no gaps.
- Most cuts are hard cuts. Use shader transitions only for hero reveals, energy shifts, or CTA landings.
- Do not use exit tweens before shader transitions. The shader is the exit.
- Use real assets or local placeholders clearly marked as placeholders. Do not use remote placeholder image services.

## Design Rules

- Mine attachments and screenshots first for palette, typography, tone, spacing, and product language.
- Avoid generic LLM visual defaults: Inter, Roboto, Poppins, cyan-on-black, equal-weight centered cards, generic gradient text.
- Use dramatic type weight contrast and readable sizes: large headlines, body text at video-safe sizes, tabular numerals for stats.
- Every scene needs visible content, entrance motion, and at least one mid-scene activity: counter, bar fill, SVG draw, float, glow pulse, Ken Burns zoom, highlight sweep, or character stagger.
- Keep text readable within the scene duration. Split long paragraphs into multiple scenes.

## Verification Checklist

Before saying the work is complete:

- `npx hyperframes lint` passes or failures are reported with exact blockers.
- Preview plays start to finish.
- All scenes are visible.
- Shader transitions do not blink.
- Text is readable.
- No scene is static.
- Render succeeds if the user requested an MP4.
- For repo integration, run the repo's normal lint/test/build checks for any production files changed.

## Useful Prompts

For reusable handoff and generation prompts, read [PROMPTS.md](PROMPTS.md).
