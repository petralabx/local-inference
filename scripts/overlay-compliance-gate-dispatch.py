#!/usr/bin/env python3
"""Apply the local-inference dispatch overlay onto a PLX_MC downstream gate.

The pinned generator still emits pull_request-only YAML. Cursor/github-actions
pushes do not fire pull_request workflows, so this repo overlays
workflow_dispatch plus PR-field fallbacks. Drift CI: generator --emit
downstream | this script, then diff against the committed gate file.
"""

from __future__ import annotations

import sys
from pathlib import Path

TRIGGER_FROM = """on:
  pull_request:
    types: [opened, synchronize, reopened]
"""

TRIGGER_TO = """on:
  pull_request:
    types: [opened, synchronize, reopened]
  workflow_dispatch:
    inputs:
      pr_number:
        description: "PR number for compliance verify when pull_request context is missing"
        required: false
        default: "47"
        type: string
      head_sha:
        description: "Optional head SHA override (defaults to github.sha)"
        required: false
        type: string
"""

ENV_FROM = """          MC_BASE_URL: ${{ secrets.PLX_MC_BASE_URL }}
          MC_CI_TOKEN: ${{ secrets.COMPLIANCE_CI_TOKEN }}
          MODE: ${{ vars.COMPLIANCE_MODE || 'soft' }}
          PR_BODY: ${{ github.event.pull_request.body }}
          PR_LABELS: ${{ toJson(github.event.pull_request.labels.*.name) }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}
          PR_BASE_REF: ${{ github.base_ref }}
          REPO_NAME: ${{ github.event.repository.name }}
          REPO_FULL_NAME: ${{ github.repository }}
"""

ENV_TO = """          MC_BASE_URL: ${{ secrets.PLX_MC_BASE_URL }}
          MC_CI_TOKEN: ${{ secrets.COMPLIANCE_CI_TOKEN }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          MODE: ${{ vars.COMPLIANCE_MODE || 'soft' }}
          PR_BODY: ${{ github.event.pull_request.body || '' }}
          PR_LABELS: ${{ github.event.pull_request.labels && toJson(github.event.pull_request.labels.*.name) || '[]' }}
          PR_NUMBER: ${{ github.event.pull_request.number || inputs.pr_number || '' }}
          PR_HEAD_SHA: ${{ github.event.pull_request.head.sha || inputs.head_sha || github.sha }}
          PR_BASE_REF: ${{ github.base_ref || 'main' }}
          REPO_NAME: ${{ github.event.repository.name }}
          REPO_FULL_NAME: ${{ github.repository }}
"""

AFTER_SKIP_FROM = """          if [ -z "${MC_BASE_URL:-}" ]; then
            echo "PLX_MC_BASE_URL not configured — compliance gate skipped (pre-rollout)."
            exit 0
          fi
          OIDC_TOKEN=""
"""

AFTER_SKIP_TO = """          if [ -z "${MC_BASE_URL:-}" ]; then
            echo "PLX_MC_BASE_URL not configured — compliance gate skipped (pre-rollout)."
            exit 0
          fi
          # workflow_dispatch has no github.event.pull_request. Resolve PR
          # fields before jq so --argjson never sees empty JSON.
          if [ -z "${PR_NUMBER:-}" ]; then
            echo "PR_NUMBER empty — defaulting to 47"
            PR_NUMBER=47
          fi
          case "${PR_NUMBER}" in
            *[!0-9]*) echo "::error::PR_NUMBER is not an integer: ${PR_NUMBER}"; exit 1 ;;
          esac
          if [ -z "${PR_HEAD_SHA:-}" ]; then
            PR_HEAD_SHA="$(git rev-parse HEAD)"
          fi
          if [ -z "${PR_BASE_REF:-}" ]; then
            PR_BASE_REF=main
          fi
          if [ -z "${PR_LABELS:-}" ] || [ "${PR_LABELS}" = "null" ]; then
            PR_LABELS='[]'
          fi
          if [ -z "${PR_BODY:-}" ]; then
            echo "PR_BODY empty — fetching repos/${REPO_FULL_NAME}/pulls/${PR_NUMBER}"
            PR_BODY=$(gh api "repos/${REPO_FULL_NAME}/pulls/${PR_NUMBER}" --jq .body || true)
          fi
          OIDC_TOKEN=""
"""

JQ_PR_FROM = """            --argjson prNumber "$PR_NUMBER" \\
            --arg headSha "$PR_HEAD_SHA" \\
            --argjson changedPaths "$changed" \\
            --argjson labels "${PR_LABELS:-[]}" \\
            --argjson checkoutIds "${checkoutIds:-[]}" \\
            --arg checkoutId "${checkout:-}" \\
            '{repo:$repo, repoFullName:$repoFullName, prNumber:$prNumber, headSha:$headSha, changedPaths:$changedPaths, labels:$labels, checkoutIds:$checkoutIds}
"""

JQ_PR_TO = """            --arg prNumber "$PR_NUMBER" \\
            --arg headSha "$PR_HEAD_SHA" \\
            --argjson changedPaths "$changed" \\
            --argjson labels "${PR_LABELS:-[]}" \\
            --argjson checkoutIds "${checkoutIds:-[]}" \\
            --arg checkoutId "${checkout:-}" \\
            '{repo:$repo, repoFullName:$repoFullName, prNumber:($prNumber | tonumber), headSha:$headSha, changedPaths:$changedPaths, labels:$labels, checkoutIds:$checkoutIds}
"""


def overlay(text: str) -> str:
    replacements = (
        (TRIGGER_FROM, TRIGGER_TO, "trigger"),
        (ENV_FROM, ENV_TO, "env"),
        (AFTER_SKIP_FROM, AFTER_SKIP_TO, "dispatch fallbacks"),
        (JQ_PR_FROM, JQ_PR_TO, "jq prNumber"),
    )
    for needle, insert, label in replacements:
        if needle not in text:
            raise SystemExit(f"overlay failed: generator {label} block changed; update overlay")
        text = text.replace(needle, insert, 1)
    return text


def main() -> int:
    if len(sys.argv) == 2:
        path = Path(sys.argv[1])
        path.write_text(overlay(path.read_text(encoding="utf-8")), encoding="utf-8")
        return 0
    sys.stdout.write(overlay(sys.stdin.read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
