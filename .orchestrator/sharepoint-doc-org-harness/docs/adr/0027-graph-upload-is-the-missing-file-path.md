# Graph upload is the missing-file path

Decided 2026-08-26.

Vince Personal files that exist locally but not on the SharePoint server are
uploaded with **delegated Microsoft Graph**, not by renaming or moving through
the OneDrive sync client.

## Decision

1. **`LiveGraphDriveClient.upload_file`** creates missing parent folders, then
   `PUT /content` for files smaller than 4 MiB, or `createUploadSession` plus
   chunked PUT (320 KiB multiples) for larger files.
2. **Conflict:** if the server item already exists with the same size, skip.
   If the size differs, fail that file unless `--replace` is explicit.
3. **`harness harvest`** uploads `local_only` rows from a sync-audit report or
   a live MSAL compare, then stamps Title + Party/Prefix/Home. Default is
   dry-run. `--apply` is additive Graph-only and does not delete.
4. **No OneDrive client moves** for this job. Saturday 2026-08-23 rehome
   deleted cloud originals when local moves failed (`OSError 22`).
5. **No `FileLeafRef` `$filter`.** Path GET / folder `/children` / upload by
   path only. The library is over the 5k view threshold.
6. Secrets and code exclude globs are never uploaded.
7. Leftover-tree **fold** stays dry-run by default and is refused on
   non-Windows when `--apply` would move a live library (ADR 0026). Harvest
   does not fold.

## Rejected

- Moving or renaming via Explorer / OneDrive client to "force sync"
- Pasting a Graph token into env for `sync-audit` (MSAL cache from
  `graph-login` is the live path; `--cassette` stays for tests)
- Hub / Portal `MC-Checkout` stamps on this tooling PR
