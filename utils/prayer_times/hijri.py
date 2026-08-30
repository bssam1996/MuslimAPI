"""Hijri payload formatting for the initial HJCoSA-compatible API response."""

from datetime import date as Date

from hijridate import Gregorian


_HIJRI_WEEKDAYS = (
    "Al Ithnayn",
    "Ath Thulatha",
    "Al Arbia",
    "Al Khamees",
    "Al Jumuah",
    "As Sabt",
    "Al Ahad",
)


def hijri_payload(on_date: Date) -> dict:
    """Return the AlAdhan-shaped Hijri date fields needed by Muslim.

    hijridate supplies the Umm al-Qura calendar data.  Its default result for
    the deployed API's reference date matches AlAdhan's HJCoSA date; calendar
    method variants are intentionally added in the subsequent calendar phase.
    """
    hijri = Gregorian(on_date.year, on_date.month, on_date.day).to_hijri()
    return {
        "date": f"{hijri.day:02d}-{hijri.month:02d}-{hijri.year:04d}",
        "format": "DD-MM-YYYY",
        "day": str(hijri.day),
        "weekday": {"en": _HIJRI_WEEKDAYS[on_date.weekday()]},
        "month": {
            "number": hijri.month,
            "en": hijri.month_name("en"),
            "days": hijri.month_length(),
        },
        "year": str(hijri.year),
        "designation": {"abbreviated": "AH", "expanded": "Anno Hegirae"},
        "holidays": [],
        "adjustedHolidays": [],
        "method": "HJCoSA",
    }
