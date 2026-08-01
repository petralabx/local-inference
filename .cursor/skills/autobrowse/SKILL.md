---
name: autobrowse
description: Route web browsing tasks through the most reliable available path. Use when the user says autobrowse, asks to open or inspect a URL, mentions X/Twitter browser failures, asks for MCP fetch/search fallback, or needs browser automation with verification.
---

# Autobrowse

## Goal

Use the least flaky browsing path for the job, then verify the result before relying on it.

## Routing

1. **Static web page or documentation**
   - Prefer `WebFetch` or the relevant MCP `web_fetch`.
   - Use browser automation only when page state, login, forms, screenshots, or interaction matters.

2. **X/Twitter URL**
   - First try the `user-x-twitter` MCP:
     - Read the relevant tool descriptor before calling it.
     - Call `web_search` with the exact URL or status ID.
     - Call `web_fetch` only after search confirms the target.
   - Treat MCP fetch output as provisional if it contains stale timestamps, generic profile data, invented media URLs, or does not match search snippets.
   - Use browser automation only for visual/session-dependent behavior, and expect X to fail in embedded browsers because of login, privacy extensions, cookies, or anti-bot checks.

3. **Browser UI verification**
   - Use the `cursor-ide-browser` MCP.
   - Before interacting, read the tool schema, list tabs, lock the tab, navigate, snapshot, then act by snapshot refs.
   - After navigation, clicks, typing, waits, or scrolls, take a fresh snapshot before the next structural action.
   - Stop after four failed attempts and report the blocker with the current URL and observed state.

4. **Local app browser sanity checks**
   - Prefer an already-running app server only after mapping its port to its
     working directory (`ss -ltnp` plus `/proc/<pid>/cwd`) so the browser is
     pointed at the current worktree, not a stale checkout.
   - For VMC `/vmc/*` smoke tests, if no current-worktree server is running,
     start an isolated local preview with:
     `VMC_LOCAL_AUTH_BYPASS=1 npm run dev -- --hostname 0.0.0.0 --port <free-port>`.
   - Probe the exact URL for HTTP 200 before browser navigation.
   - If the embedded browser lands on an auth callback or
     `chrome-error://chromewebdata/`, stop retrying that path and switch to the
     isolated local preview URL.
   - If starting VMC locally and `next dev` hits `ENOSPC` / file watcher limits, do not keep retrying.
   - Check `sysctl fs.inotify.max_user_watches fs.inotify.max_user_instances fs.inotify.max_queued_events`.
   - If sudo is available, raise to:
     - `fs.inotify.max_user_watches=1048576`
     - `fs.inotify.max_user_instances=1024`
     - `fs.inotify.max_queued_events=32768`
   - If sudo is unavailable, try polling as a temporary workaround:
     - `WATCHPACK_POLLING=true CHOKIDAR_USEPOLLING=true npm run dev -- --webpack --hostname 127.0.0.1 --port 3000`
   - If polling exposes a separate app bundling issue, stop and report that separately.
   - Stop temporary preview servers and revert generated churn such as
     `next-env.d.ts` after the smoke test.

## X/Twitter Checklist

For `https://x.com/<user>/status/<id>`:

1. Read `user-x-twitter/tools/web_search.json`.
2. Search exact URL or status ID with `platform: "Twitter"`.
3. Read `user-x-twitter/tools/web_fetch.json`.
4. Fetch the URL.
5. Compare search and fetch:
   - Same author/handle.
   - Same topic.
   - Plausible timestamp.
   - No placeholder media IDs.
6. If mismatch, say the MCP fetch is untrusted and use search snippets or ask for an authenticated browser/session path.

## Reporting

Always include:

- Which path was used: browser, MCP fetch, MCP search, or generic web fetch.
- Whether the result was verified.
- Any blocker that needs operator action, such as sudo, login, CAPTCHA, or X privacy-extension failure.
