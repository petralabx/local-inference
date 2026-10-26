// node --test scripts/workstream-note.test.mjs
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { SECTIONS, check, findNote, parseIndex, sessionStartText, staleReason } from "./workstream-note.mjs";

const SCRIPT = join(dirname(fileURLToPath(import.meta.url)), "workstream-note.mjs");

const INDEX = `# Workstreams

| Workstream | Owner | Branches | Status | Depends on | MC tasks |
|---|---|---|---|---|---|
| [alpha](alpha.md) | Vince | \`claude/alpha-1\`, \`cursor/alpha\` | active | — | TASK-1 |
| [beta](https://github.com/petralabx/other/blob/main/docs/workstreams/beta.md) | Vince | \`claude/beta\` | blocked | alpha | TASK-2 |
`;

function note(extra = "") {
  return `# Alpha\n\n${SECTIONS.map((s) => `## ${s}\n\n${s === "Last updated" ? "2026-10-26 by test" : "x"}\n`).join("\n")}${extra}`;
}

function repo(files) {
  const root = mkdtempSync(join(tmpdir(), "ws-note-"));
  const run = (...args) => execFileSync("git", args, { cwd: root, stdio: "ignore" });
  run("init", "-q", "-b", "main");
  run("config", "user.email", "t@example.com");
  run("config", "user.name", "t");
  for (const [p, body] of Object.entries(files)) {
    mkdirSync(dirname(join(root, p)), { recursive: true });
    writeFileSync(join(root, p), body);
  }
  run("add", "-A");
  run("commit", "-q", "-m", "base");
  return { root, run };
}

