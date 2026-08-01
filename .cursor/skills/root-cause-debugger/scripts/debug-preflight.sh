#!/usr/bin/env bash
set -u

if [ -n "${VMC_REPO_ROOT:-}" ] && [ -d "$VMC_REPO_ROOT" ]; then
  repo_root="$VMC_REPO_ROOT"
elif git_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  repo_root="$git_root"
else
  repo_root="$(pwd)"
fi

echo "Root Cause Debugger Preflight"
echo "repo_root=$repo_root"

if git -C "$repo_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch="$(git -C "$repo_root" branch --show-current 2>/dev/null || true)"
  sha="$(git -C "$repo_root" rev-parse --short HEAD 2>/dev/null || true)"
  status="$(git -C "$repo_root" status --short 2>/dev/null | wc -l | tr -d ' ')"
  echo "git_branch=${branch:-unknown}"
  echo "git_sha=${sha:-unknown}"
  echo "git_changed_files=$status"
else
  echo "git=not-detected"
fi

echo "tools:"
for tool in node npm npx python3 rg git; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "  $tool=$(command -v "$tool")"
  else
    echo "  $tool=missing"
  fi
done

if [ -f "$repo_root/apps/vmc-web/package.json" ]; then
  echo "vmc_web=present"
  if [ -d "$repo_root/apps/vmc-web/node_modules" ]; then
    echo "vmc_web_node_modules=present"
  else
    echo "vmc_web_node_modules=missing"
  fi

  echo "vmc_web_scripts:"
  node -e '
    const pkg = require(process.argv[1]);
    const wanted = [
      "typecheck",
      "lint",
      "test",
      "test:unit",
      "test:routes",
      "test:contracts",
      "test:cross-domain",
      "test:e2e",
      "test:e2e:smoke",
      "ci",
      "trading-v2:readiness"
    ];
    for (const key of wanted) {
      if (pkg.scripts && pkg.scripts[key]) {
        console.log(`  ${key}=${pkg.scripts[key]}`);
      }
    }
  ' "$repo_root/apps/vmc-web/package.json" 2>/dev/null || echo "  package_script_read=failed"
else
  echo "vmc_web=not-detected"
fi

if [ -f "$repo_root/scripts/ci-local.sh" ]; then
  echo "ci_local=present"
else
  echo "ci_local=missing"
fi

if [ -f "$repo_root/scripts/assert-staging-context.sh" ]; then
  echo "staging_guard=present"
else
  echo "staging_guard=missing"
fi

echo "suggested_first_checks:"
echo "  contract=npx tsx --test <specific-test>   # run from apps/vmc-web"
echo "  vmc_contracts=npm run test:contracts --prefix apps/vmc-web"
echo "  vmc_typecheck=npm run typecheck --prefix apps/vmc-web"
echo "  vmc_tests=npm run test --prefix apps/vmc-web"
echo "  ui_smoke=npm run test:e2e:smoke --prefix apps/vmc-web"
