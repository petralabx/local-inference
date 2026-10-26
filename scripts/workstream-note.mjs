#!/usr/bin/env node
// Workstream notes (docs/workstreams/): find the note for this branch, surface it
// when a session starts, remind the agent when it goes stale, and check that the
// index and the notes agree. No dependencies; Node 18+.
//
//   node scripts/workstream-note.mjs session-start   Claude Code SessionStart hook: prints the note
//   node scripts/workstream-note.mjs stop            Claude Code Stop hook: asks once for a stale note
//   node scripts/workstream-note.mjs path            prints this branch's note path, or nothing
//   node scripts/workstream-note.mjs check [--strict] index and notes agree; --strict exits 1 on a problem
//
// Hooks never fail a session: any error exits 0 with nothing printed.

import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

export const SECTIONS = [
  "Goal",
  "Status",
  "Done",
  "Next steps",
  "Decisions and why",
  "Open questions",
  "Files / areas touched",
  "How to run the tests",
  "Blockers or dependencies on other workstreams",
  "Last updated",
];
export const STATUSES = ["active", "blocked", "paused", "done"];
const MAX_NOTE_CHARS = 8000; // SessionStart output is capped at 10,000 characters.
const REMIND_EVERY_MS = 45 * 60 * 1000;
const DEFAULT_BRANCHES = ["main", "master", "staging"];

