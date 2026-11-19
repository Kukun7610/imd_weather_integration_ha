"""Config flow with two location modes.

  A) India > State > District > Subdivision > City
  B) Latitude / Longitude  (nearest IMD city station is picked automatically;
     State > District > Subdivision are then asked for warnings/nowcast)

Optional data/hierarchy.json refines the dropdown filtering:
  {"subdivisions": {"West Bengal": ["Gangetic West Bengal", "Sub-Himalayan West Bengal & Sikkim"]},
   "cities": {"KOLKATA": ["42807"]}}        # district name -> city station codes
Without it, the subdivision and city lists are unfiltered (full alphabetical).
"""
from __future__ import annotations

import json
import voluptuous as vol
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict, SelectSelector, SelectSelectorConfig, SelectSelectorMode,
)

from .api import IMDApiClient, IMDApiError
from .const import (
    CONF_CITY_ID, CONF_CITY_NAME, CONF_DISTRICT, CONF_DISTRICT_ID, CONF_MODE,
    CONF_STATE, CONF_SUBDIVISION, DOMAIN, MODE_COORDS, MODE_HIERARCHY,
)
from .util import as_list, haversine_km

HIERARCHY_FILE = Path(__file__).parent / "data" / "hierarchy.json"


def _select(options: list[tuple[str, str]]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=v, label=l) for v, l in options],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _load_hierarchy() -> dict:
    try:
        return json.loads(HIERARCHY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class IMDConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._districts: list[dict] = []
        self._cities: list[dict] = []
        self._hierarchy: dict = {}

    @property
    def _client(self) -> IMDApiClient:
        return IMDApiClient(async_get_clientsession(self.hass))

    # ---- entry: choose mode ---------------------------------------------
    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="user", menu_options=[MODE_HIERARCHY, MODE_COORDS]
        )

    # ---- Mode B: lat/lon --------------------------------------------------
    async def async_step_coordinates(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._cities = as_list(await self._client.city_forecast_loc())
            except IMDApiError:
                errors["base"] = "cannot_connect"
            else:
                lat, lon = user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE]
                best = None
                for c in self._cities:
                    try:
                        dist = haversine_km(
                            lat, lon, float(c["Latitude"]), float(c["Longitude"])
                        )
                    except (KeyError, TypeError, ValueError):
                        continue
                    if best is None or dist < best[0]:
                        best = (dist, c)
                if best is None:
                    errors["base"] = "no_stations"
                else:
                    self._data = {
                        CONF_MODE: MODE_COORDS,
                        CONF_LATITUDE: lat,
                        CONF_LONGITUDE: lon,
                        CONF_CITY_ID: str(best[1].get("Station_Code")),
                        CONF_CITY_NAME: best[1].get("Station_Name"),
                    }
                    return await self.async_step_state()
        schema = vol.Schema(
            {
                vol.Required(CONF_LATITUDE, default=self.hass.config.latitude): cv.latitude,
                vol.Required(CONF_LONGITUDE, default=self.hass.config.longitude): cv.longitude,
            }
        )
        return self.async_show_form(step_id=MODE_COORDS, data_schema=schema, errors=errors)

    # ---- Mode A entry = state step (shared) ------------------------------
    async def async_step_hierarchy(self, user_input=None) -> ConfigFlowResult:
        self._data = {CONF_MODE: MODE_HIERARCHY}
        return await self.async_step_state()

    async def async_step_state(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if not self._districts:
            try:
                self._districts = as_list(await self._client.state_district_forecast())
            except IMDApiError:
                errors["base"] = "cannot_connect"
        if user_input is not None and not errors:
            self._data[CONF_STATE] = user_input[CONF_STATE]
            return await self.async_step_district()
        states = sorted({str(d.get("State", "")).strip() for d in self._districts} - {""})
        return self.async_show_form(
            step_id="state",
            data_schema=vol.Schema(
                {vol.Required(CONF_STATE): _select([(s, s.title()) for s in states])}
            ),
            errors=errors,
        )

    async def async_step_district(self, user_input=None) -> ConfigFlowResult:
        state = self._data[CONF_STATE]
        rows = [d for d in self._districts if str(d.get("State", "")).strip() == state]
        if user_input is not None:
            obj_id = user_input[CONF_DISTRICT]
            name = next((r.get("District") for r in rows if str(r.get("Obj_id")) == obj_id), obj_id)
            self._data[CONF_DISTRICT_ID] = obj_id
            self._data[CONF_DISTRICT] = name
            return await self.async_step_subdivision()
        opts = sorted(
            (str(r["Obj_id"]), str(r["District"]).title()) for r in rows if "Obj_id" in r
        )
        return self.async_show_form(
            step_id="district",
            data_schema=vol.Schema({vol.Required(CONF_DISTRICT): _select(opts)}),
        )

    async def async_step_subdivision(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if not self._hierarchy:
            self._hierarchy = await self.hass.async_add_executor_job(_load_hierarchy)
        if user_input is not None:
            self._data[CONF_SUBDIVISION] = user_input[CONF_SUBDIVISION]
            if self._data[CONF_MODE] == MODE_COORDS:
                return await self._create()
            return await self.async_step_city()
        try:
            rows = as_list(await self._client.subdivision_warning())
        except IMDApiError:
            rows, errors["base"] = [], "cannot_connect"
        names = sorted({str(r.get("SUBDIV", "")).strip() for r in rows} - {""})
        allowed = self._hierarchy.get("subdivisions", {}).get(self._data[CONF_STATE])
        if allowed:
            names = [n for n in names if n in allowed] or names
        return self.async_show_form(
            step_id="subdivision",
            data_schema=vol.Schema({vol.Required(CONF_SUBDIVISION): _select([(n, n) for n in names])}),
            errors=errors,
        )

    async def async_step_city(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if not self._cities:
            try:
                self._cities = as_list(await self._client.city_forecast_loc())
            except IMDApiError:
                errors["base"] = "cannot_connect"
        if user_input is not None and not errors:
            code = user_input[CONF_CITY_ID]
            city = next((c for c in self._cities if str(c.get("Station_Code")) == code), {})
            self._data[CONF_CITY_ID] = code
            self._data[CONF_CITY_NAME] = city.get("Station_Name", code)
            if "Latitude" in city:
                self._data[CONF_LATITUDE] = float(city["Latitude"])
                self._data[CONF_LONGITUDE] = float(city["Longitude"])
            return await self._create()
        allowed = self._hierarchy.get("cities", {}).get(str(self._data.get(CONF_DISTRICT, "")).upper())
        cities = [
            c for c in self._cities
            if "Station_Code" in c and (not allowed or str(c["Station_Code"]) in allowed)
        ] or [c for c in self._cities if "Station_Code" in c]
        opts = sorted((str(c["Station_Code"]), str(c.get("Station_Name", "")).title()) for c in cities)
        return self.async_show_form(
            step_id="city",
            data_schema=vol.Schema({vol.Required(CONF_CITY_ID): _select(opts)}),
            errors=errors,
        )

    async def _create(self) -> ConfigFlowResult:
        uid = f"{self._data[CONF_CITY_ID]}_{self._data[CONF_DISTRICT_ID]}"
        await self.async_set_unique_id(uid)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"IMD {self._data.get(CONF_CITY_NAME, self._data[CONF_DISTRICT])}",
            data=self._data,
        )
