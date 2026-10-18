"""External maintenance feed: fake and live backends.

The feed reports third-party fiber maintenance windows that may explain
alarm bursts. ``FakeFiberFeed`` is seeded and deterministic. ``LiveFiberFeed``
is a stub: it returns an explicit gap result instead of hallucinating, and
documents the interface a real provider adapter must implement.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MaintenanceWindow:
    provider: str  # fictional third-party name
    region: str
    start_min: int
    end_min: int
    description: str


@dataclass
class FeedResult:
    ok: bool
    windows: list[MaintenanceWindow]
    gap: str = ""  # non-empty when this is an explicit gap, not data


class FakeFiberFeed:
    """Deterministic seeded feed for tests and offline demos."""

    WINDOWS = [
        MaintenanceWindow("NorthLine Fiber Co", "NORTH", 0, 240,
                          "Planned splice on the north ring"),
        MaintenanceWindow("WestSpan Telecom", "WEST", 60, 180,
                          "Emergency pole replacement"),
    ]

    def fetch(self, region: str) -> FeedResult:
        return FeedResult(
            ok=True,
            windows=[w for w in self.WINDOWS if w.region == region.upper()],
        )


class LiveFiberFeed:
    """Stub for a real provider adapter.

    A production implementation must implement ``fetch(region)`` returning
    ``FeedResult`` and MUST return ``ok=False`` with a ``gap`` explanation on
    any transport/auth failure — never synthesized windows.
    """

    def fetch(self, region: str) -> FeedResult:  # noqa: ARG002
        return FeedResult(
            ok=False, windows=[],
            gap=("live fiber-maintenance feed is not configured in this "
                 "build; connect a provider adapter to enable it"),
        )
