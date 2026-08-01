#!/usr/bin/env node
// EN-007 close-out verify — sibling of scripts/compliance-checkout.mjs.
//
// Why this exists: prose rules requiring the actor.repo handshake were already
// active when petralabx/local-inference#11 was stamped wrong-scope, and
// mc_complete_task returned ok 19 seconds before the GitHub compliance gate
// BLOCKED. A successful complete() is evidence hand-in, not gate success.
//
// Checks (exit 1 on any failure):
//   1. checkout scope — MC actor.repo must equal MC_REPO
//   2. PR stamps      — one MC-Checkout: dsp_* per referenced TASK-*
//   3. task evidence  — summary + rollback on every referenced task
//   4. gate conclusion — GitHub `compliance` check must be SUCCESS
//
// Env:
//   MC_BASE_URL            default https://mc.plxcustomer.io
//   MC_REPO                full slug (required), e.g. petralabx/local-inference
//   MC_MCP_API_KEY / PLX_MC_MCP_API_KEY
//   MC_OPERATOR_EMAIL / MC_ACCOUNTABLE
//   MC_RUNTIME             default cursor-cloud
//   MC_PR_NUMBER           optional; else resolve via `gh` for current branch
//   WAIT_SECS              poll budget for --wait (default 300)
//
// CLI:
//   node scripts/compliance-pr-verify.mjs [--pr N] [--wait] [--repo owner/name]

import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";

/**
 * @param {{
 *   env?: Record<string, string | undefined>,
 *   fetch?: typeof globalThis.fetch,
 *   log?: (msg: string) => void,
 *   gh?: (args: string[]) => { status: number, stdout: string, stderr: string },
 *   argv?: string[],
 *   now?: () => number,
 *   sleep?: (ms: number) => Promise<void>,
 * }} [opts]
 */
