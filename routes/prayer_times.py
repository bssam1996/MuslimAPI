"""Public coordinate-only prayer-time routes."""

from __future__ import annotations

import calendar
from datetime import date as Date
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from utils.prayer_times.engine import (
    CalculationError,
    CalculationRequest,
    TUNE_NAMES,
    calculate_prayer_times,
    public_methods,
)
from utils.prayer_times.timezone import TimezoneResolutionError, resolve_timezone


router = APIRouter(prefix="/v1", tags=["Prayer Times"])


class PrayerRequestError(ValueError):
    """A request is syntactically valid HTTP but invalid for this API."""


def _error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": status_code, "status": "BAD_REQUEST", "data": {"message": message}})


def _parse_date(value: str, latitude: float, longitude: float, timezone_name: str | None) -> Date:
    if value.lower() == "today":
        timezone_info, _, _ = resolve_timezone(latitude, longitude, timezone_name)
        return datetime.now(timezone_info).date()
    try:
        return datetime.strptime(value, "%d-%m-%Y").date()
    except ValueError as exc:
        raise PrayerRequestError("date must be DD-MM-YYYY or today") from exc


def _float(name: str, value: str | None) -> float:
    if value is None or value == "":
        raise PrayerRequestError(f"{name} is required")
    try:
        return float(value)
    except ValueError as exc:
        raise PrayerRequestError(f"{name} must be a number") from exc


def _integer(name: str, value: str | None, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise PrayerRequestError(f"{name} must be an integer") from exc


def _parse_tune(value: str | None) -> tuple[int, ...]:
    if not value:
        return (0,) * len(TUNE_NAMES)
    parts = value.split(",")
    if len(parts) > len(TUNE_NAMES):
        raise PrayerRequestError("tune can contain at most nine comma-separated minute offsets")
    try:
        offsets = tuple(int(part.strip() or "0") for part in parts)
    except ValueError as exc:
        raise PrayerRequestError("tune must contain integer minute offsets") from exc
    return offsets + (0,) * (len(TUNE_NAMES) - len(offsets))


def _request_from_values(
    date_value: str,
    latitude: str | None,
    longitude: str | None,
    method: str | None,
    school: str | None,
    shafaq: str | None,
    tune: str | None,
    midnight_mode: str | None,
    latitude_adjustment_method: str | None,
    timezone_name: str | None,
    method_settings: str | None,
) -> CalculationRequest:
    parsed_latitude = _float("latitude", latitude)
    parsed_longitude = _float("longitude", longitude)
    parsed_timezone_name = timezone_name or None
    parsed_method = _integer("method", method, 3)
    parsed_school = _integer("school", school, 0)
    parsed_latitude_adjustment = _integer("latitudeAdjustmentMethod", latitude_adjustment_method, 3)
    return CalculationRequest(
        on_date=_parse_date(date_value, parsed_latitude, parsed_longitude, parsed_timezone_name),
        latitude=parsed_latitude,
        longitude=parsed_longitude,
        method=3 if parsed_method is None else parsed_method,
        school=0 if parsed_school is None else parsed_school,
        shafaq=(shafaq or "general").lower(),
        tune=_parse_tune(tune),
        midnight_mode=_integer("midnightMode", midnight_mode),
        latitude_adjustment_method=3 if parsed_latitude_adjustment is None else parsed_latitude_adjustment,
        timezone_name=parsed_timezone_name,
        method_settings=method_settings,
    )


def _headers() -> dict[str, str]:
    # Prayer times are deterministic for a complete path/query.  Browser caching
    # remains short, while Vercel's CDN absorbs repeated public requests.
    return {
        "Cache-Control": "public, max-age=300",
        "Vercel-CDN-Cache-Control": "public, s-maxage=86400",
    }


def _date_payload(on_date: Date, result) -> dict:
    return {
        "readable": on_date.strftime("%d %b %Y"),
        "timestamp": str(int(datetime.combine(on_date, datetime.min.time(), tzinfo=timezone.utc).timestamp())),
        "gregorian": {
            "date": on_date.strftime("%d-%m-%Y"),
            "format": "DD-MM-YYYY",
            "day": str(on_date.day),
            "weekday": {"en": on_date.strftime("%A")},
            "month": {"number": on_date.month, "en": on_date.strftime("%B")},
            "year": str(on_date.year),
        },
        "hijri": None,
    }


def _payload(on_date: Date, result) -> dict:
    return {"timings": result.timings, "date": _date_payload(on_date, result), "meta": result.metadata}


@router.get("/methods")
async def get_methods():
    return JSONResponse(status_code=200, content={"code": 200, "status": "OK", "data": public_methods()}, headers=_headers())


@router.get("/timings/{date_value}")
async def get_timings(
    date_value: str,
    latitude: str | None = None,
    longitude: str | None = None,
    method: str | None = None,
    school: str | None = None,
    shafaq: str | None = None,
    tune: str | None = None,
    midnightMode: str | None = None,
    latitudeAdjustmentMethod: str | None = None,
    timezonestring: str | None = None,
    methodSettings: str | None = None,
):
    try:
        calculation_request = _request_from_values(
            date_value, latitude, longitude, method, school, shafaq, tune,
            midnightMode, latitudeAdjustmentMethod, timezonestring, methodSettings,
        )
        result = calculate_prayer_times(calculation_request)
    except (PrayerRequestError, CalculationError, TimezoneResolutionError) as exc:
        return _error(str(exc))
    return JSONResponse(status_code=200, content={"code": 200, "status": "OK", "data": _payload(calculation_request.on_date, result)}, headers=_headers())


@router.get("/calendar/{year}/{month}")
async def get_calendar(
    year: int,
    month: int,
    latitude: str | None = None,
    longitude: str | None = None,
    method: str | None = None,
    school: str | None = None,
    shafaq: str | None = None,
    tune: str | None = None,
    midnightMode: str | None = None,
    latitudeAdjustmentMethod: str | None = None,
    timezonestring: str | None = None,
    methodSettings: str | None = None,
):
    if not 1 <= month <= 12 or not 1 <= year <= 9999:
        return _error("year or month is outside its valid range")
    try:
        first = _request_from_values(
            f"01-{month:02d}-{year:04d}", latitude, longitude, method, school, shafaq, tune,
            midnightMode, latitudeAdjustmentMethod, timezonestring, methodSettings,
        )
        days = calendar.monthrange(year, month)[1]
        entries = []
        for day in range(1, days + 1):
            request_for_day = CalculationRequest(**{**first.__dict__, "on_date": Date(year, month, day)})
            entries.append(_payload(request_for_day.on_date, calculate_prayer_times(request_for_day)))
    except (PrayerRequestError, CalculationError, TimezoneResolutionError) as exc:
        return _error(str(exc))
    return JSONResponse(status_code=200, content={"code": 200, "status": "OK", "data": entries}, headers=_headers())
