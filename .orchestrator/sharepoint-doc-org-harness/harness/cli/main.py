from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from harness import __version__
from harness.config import load_config
from harness.graph.factory import resolve_graph_client
from harness.journal.store import ActionJournal, reverse_actions


def _close_graph(graph) -> None:
    closer = getattr(graph, "close", None)
    if callable(closer):
        closer()


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

    rel = sub.add_parser(
        "relabel",
        help="apply Organizer name law + ledger to files already in 00-06",
    )
    rel.add_argument("--report", required=True, help="Path to write relabel JSON report")
    rel.add_argument("--journal", default=None)
    rel.add_argument("--limit", type=int, default=None, help="Max files this run")

    stmp = sub.add_parser(
        "stamp",
        help="metadata-only backfill of SharePoint Title + Party/Prefix/Home (no rename)",
    )
    stmp.add_argument("--report", required=True, help="Path to write stamp JSON report")
    stmp.add_argument("--journal", default=None)
    stmp.add_argument("--limit", type=int, default=None, help="Max files this run")

    sub.add_parser(
        "graph-login",
        help="delegated MSAL device-code login for Vince Personal Graph writes",
        description="Delegated MSAL device-code login for Vince Personal Graph writes.",
    )

    inv = sub.add_parser(
        "inventory",
        help="report-only leftover document inventory (no copy/upload)",
    )
    inv.add_argument("--report", required=True, help="Path to write inventory JSON report")
    inv.add_argument(
        "--root",
        action="append",
        default=None,
        help="Local root to scan (repeatable). Use machine-local leftover paths.",
    )
    inv.add_argument(
        "--roots-file",
        default=None,
        help="YAML list of roots (config/inventory_roots.example.yaml). Merged with --root.",
    )
    inv.add_argument("--journal", default=None)
    inv.add_argument("--limit", type=int, default=None, help="Max files to classify this run")

    audit = sub.add_parser(
        "sync-audit",
        help="report-only local vs SharePoint file inventory (no upload/rename/stamp)",
    )
    audit.add_argument(
        "--report",
        default=None,
        help="JSON report path (default: data/reports/sync-audit.json)",
    )
    audit.add_argument(
        "--dry-run",
        action="store_true",
        help="Path inventory only — skip content hashes. Never mutates.",
    )
    audit.add_argument(
        "--hashes",
        action="store_true",
        help="Compare hashes when the server listing provides sha256 (ignored with --dry-run)",
    )
    audit.add_argument(
        "--backend",
        choices=("graph", "rest"),
        default="graph",
        help="Folder listing API: Graph drive children or SharePoint REST Files/Folders",
    )
    audit.add_argument(
        "--cassette",
        default=None,
        help="JSON remote tree for tests/offline. Live VTA omits this and uses env tokens.",
    )
    audit.add_argument(
        "--only",
        action="append",
        default=None,
        help="Relative folder to walk (repeatable), e.g. 05_Personal. Default: library root.",
    )

    fld = sub.add_parser(
        "fold",
        help="plan leftover-tree fold into 00-06 (dry-run default; --apply to move)",
    )
    fld.add_argument("--report", required=True, help="Path to write fold JSON report")
    fld.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute moves. Default is dry-run (plan only).",
    )
    fld.add_argument("--journal", default=None)
    fld.add_argument(
        "--source-root",
        default=None,
        help="VincePersonal sync root (default from config). Fixtures only in tests.",
    )
    fld.add_argument(
        "--only",
        action="append",
        default=None,
        help="Leftover tree relative path (repeatable). Default: discovered leftovers.",
    )
    fld.add_argument("--limit", type=int, default=None, help="Max files to classify this run")

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

    if args.cmd == "graph-login":
        from harness.graph.auth import login_delegated

        cfg = load_config(cfg_path)
        login_delegated(cfg.graph)
        print(f"graph_login_ok upn={cfg.graph.upn}")
        return 0

    if args.cmd == "digest":
        from harness.jobs.digest import run_digest

        cfg = load_config(cfg_path)
        journal_path = Path(args.journal) if args.journal else cfg.resolve_path(cfg.journal_path)
        journal = ActionJournal(journal_path)
        graph = resolve_graph_client(cfg)
        try:
            report = run_digest(
                cfg=cfg,
                journal=journal,
                report_path=Path(args.report),
                dry_run=bool(args.dry_run),
                only=args.only,
                limit=args.limit,
                graph=graph,
            )
        finally:
            journal.close()
            _close_graph(graph)
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

    if args.cmd == "relabel":
        from harness.jobs.relabel import run_relabel

        cfg = load_config(cfg_path)
        journal_path = Path(args.journal) if args.journal else cfg.resolve_path(cfg.journal_path)
        journal = ActionJournal(journal_path)
        graph = resolve_graph_client(cfg)
        try:
            report = run_relabel(
                cfg=cfg,
                journal=journal,
                report_path=Path(args.report),
                limit=args.limit,
                graph=graph,
            )
        finally:
            journal.close()
            _close_graph(graph)
        print(
            f"run_id={report.run_id} scanned={report.scanned} renamed={report.renamed} "
            f"peeled={report.peeled} ledger_only={report.ledger_only} held={report.held} "
            f"skipped={report.skipped} errors={report.errors}"
        )
        return 1 if report.errors else 0

    if args.cmd == "stamp":
        from harness.jobs.stamp import run_stamp

        cfg = load_config(cfg_path)
        journal_path = Path(args.journal) if args.journal else cfg.resolve_path(cfg.journal_path)
        journal = ActionJournal(journal_path)
        graph = resolve_graph_client(cfg)
        try:
            report = run_stamp(
                cfg=cfg,
                journal=journal,
                report_path=Path(args.report),
                limit=args.limit,
                graph=graph,
            )
        finally:
            journal.close()
            _close_graph(graph)
        print(
            f"run_id={report.run_id} scanned={report.scanned} stamped={report.stamped} "
            f"skipped={report.skipped} columns_written={report.columns_written} "
            f"columns_skipped={report.columns_skipped} embedded={report.embedded} "
            f"errors={report.errors}"
        )
        return 1 if report.errors else 0

    if args.cmd == "inventory":
        from harness.jobs.inventory import run_inventory

        cfg = load_config(cfg_path)
        journal_path = Path(args.journal) if args.journal else cfg.resolve_path(cfg.journal_path)
        journal = ActionJournal(journal_path)
        try:
            report = run_inventory(
                cfg=cfg,
                journal=journal,
                report_path=Path(args.report),
                roots=args.root,
                roots_file=Path(args.roots_file) if args.roots_file else None,
                limit=args.limit,
            )
        except ValueError as exc:
            print(exc)
            return 2
        finally:
            journal.close()
        print(
            f"run_id={report.run_id} scanned={report.scanned} "
            f"candidate_to_consume={report.candidate_to_consume} "
            f"skip_code={report.skip_code} skip_secret={report.skip_secret} "
            f"already_in_vince_personal={report.already_in_vince_personal} "
            f"copied={report.copied} uploaded={report.uploaded} "
            f"missing_roots={len(report.missing_roots)}"
        )
        if report.missing_roots:
            print("missing_roots=" + ",".join(report.missing_roots))
        if report.missing_roots and len(report.missing_roots) == len(report.roots):
            return 1
        return 0

    if args.cmd == "sync-audit":
        from harness.graph.folder_lister import build_live_lister, lister_from_cassette
        from harness.jobs.sync_audit import default_report_path, run_sync_audit

        cfg = load_config(cfg_path)
        try:
            if args.cassette:
                lister = lister_from_cassette(Path(args.cassette), backend=args.backend)
            else:
                token = os.environ.get("HARNESS_GRAPH_TOKEN") or os.environ.get("HARNESS_SP_TOKEN")
                lister = build_live_lister(
                    backend=args.backend,
                    token=token,
                    drive_id=os.environ.get("HARNESS_GRAPH_DRIVE_ID"),
                    site_url=os.environ.get("HARNESS_SP_SITE_URL"),
                    server_relative_root=os.environ.get("HARNESS_SP_SERVER_RELATIVE_ROOT"),
                    graph_base_url=os.environ.get(
                        "HARNESS_GRAPH_BASE_URL", "https://graph.microsoft.com/v1.0"
                    ),
                )
        except ValueError as exc:
            print(
                f"sync-audit needs a folder lister ({exc}). "
                "On VTA set HARNESS_GRAPH_TOKEN and HARNESS_GRAPH_DRIVE_ID "
                "(graph) or HARNESS_SP_SITE_URL, HARNESS_SP_SERVER_RELATIVE_ROOT, "
                "and HARNESS_SP_TOKEN (rest). Cloud VMs cannot see Vince Personal — "
                "use --cassette for fixture tests. This job never uploads, renames, or stamps.",
                file=sys.stderr,
            )
            return 1
        report_path = Path(args.report) if args.report else default_report_path()
        report = run_sync_audit(
            cfg=cfg,
            lister=lister,
            report_path=report_path,
            dry_run=bool(args.dry_run),
            hashes=bool(args.hashes),
            only=args.only,
        )
        print(
            f"run_id={report.run_id} backend={report.backend} dry_run={report.dry_run} "
            f"folders_walked={report.folders_walked} local_files={report.local_files} "
            f"server_files={report.server_files} local_only={len(report.local_only)} "
            f"server_only={len(report.server_only)} path_mismatches={len(report.path_mismatches)} "
            f"hash_mismatches={len(report.hash_mismatches)} skipped={report.skipped} "
            f"errors={len(report.errors)} report={report_path}"
        )
        return 1 if report.errors else 0

    if args.cmd == "fold":
        from harness.actions.fold import FoldApplyBlocked
        from harness.jobs.fold import run_fold

        cfg = load_config(cfg_path)
        journal_path = Path(args.journal) if args.journal else cfg.resolve_path(cfg.journal_path)
        journal = ActionJournal(journal_path)
        try:
            report = run_fold(
                cfg=cfg,
                journal=journal,
                report_path=Path(args.report),
                apply=bool(args.apply),
                only=args.only,
                limit=args.limit,
                source_root=Path(args.source_root) if args.source_root else None,
            )
        except FoldApplyBlocked as exc:
            print(f"fold_blocked: {exc}")
            return 2
        finally:
            journal.close()
        print(
            f"run_id={report.run_id} apply={report.apply} dry_run={report.dry_run} "
            f"planned={report.planned} moved={report.moved} "
            f"skipped_secret={report.skipped_secret} skipped_code={report.skipped_code} "
            f"errors={report.errors}"
        )
        return 1 if report.errors else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
