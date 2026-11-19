"""Helpers: conversions and condition mapping."""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def as_list(payload: Any) -> list[dict]:
    """IMD endpoints return a list, or {"data": [...]}, or a single dict."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [p for p in data if isinstance(p, dict)]
        return [payload]
    return []


def to_float(value: Any) -> float | None:
    try:
        if value in (None, "", "NA", "-", "--"):
            return None
        return float(str(value).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def condition_from_text(text: str | None) -> str | None:
    """Map IMD's text forecast (e.g. 'Partly cloudy sky') to an HA condition."""
    if not text:
        return None
    t = text.lower()
    rules = [
        ("thunder", "lightning-rainy"), ("hail", "hail"), ("snow", "snowy"),
        ("heavy rain", "pouring"), ("rain", "rainy"), ("drizzle", "rainy"),
        ("shower", "rainy"), ("fog", "fog"), ("mist", "fog"), ("haze", "fog"),
        ("dust", "windy"), ("squall", "windy"), ("partly cloudy", "partlycloudy"),
        ("cloud", "cloudy"), ("clear", "sunny"), ("sunny", "sunny"),
    ]
    for key, cond in rules:
        if key in t:
            return cond
    return None


def condition_from_wmo(code: Any) -> str | None:
    """Map WMO synop present-weather code (00-99) to an HA condition."""
    try:
        c = int(float(code))
    except (ValueError, TypeError):
        return None
    if c in (17, 29, 91, 92, 93, 94) or c >= 95:
        return "lightning-rainy"
    if c == 13:
        return "lightning"
    if c in (27, 79, 89, 90):
        return "hail"
    if c in (64, 65, 66, 67, 82):
        return "pouring"
    if c in (22, 26, 36, 37, 38, 39) or 70 <= c <= 78 or 83 <= c <= 88:
        return "snowy"
    if c in (14, 15, 16, 20, 21, 23, 24, 25) or 50 <= c <= 63 or 68 <= c <= 69 or 80 <= c <= 81:
        return "rainy"
    if c in (4, 5, 10, 11, 12, 28) or 40 <= c <= 49:
        return "fog"
    if c in (6, 7, 8, 9, 18, 19) or 30 <= c <= 35:
        return "windy"
    if c in (0, 1, 2):
        return "sunny"
    if c == 3:
        return "cloudy"
    return None
