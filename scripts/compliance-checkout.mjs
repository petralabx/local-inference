// EN-007 capture hook (P3). At an agent run's start, resolve the work to MC
// task(s) — check out the given task(s), or request routing suggestions when
// none is supplied — and emit one PR-body stamp line per task
// ("MC-Checkout: <id>") that the gate reads. Supports MULTIPLE tasks per run.
//
// DEFAULT-OFF: does nothing unless COMPLIANCE_CAPTURE=1. Operator-local tooling —
// never auto-enabled (governance: integrations that can act ship disabled).
//
// Env:
//   COMPLIANCE_CAPTURE=1   enable (else no-op)
//   MC_BASE_URL            PLX MC base URL (required when enabled)
//   MC_ACCOUNTABLE         accountable human (required)
//   MC_REPO                full repo slug the work targets (required)
//   MC_TASK_ID             one or more task ids, comma/space separated. If empty,
//                          requests suggestions and stops unless explicit create
//                          intent is set (MC_CREATE_TASK=1).
//   MC_CREATE_TASK=1       explicit creation intent when MC_TASK_ID is empty
//                          (needs MC_TASK_TITLE + MC_BUCKET). Without this flag,
//                          missing Task ID returns suggestions and does not create.
//   MC_TASK_TITLE          title for an auto-created task (when create intent)
//   MC_BUCKET              bucket id for an auto-created task
//   MC_REPORTER            reporter for an auto-created task (default: MC_ACCOUNTABLE)
//   MC_RUNTIME             runtime label (default: cursor)
//   MC_BASIC_AUTH          optional "user:pass" for the staging access gate (legacy path)
//   MC_MCP_API_KEY         when set, uses /api/cursor/* (MCP API key auth - preferred)
//   MC_OPERATOR_EMAIL      operator email for MCP headers (defaults to MC_ACCOUNTABLE)
//   MC_TASK_TITLE / branch metadata may also be sent to /api/cursor/routing/suggest
//
// checkout + tasks are session-gated (src/middleware.ts) — they do not
// self-authenticate. Prefer MC_MCP_API_KEY (cursor routes); otherwise set
// MC_BASIC_AUTH (break-glass); local/open dev needs none.

import { pathToFileURL } from "node:url";

/**
 * @param {{
 *   env?: Record<string, string | undefined>,
 *   fetch?: typeof globalThis.fetch,
 *   log?: (msg: string) => void,
 * }} [opts]
 */
