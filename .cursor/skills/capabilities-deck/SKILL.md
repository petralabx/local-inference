---
name: capabilities-deck
description: >-
  Build a confidential, multi-concept "capabilities deck" / product-innovation
  pitch microsite for a brand (the PAUME pattern) using the typed microsite
  engine. Use when asked to build a capabilities deck, an innovation /
  diversification pitch, a multi-concept product proposal microsite, or "a
  PAUME-style microsite" for a customer, and to publish it to staging.
---

# Capabilities Deck

A confidential, public (`noindex`) **multi-section pitch microsite** built on the
typed microsite engine. Lives at `/<slug>` on **staging only**.

Use this for a **multi-concept pitch** (opportunity → concepts → why-us →
capability → diversification → commercial → pricing → begin → close). For a
**single-product sample / reformulation update**, use
[sample-feedback-deck](../sample-feedback-deck/SKILL.md) instead.

## Engine (data-only + thin route)

Adding a brand microsite is a **data change plus a thin route folder** — the
renderer is shared. Canonical engine: **`portal/src/lib/microsites/`** and
**`portal/src/components/microsite/`**.

- `schema.ts` — the `MicrositeSpec` Zod contract. Sections: `hero`,
  `opportunity`, `capability`, `why`, `trinity`, `concepts[]`,
  `diversification`, `commercial`, `pricing`, `begin`, `close`, `contact`. Rich
  headings are arrays of `{ text, em? }` segments (real JSX, not HTML strings).
- `data/paume.ts` — the worked example to copy.
- `registry.ts` — slug → spec map.
- `components/microsite/microsite.tsx` — renders any spec.

## Inputs (gather first)

- Brand name + slug (`/<slug>`, kebab-case)
- Pitch content for each `MicrositeSpec` section: opportunity moments, the
  concepts / "trinity", why-us cells + certs, capability bars, diversification
  benefits, the commercial table, pricing tiers, begin steps, and close + contact
- Imagery: an `og.png` plus one image per concept
- Delivery: confirm the operator wants the PDF export + email (default recipient
  **vince@petrasoap.com**)

## Workflow

```
- [ ] 1. Worktree off staging + bootstrap
- [ ] 2. Author data/<slug>.ts (MicrositeSpec)
- [ ] 3. Register the slug
- [ ] 4. Add the route + make it public (noindex)
- [ ] 5. Add imagery
- [ ] 6. Harden + validate
- [ ] 7. Publish to staging + verify live
- [ ] 8. Export a print-clean PDF
- [ ] 9. Email the PDF to the operator (vince@petrasoap.com)
```

1. **Worktree + bootstrap** — off `staging`; run
   `scripts/bootstrap-worktree.ps1` (see `.cursor/rules/worktree-bootstrap.mdc`).
2. **Author the spec** — `portal/src/lib/microsites/data/<slug>.ts`, copying the
   shape of `data/paume.ts`; satisfy **every** required field in `schema.ts`.
   Source real content from the operator / their brief; don't invent
   pricing or claims.
3. **Register** — add `[<slug>.slug]: <slug>` to the map in
   `portal/src/lib/microsites/registry.ts`.
4. **Route** — copy `portal/src/app/paume/page.tsx` to
   `portal/src/app/<slug>/page.tsx` (set `SLUG`); add `"/<slug>"` to
   `PUBLIC_ROUTES` in `portal/src/middleware.ts`. Keep `confidential: true`
   (→ `noindex`).
5. **Imagery** — add `portal/public/microsites/<slug>/og.png` and one
   `concept-*.png` per concept (paths are referenced from the spec).
6. **Harden + validate** — run the **ui-ux-design-loop** skill's gate pack (axe
   clean in both light and dark); then
   `cd portal && npm run typecheck && npm run lint && npm run build`
   (prefix `NODE_OPTIONS=--max-old-space-size=8192` if the webpack build OOMs).
7. **Publish** — commit, open a PR against `staging`, and babysit it to green +
   merge (the **babysit** skill); the merge auto-deploys to
   `https://staging.plxcustomer.io/<slug>`. Confirm the live URL returns 200.
