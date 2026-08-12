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
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("version", help="Print package version")

    rev = sub.add_parser("reverse", help="Undo a journaled run")
    rev.add_argument("--run-id", required=True)
    rev.add_argument(
        "--journal",
        default=None,
        help="Path to journal sqlite (default from config)",
    )

    where = sub.add_parser("where", help="Provenance lookup (P3+)")
    where.add_argument("--path", default=None)
    where.add_argument("--name", default=None)
    where.add_argument("--hash", dest="content_hash", default=None)
    where.add_argument("--journal", default=None)

    args = parser.parse_args(argv)
    if args.version or args.cmd == "version":
        print(__version__)
        return 0

    if args.cmd == "reverse":
        cfg = load_config()
        journal_path = Path(args.journal) if args.journal else cfg.resolve_path(cfg.journal_path)
        journal = ActionJournal(journal_path)
        try:
            n = reverse_actions(journal, args.run_id)
        finally:
            journal.close()
        print(f"reversed_actions={n} run_id={args.run_id}")
        return 0

    if args.cmd == "where":
        from harness.provenance.query import ProvenanceStore

        if args.journal:
            journal_path = Path(args.journal)
        else:
            cfg = load_config()
            journal_path = cfg.resolve_path(cfg.journal_path)
        journal = ActionJournal(journal_path)
        try:
            store = ProvenanceStore.from_journal(journal)
            hits = store.lookup(path=args.path, name=args.name, content_hash=args.content_hash)
        finally:
            journal.close()
        if not hits:
            print("no_matches")
            return 1
        for h in hits:
            print(h)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
