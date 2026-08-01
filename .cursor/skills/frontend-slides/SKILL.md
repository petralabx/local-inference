---
name: frontend-slides
description: Create animation-rich HTML presentations from scratch or by converting PowerPoint files. Use when the user wants to build a presentation, convert a PPT/PPTX to web, or create slides for a talk/pitch. Helps non-designers discover their aesthetic through visual exploration rather than abstract choices.
---

# Frontend Slides Skill

Create zero-dependency, animation-rich HTML presentations that run entirely in the browser. Use this skill for new decks, PPT/PPTX conversion, or polishing an existing HTML presentation.

## Core Principles

1. **Zero dependencies**: prefer a single HTML file with inline CSS/JS unless assets are required.
2. **Show, do not tell**: generate visual previews so the user can react to real styles.
3. **Distinctive design**: avoid generic purple gradients, default system fonts, standard blue primaries, and predictable hero layouts.
4. **Production quality**: write accessible, responsive, commented, performant HTML/CSS/JS.

## Phase 0: Detect Mode

Classify the request first:

- **New presentation**: user wants slides from scratch. Run content discovery, style discovery, then generate the deck.
- **PPT conversion**: user provides `.ppt` or `.pptx`. Extract content and assets, confirm structure, then generate HTML.
- **Existing HTML enhancement**: read the existing presentation, preserve working structure, and improve design/interaction.

## Phase 1: Content Discovery

Ask only for missing essentials:

- Purpose: pitch deck, tutorial, conference talk, internal update, or other.
- Approximate length: short, medium, or long.
- Content state: ready content, rough notes, or topic only.
- Audience and tone: who is watching, what should they feel, and what action should they take.

If the user has content, ask them to provide the text, bullet points, images, or file paths. If they only have a topic, draft a concise outline before designing.

## Phase 2: Visual Exploration

Most users cannot describe design preferences abstractly. Generate 3 distinct mini previews before building the full deck.

Each preview should be a self-contained title slide showing:

- Typography and hierarchy.
- Color palette.
- Motion style.
- Overall aesthetic feel.

Use `STYLE_PRESETS.md` for preset ideas, font pairings, palettes, and signature motion patterns. Choose presets based on the desired feeling:

- Impressed/confident: executive, elegant, restrained.
- Excited/energized: kinetic, cyber, bold gradients.
- Calm/focused: paper, editorial, muted, minimal.
- Inspired/moved: cinematic, atmospheric, story-driven.

Write previews under `.claude-design/slide-previews/`:

```text
.claude-design/slide-previews/
├── style-a.html
├── style-b.html
├── style-c.html
└── assets/
```

Then ask the user which style resonates, what they like, and what they would change. If they want a blend, capture exactly which elements to mix.

## Phase 3: Generate The Presentation

Build the full deck from the approved style and content.

For a single self-contained deck:

```text
presentation.html
assets/
```

For multiple decks:

```text
<presentation-name>.html
<presentation-name>-assets/
```

Use semantic slide sections:

```html
<section class="slide title-slide">
  <h1 class="reveal">Presentation Title</h1>
  <p class="reveal">Subtitle or author</p>
</section>
```

Every deck should include:

- Keyboard navigation with arrows and space.
- Touch/swipe support when practical.
- Progress indicator or navigation dots for medium/long decks.
- Intersection Observer or equivalent for reveal animations.
- Responsive layout for mobile and tablet.
- Reduced-motion support.

## HTML/CSS/JS Requirements

Use CSS custom properties at the top for easy theme changes:

```css
:root {
  --bg-primary: #0a0f1c;
  --text-primary: #ffffff;
  --text-secondary: #9ca3af;
  --accent: #00ffcc;
  --font-display: 'Clash Display', sans-serif;
  --font-body: 'Satoshi', sans-serif;
}
```

Accessibility requirements:

- Use semantic HTML: `section`, `nav`, `main` where appropriate.
- Ensure keyboard navigation works.
- Add ARIA labels where controls need them.
- Support `prefers-reduced-motion`.
- Avoid relying only on color to convey meaning.

Performance requirements:

- Prefer `transform` and `opacity` for animation.
- Disable heavy effects on small screens.
- Throttle mousemove/scroll handlers if used.
- Use `will-change` sparingly.

Code quality requirements:

- Comment major sections so the user can customize the file later.
- Keep effects understandable rather than clever.
- Keep all required assets local and referenced by relative path.

## Phase 4: PPT/PPTX Conversion

When converting PowerPoint files:

1. Extract slide text, titles, notes, and images using `python-pptx` when available.
2. Save extracted images into an `assets/` folder.
3. Present an extraction summary by slide and ask the user to confirm it looks right.
4. Run visual exploration unless the user explicitly wants a direct conversion.
5. Generate HTML preserving slide order, text, images, and useful speaker notes.

If extraction tooling is unavailable, stop and report the missing dependency instead of fabricating slide contents.

## Phase 5: Delivery

Before final response:

- Open or smoke-check the generated HTML when practical.
- Verify navigation and at least one reveal animation.
- Check mobile responsiveness at a narrow viewport when practical.
- Remove temporary previews if the final deck is complete.

Final response should include:

- Output file path.
- Style selected.
- Slide count.
- Navigation instructions.
- Any verification performed or skipped.

## Troubleshooting

- Fonts not loading: verify external font URLs and font-family names.
- Animations not triggering: confirm the observer adds the visible class.
- Scroll snap not working: check `scroll-snap-type` and slide alignment.
- Mobile issues: reduce canvas/particle effects and simplify layout.
- Performance issues: reduce particle counts and animate only transform/opacity.

## Related Reference

- `STYLE_PRESETS.md`: visual presets, color palettes, typography, and animation patterns.