8. **PDF export** — produce a **print-clean** PDF (see "PDF export" below). Never
   ship the naive full-page render of the live microsite — its grids fragment.
9. **Email** — send the PDF to the operator via Resend (see "Email delivery").

## PDF export

The microsite is a scroll-designed web layout; a naive `page.pdf()` of the live
URL paginates badly (grey voids, collapsed columns, half-cut images). Generate a
**print-clean** PDF with a print stylesheet that reflows the layout, and only
after the fonts and images have loaded.

**Reformatting rules (the failure modes we hit, and the fixes):**

- **Hairline grids fragment.** The engine's grids use a grey container background
  with `gap: 1px` as faux hairlines. Under pagination CSS grid collapses to one
  column and leaves large grey voids. **Fix:** in `@media print`, convert
  `.tcards / .whygrid / .steps / .pack-grid / .split` to
  `display: flex` with `background: transparent; border: 0`, and give each child
  `flex: 1 1 0` plus its own `1px solid var(--p-grid)` border.
- **Fixed heights strand whitespace.** `min-height` on cards/`.heroing` and the
  sticky concept visual leave empty space when a block moves to the next page.
  **Fix:** `min-height: 0 !important` and drop `position: sticky` in print.
- **Orphaned headers / split cards.** Glue each section header to its grid with
  `.sec-head { break-after: avoid }` + grid `{ break-before: avoid }`, and protect
  atomic blocks with `break-inside: avoid` on every card, `.heroing`, and
  `.claims li`. Do **not** put `break-inside: avoid` on whole `section`s — tall
  sections then force a page each and strand huge blank space.
- **Compact scale.** Shrink the print type scale + section padding (e.g.
  `--w-sec`, `--w-display`, `--w-body`, `--w-pad`) and hide screen-only chrome
  (`.sitebar`, `.scrollcue`, `.ghostmark`, `.grid-lines`). Target ≈ letter,
  `@page { margin: 11mm 10mm; size: letter }`.
- **Uniform imagery.** Concept/packaging source images have mixed aspect ratios;
  use `object-fit: cover` with a fixed thumb height so all tiles read uniform
  rather than `contain` (which leaves inconsistent bars).
- **Render discipline (Playwright/Chromium):** reveal animated blocks
  (`.rv → .in`), expand any animated bars/rail to their `--to` width, `await
  document.fonts.ready`, and wait until every `<img>` is `complete &&
  naturalWidth > 0` before `page.pdf({ printBackground: true,
  preferCSSPageSize: true })`. Verify by rasterizing pages (`pdftoppm`) and
  eyeballing every page — do not trust page count alone.

**Responsiveness requirement:** all print/reformatting rules live inside
`@media print` (and normal responsive breakpoints stay intact). The screen
microsite must remain fully responsive — never let a print override leak into
the on-screen layout, and re-check the live route at mobile/tablet/desktop after
touching shared CSS.

## Email delivery

Attach the PDF and send via Resend (`RESEND_API_KEY` is in the environment).
Default recipient **vince@petrasoap.com**; sender `onboarding@resend.dev` (custom
domain not verified). Subject names the brand + "Product Brief (PDF)"; body
includes the confidential staging link. Confirm the API returns an `id`. If you
re-send a corrected file, say so in the body so the prior attachment is discarded.

## Done

- `data/<slug>.ts` validates against `schema.ts`; registered; route + middleware
  wired; imagery present
- axe WCAG A/AA clean both themes; typecheck + lint + build pass
- Live at `staging.plxcustomer.io/<slug>`
- Print-clean PDF exported (every page verified — no grey voids, collapsed
  columns, or cut-off sections/images) and emailed to the operator

## Notes

- **Staging only** (`.cursor/rules/staging-environment.mdc`). Production needs
  explicit operator approval.
- The engine renders structured segments — never `dangerouslySetInnerHTML`.
- Keep it confidential until the operator approves sharing the link.
