"""Deterministic coordinate-based Islamic prayer-time calculations.

The implementation is a Python port of the MIT-licensed Adhan reference
algorithm.  The source revision and method data are pinned in this service so
the API can be tested and reproduced without calling an upstream provider.
"""

from .engine import CalculationRequest, PrayerTimesResult, calculate_prayer_times

__all__ = ["CalculationRequest", "PrayerTimesResult", "calculate_prayer_times"]
