"""Weather entity (current + 7-day forecast) from IMD city forecast."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.weather import (
    Forecast, WeatherEntity, WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfPressure, UnitOfSpeed, UnitOfTemperature,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_CITY_ID, CONF_CITY_NAME, DOMAIN, K_CURRENT, K_FORECAST
from .util import condition_from_text, condition_from_wmo, to_float


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([IMDWeather(entry)])


def device_info(entry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"IMD {entry.data.get(CONF_CITY_NAME, '')}".strip(),
        manufacturer="India Meteorological Department",
        entry_type=None,
    )


class IMDWeather(CoordinatorEntity, WeatherEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_attribution = "Data: India Meteorological Department (IMD), Govt. of India"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    def __init__(self, entry) -> None:
        rt = entry.runtime_data
        super().__init__(rt.coordinators[K_FORECAST])
        self._current = rt.coordinators.get(K_CURRENT)
        self._attr_unique_id = f"{entry.entry_id}_weather"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._current is not None:
            self.async_on_remove(
                self._current.async_add_listener(self.async_write_ha_state)
            )

    # -- helpers
    @property
    def _fc(self) -> dict[str, Any]:
        return self.coordinator.data or {}

    @property
    def _cur(self) -> dict[str, Any]:
        return (self._current.data if self._current and self._current.data else {}) or {}

    def _cur_get(self, *keys: str) -> Any:
        for k in keys:
            if k in self._cur:
                return self._cur[k]
        return None

    # -- current conditions: prefer current_wx, fall back to forecast fields
    @property
    def native_temperature(self) -> float | None:
        t = to_float(self._cur_get("Temperature", "TEMPERATURE", "Temp"))
        return t if t is not None else to_float(self._fc.get("Today_Max_temp"))

    @property
    def humidity(self) -> float | None:
        h = to_float(self._cur_get("Humidity", "HUMIDITY"))
        return h if h is not None else to_float(self._fc.get("Relative_Humidity_at_0830"))

    @property
    def native_pressure(self) -> float | None:
        return to_float(self._cur_get("M.S.L.P", "MSLP"))

    @property
    def native_wind_speed(self) -> float | None:
        return to_float(self._cur_get("Wind Speed", "WIND_SPEED"))

    @property
    def wind_bearing(self) -> float | None:
        return to_float(self._cur_get("Wind Direction", "WIND_DIRECTION"))

    @property
    def condition(self) -> str | None:
        code = self._cur_get("Weather Code", "WEATHER_CODE")
        return condition_from_wmo(code) or condition_from_text(self._fc.get("Todays_Forecast"))

    # -- 7-day forecast
    async def async_forecast_daily(self) -> list[Forecast] | None:
        fc = self._fc
        if not fc:
            return None
        try:
            start = datetime.strptime(str(fc.get("Date")), "%Y-%m-%d")
        except ValueError:
            start = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        out: list[Forecast] = []
        for i in range(1, 8):
            tmax = fc.get("Todays_Forecast_Max_Temp" if i == 1 else f"Day_{i}_Max_Temp")
            tmin = fc.get("Todays_Forecast_Min_temp" if i == 1 else f"Day_{i}_Min_temp")
            text = fc.get("Todays_Forecast" if i == 1 else f"Day_{i}_Forecast")
            day = (start + timedelta(days=i - 1)).replace(tzinfo=dt_util.get_time_zone("Asia/Kolkata"))
            out.append(
                Forecast(
                    datetime=day.isoformat(),
                    native_temperature=to_float(tmax),
                    native_templow=to_float(tmin),
                    condition=condition_from_text(text),
                )
            )
        return out
