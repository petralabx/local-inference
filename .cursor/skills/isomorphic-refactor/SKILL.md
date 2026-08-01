---
name: isomorphic-refactor
description: Preserve behavior while simplifying code. Use when the user asks to simplify, refactor, DRY, reduce duplication, remove boilerplate, collapse helpers, shrink types, or make an isomorphic behavior-preserving cleanup.
---

# Isomorphic Refactor

Use this skill for refactors whose goal is simpler code with the same observable behavior. The rule is:

**Prove behavior is identical, then remove complexity. No proof means no delete and no collapse.**

This skill is global and self-contained. In repositories that also provide `autonomous-verifier`, `safe-deletion`, `dead-code-triage`, or `reliable-tdd-loop`, use those skills for deeper repo-specific checks. If they are unavailable, use the fallback gates below.

## When To Use

- The user says simplify, refactor, DRY, reduce duplication, collapse helpers, remove boilerplate, shrink types, or unify implementations.
- Several functions/components/types appear to do the same job.
- AI-generated code left `_v2`, `_new`, wrapper chains, defensive catch blocks, stale flags, or copy-pasted modules.
- Dead code or unused exports may be removed, but only after proving they are unused.

## When Not To Use

- Performance work: profile first and keep optimization separate.
- Bug fixing: reproduce and fix the bug before refactoring.
- Feature work: implement behavior first, then refactor in a separate pass.
- Broad rewrites, migrations, language ports, or redesigns.

## Mandatory Loop

1. **Baseline**: run or identify current tests, typecheck, lint, and behavior evidence. If commands cannot run, record why.
2. **Map**: find candidate duplication/dead code with reads and searches, not hunches.
3. **Score**: estimate LOC saved, confidence, and risk. Reject weak candidates.
4. **Prove**: fill an isomorphism card before editing.
5. **Edit**: make one conceptual change only. Avoid broad codemods and regex rewrites.
6. **Verify**: rerun equivalent checks and compare behavior evidence.
7. **Ledger**: record accepted and rejected candidates, commands, deltas, and residual risk.

## Candidate Score

Use this lightweight score to decide whether to proceed:

```text
Score = (LOC_saved_points * Confidence) / Risk
Accept only clear wins, normally Score >= 2.0.
```

- `LOC_saved_points`: 1 under 5 LOC, 2 for 5-20, 3 for 20-50, 4 for 50-200, 5 over 200.
- `Confidence`: 1 speculative, 3 scanner plus local tests, 5 golden output or strong characterization coverage.
- `Risk`: 1 same pure function/file, 3 module boundary, 5 async/error/security/ordering/observable side effects.

Low-score candidates go in `candidate-ledger.md` as rejected or deferred. Do not force them.

## Isomorphism Card

Before editing, create or fill `isomorphism-card.md` with:

- Inputs and callers covered.
- Ordering, tie-breaking, laziness, and short-circuit behavior.
- Error semantics and thrown/returned types.
- Side effects: logs, metrics, DB writes, network calls, emitted events.
- Type narrowing, render behavior, cache keys, and serialization behavior where relevant.
- Verification commands to run before and after.

If a row cannot be answered, stop and read more code or add a characterization test.

## Fallback Safety Gates

Use these when project-specific skills are unavailable.

### Verification Fallback

- Capture baseline test/lint/typecheck status before editing.
- Prefer focused tests for touched behavior plus one broader smoke check.
- If no tests exist, create or identify a characterization test before high-risk refactors.
- Never silently re-baseline golden outputs. If behavior changes intentionally, this is no longer an isomorphic refactor.

### Safe Deletion Fallback

- Do not delete files without explicit user approval.
- Before removing a symbol/file, search for direct references, dynamic imports, string/config references, docs, tests, and barrel re-exports.
- Treat framework entry points, route handlers, generated registries, migrations, hooks, and config-named symbols as live until proven otherwise.
- If evidence is inconclusive, mark the candidate deferred.

### Dead Code Fallback

Classify every removal candidate:

- `true_positive`: no direct, dynamic, config, test, or documentation references and no public API surface.
- `false_positive`: referenced indirectly, by framework convention, through strings/config, or through barrel exports.
- `deferred`: ownership, branch age, runtime registration, or external consumers are unclear.

Only `true_positive` candidates may proceed, and file deletion still needs user approval.

### TDD Fallback

If equivalence is uncertain, add or locate a failing/characterizing test first. The test must fail or demonstrate current behavior before the refactor, then pass after the refactor.

## Refactor Levers

Pick exactly one lever per change:

- `extract`: move duplicated body into a helper.
- `parameterize`: replace literal differences with parameters.
- `dispatch`: use a small table or discriminant for bounded variation.
- `eliminate`: remove pass-through wrappers that add no behavior.
- `type-shrink`: replace broad types with narrower ones after callsite census.
- `dead-code`: remove proven-unused code with deletion gates.
- `merge-files`: merge `_v2` or `_new` variants only after choosing the canonical implementation.

Do not mix cleanup, renames, behavior fixes, formatting churn, and dependency changes into the same refactor.

## Output Contract

For meaningful refactors, leave these artifacts in the repo or summarize them in the final response:

- Completed isomorphism card.
- Candidate ledger with accepted, rejected, and deferred items.
- Verification commands and outcomes.
- LOC or complexity delta when available.
- Residual risks and rollback notes.

Use `candidate-ledger.md`, `isomorphism-card.md`, and `closeout-template.md` as copy-ready templates.
