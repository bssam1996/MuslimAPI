"""Offline coordinate-to-timezone resolution for prayer calculations."""

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from timezonefinder import TimezoneFinder


class TimezoneResolutionError(ValueError):
    """Raised when a requested IANA timezone is unknown."""


_finder = TimezoneFinder(in_memory=False)


@lru_cache(maxsize=4096)
def resolve_timezone(latitude: float, longitude: float, override: str | None = None) -> tuple[ZoneInfo, str, str]:
    """Return a ZoneInfo, canonical name, and source for coordinates.

    Coordinates are rounded only for the resolver cache. Prayer mathematics keeps
    the caller's original precision.
    """
    if override:
        try:
            return ZoneInfo(override), override, "request"
        except ZoneInfoNotFoundError as exc:
            raise TimezoneResolutionError(f"Unknown IANA timezone: {override}") from exc

    timezone_name = _finder.timezone_at(lat=latitude, lng=longitude)
    if timezone_name:
        try:
            return ZoneInfo(timezone_name), timezone_name, "coordinates"
        except ZoneInfoNotFoundError:
            # The bundled tzdata package should make this exceptional, but falling
            # back keeps ocean-coordinate requests deterministic.
            pass

    return ZoneInfo("Etc/UTC"), "Etc/UTC", "fallback_utc"
