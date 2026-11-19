"""Sensors for warnings, nowcast, rainfall, marine, cyclone and astronomy."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    K_ASTRO, K_CYCLONE, K_FORECAST, K_MARINE, K_NOWCAST, K_RAINFALL,
    K_SUBDIV_WARNING, K_WARNING, NOWCAST_COLORS, WARNING_CODES, WARNING_COLORS,
)
from .util import to_float
from .weather import device_info

IST = "Asia/Kolkata"


def _warning_text(codes: Any) -> str:
    out = []
    for c in str(codes or "").split(","):
        c = c.strip()
        if c.isdigit():
            out.append(WARNING_CODES.get(int(c), c))
    return ", ".join(out) or "No Warning"


def _ist_time(value: Any) -> datetime | None:
    """'06:45' -> today's aware datetime in IST."""
    try:
        h, m = str(value).split(":")[:2]
        tz = dt_util.get_time_zone(IST)
        return datetime.combine(dt_util.now(tz).date(), time(int(h), int(m)), tzinfo=tz)
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True, kw_only=True)
class IMDSensorDescription(SensorEntityDescription):
    key_coordinator: str
    value_fn: Callable[[Any], Any]
    attrs_fn: Callable[[Any], dict[str, Any]] | None = None


def _warn_day(n: int):
    return lambda d: _warning_text(d.get(f"Day_{n}"))


def _color(value: Any) -> str | None:
    n = to_float(value)
    return WARNING_COLORS.get(int(n)) if n is not None else None


def _warn_attrs(d: dict) -> dict:
    out: dict[str, Any] = {
        f"day_{n}": {
            "warning": _warning_text(d.get(f"Day_{n}")),
            "color": _color(d.get(f"Day{n}_Color")),
        }
        for n in range(1, 6)
    }
    out.update(issued=d.get("Date"), issued_utc=d.get("UTC"))
    return out


SENSORS: tuple[IMDSensorDescription, ...] = (
    # --- Warnings
    IMDSensorDescription(
        key="warning_today", translation_key="warning_today", name="Warning today",
        key_coordinator=K_WARNING, icon="mdi:alert", value_fn=_warn_day(1), attrs_fn=_warn_attrs,
    ),
    IMDSensorDescription(
        key="subdivision_warning", name="Subdivision warning today",
        key_coordinator=K_SUBDIV_WARNING, icon="mdi:alert-circle-outline",
        value_fn=lambda d: d.get("day1_warning") or "No Warning",
        attrs_fn=lambda d: {k: v for k, v in d.items() if k.startswith(("day", "date", "SUBDIV"))},
    ),
    # --- Nowcast
    IMDSensorDescription(
        key="nowcast", name="Nowcast", key_coordinator=K_NOWCAST, icon="mdi:weather-lightning-rainy",
        value_fn=lambda d: (str(d.get("message") or "No weather")[:250]),
        attrs_fn=lambda d: {
            "issued_at": d.get("toi"), "valid_upto": d.get("Vupto"),
            "severity": NOWCAST_COLORS.get(int(to_float(d.get("color")) or 0)),
            "date": d.get("Date"),
        },
    ),
    # --- Rainfall
    IMDSensorDescription(
        key="rain_daily", name="Rainfall today", key_coordinator=K_RAINFALL,
        native_unit_of_measurement="mm", device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: to_float(d.get("Daily Actual")),
        attrs_fn=lambda d: {k: v for k, v in d.items() if k not in ("Daily Actual",)},
    ),
    # --- Cyclone
    IMDSensorDescription(
        key="cyclone", name="Cyclone", key_coordinator=K_CYCLONE, icon="mdi:weather-hurricane",
        value_fn=lambda d: (
            ((d.get("data") or {}).get("observed") or [{}])[-1].get("CYCLONE_NAME", "None")
            if (d.get("data") or {}).get("observed") else "None"
        ),
        attrs_fn=lambda d: {
            "observed": (d.get("data") or {}).get("observed", []),
            "forecast": (d.get("data") or {}).get("forecast", []),
        },
    ),
    # --- Marine
    IMDSensorDescription(
        key="marine", name="Marine bulletins", key_coordinator=K_MARINE, icon="mdi:waves",
        value_fn=lambda d: len(d.get("sea", [])) + len(d.get("coastal", [])),
        attrs_fn=lambda d: {"sea": d.get("sea", [])[:12], "coastal": d.get("coastal", [])[:12]},
    ),
    # --- Astronomical
    *(
        IMDSensorDescription(
            key=k, name=n, key_coordinator=K_ASTRO, device_class=SensorDeviceClass.TIMESTAMP,
            icon=i, value_fn=(lambda d, k=k: _ist_time(d.get(k))),
        )
        for k, n, i in (
            ("sunrise", "Sunrise", "mdi:weather-sunset-up"),
            ("sunset", "Sunset", "mdi:weather-sunset-down"),
            ("moonrise", "Moonrise", "mdi:moon-waning-crescent"),
            ("moonset", "Moonset", "mdi:moon-waning-crescent"),
        )
    ),
    # --- Forecast extras (text forecast + station observations)
    IMDSensorDescription(
        key="forecast_text", name="Forecast today", key_coordinator=K_FORECAST,
        icon="mdi:text-short", value_fn=lambda d: d.get("Todays_Forecast"),
        attrs_fn=lambda d: {f"day_{i}": d.get(f"Day_{i}_Forecast") for i in range(2, 8)},
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coords = entry.runtime_data.coordinators
    async_add_entities(
        IMDSensor(entry, coords[d.key_coordinator], d)
        for d in SENSORS
        if d.key_coordinator in coords
    )


class IMDSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    entity_description: IMDSensorDescription

    def __init__(self, entry, coordinator, description) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self):
        data = self.coordinator.data
        if data is None:
            return None
        return self.entity_description.value_fn(data)

    @property
    def extra_state_attributes(self):
        fn = self.entity_description.attrs_fn
        data = self.coordinator.data
        return fn(data) if fn and data else None