function git(root, args) {
  try {
    // trimEnd, not trim: `status --porcelain` lines start with a significant space.
    return execFileSync("git", args, { cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trimEnd();
  } catch {
    return "";
  }
}

export function repoRoot() {
  if (process.env.CLAUDE_PROJECT_DIR) return process.env.CLAUDE_PROJECT_DIR;
  return git(process.cwd(), ["rev-parse", "--show-toplevel"]) || process.cwd();
}

function stripMd(cell) {
  return cell.replace(/`/g, "").replace(/\*\*/g, "").trim();
}

/** Rows of the first table whose header has Workstream and Branch columns. */
export function parseIndex(text) {
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length - 1; i++) {
    if (!lines[i].trim().startsWith("|") || !/^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) continue;
    const header = lines[i].split("|").slice(1, -1).map((h) => stripMd(h).toLowerCase());
    const col = (re) => header.findIndex((h) => re.test(h));
    const ws = col(/^workstream/);
    const br = col(/^branch/);
    if (ws < 0 || br < 0) continue;
    const st = col(/^status/);
    const rows = [];
    for (let j = i + 2; j < lines.length && lines[j].trim().startsWith("|"); j++) {
      const cells = lines[j].split("|").slice(1, -1);
      const wsCell = (cells[ws] ?? "").trim();
      const link = /\[([^\]]+)\]\(([^)]+)\)/.exec(wsCell);
      const target = link ? link[2].trim() : "";
      const local = target && !/^[a-z]+:\/\//i.test(target) ? target.replace(/^\.\//, "") : "";
      rows.push({
        slug: stripMd(link ? link[1] : wsCell),
        note: local, // relative to docs/workstreams/, empty when the note lives elsewhere
        url: local ? "" : target,
        branches: stripMd(cells[br] ?? "")
          .split(/[\s,]+|<br\s*\/?>/i)
          .map((b) => b.trim())
          .filter((b) => b && b !== "-" && b !== "—"),
        status: st >= 0 ? stripMd(cells[st] ?? "").toLowerCase() : "",
      });
    }
    return rows;
  }
  return [];
}

/** The index row and note path for a branch, or null. */
export function findNote(root, branch) {
  const dir = join(root, "docs", "workstreams");
  const indexPath = join(dir, "README.md");
  if (!existsSync(indexPath)) return null;
  const rows = parseIndex(readFileSync(indexPath, "utf8"));
  const row = rows.find((r) => r.branches.includes(branch));
  if (row) return { row, path: row.note ? join(dir, row.note) : "", url: row.url };
  // No index row yet: a note named after the branch, or after <lane>/<slug>[-n].
  const candidates = [branch.replace(/\//g, "-")];
  const m = /^[^/]+\/(.+?)(?:-\d+)?$/.exec(branch);
  if (m) candidates.push(m[1].replace(/\//g, "-"));
  for (const slug of candidates) {
    const p = join(dir, `${slug}.md`);
    if (existsSync(p)) return { row: { slug, branches: [], status: "" }, path: p, url: "" };
  }
  return null;
}

function currentBranch(root) {
  return git(root, ["rev-parse", "--abbrev-ref", "HEAD"]);
}

function activeSummary(root) {
  const indexPath = join(root, "docs", "workstreams", "README.md");
  const rows = parseIndex(readFileSync(indexPath, "utf8")).filter((r) => r.status !== "done");
  if (rows.length === 0) return "No active workstreams are listed in docs/workstreams/README.md.";
  return ["Active workstreams (docs/workstreams/README.md):"]
    .concat(rows.map((r) => `- ${r.slug}: ${r.status || "?"}, branch ${r.branches.join(", ") || "?"}`))
    .join("\n");
}

export function sessionStartText(root, branch) {
  if (!existsSync(join(root, "docs", "workstreams", "README.md"))) return "";
  const found = findNote(root, branch);
  const footer =
    "Workstream protocol: keep to this workstream's scope and flag edits outside it. Update the note " +
    "before you end the session and after any significant decision (/handoff in Claude Code).";
  if (!found) {
    return [
      `=== Workstream (SessionStart hook) ===`,
      `No workstream note matches branch ${branch}.`,
      activeSummary(root),
      "If this work belongs to one of them, read its note. If it is new and spans more than one PR or " +
        "session, copy docs/workstreams/_template.md to docs/workstreams/<slug>.md and add an index row.",
    ].join("\n");
  }
  if (!found.path) {
    return `=== Workstream (SessionStart hook) ===\nBranch ${branch} belongs to workstream ${found.row.slug}. ` +
      `Its note lives in another repository: ${found.url}\n${footer}`;
  }
  if (!existsSync(found.path)) {
    return `=== Workstream (SessionStart hook) ===\nThe index points branch ${branch} at ${found.path}, ` +
      "which does not exist. Create it from docs/workstreams/_template.md.";
  }
  let note = readFileSync(found.path, "utf8");
  if (note.length > MAX_NOTE_CHARS) note = `${note.slice(0, MAX_NOTE_CHARS)}\n[… truncated; read the file for the rest]`;
  const rel = found.path.slice(root.length + 1);
  return `=== Workstream note: ${rel} (SessionStart hook) ===\n${note.trim()}\n=== end of note ===\n${footer}`;
}

function defaultBase(root) {
  const head = git(root, ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"]).replace("refs/remotes/", "");
  const candidates = head ? [head] : DEFAULT_BRANCHES.map((b) => `origin/${b}`);
  for (const ref of candidates) if (git(root, ["rev-parse", "--verify", "--quiet", ref])) return ref;
  return "";
}

/** Files this branch changed (committed and uncommitted), outside docs/workstreams/. */
export function changedFiles(root) {
  const files = new Set();
  const base = defaultBase(root);
  if (base) {
    const mergeBase = git(root, ["merge-base", base, "HEAD"]);
    if (mergeBase) for (const f of git(root, ["diff", "--name-only", mergeBase, "HEAD"]).split("\n")) if (f) files.add(f);
  }
  for (const line of git(root, ["status", "--porcelain"]).split("\n")) {
    const f = line.slice(3).split(" -> ").pop();
    if (f) files.add(f.replace(/^"|"$/g, ""));
  }
  return [...files].filter((f) => !f.startsWith("docs/workstreams/"));
}

function mtime(p) {
  try {
    return statSync(p).mtimeMs;
  } catch {
    return 0;
  }
}

/** The Stop-hook reason when the note needs attention, or "" when it does not. */
export function staleReason(root, branch) {
  if (!existsSync(join(root, "docs", "workstreams", "README.md"))) return "";
  if (DEFAULT_BRANCHES.includes(branch) || branch === "HEAD" || !branch) return "";
  const changed = changedFiles(root);
  if (changed.length === 0) return "";
  const found = findNote(root, branch);
  if (!found) {
    return `Branch ${branch} has changes but no workstream note. If this work spans more than one PR or ` +
      "session, create docs/workstreams/<slug>.md from docs/workstreams/_template.md and add an index row " +
      "(/handoff does both). For a one-PR change, say so and carry on.";
  }
  if (!found.path || !existsSync(found.path)) return "";
  const newest = Math.max(...changed.map((f) => mtime(join(root, f))));
  if (mtime(found.path) >= newest) return "";
  const rel = found.path.slice(root.length + 1);
  return `${rel} is older than this branch's latest change. Before you finish, update its Status, Done, ` +
    "Next steps and Last updated (/handoff), or say why it is still accurate.";
}

function readStdin() {
  try {
    return JSON.parse(readFileSync(0, "utf8") || "{}");
  } catch {
    return {};
  }
}

/** True when this session already had this kind of reminder recently (or, for "no note", at all). */
function remindedRecently(sessionId, onceOnly) {
  const file = join(tmpdir(), `workstream-note-${String(sessionId || "none").replace(/[^\w-]/g, "")}.json`);
  let state = {};
  try {
    state = JSON.parse(readFileSync(file, "utf8")) || {};
  } catch {
    state = {};
  }
  const key = onceOnly ? "noNote" : "stale";
  if (onceOnly ? state[key] : Date.now() - (state[key] || 0) < REMIND_EVERY_MS) return true;
  try {
    writeFileSync(file, JSON.stringify({ ...state, [key]: Date.now() }));
  } catch {
    // A reminder without a record only means the next one may come sooner.
  }
  return false;
}

/** Problems with the index and the notes, as strings. */
export function check(root) {
  const dir = join(root, "docs", "workstreams");
  const indexPath = join(dir, "README.md");
  if (!existsSync(indexPath)) return [];
  const problems = [];
  const rows = parseIndex(readFileSync(indexPath, "utf8"));
  const notes = readdirSync(dir).filter((f) => f.endsWith(".md") && f !== "README.md" && !f.startsWith("_"));
  for (const row of rows) {
    if (row.status && !STATUSES.includes(row.status)) {
      problems.push(`index: ${row.slug} has status "${row.status}" (use ${STATUSES.join(", ")})`);
    }
    if (row.note && !existsSync(join(dir, row.note))) problems.push(`index: ${row.slug} links ${row.note}, which does not exist`);
    if (!row.note && !row.url) problems.push(`index: ${row.slug} has no link to its note`);
  }
  const indexed = new Set(rows.map((r) => r.note));
  for (const file of notes) {
    if (!indexed.has(file)) problems.push(`${file}: no row in the index (docs/workstreams/README.md)`);
    const text = readFileSync(join(dir, file), "utf8");
    const headings = [...text.matchAll(/^## (.+?)\s*$/gm)].map((m) => m[1]);
    const missing = SECTIONS.filter((s) => !headings.includes(s));
    if (missing.length) problems.push(`${file}: missing section(s): ${missing.join(", ")}`);
    const order = headings.filter((h) => SECTIONS.includes(h));
    if (!missing.length && order.join("|") !== SECTIONS.join("|")) problems.push(`${file}: sections are out of template order`);
    const updated = /^## Last updated\s*\n+([^\n]*)/m.exec(text);
    if (updated && !/\d{4}-\d{2}-\d{2}/.test(updated[1])) problems.push(`${file}: Last updated has no YYYY-MM-DD date`);
  }
  return problems;
}

function main(argv) {
  const [cmd, ...rest] = argv;
  const root = repoRoot();
  const branch = currentBranch(root);
  switch (cmd) {
    case "session-start": {
      const text = sessionStartText(root, branch);
      if (text) process.stdout.write(`${text}\n`);
      return 0;
    }
    case "stop": {
      const input = readStdin();
      if (input.stop_hook_active) return 0;
      const reason = staleReason(root, branch);
      // "No note yet" comes once a session: most branches are one-PR changes.
      const onceOnly = Boolean(reason) && !findNote(root, branch);
      if (reason && !remindedRecently(input.session_id, onceOnly)) {
        process.stdout.write(`${JSON.stringify({ decision: "block", reason })}\n`);
      }
      return 0;
    }
    case "path": {
      const found = findNote(root, branch);
      if (found?.path) process.stdout.write(`${found.path.slice(root.length + 1)}\n`);
      else if (found?.url) process.stdout.write(`${found.url}\n`);
      return 0;
    }
    case "check": {
      const problems = check(root);
      for (const p of problems) process.stdout.write(`workstream-note: ${p}\n`);
      if (problems.length === 0) process.stdout.write("workstream-note: index and notes agree\n");
      return problems.length && rest.includes("--strict") ? 1 : 0;
    }
    default:
      process.stderr.write("usage: workstream-note.mjs session-start | stop | path | check [--strict]\n");
      return 2;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  let code = 0;
  try {
    code = main(process.argv.slice(2));
  } catch (err) {
    // Hooks must never break a session; `check` reports the error.
    if (process.argv[2] === "check") {
      process.stderr.write(`workstream-note: ${err.message}\n`);
      code = 1;
    }
  }
  process.exitCode = code;
}
