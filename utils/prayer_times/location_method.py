"""Offline coordinate-based defaults for prayer-time calculation methods."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .timezone import resolve_timezone


@dataclass(frozen=True)
class MethodResolution:
    """The method selected when a request does not provide one."""

    method: int
    selection: str
    timezone: str
    region: str | None = None

    def metadata(self) -> dict[str, str]:
        response = {"selection": self.selection, "timezone": self.timezone}
        if self.region:
            response["region"] = self.region
        return response


@lru_cache(maxsize=1)
def _location_defaults() -> dict:
    path = Path(__file__).resolve().parents[2] / "data" / "prayer_times" / "location_defaults.json"
    return json.loads(path.read_text(encoding="utf8"))


def default_method_for_coordinates(latitude: float, longitude: float) -> MethodResolution:
    """Return the configured authority for the location, or MWL as fallback.

    The timezone lookup is based on the supplied coordinates, never a client
    timezone override.  This makes automatic method selection deterministic and
    prevents an arbitrary ``timezonestring`` from changing the chosen authority.
    """
    _, timezone_name, _ = resolve_timezone(latitude, longitude)
    defaults = _location_defaults()
    entry = defaults["timezone_methods"].get(timezone_name)
    if entry:
        return MethodResolution(
            method=int(entry["method"]),
            selection="location_default",
            timezone=timezone_name,
            region=entry.get("region"),
        )
    return MethodResolution(
        method=int(defaults["fallback_method"]),
        selection="fallback",
        timezone=timezone_name,
    )
