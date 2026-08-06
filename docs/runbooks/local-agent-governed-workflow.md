# Local agent governed workflow

**Owner:** Vince  
**Agent operator:** `cos@petrasoap.com`  
**Repository:** `petralabx/local-inference`

This repository uses direct feature-branch development. The former
`taylorvalton/local-inference-dev` repository is legacy; it is not an active
promotion source.

## Security contract

| Attribute | Contract |
|---|---|
| Scope | Operator-local Hermes/Claude agent working only in `petralabx/local-inference` |
| Auth source | Dedicated runtime key supplied as `MC_MCP_API_KEY` with its reviewed `MC_MCP_PRINCIPAL_ID` in `~/.hermes/.env`; Hermes uses `sp_mcp_hermes`; GitHub credential managed outside Git |
| Default state | Local MC and remote writes unavailable until the operator provisions credentials and permissions |
| Kill switch | Remove the MC key and the Claude permission entries; revoke the local GitHub credential |
| Health check | `bash scripts/local-agent-preflight.sh --online` |
| Fallback | Keep the local agent read/prepare-only and dispatch a Cursor Cloud agent |
| Audit boundary | MC records checkout/evidence; GitHub records branch pushes, PRs, reviews, and checks |

Never commit, print, paste, or send credential values to an agent conversation.
The MC key is not the VMC key.

## 1. Structural check before provisioning

From the canonical checkout:

```bash
bash scripts/local-agent-preflight.sh --offline
```

This checks tools, repository identity, and branch posture without calling MC
or GitHub write endpoints.

## 2. Provision the narrow MC identity

Add these names to `~/.hermes/.env`; substitute the dedicated
`sp_mcp_hermes` key value locally:

```dotenv
MC_MCP_API_KEY=<operator-provisioned-value>
MC_MCP_PRINCIPAL_ID=sp_mcp_hermes
MC_OPERATOR_EMAIL=cos@petrasoap.com
MC_REPO=petralabx/local-inference
MC_RUNTIME=local
```

Restrict the file to the local user where the operating system supports it
(`chmod 600 ~/.hermes/.env` on Unix-like systems). Do not provision broad AWS
credentials or the legacy shared `sp_mcp_cursor` key for this workflow.

Hermes loads its own environment file. Plain Claude Code does not; launch it
from an operator-controlled shell that has exported these variables without
printing them.

## 3. Configure scoped Claude Code permissions

Put local policy in `~/.claude/settings.json`, not in the repository. Merge the
following entries with existing settings. Privileged operations remain
one-click confirmations because repository scripts are writable development
artifacts; silently allowlisting them would let a modified script inherit the
same credentials. A `deny` rule at any scope overrides an `ask` or `allow`
rule.

```json
{
  "permissions": {
    "allow": [
      "Bash(bash scripts/local-agent-preflight.sh --offline)"
    ],
    "ask": [
      "Bash(bash scripts/local-agent-preflight.sh --online)",
      "Bash(bash scripts/mc-checkout-local-inference.sh TASK-*)",
      "Bash(bash scripts/push-agent-branch.sh)",
      "Bash(gh pr create --repo petralabx/local-inference *)",
      "Bash(node scripts/compliance-pr-verify.mjs --wait)"
    ]
  }
}
```

Do not add generic `git *`, `git push *`, `gh api *`, or Run Everything
allow rules. Remove any existing broad allow that would bypass these prompts;
command-pattern permissions are workflow friction, not a security sandbox.
The argument-free push wrapper accepts only a clean `cursor/*` branch, runs the
repository validation commands, requires exact canonical fetch and push URLs,
and refuses to run if its content differs from `origin/main`.

The wrapper becomes usable after the PR that introduces it merges to `main`.
That bootstrap PR must be pushed by the existing Cursor Cloud delivery path or
an operator-reviewed manual command.

## 4. Validate and start governed work

```bash
git checkout -b cursor/<descriptive-name>
bash scripts/local-agent-preflight.sh --online
bash scripts/mc-checkout-local-inference.sh --self-check
bash scripts/mc-checkout-local-inference.sh TASK-NNN
```

Use a real assigned task. Never use a fabricated test task. Confirm that the
checkout output reports `actorRepo` as `petralabx/local-inference`, then copy
the returned `MC-Checkout: dsp_…` line unchanged into the PR body.

After implementation:

```bash
bash scripts/push-agent-branch.sh
gh pr create --repo petralabx/local-inference --base main \
  --head cursor/<descriptive-name> --title "<title>" --body-file "<body-file>"
```

The PR body must include the task ID, exact checkout stamp, test evidence, an
accountable human, and `## Rollback Plan`. Complete MC evidence only after the
last push; a later push requires a fresh checkout stamp. Then run:

```bash
node scripts/compliance-pr-verify.mjs --wait
```

Only an exit-zero compliance verifier and successful GitHub checks establish
readiness.

## Legacy repository deprecation

Do not delete the old repository. Deprecate it in this order:

1. Freeze new branches and merges in `taylorvalton/local-inference-dev`.
2. Inventory open PRs, non-default branches, releases, deploy keys, and unique
   tracked files. Compare files, not commit ancestry; the histories are
   unrelated.
3. Copy any approved unique files into a canonical feature branch and review
   them through the normal MC-gated PR flow.
4. Repoint operator checkouts and automation to
   `petralabx/local-inference`; verify no active job still references the old
   remote.
5. Revoke the old write deploy key, add an archive notice that points to the
   canonical repository, and archive the GitHub repository read-only.
6. Preserve the archived repository for history and rollback evidence.

The archive step remains blocked until an authenticated operator audits the old
private repository and records the result in Mission Control.
