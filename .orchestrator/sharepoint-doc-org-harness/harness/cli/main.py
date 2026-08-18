from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness import __version__
from harness.config import load_config
from harness.journal.store import ActionJournal, reverse_actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness", description="SharePoint doc org harness")
    parser.add_argument("--version", action="store_true")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to harness YAML (or set HARNESS_CONFIG)",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("version", help="Print package version")

    rev = sub.add_parser("reverse", help="Undo a journaled run")
    rev.add_argument("--run-id", required=True)
    rev.add_argument(
        "--journal",
        default=None,
        help="Path to journal sqlite (default from config)",
    )

    where = sub.add_parser("where", help="Provenance lookup")
    where.add_argument("--path", default=None)
    where.add_argument("--name", default=None)
    where.add_argument("--hash", dest="content_hash", default=None)
    where.add_argument("--journal", default=None)

    dig = sub.add_parser("digest", help="scan → classify → act → report")
    dig.add_argument("--report", required=True, help="Path to write digest JSON report")
    dig.add_argument("--dry-run", action="store_true")
    dig.add_argument("--journal", default=None)
    dig.add_argument(
        "--only",
        action="append",
        default=None,
        help="Capture folder name (repeatable), e.g. _from_mail. Default: all captures plus inbox root files.",
    )
    dig.add_argument("--limit", type=int, default=None, help="Max files to classify this run")

    drn = sub.add_parser("drain", help="move unique Petra sources onto VincePersonal homes")
    drn.add_argument("--report", required=True, help="Path to write drain JSON report")
    drn.add_argument("--dry-run", action="store_true")
    drn.add_argument("--journal", default=None)
    drn.add_argument("--source-root", default=None, help="Petra OneDrive root")
    drn.add_argument(
        "--map",
        dest="drain_map",
        default=None,
        help="Drain map YAML (default config/drain_map.yaml). Use config/legacy_roots.yaml for leftover VincePersonal roots.",
    )
    drn.add_argument(
        "--only",
        action="append",
        default=None,
        help="Mapped source folder name (repeatable). Default: all mapped sources.",
    )
    drn.add_argument("--limit", type=int, default=None, help="Max files to plan/move this run")

    args = parser.parse_args(argv)
    if args.version or args.cmd == "version":
        print(__version__)
        return 0

    cfg_path = Path(args.config) if getattr(args, "config", None) else None

    if args.cmd == "reverse":
        cfg = load_config(cfg_path)
        journal_path = Path(args.journal) if args.journal else cfg.resolve_path(cfg.journal_path)
        journal = ActionJournal(journal_path)
        try:
            n = reverse_actions(journal, args.run_id)
        finally:
            journal.close()
        print(f"reversed_actions={n} run_id={args.run_id}")
        return 0

    if args.cmd == "where":
        from harness.ledger.documents import DocumentLedger
        from harness.provenance.query import ProvenanceStore

        if args.journal:
            journal_path = Path(args.journal)
        else:
            cfg = load_config(cfg_path)
            journal_path = cfg.resolve_path(cfg.journal_path)
        ledger = DocumentLedger(journal_path)
        journal = ActionJournal(journal_path)
        try:
            rows = ledger.lookup(
                path=args.path, name=args.name, content_hash=args.content_hash
            )
            store = ProvenanceStore.from_journal(journal)
            hits = store.lookup(path=args.path, name=args.name, content_hash=args.content_hash)
        finally:
            journal.close()
            ledger.close()
        if not rows and not hits:
            print("no_matches")
            return 1
        for rec in rows:
            print(rec)
        for h in hits:
            print(h)
        return 0

    if args.cmd == "digest":
        from harness.jobs.digest import run_digest

        cfg = load_config(cfg_path)
        journal_path = Path(args.journal) if args.journal else cfg.resolve_path(cfg.journal_path)
        journal = ActionJournal(journal_path)
        try:
            report = run_digest(
                cfg=cfg,
                journal=journal,
                report_path=Path(args.report),
                dry_run=bool(args.dry_run),
                only=args.only,
                limit=args.limit,
            )
        finally:
            journal.close()
        print(
            f"run_id={report.run_id} moved={report.moved} held={report.held} "
            f"archived={report.archived} inbox_active={report.inbox_active} "
            f"ceiling_breach={report.ceiling_breach}"
        )
        return 2 if report.ceiling_breach else 0

    if args.cmd == "drain":
        from harness.jobs.drain import run_drain

        cfg = load_config(cfg_path)
        journal_path = Path(args.journal) if args.journal else cfg.resolve_path(cfg.journal_path)
        journal = ActionJournal(journal_path)
        try:
            report = run_drain(
                cfg=cfg,
                journal=journal,
                report_path=Path(args.report),
                source_root=Path(args.source_root) if args.source_root else None,
                only=args.only,
                limit=args.limit,
                dry_run=bool(args.dry_run),
                map_path=Path(args.drain_map) if args.drain_map else None,
            )
        finally:
            journal.close()
        print(
            f"run_id={report.run_id} moved={report.moved} planned={report.planned} "
            f"skipped_duplicate={report.skipped_duplicate} skipped_secret={report.skipped_secret} "
            f"errors={report.errors}"
        )
        return 1 if report.errors else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