export async function capture({ env = process.env, fetch = globalThis.fetch, log = console.log } = {}) {
  if (env.COMPLIANCE_CAPTURE !== "1") {
    log("[compliance-capture] disabled (set COMPLIANCE_CAPTURE=1 to enable)");
    return {
      enabled: false,
      created: [],
      stamps: [],
      receipts: [],
      taskIds: [],
      suggestions: null,
    };
  }

  log("[compliance-capture] fallback path — prefer MCP checkout");

  const base = env.MC_BASE_URL;
  const accountableHuman = env.MC_ACCOUNTABLE;
  const repo = env.MC_REPO;
  const runtime = env.MC_RUNTIME || "cursor";
  if (!base) throw new Error("MC_BASE_URL not set");
  if (!accountableHuman) throw new Error("MC_ACCOUNTABLE not set");
  if (!repo) throw new Error("MC_REPO not set");
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)) {
    throw new Error("MC_REPO must be a full repository slug (for example petralabx/PLX_MC)");
  }

  const url = (p) => `${base.replace(/\/$/, "")}${p}`;
  const mcpKey = (env.MC_MCP_API_KEY || "").replace(/\$\{.*\}/, "").trim();
  const operatorEmail = (env.MC_OPERATOR_EMAIL || accountableHuman).trim().toLowerCase();
  const useCursorApi = !!mcpKey;

  const headers = { "content-type": "application/json" };
  if (mcpKey) {
    headers["x-api-key"] = mcpKey;
    headers["x-mc-operator-email"] = operatorEmail;
    headers["x-mc-runtime"] = runtime;
    headers["x-mc-worker-id"] = `capture-${process.pid}`;
    headers["x-mc-repo"] = repo;
  } else if (env.MC_BASIC_AUTH) {
    headers.authorization = `Basic ${Buffer.from(env.MC_BASIC_AUTH).toString("base64")}`;
  }

  // Resolve the task id list: explicit MC_TASK_ID(s), else suggest (or create
  // only when MC_CREATE_TASK=1 is an explicit creation intent).
  let taskIds = (env.MC_TASK_ID || "").split(/[\s,]+/).filter(Boolean);
  const created = [];
  if (taskIds.length === 0) {
    const createIntent =
      env.MC_CREATE_TASK === "1" || env.MC_ROUTING_CREATE_INTENT === "1";

    if (!createIntent) {
      if (!useCursorApi) {
        throw new Error(
          "no MC_TASK_ID: set MC_TASK_ID to select a task, or set MC_MCP_API_KEY to request routing suggestions, or set MC_CREATE_TASK=1 for explicit creation"
        );
      }
      const suggestRes = await fetch(url("/api/cursor/routing/suggest"), {
        method: "POST",
        headers,
        body: JSON.stringify({
          title: env.MC_TASK_TITLE || undefined,
          branch: env.MC_BRANCH || undefined,
          baseBranch: env.MC_BASE_BRANCH || undefined,
          sourceBranch: env.MC_SOURCE_BRANCH || env.MC_BRANCH || undefined,
          headSha: env.MC_HEAD_SHA || undefined,
          changedPaths: env.MC_CHANGED_PATHS
            ? env.MC_CHANGED_PATHS.split(/[\s,]+/).filter(Boolean)
            : undefined,
        }),
      });
      if (!suggestRes.ok) {
        throw new Error(`routing suggest failed: HTTP ${suggestRes.status}`);
      }
      const suggestJson = await suggestRes.json();
      const suggestions = suggestJson?.data ?? suggestJson;
      const routingSessionId = suggestions?.routingSessionId ?? null;
      const candidates = Array.isArray(suggestions?.candidates) ? suggestions.candidates : [];
      log(
        `[compliance-capture] no MC_TASK_ID — routing suggestions ready (session ${routingSessionId ?? "n/a"}); select a candidate or set MC_CREATE_TASK=1 for explicit creation`
      );
      for (const c of candidates.slice(0, 3)) {
        log(
          `[compliance-capture] candidate #${c.rank ?? "?"} ${c.taskId} score=${c.matchScore ?? "?"} — ${(c.reasons || []).slice(0, 2).join("; ")}`
        );
        if (c.link) log(`[compliance-capture]   link: ${c.link}`);
      }
      if (suggestions?.mcRoutingMarker) {
        log(suggestions.mcRoutingMarker);
      }
      return {
        enabled: true,
        created: [],
        stamps: [],
        receipts: [],
        taskIds: [],
        suggestions,
        routingSessionId,
        needsSelection: true,
      };
    }

    const title = env.MC_TASK_TITLE;
    const bucket = env.MC_BUCKET;
    if (!title) throw new Error("MC_CREATE_TASK=1 requires MC_TASK_TITLE");
    if (!bucket) throw new Error("MC_CREATE_TASK=1 requires MC_BUCKET");
    // Under MCP auth use the self-authenticating /api/cursor/tasks route; the
    // legacy /api/tasks is session-gated and would 302 to the sign-in HTML page
    // (the headers carry an API key, not a session cookie).
    const createPath = useCursorApi ? "/api/cursor/tasks" : "/api/tasks";
    const res = await fetch(url(createPath), {
      method: "POST",
      headers,
      body: JSON.stringify({
        title,
        bucket,
        reporter: env.MC_REPORTER || accountableHuman,
        accountableOwner: accountableHuman,
      }),
    });
    if (!res.ok) throw new Error(`task create failed: HTTP ${res.status}`);
    const json = await res.json();
    // cursor route returns { data: { taskId, task } }; legacy returns { data: { id } }.
    const id = json?.data?.taskId || json?.data?.task?.id || json?.data?.id;
    if (!id) throw new Error("no task id in create response");
    log(`[compliance-capture] auto-created ${id} (${title})`);
    taskIds = [id];
    created.push(id);
  }

  // Check out each task and emit its stamp. The caller appends these lines to the
  // PR body; the gate + webhook read every one (multi-task verify).
  const stamps = [];
  const receipts = [];
  for (const taskId of taskIds) {
    const checkoutPath = useCursorApi ? "/api/cursor/checkout" : "/api/compliance/checkout";
    const checkoutBody = useCursorApi
      ? { taskId }
      : { taskId, runtime, accountableHuman, repo };
    const res = await fetch(url(checkoutPath), {
      method: "POST",
      headers,
      body: JSON.stringify(checkoutBody),
    });
    if (!res.ok) throw new Error(`checkout failed for ${taskId}: HTTP ${res.status}`);
    const json = await res.json();
    const data = json?.data ?? json;
    const checkoutId = data?.checkoutId;
    if (!checkoutId) throw new Error(`no checkoutId for ${taskId}`);
    const expectedPrBodyLine = `MC-Checkout: ${checkoutId}`;
    const prBodyLine = data?.prBodyLine || (!useCursorApi ? expectedPrBodyLine : "");
    if (!prBodyLine) throw new Error(`checkout stamp missing for ${taskId}`);

    if (useCursorApi) {
      if (data?.taskId !== taskId) {
        throw new Error(
          `checkout task mismatch: expected ${taskId}, received ${data?.taskId || "missing"}`
        );
      }
      const responseRepo = json?.meta?.actor?.repo;
      if (responseRepo !== repo) {
        throw new Error(
          `checkout repo mismatch: expected ${repo}, received ${responseRepo || "missing"}`
        );
      }
    }
    if (prBodyLine !== expectedPrBodyLine) {
      throw new Error(
        `checkout stamp mismatch: expected "${expectedPrBodyLine}", received "${prBodyLine}"`
      );
    }
    if (useCursorApi && json?.meta?.links?.checkoutStamp !== prBodyLine) {
      throw new Error(
        `checkout metadata stamp mismatch: expected "${prBodyLine}", received "${
          json?.meta?.links?.checkoutStamp || "missing"
        }"`
      );
    }

    log(`[compliance-capture] handshake ok task=${taskId} repo=${repo}`);
    log(prBodyLine);
    stamps.push(checkoutId);
    receipts.push({ taskId, repo, checkoutId, prBodyLine });
  }

  return { enabled: true, created, stamps, receipts, taskIds, suggestions: null };
}

// Run when invoked as a CLI (the hook), not when imported by a test. pathToFileURL
// makes this robust to relative paths, symlinks, spaces, and Windows drive letters
// (a hand-built `file://` + argv[1] is none of those).
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  capture().catch((e) => {
    console.error(`[compliance-capture] ${e.message}`);
    process.exit(1);
  });
}
