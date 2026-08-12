from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

from harness.journal.store import ActionJournal


@dataclass
class ProvenanceHit:
    content_hash: str | None
    current_path: str | None
    prior_paths: list[str]
    run_ids: list[str]

    def __str__(self) -> str:
        priors = " <- ".join(self.prior_paths) if self.prior_paths else "(none)"
        return (
            f"hash={self.content_hash or '?'} current={self.current_path or '?'} "
            f"history={priors} runs={','.join(self.run_ids) or '-'}"
        )


class ProvenanceStore:
    """NetworkX projection rebuilt from the SQLite journal (phase-0 KG)."""

    def __init__(self, graph: nx.DiGraph) -> None:
        self.graph = graph

    @classmethod
    def from_journal(cls, journal: ActionJournal) -> ProvenanceStore:
        g: nx.DiGraph = nx.DiGraph()
        # Walk all runs/actions — simple full rebuild
        rows = journal._conn.execute(
            "SELECT run_id, action_type, payload_json FROM actions "
            "WHERE reversed = 0 ORDER BY id ASC"
        ).fetchall()
        import json

        for run_id, action_type, payload_json in rows:
            payload = json.loads(payload_json)
            if action_type not in {"move", "rename"}:
                continue
            frm = payload["from"]
            to = payload["to"]
            digest = payload.get("sha256")
            g.add_node(frm, kind="path")
            g.add_node(to, kind="path")
            g.add_edge(frm, to, run_id=run_id, sha256=digest, action=action_type)
            if digest:
                hnode = f"hash:{digest}"
                g.add_node(hnode, kind="hash", sha256=digest)
                g.add_edge(hnode, to, run_id=run_id, rel="located_at")
        return cls(g)

    def lookup(
        self,
        *,
        path: str | None = None,
        name: str | None = None,
        content_hash: str | None = None,
    ) -> list[ProvenanceHit]:
        hits: list[ProvenanceHit] = []
        if content_hash:
            hnode = f"hash:{content_hash}"
            if hnode in self.graph:
                currents = [
                    n
                    for n in self.graph.successors(hnode)
                    if self.graph.nodes[n].get("kind") == "path"
                ]
                for cur in currents or [None]:
                    hits.append(self._hit_for_path(cur, content_hash))
            return hits

        candidates: list[str] = []
        if path and path in self.graph:
            candidates.append(path)
        if name:
            needle = name.lower()
            for n, data in self.graph.nodes(data=True):
                if data.get("kind") == "path" and needle in str(n).lower():
                    candidates.append(str(n))
        # Also match path as a historical node
        for c in list(candidates):
            hits.append(self._hit_for_path(c, None))
        # de-dupe by current path
        seen: set[str] = set()
        uniq: list[ProvenanceHit] = []
        for h in hits:
            key = h.current_path or "|".join(h.prior_paths)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(h)
        return uniq

    def _hit_for_path(self, path: str | None, digest: str | None) -> ProvenanceHit:
        if path is None:
            return ProvenanceHit(digest, None, [], [])
        # Follow outbound move edges to tip
        current = path
        seen_nodes = {path}
        while True:
            outs = [
                (v, d)
                for _, v, d in self.graph.out_edges(current, data=True)
                if d.get("action") in {"move", "rename"}
            ]
            if not outs:
                break
            nxt = outs[-1][0]
            if nxt in seen_nodes:
                break
            seen_nodes.add(nxt)
            current = nxt
        # Walk predecessors for history
        history: list[str] = []
        run_ids: list[str] = []
        node = current
        visited: set[str] = set()
        while True:
            preds = [
                (u, d)
                for u, _, d in self.graph.in_edges(node, data=True)
                if d.get("action") in {"move", "rename"}
            ]
            if not preds:
                break
            prev, data = preds[-1]
            if prev in visited:
                break
            visited.add(prev)
            history.append(prev)
            if data.get("run_id"):
                run_ids.append(data["run_id"])
            if not digest and data.get("sha256"):
                digest = data["sha256"]
            node = prev
        history.reverse()
        if path != current and path not in history:
            # query was a prior path
            if path not in history:
                history.insert(0, path)
        return ProvenanceHit(digest, current, history, run_ids)
