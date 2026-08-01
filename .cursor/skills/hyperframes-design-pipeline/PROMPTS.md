# HyperFrames Prompt Pack

## Claude Design First Draft

```text
Use the HyperFrames template-first workflow. Create a valid HyperFrames project, not React. Use plain HTML, CSS, and GSAP only.

Deliver a ZIP with index.html, preview.html, README.md, DESIGN.md, and any assets.

The draft must pass npx hyperframes lint structurally. Use scene-content wrappers, deterministic GSAP timeline animation, no React/Babel, no Math.random, no setTimeout/setInterval, and mostly hard cuts with only 2-3 shader transitions.

This is a first-cut design artifact for Cursor/Claude Code to polish.

Brief:
- Subject:
- Audience:
- Aspect ratio:
- Duration:
- Brand/source direction:
- Required scenes:
- Must avoid:
```

## Cursor Polish Request

```text
Use the hyperframes-design-pipeline skill. Ingest this HyperFrames draft, run doctor/lint/preview, fix structural issues, then polish animation timing, scene visibility, shader transitions, pacing, readability, typography, and mid-scene motion. Render an MP4 if validation passes.
```

## Cursor-Only Build Request

```text
Use the hyperframes-design-pipeline skill. Build a complete HyperFrames project in Cursor from this brief. Create index.html, preview.html, README.md, DESIGN.md, and any needed assets. Validate with npx hyperframes lint, preview the result, polish it, and render output.mp4 if requested.

Brief:
- Subject:
- Audience:
- Aspect ratio:
- Duration:
- Brand/source direction:
- Required scenes:
- Must avoid:
```

## PLX Launch Teaser Example

```text
Use the hyperframes-design-pipeline skill. Create a 25-second 16:9 HyperFrames launch teaser for the PLX Customer Portal document workflow: secure login, document upload, SharePoint storage, DocuSign signature, admin approval, and customer completion. Make it feel premium, operational, and manufacturing-specific rather than generic SaaS. Use mostly hard cuts with two shader transitions.
```

## PLX UI Motion Study Example

```text
Use the hyperframes-design-pipeline skill. Create a HyperFrames motion study for a premium manufacturing dashboard hero. Focus on card entrance timing, stat counters, status badges, approval workflow motion, and a calm industrial visual system. This is a design reference only, not production React code.
```
