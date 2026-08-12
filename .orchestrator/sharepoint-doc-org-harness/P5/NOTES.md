# P5 — File actions

- Inbox sorter: move-not-copy + processed manifest (idempotent skip).
- Dedupe: hash-map / fclones wrap; delete gated (default tombstone).
- Archive-in-place: `_Archive/<yyyy>/` for files older than `horizon_days`.
- Acceptance: `python -m pytest -q -k test_p5_` (passed).
