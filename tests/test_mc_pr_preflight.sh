#!/usr/bin/env bash
# Red/green cases for scripts/mc-pr-preflight.sh.
# Stubs `gh` so PR body and check conclusion are controlled; MC reads stay real.
set -uo pipefail
cd "$(dirname "$0")/.."

STUB_DIR="$(mktemp -d)"
trap 'rm -rf "$STUB_DIR"' EXIT
cat > "$STUB_DIR/gh" <<'STUB'
#!/usr/bin/env bash
for a in "$@"; do
  case "$a" in
    *statusCheckRollup*) printf '%s\n' "${FAKE_ROLLUP:-}"; exit 0 ;;
    body) printf '%s\n' "${FAKE_BODY:-}"; exit 0 ;;
  esac
done
printf '%s\n' "${FAKE_BODY:-}"
STUB
chmod +x "$STUB_DIR/gh"
export PATH="$STUB_DIR:$PATH"

PASSCOUNT=0
FAILCOUNT=0
check() { # name want_exit
  local name="$1" want="$2" got
  bash scripts/mc-pr-preflight.sh --pr 999 >/tmp/pf.out 2>&1
  got=$?
  if [[ "$got" == "$want" ]]; then
    printf 'ok   %s (exit %s)\n' "$name" "$got"; PASSCOUNT=$((PASSCOUNT+1))
  else
    printf 'FAIL %s (want exit %s, got %s)\n' "$name" "$want" "$got"; FAILCOUNT=$((FAILCOUNT+1))
    sed 's/^/       | /' /tmp/pf.out
  fi
}

GOOD_ROLLUP=$'COMPLETED\tSUCCESS'

FAKE_BODY='## Summary
no mission control anything here' \
FAKE_ROLLUP="$GOOD_ROLLUP" \
check "rejects PR with no MC-Checkout stamp" 1

FAKE_BODY='- Task: TASK-883
- Task: TASK-887
- MC-Checkout: dsp_ms9eus2g4p51u3' \
FAKE_ROLLUP="$GOOD_ROLLUP" \
check "rejects 2 tasks carrying only 1 stamp" 1

FAKE_BODY='- Task: TASK-883
- MC-Checkout: dsp_ms9eus2g4p51u3' \
FAKE_ROLLUP=$'COMPLETED\tFAILURE' \
check "rejects a failing compliance conclusion" 1

FAKE_BODY='- Task: TASK-883
- MC-Checkout: dsp_ms9eus2g4p51u3' \
FAKE_ROLLUP=$'IN_PROGRESS\t' \
check "rejects an unconcluded compliance check" 1

FAKE_BODY='- Task: TASK-883
- MC-Checkout: dsp_ms9eus2g4p51u3' \
FAKE_ROLLUP="$GOOD_ROLLUP" \
check "accepts correct scope + stamp + evidence + green gate" 0

printf '\n%s passed, %s failed\n' "$PASSCOUNT" "$FAILCOUNT"
[[ "$FAILCOUNT" -eq 0 ]]
