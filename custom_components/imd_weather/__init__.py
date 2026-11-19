"""IMD Weather integration."""
from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IMDApiClient
from .const import (
    CONF_CITY_ID, CONF_DISTRICT_ID, CONF_SUBDIVISION,
    INTERVAL_ASTRO, INTERVAL_CURRENT, INTERVAL_CYCLONE, INTERVAL_FORECAST,
    INTERVAL_MARINE, INTERVAL_NOWCAST, INTERVAL_RAINFALL, INTERVAL_WARNING,
    K_ASTRO, K_CURRENT, K_CYCLONE, K_FORECAST, K_MARINE, K_NOWCAST,
    K_RAINFALL, K_SUBDIV_WARNING, K_WARNING,
)
from .coordinator import IMDCoordinator
from .util import as_list

PLATFORMS = [Platform.WEATHER, Platform.SENSOR]


@dataclass
class IMDRuntime:
    client: IMDApiClient
    coordinators: dict[str, IMDCoordinator] = field(default_factory=dict)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = IMDApiClient(async_get_clientsession(hass))
    d = entry.data
    city_id = d.get(CONF_CITY_ID)
    district_id = d.get(CONF_DISTRICT_ID)
    subdiv = d.get(CONF_SUBDIVISION)
    lat = d.get(CONF_LATITUDE, hass.config.latitude)
    lon = d.get(CONF_LONGITUDE, hass.config.longitude)

    def first(rows):
        rows = as_list(rows)
        return rows[0] if rows else {}

    async def f_forecast():
        return first(await client.city_forecast(city_id))

    async def f_current():
        return first(await client.current_wx(city_id))

    async def f_nowcast():
        return first(await client.district_nowcast(district_id))

    async def f_warning():
        return first(await client.district_warning(district_id))

    async def f_subdiv():
        rows = as_list(await client.subdivision_warning())
        for r in rows:
            if str(r.get("SUBDIV", "")).strip().lower() == str(subdiv).strip().lower():
                return r
        return {}

    async def f_rain():
        return first(await client.district_rainfall(district_id))

    async def f_marine():
        return {
            "sea": as_list(await client.sea_bulletin()),
            "coastal": as_list(await client.coastal_bulletin()),
        }

    async def f_cyclone():
        payload = await client.cyclone_track()
        return payload if isinstance(payload, dict) else {}

    async def f_astro():
        merged: dict = {}
        for item in as_list(await client.sunmoon(lat, lon)):
            merged.update(item)
        return merged

    specs = {
        K_FORECAST: (f_forecast, INTERVAL_FORECAST, bool(city_id)),
        K_CURRENT: (f_current, INTERVAL_CURRENT, bool(city_id)),
        K_NOWCAST: (f_nowcast, INTERVAL_NOWCAST, bool(district_id)),
        K_WARNING: (f_warning, INTERVAL_WARNING, bool(district_id)),
        K_SUBDIV_WARNING: (f_subdiv, INTERVAL_WARNING, bool(subdiv)),
        K_RAINFALL: (f_rain, INTERVAL_RAINFALL, bool(district_id)),
        K_MARINE: (f_marine, INTERVAL_MARINE, True),
        K_CYCLONE: (f_cyclone, INTERVAL_CYCLONE, True),
        K_ASTRO: (f_astro, INTERVAL_ASTRO, True),
    }

    runtime = IMDRuntime(client)
    for key, (fetch, interval, enabled) in specs.items():
        if not enabled:
            continue
        coord = IMDCoordinator(hass, entry, key, fetch, interval)
        # Forecast must succeed; the rest may fail without blocking setup.
        if key == K_FORECAST:
            await coord.async_config_entry_first_refresh()
        else:
            await coord.async_refresh()
        runtime.coordinators[key] = coord

    entry.runtime_data = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
