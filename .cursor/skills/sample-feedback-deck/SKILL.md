---
name: sample-feedback-deck
description: >-
  Build a confidential, customer-facing "sample feedback" deck (the SoapBox
  pattern): a single-product scroll-snap microsite that explains a formulation /
  sample reformulation update and asks the customer which version to move forward
  with. Use when asked to build a sample-feedback page, a reformulation / R&D
  sample update for a customer or brand, "a SoapBox-style deck", or to turn a
  technical-overview document into a polished client page, and to publish it to
  staging.
---

# Sample Feedback Deck

A confidential, public (`noindex`) scroll-snap deck that turns a **single-product
sample / reformulation update** into a polished client story with a clear
"pick a direction" ask. Lives at `/<slug>` on **staging only**.

Use this for a **single-product narrative** (problems → changes → proof → CTA).
For a **multi-concept innovation pitch**, use
[capabilities-deck](../capabilities-deck/SKILL.md) instead.

## Template (copy, don't reinvent)

Canonical example: **`portal/src/app/soapbox/`**

- `page.tsx` — server route + metadata (`robots: { index:false, follow:false }`)
- `soapbox-deck.tsx` — `"use client"` deck: slides + scroll-spy rail, progress
  bar, keyboard nav, light/dark toggle, reveal-on-enter, reduced-motion + no-JS
  fallbacks
- `soapbox.css` — scoped `.sbx-deck` chassis (PLX paper palette; Mazius + Inter +
  JetBrains Mono). The chassis is the reusable part; **only the slide content
  changes per customer.**

## Inputs (gather first)

- Customer / brand name and a slug (`/<slug>`, kebab-case)
- Source document(s) — usually a technical-overview PDF in SharePoint
- The narrative: the brief / problems addressed, a before→after comparison
  (e.g. Previous vs. V4 vs. V5), the rationale per change, the validation result
  (consumer panel / blind test), and the closing CTA
- Any verbatim copy the operator supplies — use it **verbatim**

## Deck structure (6 slides)

1. **Cover** — brand, title, version(s), prepared-for, issued, status
2. **The brief** — the problem(s) the update solves (2–3 cards)
3. **Comparison** — before vs. each new version (line-by-line table)
4. **Rationale** — what each change does and why (cards)
5. **Validation** — the headline result (panel / blind test) + claim pills
6. **Close** — headline + CTA inviting the customer to choose a direction

## Workflow

```
- [ ] 1. Worktree off staging + bootstrap
- [ ] 2. Ingest the source document
- [ ] 3. Scaffold the route from the soapbox template
- [ ] 4. Make it public (noindex) in middleware
- [ ] 5. Harden (UI/UX gate pack)
- [ ] 6. Validate (typecheck / lint / build)
- [ ] 7. Publish to staging + verify live
```

1. **Worktree + bootstrap** — new worktree off `staging`; run
   `scripts/bootstrap-worktree.ps1` (see `.cursor/rules/worktree-bootstrap.mdc`).
2. **Ingest** — pull the source from SharePoint with app-only Microsoft Graph
   (see `.cursor/rules/credentials-and-access.mdc`; resolve a `:f:` share link via
   `GET /shares/{token}/driveItem`, where `token = "u!" + base64url(url)`). Read
   the PDF for the real numbers — **never fabricate formula / spec / validation
   figures.**
3. **Scaffold** — copy `portal/src/app/soapbox/` to `portal/src/app/<slug>/`,
   rename the component, and replace the six slides' content. Reuse the
   `.sbx-deck` chassis (import or copy `soapbox.css`). Escape apostrophes
   (`&apos;`) for the linter.
4. **Public route** — add `"/<slug>"` to `PUBLIC_ROUTES` in
   `portal/src/middleware.ts`; keep `robots: { index:false, follow:false }`.
5. **Harden** — run the **ui-ux-design-loop** skill's gate pack (G1 tokens, G2
   wiring, G3 responsive, G4 axe) against the local preview; axe must be clean in
   **both** light and dark.
6. **Validate** — `cd portal && npm run typecheck && npm run lint`, then
   `npm run build` (prefix `NODE_OPTIONS=--max-old-space-size=8192` if the webpack
   build OOMs locally).
7. **Publish** — commit, open a PR against `staging`, and babysit it to green +
   merge (the **babysit** skill); the merge auto-deploys to
   `https://staging.plxcustomer.io/<slug>`. Confirm the live URL returns 200.

## Done

- `/<slug>` is public, `noindex`, renders all six slides in light + dark
- axe WCAG A/AA clean both themes; typecheck + lint + build pass
- Live at `staging.plxcustomer.io/<slug>`; content matches the source (no
  fabricated figures)

## Notes

- **Staging only** (`.cursor/rules/staging-environment.mdc`). Production
  (`www.plxcustomer.io`) needs explicit operator approval.
- Keep it confidential until the operator approves sharing the link.
- If many sample-feedback decks accrue, consider extracting the `.sbx-deck`
  chassis (CSS + interactivity) into a shared component that takes the slides as
  content — the per-customer work is the content, not the chassis.
