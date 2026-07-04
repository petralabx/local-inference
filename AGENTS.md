# AGENTS.md — Local Inference

Platform repo under PLX MC governance. Link work to MC tasks (`MC-Checkout`).

## Repo Topology (dev -> promote)

Two remotes carry this codebase with unrelated git histories:

- Dev / working repo: `taylorvalton/local-inference` — day-to-day changes land here first.
- Canonical / PLX org repo: [petralabx/local-inference](https://github.com/petralabx/local-inference) —
  the MC-registered source of truth. Receives promotion PRs from the dev repo.

### Promotion workflow

1. Develop and merge changes on `taylorvalton/local-inference` `main`.
2. When stable, copy the changed tracked files into the PLX checkout
   (histories are unrelated — promote by file copy, not by merging branches).
3. Open a `feat/promote-*` PR on `petralabx/local-inference`, referencing the
   dev-repo commits it promotes.
4. After merge, verify both repos' `main` trees match for the promoted paths.

### Rules

- Do not merge or rebase across the two remotes; they have unrelated roots.
- Secrets (`.env.local`) stay untracked in both repos.
- `.orchestrator/` evidence is promoted intentionally, not by default.
