# Guided Project Discovery — Reference

Detail for [SKILL.md](SKILL.md). Read the section you need; the main file carries
the operating contract.

## 1. Discovery Ledger Schema

`.discovery/<slug>/DISCOVERY.md`. Frontmatter is required and validated by
[scripts/discovery-validate.sh](scripts/discovery-validate.sh).

```yaml
---
slug: tenant-usage-reporting
created: 2026-07-28T09:00:00Z
updated: 2026-07-29T11:20:00Z
status: interviewing          # interviewing | ready-for-review | in-review | approved | handed-off
mode: research+plan           # research | research+plan | research+plan+execute
lens_cursor: L4               # next lens to ask; makes the run resumable
---
```

Required sections, in order:

| Section | Contents |
|---|---|
| `## Mission` | one paragraph — what the initiative is for, in the user's terms |
| `## Lenses` | table of every lens with status and, when answered, when |
| `## Answers` | one `### <lens id>` block per answered lens |
| `## Assumptions` | unresolved items being carried, each with an owner |
| `## Non-Goals` | what is explicitly excluded |
| `## Evidence` | what was read at Stage 0 and what it pre-filled |
| `## Decision Log` | material choices made during the interview, with rationale |
| `## Handoff` | target mode, candidate digest, spine skill, outstanding gates |

The `## Lenses` table drives resumability:

```markdown
| Lens | Name | Blocking | Status | Answered |
|------|------|----------|--------|----------|
| L1   | Outcome           | yes | answered | 2026-07-28T09:12:00Z |
| L2   | Users and jobs    | yes | answered | 2026-07-28T09:26:00Z |
| L3   | Current reality   | yes | prefilled | 2026-07-28T09:02:00Z |
| L4   | Constraints       | yes | open     | — |
```

Statuses are `open`, `asked`, `answered`, `prefilled`, and `waived`. A `waived`
lens needs a one-line reason in `## Decision Log`. `lens_cursor` must name a lens
that exists in the table, or the literal `done` when the interview is complete;
that invariant is what lets an interrupted session resume without re-asking.

## 2. Lens Bank

Lenses are dimensions, not a script. Pick by expected information gain. Blocking
lenses must be answered, prefilled, or waived before Stage 2 convergence.

| Lens | Blocking | Asks about |
|---|---|---|
| Outcome | yes | what changes in the world when this is done; how success is recognized |
| Users and jobs | yes | who acts, what they are trying to accomplish, how often |
| Current reality | yes | what exists today, what is painful, what is load-bearing |
| Constraints | yes | budget, deadline, stack, compliance, headcount, dependencies |
| Blast radius | yes | production, data, auth, money, external partners, reversibility |
| Success evidence | yes | how the result gets verified, and by whom |
| Non-goals | yes | what must stay out, what behavior must not change |
| Stakeholders | yes | who approves, who is consulted, who is merely informed |
| Alternatives | no | what has been tried, what was rejected and why |
| Timing | no | why now, what happens if it slips |
| Operations | no | who runs it after launch, what breaks at 3am |
| Taste | no | references, examples, counterexamples for subjective calls |

Per-lens question style:

- Ask for a decision, not a description. "What would make you kill this?" beats
  "tell me about your goals".
- Prefer a forced choice when the space is small. "Is this reversible in a day, a
  week, or not at all?"
- Follow a vague answer once, then record the vagueness as an assumption and move
  on. Two follow-ups on the same lens is interview drift.
- When the answer contradicts the repository, surface the contradiction in the
  same turn rather than silently preferring one.

## 3. Mode Contracts

Each mode's obligations at handoff. The review gate in
[review-gate.md](review-gate.md) is mandatory for all three.

### `research`

- Blocking lenses: Outcome, Users and jobs, Current reality, Success evidence.
- Handoff: the approved candidate seeds `project-researcher` Stage 0. Its output
  is `.orchestrator/<slug>/RESEARCH.md`.
- Prohibited: writing a spec, writing product code.

### `research+plan`

- Blocking lenses: all of `research`, plus Constraints, Non-goals, Stakeholders.
- Handoff: `project-researcher`, then `project-orchestrator` Stages 1-2, halting
  at its spec approval gate.
- Prohibited: executing phases. Spec approval approves a plan's content; it does
  not authorize building it.

### `research+plan+execute`

- Blocking lenses: all of `research+plan`, plus Blast radius.
- Handoff: as above, then `project-orchestrator` Stage 3 onward — but only after
  the separate human execution authorization recorded at that skill's Stage 2.
- The discovery ledger's `## Handoff` section must state that execution
  authorization is outstanding until it is actually given.

## 4. Interview Budgets and Stop Conditions

| Budget | Default | On exceed |
|---|---|---|
| lenses asked | 12 | stop, summarize, offer early exit |
| follow-ups per lens | 1 | record an assumption and advance |
| review rounds | 4 | hard stop, escalate to accountable human |
| unreachable-approver rounds | 2 | hard stop, escalate to accountable human |

Hard stops use the
[orchestration-kernel](../orchestration-kernel/SKILL.md#5-hard-stop-format) shape
and are written to `.discovery/<slug>/BLOCKER.md`.

Oscillation detector: if two consecutive lenses produce no change to `## Answers`,
`## Assumptions`, or `## Non-Goals`, the interview is not converging. Stop and
present what is known.

## 5. Validation

```bash
# ledger schema, lens-table invariants, cursor resolvability
bash .cursor/skills/guided-project-discovery/scripts/discovery-validate.sh .discovery/<slug>/DISCOVERY.md

# review round: provenance, dispositions, candidate-bound approvals, execution prohibition
bash .cursor/skills/guided-project-discovery/scripts/review-validate.sh .discovery/<slug>/review/round-<n>.md

# both validators against the bundled samples
bash .cursor/skills/guided-project-discovery/scripts/discovery-validate.sh --selftest
bash .cursor/skills/guided-project-discovery/scripts/review-validate.sh --selftest

# five pilot scenarios, including the two that must fail
bash .cursor/skills/guided-project-discovery/scripts/pilots-run.sh
```

Paths above are the installed layout, which is where the skill runs: Cursor
Cloud's `/` picker is project-scoped and reads `.cursor/skills/` in the repo the
session launched against. Inside the `petralabx/skills` catalog itself the same
scripts live under `skills/guided-project-discovery/scripts/` — substitute that
prefix when validating a change to the skill before publishing it.

Either way the scripts resolve `--selftest` and their bundled samples relative to
the script rather than the working directory, so both layouts work without
arguments.

## 6. Model Roles

Per the [orchestration-kernel](../orchestration-kernel/SKILL.md#1-role-based-model-resolution)
contract, name roles rather than model slugs.

- **deep**: choosing the next lens, detecting contradictions, drafting disposition
  options and their consequences.
- **mechanical**: ledger writes, digest computation, redline extraction, reviewer
  pack assembly.
- **critic**: an independent pass over the frozen candidate for unstated
  assumptions, before reviewer packs go out.

No role may issue a disposition or an approval. Those are human acts.