test("parseIndex reads slugs, local notes, remote notes, branches and status", () => {
  const rows = parseIndex(INDEX);
  assert.equal(rows.length, 2);
  assert.deepEqual(rows[0], { slug: "alpha", note: "alpha.md", url: "", branches: ["claude/alpha-1", "cursor/alpha"], status: "active" });
  assert.equal(rows[1].note, "");
  assert.match(rows[1].url, /^https:\/\//);
});

test("findNote uses the index first, then <lane>/<slug>[-n]", () => {
  const { root } = repo({ "docs/workstreams/README.md": INDEX, "docs/workstreams/alpha.md": note(), "docs/workstreams/gamma.md": note() });
  try {
    assert.equal(findNote(root, "cursor/alpha").row.slug, "alpha");
    assert.match(findNote(root, "claude/beta").url, /other/);
    assert.equal(findNote(root, "claude/gamma-3").row.slug, "gamma");
    assert.equal(findNote(root, "claude/unknown"), null);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("session-start prints the note, or the active list when no note matches", () => {
  const { root } = repo({ "docs/workstreams/README.md": INDEX, "docs/workstreams/alpha.md": note() });
  try {
    assert.match(sessionStartText(root, "claude/alpha-1"), /Workstream note: docs\/workstreams\/alpha\.md[\s\S]*## Goal/);
    const none = sessionStartText(root, "claude/other");
    assert.match(none, /No workstream note matches branch claude\/other/);
    assert.match(none, /alpha: active/);
    assert.match(sessionStartText(root, "claude/beta"), /lives in another repository/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("a repo without docs/workstreams stays silent", () => {
  const { root } = repo({ "README.md": "x" });
  try {
    assert.equal(sessionStartText(root, "claude/x"), "");
    assert.equal(staleReason(root, "claude/x"), "");
    assert.deepEqual(check(root), []);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("staleReason asks only when the note is older than the latest change", () => {
  const { root, run } = repo({ "docs/workstreams/README.md": INDEX, "docs/workstreams/alpha.md": note(), "src/a.js": "1" });
  try {
    run("checkout", "-q", "-b", "claude/alpha-1");
    assert.equal(staleReason(root, "claude/alpha-1"), "", "no change, no reminder");
    writeFileSync(join(root, "src/a.js"), "2");
    const old = new Date(Date.now() - 3600_000);
    utimesSync(join(root, "docs/workstreams/alpha.md"), old, old);
    assert.match(staleReason(root, "claude/alpha-1"), /alpha\.md is older/);
    writeFileSync(join(root, "docs/workstreams/alpha.md"), note("\nupdated\n"));
    assert.equal(staleReason(root, "claude/alpha-1"), "", "fresh note, no reminder");
    run("checkout", "-q", "-b", "claude/new-thing");
    assert.match(staleReason(root, "claude/new-thing"), /no workstream note/);
    assert.equal(staleReason(root, "main"), "", "never on the default branch");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("check finds a missing section, an unindexed note, a bad status and a dangling link", () => {
  const bad = INDEX.replace("| blocked |", "| stuck |") + "| [ghost](ghost.md) | V | `x` | active | — | — |\n";
  const { root } = repo({
    "docs/workstreams/README.md": bad,
    "docs/workstreams/alpha.md": note().replace("## Open questions", "## Questions"),
    "docs/workstreams/orphan.md": note(),
    "docs/workstreams/_template.md": "# template",
  });
  try {
    const problems = check(root).join("\n");
    assert.match(problems, /alpha\.md: missing section\(s\): Open questions/);
    assert.match(problems, /orphan\.md: no row in the index/);
    assert.match(problems, /status "stuck"/);
    assert.match(problems, /ghost\.md, which does not exist/);
    assert.doesNotMatch(problems, /_template/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("CLI: check --strict exits 1 on a problem and 0 when clean; stop honours stop_hook_active", () => {
  const { root, run } = repo({ "docs/workstreams/README.md": INDEX, "docs/workstreams/alpha.md": note(), "src/a.js": "1" });
  try {
    const cli = (args, input = "") =>
      spawnSync(process.execPath, [SCRIPT, ...args], { cwd: root, input, encoding: "utf8", env: { ...process.env, CLAUDE_PROJECT_DIR: root } });
    assert.equal(cli(["check", "--strict"]).status, 0);
    writeFileSync(join(root, "docs/workstreams/orphan.md"), note());
    assert.equal(cli(["check", "--strict"]).status, 1);
    assert.equal(cli(["check"]).status, 0, "without --strict it only reports");
    rmSync(join(root, "docs/workstreams/orphan.md"));

    run("checkout", "-q", "-b", "claude/alpha-1");
    writeFileSync(join(root, "src/a.js"), "2");
    const old = new Date(Date.now() - 3600_000);
    utimesSync(join(root, "docs/workstreams/alpha.md"), old, old);
    assert.equal(cli(["stop"], JSON.stringify({ stop_hook_active: true, session_id: "t1" })).stdout, "");
    const sid = `t-${process.pid}-${Date.now()}`;
    const first = JSON.parse(cli(["stop"], JSON.stringify({ session_id: sid })).stdout);
    assert.equal(first.decision, "block");
    assert.equal(cli(["stop"], JSON.stringify({ session_id: sid })).stdout, "", "one reminder per window");
    assert.equal(cli(["path"]).stdout.trim(), "docs/workstreams/alpha.md");

    run("checkout", "-q", "-b", "claude/one-pr-fix");
    const sid2 = `t2-${process.pid}-${Date.now()}`;
    const ask = JSON.parse(cli(["stop"], JSON.stringify({ session_id: sid2 })).stdout);
    assert.match(ask.reason, /^Branch claude\/one-pr-fix has changes but no workstream note/);
    assert.equal(cli(["stop"], JSON.stringify({ session_id: sid2 })).stdout, "", "no-note reminder comes once per session");
    run("checkout", "-q", "claude/alpha-1");
    assert.match(cli(["session-start"]).stdout, /## Goal/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("the template carries every section in order", () => {
  const template = readFileSync(join(dirname(SCRIPT), "..", "docs", "workstreams", "_template.md"), "utf8");
  const headings = [...template.matchAll(/^## (.+?)\s*$/gm)].map((m) => m[1]);
  assert.deepEqual(headings, SECTIONS);
});
