#!/usr/bin/env bash
set -u

domain="${1:-}"

if [ -n "${VMC_REPO_ROOT:-}" ] && [ -d "$VMC_REPO_ROOT" ]; then
  repo_root="$VMC_REPO_ROOT"
elif git_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  repo_root="$git_root"
else
  repo_root="$(pwd)"
fi

if [ -z "$domain" ]; then
  echo "usage: bash map-vmc-domain.sh <chat|todos|swarm|dispatch|trading|api|browser|ci>"
  exit 2
fi

echo "domain=$domain"
echo "repo_root=$repo_root"

print_common() {
  echo "common_commands:"
  echo "  npm run test:contracts --prefix apps/vmc-web"
  echo "  npm run test --prefix apps/vmc-web"
  echo "  npm run typecheck --prefix apps/vmc-web"
}

case "$domain" in
  chat)
    echo "lifecycle=UI input -> chat stream API -> chat dispatch -> swarm queue -> callback/completion -> persistence -> UI render"
    echo "paths:"
    echo "  apps/vmc-web/src/components/vmc/chat/"
    echo "  apps/vmc-web/src/app/api/vmc/chat/stream/route.ts"
    echo "  apps/vmc-web/src/lib/vmc/chat/"
    echo "  apps/vmc-web/src/lib/vmc/chat/chat-dispatch.ts"
    echo "  apps/vmc-web/src/lib/vmc/chat/dispatch-context.ts"
    echo "  apps/vmc-web/src/app/api/vmc/queue/dispatch-callback/route.ts"
    echo "  apps/vmc-web/src/lib/vmc/queue/swarm-dispatches.ts"
    echo "tests:"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/routes/chat-thread-contracts.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/routes/chat-dispatch-contracts.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/cross-domain/chat-todos-contracts.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/cross-domain/chat-second-brain-contracts.test.ts"
    echo "  apps/vmc-web/e2e/chat-load.spec.ts"
    print_common
    ;;
  todos|todo)
    echo "lifecycle=API/UI create -> store -> dispatch/steer -> queue/cron -> callback -> status reconciliation -> stream/UI"
    echo "paths:"
    echo "  apps/vmc-web/src/app/api/vmc/todos/"
    echo "  apps/vmc-web/src/app/api/cron/todo-dispatch/route.ts"
    echo "  apps/vmc-web/src/lib/vmc/todos.ts"
    echo "  apps/vmc-web/src/lib/vmc/todos-store.ts"
    echo "  apps/vmc-web/src/lib/vmc/todos-dispatch.ts"
    echo "tests:"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/routes/todos-route-contracts.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/todos-store-contracts.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/todo-dispatch-contracts.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/cross-domain/chat-todos-contracts.test.ts"
    echo "  apps/vmc-web/e2e/todos-load.spec.ts"
    print_common
    ;;
  swarm|dispatch|swarm-dispatch)
    echo "lifecycle=enqueue -> queue store -> dispatch contract -> worker/adapter -> callback -> poll/stream -> UI or linked domain"
    echo "paths:"
    echo "  apps/vmc-web/src/lib/vmc/dispatch/dispatch-contract.ts"
    echo "  apps/vmc-web/src/lib/vmc/queue/swarm-dispatches.ts"
    echo "  apps/vmc-web/src/lib/vmc/queue/dispatch-links-store.ts"
    echo "  apps/vmc-web/src/lib/vmc/workflows/workflow-dispatch.ts"
    echo "  apps/vmc-web/src/app/api/vmc/workflow-dispatch/route.ts"
    echo "  apps/vmc-web/src/app/api/cron/dispatch-poll/route.ts"
    echo "  apps/vmc-web/src/app/api/vmc/queue/dispatch-callback/route.ts"
    echo "  apps/vmc-web/src/app/api/vmc/royale/dispatch/"
    echo "tests:"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/routes/swarm-dispatches-contracts.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/routes/royale-dispatch-contracts.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/routes/royale-enqueue-contracts.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/routes/dispatcher-health-contracts.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/cross-domain/swarm-coordination-contracts.test.ts"
    echo "  apps/vmc-web/e2e/dispatch.spec.ts"
    print_common
    ;;
  trading|trading-v2)
    echo "lifecycle=signal/input -> trading-v2 API -> store/riskguard -> paper dispatcher -> ledger/KPI -> readiness -> promotion gate"
    echo "safety=paper/staging-only unless explicitly approved"
    echo "paths:"
    echo "  apps/vmc-web/src/lib/vmc/trading-v2/"
    echo "  apps/vmc-web/src/app/api/vmc/trading-v2/"
    echo "  apps/vmc-web/src/components/vmc/trading-lab/"
    echo "  scripts/trading-research/"
    echo "  docs/modules/trading-v2/"
    echo "  docs/runbooks/"
    echo "tests:"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/routes/trading-paper-contracts.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/routes/trading-lab-kpi-m42-contracts.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/trading-v2-promotion-baseline.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/trading-v2-riskguard-breaker.test.ts"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/trading-v2-circuit-breaker-manipulation.test.ts"
    echo "  scripts/trading-research/test_paper_dispatcher_contracts.py"
    print_common
    echo "  npm run trading-v2:readiness --prefix apps/vmc-web"
    ;;
  api)
    echo "lifecycle=request -> auth/validation -> handler -> store/service -> dependency -> response shape -> caller"
    echo "paths:"
    echo "  apps/vmc-web/src/app/api/vmc/"
    echo "  apps/vmc-web/src/lib/vmc/"
    echo "tests:"
    echo "  apps/vmc-web/src/lib/vmc/__tests__/routes/"
    print_common
    ;;
  browser|ui)
    echo "lifecycle=user action -> component state -> API/network -> stream/subscription -> cache/reconciliation -> render"
    echo "paths:"
    echo "  apps/vmc-web/src/components/vmc/"
    echo "  apps/vmc-web/e2e/"
    echo "commands:"
    echo "  npm run typecheck --prefix apps/vmc-web"
    echo "  npm run test:e2e:smoke --prefix apps/vmc-web"
    print_common
    ;;
  ci)
    echo "lifecycle=CI job -> exact command -> local reproduction -> environment delta -> deterministic fix -> CI-equivalent verification"
    echo "commands:"
    echo "  ./scripts/ci-local.sh --quick"
    echo "  ./scripts/ci-local.sh"
    print_common
    ;;
  *)
    echo "unknown_domain=$domain"
    echo "known_domains=chat todos swarm dispatch trading api browser ci"
    exit 2
    ;;
esac

if [ -d "$repo_root/apps/vmc-web" ]; then
  echo "vmc_web_detected=true"
else
  echo "vmc_web_detected=false"
fi
