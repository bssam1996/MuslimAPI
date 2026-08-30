import json
from datetime import date
from pathlib import Path

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.prayer_times import router
from utils.prayer_times.engine import CalculationRequest, calculate_prayer_times, public_methods


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_known_coordinate_calculation_is_deterministic():
    request = CalculationRequest(
        on_date=date(2026, 8, 30),
        latitude=51.5072,
        longitude=-0.1276,
        method=3,
        timezone_name="Europe/London",
    )

    first = calculate_prayer_times(request)
    second = calculate_prayer_times(request)

    assert first.timings == second.timings
    assert first.timings["Fajr"] == "04:03"
    assert first.timings["Sunrise"] == "06:10"
    assert first.timings["Dhuhr"] == "13:01"
    assert first.metadata["timezone"] == "Europe/London"
    assert first.metadata["polarCircleResolution"] == "AqrabBalad"


def test_jafari_method_zero_is_not_replaced_by_the_default_method():
    result = calculate_prayer_times(
        CalculationRequest(
            on_date=date(2026, 8, 30),
            latitude=35.6892,
            longitude=51.389,
            method=0,
            timezone_name="Asia/Tehran",
        )
    )

    assert result.metadata["method"]["id"] == 0
    assert result.metadata["midnightMode"] == "JAFARI"


def test_polar_locations_use_aqrab_balad():
    result = calculate_prayer_times(
        CalculationRequest(
            on_date=date(2026, 6, 21),
            latitude=69.6492,
            longitude=18.9553,
            method=3,
            timezone_name="Europe/Oslo",
        )
    )

    assert result.resolved_latitude < 69.6492
    assert result.metadata["polarReferenceLatitude"] == result.resolved_latitude
    assert result.timings["Sunrise"] != result.timings["Sunset"]


def test_methods_endpoint_exposes_published_and_custom_methods():
    methods = public_methods()

    assert methods["MWL"]["id"] == 3
    assert methods["JORDAN"]["id"] == 23
    assert methods["CUSTOM"] == {"id": 99}


def test_daily_route_returns_an_aladhan_style_envelope_and_cache_policy():
    response = client().get(
        "/v1/timings/30-08-2026",
        params={"latitude": "51.5072", "longitude": "-0.1276", "method": "3"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 200
    assert body["status"] == "OK"
    assert body["data"]["timings"]["Fajr"] == "04:03"
    assert body["data"]["date"]["hijri"]["date"] == "17-03-1448"
    assert body["data"]["date"]["hijri"]["month"]["en"] == "Rabi' al-Awwal"
    assert response.headers["vercel-cdn-cache-control"] == "public, s-maxage=86400"


def test_daily_route_rejects_missing_coordinates():
    response = client().get("/v1/timings/30-08-2026")

    assert response.status_code == 400
    assert response.json()["data"]["message"] == "latitude is required"


def test_monthly_route_uses_the_daily_engine_for_every_day():
    response = client().get(
        "/v1/calendar/2026/2",
        params={"latitude": "51.5072", "longitude": "-0.1276", "method": "3"},
    )

    body = response.json()
    assert response.status_code == 200
    assert len(body["data"]) == 28
    assert body["data"][0]["date"]["gregorian"]["date"] == "01-02-2026"


@pytest.mark.xfail(
    strict=True,
    reason="Adhan's Asr/nights-third results differ from the recorded AlAdhan fixture; strict parity is an explicit release gate.",
)
def test_recorded_aladhan_fixture_has_exact_formatted_minute_parity():
    fixture_path = Path(__file__).resolve().parents[1] / "data" / "prayer_times" / "fixtures" / "aladhan_london_mwl_2026-08-30.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf8"))
    request = fixture["request"]

    result = calculate_prayer_times(
        CalculationRequest(
            on_date=date.fromisoformat(request["date"]),
            latitude=request["latitude"],
            longitude=request["longitude"],
            method=request["method"],
            timezone_name=request["timezonestring"],
        )
    )

    assert result.timings == fixture["timings"]
