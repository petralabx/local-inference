from __future__ import annotations

from collections.abc import Callable

from harness.config import HarnessConfig
from harness.graph.auth import token_provider_for
from harness.graph.drive_client import GraphDriveClient
from harness.graph.live_client import LiveGraphDriveClient


def resolve_graph_client(
    cfg: HarnessConfig,
    *,
    interactive: bool | None = None,
    token_provider: Callable[[], str] | None = None,
    http=None,
) -> GraphDriveClient | None:
    """Return a live delegated client when credentials exist; else None (offline)."""
    if not cfg.graph.enabled:
        return None
    provider = token_provider or token_provider_for(cfg.graph, interactive=interactive)
    if provider is None:
        return None
    return LiveGraphDriveClient(
        token_provider=provider,
        site_url=cfg.graph.site_url,
        library=cfg.graph.library,
        sync_root=cfg.sync_root,
        http=http,
    )
