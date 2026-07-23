---
name: taste-skill
description: Senior UI/UX engineering taste guard. Use when designing or reviewing frontend surfaces, correcting default LLM visual bias, enforcing component architecture, responsive layout, motion discipline, and premium design execution.
---
# Taste Skill

Use this skill for frontend/UI work that needs strong design taste, not generic LLM defaults. It sets a high-agency baseline for visual quality while still adapting to explicit user direction.

## Baseline Variables

Default unless the user asks otherwise:

- `DESIGN_VARIANCE = 8` where 1 is perfect symmetry and 10 is artsy chaos.
- `MOTION_INTENSITY = 6` where 1 is static and 10 is cinematic.
- `VISUAL_DENSITY = 4` where 1 is airy gallery and 10 is dense cockpit.

Use these as design drivers, not rigid user-facing jargon.

## Architecture Rules

- Verify dependencies in `package.json` before importing third-party libraries.
- Default to React/Next.js conventions when stack is unspecified.
- In Next.js, keep Server Components static; isolate interactive or animated pieces into leaf Client Components with `'use client'`.
- Use local state for isolated UI and global state only when it removes meaningful prop drilling.
- Check Tailwind version before using version-specific syntax.
- Do not use emoji in code, markup, text content, or alt text; prefer real icons or SVG primitives.
- Use CSS Grid for layout structure; avoid fragile flex percentage math.
- Avoid `h-screen` for full-height mobile hero sections; use dynamic viewport-safe alternatives.

## Bias-Correction Rules

LLMs tend toward centered heroes, purple-blue gradients, generic cards, and static success states. Correct those defaults proactively:

- **Typography**: use deliberate display/body hierarchy. Avoid default Inter for premium or creative work unless the product already standardizes it.
- **Color**: use one coherent palette and one accent color. Avoid the generic AI purple/blue glow aesthetic unless explicitly requested.
- **Layout**: for higher variance, avoid centered hero/H1 blocks. Prefer split-screen, left-aligned, asymmetric, or editorial layouts.
- **Cards**: use cards only when elevation communicates hierarchy. For dense dashboards, prefer borders, dividers, grouping, and whitespace.
- **States**: include loading, empty, error, hover, focus, active, disabled, and success states when the UI is interactive.

## Motion Rules

Use motion to clarify state or create delight, not to decorate everything.

- Animate transform and opacity first.
- Keep durations consistent and responsive.
- Use stagger sparingly.
- Respect reduced-motion preferences.
- Avoid layout-shifting animation on load.
- Heavy animation belongs in isolated Client Components.

## Responsive Rules

- Design mobile, tablet, and desktop consciously.
- Use standard breakpoints and avoid one-off pixel math.
- Keep touch targets comfortable.
- Prevent overflow in long labels, tables, cards, and nav.
- Prefer container width constraints like `max-w-7xl` or project-local equivalents.

## Review Checklist

Before calling UI work done, check:

- Does the page avoid generic AI visual patterns?
- Is the layout intentional at mobile/tablet/desktop sizes?
- Are interactive states complete?
- Are dependencies verified?
- Are Client Components limited to interactive leaves?
- Is motion purposeful and accessible?
- Does color come from the app's design system or a consistent local palette?
- Are icons, copy, and spacing aligned with product tone?

## When To Defer To Local Rules

If the repo has a design system, tokens, component library, or UI playbook, follow it first. Use this skill to improve taste within those constraints, not to override product standards.

For VMC surfaces specifically, pair this with `ui-ux-design-loop` and the VMC token rules.
