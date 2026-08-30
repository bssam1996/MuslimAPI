"""Coordinate-based prayer times using the Adhan astronomical algorithm.

This module is intentionally independent of FastAPI.  Its solar calculations
are a Python port of batoulapps/adhan-js (MIT), whose high-precision equations
are based on Jean Meeus' *Astronomical Algorithms*.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date as Date
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from .timezone import resolve_timezone


ENGINE_VERSION = "adhan-python-port-1"
ADHAN_REFERENCE = "batoulapps/adhan-js main (retrieved 2026-08-30)"
SUNRISE_SUNSET_ANGLE = -50.0 / 60.0
TUNE_NAMES = (
    "Imsak",
    "Fajr",
    "Sunrise",
    "Dhuhr",
    "Asr",
    "Maghrib",
    "Sunset",
    "Isha",
    "Midnight",
)


class CalculationError(ValueError):
    """A validated calculation request cannot produce a timetable."""


@dataclass(frozen=True)
class Method:
    id: int
    key: str
    name: str
    fajr_angle: float
    isha_angle: float = 0.0
    isha_interval: int = 0
    maghrib_angle: float = 0.0
    maghrib_interval: int = 0
    midnight_mode: str = "STANDARD"
    moonsighting: bool = False

    def public_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {"Fajr": self.fajr_angle}
        if self.maghrib_interval:
            params["Maghrib"] = f"{self.maghrib_interval} min"
        elif self.maghrib_angle:
            params["Maghrib"] = self.maghrib_angle
        if self.isha_interval:
            params["Isha"] = f"{self.isha_interval} min"
        else:
            params["Isha"] = self.isha_angle
        if self.midnight_mode == "JAFARI":
            params["Midnight"] = "JAFARI"
        if self.moonsighting:
            params["shafaq"] = "general"
        return params


@lru_cache(maxsize=1)
def methods() -> tuple[dict[int, Method], str]:
    path = Path(__file__).resolve().parents[2] / "data" / "prayer_times" / "methods.json"
    raw = json.loads(path.read_text(encoding="utf8"))
    loaded = {
        entry["id"]: Method(
            id=entry["id"],
            key=entry["key"],
            name=entry["name"],
            fajr_angle=float(entry["fajr_angle"]),
            isha_angle=float(entry.get("isha_angle", 0)),
            isha_interval=int(entry.get("isha_interval", 0)),
            maghrib_angle=float(entry.get("maghrib_angle", 0)),
            maghrib_interval=int(entry.get("maghrib_interval", 0)),
            midnight_mode=entry.get("midnight_mode", "STANDARD"),
            moonsighting=bool(entry.get("moonsighting", False)),
        )
        for entry in raw["methods"]
    }
    return loaded, raw["version"]


def public_methods() -> dict[str, Any]:
    registry, _ = methods()
    response = {
        method.key: {
            "id": method.id,
            "name": method.name,
            "params": method.public_params(),
        }
        for method in registry.values()
    }
    response["CUSTOM"] = {"id": 99}
    return response


@dataclass(frozen=True)
class CalculationRequest:
    on_date: Date
    latitude: float
    longitude: float
    method: int = 3
    school: int = 0
    shafaq: str = "general"
    tune: tuple[int, ...] = field(default_factory=lambda: (0,) * len(TUNE_NAMES))
    midnight_mode: int | None = None
    latitude_adjustment_method: int = 3
    timezone_name: str | None = None
    method_settings: str | None = None


@dataclass(frozen=True)
class PrayerTimesResult:
    timings: dict[str, str]
    metadata: dict[str, Any]
    resolved_latitude: float


def _degrees_to_radians(value: float) -> float:
    return value * math.pi / 180.0


def _radians_to_degrees(value: float) -> float:
    return value * 180.0 / math.pi


def _normalize(value: float, maximum: float) -> float:
    return value - maximum * math.floor(value / maximum)


def _unwind(value: float) -> float:
    return _normalize(value, 360.0)


def _quadrant_shift(value: float) -> float:
    if -180 <= value <= 180:
        return value
    return value - 360 * round(value / 360)


def _safe_acos(value: float) -> float:
    if value < -1 or value > 1:
        return math.nan
    return math.acos(value)


def _julian_day(on_date: Date, hours: float = 0) -> float:
    year = on_date.year if on_date.month > 2 else on_date.year - 1
    month = on_date.month if on_date.month > 2 else on_date.month + 12
    day = on_date.day + hours / 24
    century = math.trunc(year / 100)
    correction = math.trunc(2 - century + math.trunc(century / 4))
    return math.trunc(365.25 * (year + 4716)) + math.trunc(30.6001 * (month + 1)) + day + correction - 1524.5


def _solar_coordinates(julian_day: float) -> tuple[float, float, float]:
    """Return declination, right ascension, and apparent sidereal time."""
    century = (julian_day - 2451545.0) / 36525
    mean_solar_longitude = _unwind(280.4664567 + 36000.76983 * century + 0.0003032 * century**2)
    mean_lunar_longitude = _unwind(218.3165 + 481267.8813 * century)
    ascending_node = _unwind(125.04452 - 1934.136261 * century + 0.0020708 * century**2 + century**3 / 450000)
    mean_anomaly = _unwind(357.52911 + 35999.05029 * century - 0.0001537 * century**2)
    anomaly_radians = _degrees_to_radians(mean_anomaly)
    equation_center = (
        (1.914602 - 0.004817 * century - 0.000014 * century**2) * math.sin(anomaly_radians)
        + (0.019993 - 0.000101 * century) * math.sin(2 * anomaly_radians)
        + 0.000289 * math.sin(3 * anomaly_radians)
    )
    omega = 125.04 - 1934.136 * century
    apparent_longitude = _unwind(mean_solar_longitude + equation_center - 0.00569 - 0.00478 * math.sin(_degrees_to_radians(omega)))
    mean_obliquity = 23.439291 - 0.013004167 * century - 0.0000001639 * century**2 + 0.0000005036 * century**3
    apparent_obliquity = _degrees_to_radians(mean_obliquity + 0.00256 * math.cos(_degrees_to_radians(omega)))
    longitude_radians = _degrees_to_radians(apparent_longitude)
    declination = _radians_to_degrees(math.asin(math.sin(apparent_obliquity) * math.sin(longitude_radians)))
    right_ascension = _unwind(_radians_to_degrees(math.atan2(math.cos(apparent_obliquity) * math.sin(longitude_radians), math.cos(longitude_radians))))
    mean_sidereal = _unwind(280.46061837 + 360.98564736629 * (julian_day - 2451545) + 0.000387933 * century**2 - century**3 / 38710000)
    nutation_longitude = (
        (-17.2 / 3600) * math.sin(_degrees_to_radians(ascending_node))
        - (1.32 / 3600) * math.sin(2 * _degrees_to_radians(mean_solar_longitude))
        - (0.23 / 3600) * math.sin(2 * _degrees_to_radians(mean_lunar_longitude))
        + (0.21 / 3600) * math.sin(2 * _degrees_to_radians(ascending_node))
    )
    nutation_obliquity = (
        (9.2 / 3600) * math.cos(_degrees_to_radians(ascending_node))
        + (0.57 / 3600) * math.cos(2 * _degrees_to_radians(mean_solar_longitude))
        + (0.1 / 3600) * math.cos(2 * _degrees_to_radians(mean_lunar_longitude))
        - (0.09 / 3600) * math.cos(2 * _degrees_to_radians(ascending_node))
    )
    apparent_sidereal = mean_sidereal + nutation_longitude * math.cos(_degrees_to_radians(mean_obliquity + nutation_obliquity))
    return declination, right_ascension, apparent_sidereal


@dataclass(frozen=True)
class _SolarTime:
    on_date: Date
    latitude: float
    longitude: float
    declination: float
    right_ascension: float
    sidereal_time: float
    previous_right_ascension: float
    next_right_ascension: float
    previous_declination: float
    next_declination: float
    transit: float
    sunrise: float
    sunset: float

    @classmethod
    def create(cls, on_date: Date, latitude: float, longitude: float) -> "_SolarTime":
        julian = _julian_day(on_date)
        declination, right_ascension, sidereal = _solar_coordinates(julian)
        previous_declination, previous_right_ascension, _ = _solar_coordinates(julian - 1)
        next_declination, next_right_ascension, _ = _solar_coordinates(julian + 1)
        approximate_transit = _normalize((right_ascension - longitude - sidereal) / 360, 1)
        expected_transit = _normalize((12.0 - longitude / 15.0) / 24.0, 1)
        if approximate_transit - expected_transit > 0.5:
            approximate_transit -= 1.0
        elif expected_transit - approximate_transit > 0.5:
            approximate_transit += 1.0
        provisional = cls(
            on_date, latitude, longitude, declination, right_ascension, sidereal,
            previous_right_ascension, next_right_ascension, previous_declination,
            next_declination, math.nan, math.nan, math.nan,
        )
        transit = provisional._corrected_transit(approximate_transit)
        sunrise = provisional._corrected_hour_angle(approximate_transit, SUNRISE_SUNSET_ANGLE, False)
        sunset = provisional._corrected_hour_angle(approximate_transit, SUNRISE_SUNSET_ANGLE, True)
        return cls(
            on_date, latitude, longitude, declination, right_ascension, sidereal,
            previous_right_ascension, next_right_ascension, previous_declination,
            next_declination, transit, sunrise, sunset,
        )

    def _interpolate(self, current: float, previous: float, following: float, factor: float) -> float:
        first = current - previous
        second = following - current
        return current + factor / 2 * (first + second + factor * (second - first))

    def _interpolate_angle(self, current: float, previous: float, following: float, factor: float) -> float:
        first = _unwind(current - previous)
        second = _unwind(following - current)
        return current + factor / 2 * (first + second + factor * (second - first))

    def _corrected_transit(self, approximate_transit: float) -> float:
        theta = _unwind(self.sidereal_time + 360.985647 * approximate_transit)
        ascension = _unwind(self._interpolate_angle(self.right_ascension, self.previous_right_ascension, self.next_right_ascension, approximate_transit))
        hour_angle = _quadrant_shift(theta + self.longitude - ascension)
        return (approximate_transit + hour_angle / -360) * 24

    def _corrected_hour_angle(self, approximate_transit: float, angle: float, after_transit: bool) -> float:
        term1 = math.sin(_degrees_to_radians(angle)) - math.sin(_degrees_to_radians(self.latitude)) * math.sin(_degrees_to_radians(self.declination))
        term2 = math.cos(_degrees_to_radians(self.latitude)) * math.cos(_degrees_to_radians(self.declination))
        hour_angle = _radians_to_degrees(_safe_acos(term1 / term2))
        if not math.isfinite(hour_angle):
            return math.nan
        fraction = approximate_transit + hour_angle / 360 if after_transit else approximate_transit - hour_angle / 360
        theta = _unwind(self.sidereal_time + 360.985647 * fraction)
        ascension = _unwind(self._interpolate_angle(self.right_ascension, self.previous_right_ascension, self.next_right_ascension, fraction))
        declination = self._interpolate(self.declination, self.previous_declination, self.next_declination, fraction)
        local_hour_angle = theta + self.longitude - ascension
        altitude = _radians_to_degrees(math.asin(
            math.sin(_degrees_to_radians(self.latitude)) * math.sin(_degrees_to_radians(declination))
            + math.cos(_degrees_to_radians(self.latitude)) * math.cos(_degrees_to_radians(declination)) * math.cos(_degrees_to_radians(local_hour_angle))
        ))
        correction_denominator = 360 * math.cos(_degrees_to_radians(declination)) * math.cos(_degrees_to_radians(self.latitude)) * math.sin(_degrees_to_radians(local_hour_angle))
        if correction_denominator == 0:
            return math.nan
        return (fraction + (altitude - angle) / correction_denominator) * 24

    def hour_angle(self, angle: float, after_transit: bool) -> float:
        approximate_transit = _normalize((self.right_ascension - self.longitude - self.sidereal_time) / 360, 1)
        expected_transit = _normalize((12.0 - self.longitude / 15.0) / 24.0, 1)
        if approximate_transit - expected_transit > 0.5:
            approximate_transit -= 1.0
        elif expected_transit - approximate_transit > 0.5:
            approximate_transit += 1.0
        return self._corrected_hour_angle(approximate_transit, angle, after_transit)

    def afternoon(self, shadow_length: int) -> float:
        tangent = abs(self.latitude - self.declination)
        inverse = shadow_length + math.tan(_degrees_to_radians(tangent))
        return self.hour_angle(_radians_to_degrees(math.atan(1.0 / inverse)), True)


def _is_valid_solar(solar: _SolarTime) -> bool:
    return math.isfinite(solar.sunrise) and math.isfinite(solar.sunset)


def _resolve_polar(on_date: Date, latitude: float, longitude: float) -> tuple[_SolarTime, _SolarTime, float]:
    solar = _SolarTime.create(on_date, latitude, longitude)
    tomorrow = _SolarTime.create(on_date + timedelta(days=1), latitude, longitude)
    if _is_valid_solar(solar) and _is_valid_solar(tomorrow):
        return solar, tomorrow, latitude

    candidate = latitude - math.copysign(0.5, latitude if latitude else 1)
    while abs(candidate) >= 65:
        solar = _SolarTime.create(on_date, candidate, longitude)
        tomorrow = _SolarTime.create(on_date + timedelta(days=1), candidate, longitude)
        if _is_valid_solar(solar) and _is_valid_solar(tomorrow):
            return solar, tomorrow, candidate
        candidate -= math.copysign(0.5, latitude if latitude else 1)
    raise CalculationError("No usable solar event could be resolved with the AqrabBalad policy")


def _time_from_utc_hour(on_date: Date, utc_hour: float, timezone_info) -> datetime:
    if not math.isfinite(utc_hour):
        raise CalculationError("The requested solar event does not exist")
    utc = datetime.combine(on_date, time.min, tzinfo=timezone.utc) + timedelta(hours=utc_hour)
    return utc.astimezone(timezone_info)


def _optional_time_from_utc_hour(on_date: Date, utc_hour: float, timezone_info) -> datetime | None:
    return None if not math.isfinite(utc_hour) else _time_from_utc_hour(on_date, utc_hour, timezone_info)


def _round_minute(value: datetime, rounding: str = "nearest") -> datetime:
    seconds = value.second + value.microsecond / 1_000_000
    if rounding == "up":
        adjustment = 60 - seconds if seconds else 0
    elif rounding == "nearest":
        adjustment = 60 - seconds if seconds >= 30 else -seconds
    else:
        adjustment = 0
    return (value + timedelta(seconds=adjustment)).replace(microsecond=0)


def _night_portion(method: int, fajr_angle: float, isha_angle: float) -> tuple[float, float]:
    if method == 1:  # Middle of the night.
        return 1 / 2, 1 / 2
    if method == 2:  # One seventh.
        return 1 / 7, 1 / 7
    return fajr_angle / 60, isha_angle / 60


def _season_adjusted_twilight(latitude: float, day_of_year: int, year: int, event: datetime, morning: bool, shafaq: str) -> datetime:
    if morning:
        values = (75 + 28.65 / 55 * abs(latitude), 75 + 19.44 / 55 * abs(latitude), 75 + 32.74 / 55 * abs(latitude), 75 + 48.1 / 55 * abs(latitude))
    elif shafaq == "ahmer":
        values = (62 + 17.4 / 55 * abs(latitude), 62 - 7.16 / 55 * abs(latitude), 62 + 5.12 / 55 * abs(latitude), 62 + 19.44 / 55 * abs(latitude))
    elif shafaq == "abyad":
        values = (75 + 25.6 / 55 * abs(latitude), 75 + 7.16 / 55 * abs(latitude), 75 + 36.84 / 55 * abs(latitude), 75 + 81.84 / 55 * abs(latitude))
    else:
        values = (75 + 25.6 / 55 * abs(latitude), 75 + 2.05 / 55 * abs(latitude), 75 - 9.21 / 55 * abs(latitude), 75 + 6.14 / 55 * abs(latitude))
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days_in_year = 366 if leap else 365
    since_solstice = day_of_year + 10 if latitude >= 0 else day_of_year - (173 if leap else 172)
    since_solstice %= days_in_year
    a, b, c, d = values
    if since_solstice < 91:
        adjustment = a + (b - a) / 91 * since_solstice
    elif since_solstice < 137:
        adjustment = b + (c - b) / 46 * (since_solstice - 91)
    elif since_solstice < 183:
        adjustment = c + (d - c) / 46 * (since_solstice - 137)
    elif since_solstice < 229:
        adjustment = d + (c - d) / 46 * (since_solstice - 183)
    elif since_solstice < 275:
        adjustment = c + (b - c) / 46 * (since_solstice - 229)
    else:
        adjustment = b + (a - b) / 91 * (since_solstice - 275)
    return event + timedelta(minutes=(-adjustment if morning else adjustment))


def _method_for_request(request: CalculationRequest) -> Method:
    if request.method == 99:
        if not request.method_settings:
            raise CalculationError("methodSettings is required when method is 99")
        parts = [part.strip() for part in request.method_settings.split(",")]
        if len(parts) != 3:
            raise CalculationError("methodSettings must contain Fajr, Maghrib, and Isha values")
        try:
            fajr = float(parts[0]) if parts[0] and parts[0].lower() != "null" else 18.0
            maghrib = float(parts[1]) if parts[1] and parts[1].lower() != "null" else 0.0
            isha = float(parts[2]) if parts[2] and parts[2].lower() != "null" else 17.0
        except ValueError as exc:
            raise CalculationError("methodSettings values must be numbers or null") from exc
        return Method(99, "CUSTOM", "Custom", fajr, isha_angle=isha, maghrib_angle=maghrib)
    registry, _ = methods()
    method = registry.get(request.method)
    if method is None:
        raise CalculationError(f"Unsupported calculation method: {request.method}")
    return method


def calculate_prayer_times(request: CalculationRequest) -> PrayerTimesResult:
    if not -90 <= request.latitude <= 90 or not -180 <= request.longitude <= 180:
        raise CalculationError("latitude or longitude is outside its valid range")
    if request.school not in (0, 1):
        raise CalculationError("school must be 0 (Shafi) or 1 (Hanafi)")
    if request.shafaq not in ("general", "ahmer", "abyad"):
        raise CalculationError("shafaq must be general, ahmer, or abyad")
    if request.latitude_adjustment_method not in (1, 2, 3):
        raise CalculationError("latitudeAdjustmentMethod must be 1, 2, or 3")
    if request.midnight_mode not in (None, 0, 1):
        raise CalculationError("midnightMode must be 0 (standard) or 1 (Jafari)")
    if len(request.tune) != len(TUNE_NAMES):
        raise CalculationError("tune must contain exactly nine minute offsets")

    method = _method_for_request(request)
    timezone_info, timezone_name, timezone_source = resolve_timezone(request.latitude, request.longitude, request.timezone_name)
    solar, tomorrow_solar, resolved_latitude = _resolve_polar(request.on_date, request.latitude, request.longitude)
    tomorrow = request.on_date + timedelta(days=1)
    sunrise = _time_from_utc_hour(request.on_date, solar.sunrise, timezone_info)
    sunset = _time_from_utc_hour(request.on_date, solar.sunset, timezone_info)
    dhuhr = _time_from_utc_hour(request.on_date, solar.transit, timezone_info)
    asr = _time_from_utc_hour(request.on_date, solar.afternoon(2 if request.school else 1), timezone_info)
    tomorrow_sunrise = _time_from_utc_hour(tomorrow, tomorrow_solar.sunrise, timezone_info)
    night = tomorrow_sunrise - sunset
    fajr = _optional_time_from_utc_hour(request.on_date, solar.hour_angle(-method.fajr_angle, False), timezone_info)
    if method.moonsighting and request.latitude >= 55:
        fajr = sunrise - night / 7
    if method.moonsighting:
        safe_fajr = _season_adjusted_twilight(resolved_latitude, request.on_date.timetuple().tm_yday, request.on_date.year, sunrise, True, request.shafaq)
    else:
        fajr_portion, _ = _night_portion(request.latitude_adjustment_method, method.fajr_angle, method.isha_angle)
        safe_fajr = sunrise - night * fajr_portion
    if fajr is None or fajr < safe_fajr:
        fajr = safe_fajr

    if method.isha_interval:
        isha = sunset + timedelta(minutes=method.isha_interval)
    else:
        isha = _optional_time_from_utc_hour(request.on_date, solar.hour_angle(-method.isha_angle, True), timezone_info)
        if method.moonsighting and request.latitude >= 55:
            isha = sunset + night / 7
        if method.moonsighting:
            safe_isha = _season_adjusted_twilight(resolved_latitude, request.on_date.timetuple().tm_yday, request.on_date.year, sunset, False, request.shafaq)
        else:
            _, isha_portion = _night_portion(request.latitude_adjustment_method, method.fajr_angle, method.isha_angle)
            safe_isha = sunset + night * isha_portion
        if isha is None or isha > safe_isha:
            isha = safe_isha

    maghrib = sunset + timedelta(minutes=method.maghrib_interval)
    if method.maghrib_angle:
        angle_maghrib = _time_from_utc_hour(request.on_date, solar.hour_angle(-method.maghrib_angle, True), timezone_info)
        if sunset < angle_maghrib < isha:
            maghrib = angle_maghrib

    midnight_mode = request.midnight_mode
    if midnight_mode is None:
        midnight_mode = 1 if method.midnight_mode == "JAFARI" else 0
    midnight_end = fajr if midnight_mode == 1 else tomorrow_sunrise
    midnight = sunset + (midnight_end - sunset) / 2
    imsak = fajr - timedelta(minutes=10)

    base_values = {
        "Imsak": imsak,
        "Fajr": fajr,
        "Sunrise": sunrise,
        "Dhuhr": dhuhr,
        "Asr": asr,
        "Sunset": sunset,
        "Maghrib": maghrib,
        "Isha": isha,
        "Midnight": midnight,
        "Firstthird": sunset + (midnight_end - sunset) / 3,
        "Lastthird": sunset + (midnight_end - sunset) * 2 / 3,
    }
    values = {
        name: _round_minute(base_values[name] + timedelta(minutes=request.tune[index]), "nearest")
        for index, name in enumerate(TUNE_NAMES)
    }
    # Tune does not apply to the third-night helper fields.
    values["Firstthird"] = _round_minute(base_values["Firstthird"])
    values["Lastthird"] = _round_minute(base_values["Lastthird"])
    timings = {name: value.strftime("%H:%M") for name, value in values.items()}
    registry_version = methods()[1]
    metadata = {
        "latitude": request.latitude,
        "longitude": request.longitude,
        "timezone": timezone_name,
        "timezoneSource": timezone_source,
        "method": {"id": method.id, "name": method.name, "params": method.public_params()},
        "school": "Hanafi" if request.school else "Shafi",
        "midnightMode": "JAFARI" if midnight_mode else "STANDARD",
        "latitudeAdjustmentMethod": request.latitude_adjustment_method,
        "shafaq": request.shafaq,
        "polarCircleResolution": "AqrabBalad",
        "polarReferenceLatitude": resolved_latitude,
        "engineVersion": ENGINE_VERSION,
        "methodRegistryVersion": registry_version,
        "adhanReference": ADHAN_REFERENCE,
    }
    return PrayerTimesResult(timings, metadata, resolved_latitude)