export async function verify(opts = {}) {
  const env = opts.env ?? process.env;
  const fetchFn = opts.fetch ?? globalThis.fetch;
  const log = opts.log ?? console.log;
  const gh =
    opts.gh ??
    ((args) => {
      const r = spawnSync("gh", args, { encoding: "utf8" });
      return {
        status: r.status ?? 1,
        stdout: r.stdout ?? "",
        stderr: r.stderr ?? "",
      };
    });
  const now = opts.now ?? Date.now;
  const sleep =
    opts.sleep ?? ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));

  const argv = opts.argv ?? process.argv.slice(2);
  let prNumber = env.MC_PR_NUMBER || "";
  let wait = false;
  let repoOverride = "";
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--wait") wait = true;
    else if (a === "--pr") prNumber = argv[++i] || "";
    else if (a === "--repo") repoOverride = argv[++i] || "";
    else if (a === "-h" || a === "--help") {
      log(
        "usage: node scripts/compliance-pr-verify.mjs [--pr N] [--wait] [--repo owner/name]"
      );
      return { ok: true, skipped: true, reasons: ["help"] };
    } else {
      throw new Error(`unknown argument: ${a}`);
    }
  }

  const base = (env.MC_BASE_URL || "https://mc.plxcustomer.io").replace(/\/$/, "");
  const repo = repoOverride || env.MC_REPO || "";
  if (!repo) throw new Error("MC_REPO (or --repo) required — full slug");
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)) {
    throw new Error(`MC_REPO must be a full repository slug, got: ${repo}`);
  }

  const apiKey = (env.PLX_MC_MCP_API_KEY || env.MC_MCP_API_KEY || "")
    .replace(/\$\{.*\}/, "")
    .trim();
  if (!apiKey) {
    throw new Error("PLX_MC_MCP_API_KEY or MC_MCP_API_KEY required");
  }
  const operatorEmail = (
    env.MC_OPERATOR_EMAIL ||
    env.MC_ACCOUNTABLE ||
    "cos@petrasoap.com"
  )
    .trim()
    .toLowerCase();
  const runtime = env.MC_RUNTIME || "cursor-cloud";
  const waitSecs = Number(env.WAIT_SECS || 300);

  const headers = {
    "content-type": "application/json",
    "x-api-key": apiKey,
    "x-mc-operator-email": operatorEmail,
    "x-mc-repo": repo,
    "x-mc-runtime": runtime,
  };

  const reasons = [];
  let failed = false;
  const pass = (m) => {
    log(`  PASS  ${m}`);
    reasons.push(`PASS: ${m}`);
  };
  const fail = (m) => {
    failed = true;
    log(`  FAIL  ${m}`);
    reasons.push(`FAIL: ${m}`);
  };
  const info = (m) => log(`  ..    ${m}`);

  log("== 1. checkout scope ==");
  const selfRes = await fetchFn(`${base}/api/cursor/self-check`, { headers });
  if (!selfRes.ok) {
    fail(`self-check HTTP ${selfRes.status}`);
  } else {
    const selfJson = await selfRes.json();
    const actorRepo = selfJson?.meta?.actor?.repo ?? "";
    if (actorRepo === repo) pass(`actor.repo == ${repo}`);
    else
      fail(
        `actor.repo is '${actorRepo || "<none>"}', want '${repo}' — a stamp minted here is wrong-scope (decision 3)`
      );
  }

  log("== 2. PR stamps ==");
  if (!prNumber) {
    const branchRes = spawnSync("git", ["rev-parse", "--abbrev-ref", "HEAD"], {
      encoding: "utf8",
    });
    const branch = (branchRes.stdout || "").trim();
    if (branch && branch !== "HEAD") {
      const list = gh([
        "pr",
        "list",
        "--repo",
        repo,
        "--head",
        branch,
        "--state",
        "all",
        "--json",
        "number",
        "--jq",
        ".[0].number // empty",
      ]);
      prNumber = (list.stdout || "").trim();
    }
  }

  if (!prNumber) {
    info("no PR for this branch yet — stamp and gate checks deferred");
    return { ok: !failed, deferred: true, reasons };
  }

  const bodyRes = gh([
    "pr",
    "view",
    String(prNumber),
    "--repo",
    repo,
    "--json",
    "body",
    "--jq",
    ".body",
  ]);
  if (bodyRes.status !== 0) {
    fail(`could not read PR #${prNumber}: ${bodyRes.stderr.trim()}`);
    return { ok: false, reasons };
  }
  const body = bodyRes.stdout || "";
  const stamps = [
    ...new Set(
      [...body.matchAll(/MC-Checkout:\s*(dsp_[A-Za-z0-9]+)/g)].map((m) => m[1])
    ),
  ];
  const tasks = [
    ...new Set([...body.matchAll(/\b(TASK-\d+)\b/g)].map((m) => m[1])),
  ];

  if (stamps.length === 0) {
    fail(`PR #${prNumber} has no 'MC-Checkout: dsp_…' stamp`);
  } else {
    pass(`PR #${prNumber} carries ${stamps.length} stamp(s): ${stamps.join(" ")}`);
  }
  if (tasks.length === 0) {
    fail(`PR #${prNumber} references no TASK-* id`);
  } else if (stamps.length < tasks.length) {
    fail(
      `one stamp required per task: ${tasks.length} task(s) (${tasks.join(", ")}) but only ${stamps.length} stamp(s)`
    );
  } else {
    pass(
      `stamp/task parity: ${stamps.length} stamp(s) for ${tasks.length} task(s)`
    );
  }

  log("== 3. task evidence ==");
  for (const taskId of tasks) {
    const ctxRes = await fetchFn(
      `${base}/api/cursor/context?taskIds=${encodeURIComponent(taskId)}&depth=full`,
      { headers }
    );
    if (!ctxRes.ok) {
      fail(`${taskId}: context HTTP ${ctxRes.status}`);
      continue;
    }
    const ctx = await ctxRes.json();
    const task = ctx?.data?.tasks?.[0];
    const summary = task?.evidence?.summary || "";
    const rollback = task?.evidence?.rollback || "";
    const stage = task?.stage || "unknown";
    if (summary && rollback) {
      pass(`${taskId} evidence complete (summary + rollback), stage=${stage}`);
    } else {
      fail(
        `${taskId} evidence incomplete (summary=${Boolean(summary)} rollback=${Boolean(rollback)}) — run mc_complete_task`
      );
    }
  }

  log("== 4. compliance gate conclusion ==");
  const deadline = now() + waitSecs * 1000;
  let status = "";
  let conclusion = "";
  for (;;) {
    // Prefer the newest compliance check-run. StatusCheckRollup can retain a
    // stale FAILURE alongside a later SUCCESS after evidence is handed in
    // (seen on PR reopen / complete-then-rerun). First-line select is wrong.
    const roll = gh([
      "pr",
      "view",
      String(prNumber),
      "--repo",
      repo,
      "--json",
      "statusCheckRollup",
      "--jq",
      '[.statusCheckRollup[] | select(.name=="compliance")] | sort_by(.completedAt // .startedAt // "") | last | [.status,(.conclusion//"")] | @tsv',
    ]);
    const line = (roll.stdout || "").trim().split("\n")[0] || "";
    status = line.split("\t")[0] || "";
    conclusion = line.split("\t")[1] || "";
    if (!status) info("compliance check not reported yet");
    else if (status !== "COMPLETED") info(`compliance ${status}…`);
    else break;
    if (!wait || now() >= deadline) break;
    await sleep(10_000);
  }

  if (conclusion === "SUCCESS") pass("compliance = SUCCESS");
  else if (!conclusion)
    fail(
      "compliance has not concluded — do NOT claim the PR is ready (re-run with --wait)"
    );
  else
    fail(
      `compliance = ${conclusion} — fix stamp/evidence and push; never edit .github/workflows/*compliance*`
    );

  log("");
  if (!failed) {
    log(`PREFLIGHT OK — PR #${prNumber} satisfies the MC compliance gate.`);
    return { ok: true, prNumber, stamps, tasks, reasons };
  }
  log(
    `PREFLIGHT FAILED — PR #${prNumber} is NOT ready. Do not report this work as done.`
  );
  return { ok: false, prNumber, stamps, tasks, reasons };
}

async function main() {
  try {
    const result = await verify();
    process.exit(result.ok ? 0 : 1);
  } catch (err) {
    console.error(String(err?.stack || err));
    process.exit(1);
  }
}

const isCli =
  process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isCli) {
  main();
}
