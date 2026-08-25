from __future__ import annotations

from typing import Any

__all__ = [
    "HarvestStamp",
    "StampResult",
    "party_for_document",
    "write_embedded_properties",
]


def __getattr__(name: str) -> Any:
    # Eager imports here re-enter embed while drain→inbox is still loading harvest.
    if name == "write_embedded_properties":
        from harness.stamp.embed import write_embedded_properties

        return write_embedded_properties
    if name in {"HarvestStamp", "StampResult", "party_for_document"}:
        from harness.stamp.harvest import HarvestStamp, StampResult, party_for_document

        return {
            "HarvestStamp": HarvestStamp,
            "StampResult": StampResult,
            "party_for_document": party_for_document,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
