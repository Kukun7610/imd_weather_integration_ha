"""Thin async client for the IMD public API (https://api.imd.gov.in)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import BASE_URL

_LOGGER = logging.getLogger(__name__)


class IMDApiError(Exception):
    """Raised when the IMD API cannot be reached or returns junk."""


class IMDApiClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, path: str, **params: Any) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        url = f"{BASE_URL}/{path}"
        last: Exception | None = None
        for attempt in range(3):
            try:
                async with asyncio.timeout(25):
                    resp = await self._session.get(url, params=params)
                    resp.raise_for_status()
                    return await resp.json(content_type=None)
            except (TimeoutError, aiohttp.ClientError, ValueError) as err:
                last = err
                _LOGGER.debug("IMD %s attempt %s failed: %s", path, attempt + 1, err)
                await asyncio.sleep(2 * (attempt + 1))
        raise IMDApiError(f"{path}: {last}") from last

    # --- Forecast ---------------------------------------------------------
    async def city_forecast(self, city_id: str) -> Any:
        return await self._get("cityforecast", id=city_id)

    async def city_forecast_loc(self) -> Any:  # all stations incl. lat/lon
        return await self._get("cityforecastloc")

    async def subdivision_warning(self) -> Any:
        return await self._get("subdivisionwarning")

    async def state_district_forecast(self) -> Any:  # State/District/Obj_id list
        return await self._get("state_district_rainfall_forecast")

    # --- Current & nowcast ------------------------------------------------
    async def current_wx(self, station_id: str) -> Any:
        return await self._get("current_wx", id=station_id)

    async def district_nowcast(self, district_id: str) -> Any:
        return await self._get("districtnowcast", id=district_id)

    # --- Warnings / rainfall ---------------------------------------------
    async def district_warning(self, district_id: str) -> Any:
        return await self._get("districtwarning", id=district_id)

    async def district_rainfall(self, district_id: str) -> Any:
        return await self._get("districtrainfall", id=district_id)

    # --- Marine / cyclone / astro ----------------------------------------
    async def sea_bulletin(self) -> Any:
        return await self._get("seabulletin")

    async def coastal_bulletin(self) -> Any:
        return await self._get("coastalbulletin")

    async def cyclone_track(self) -> Any:
        return await self._get("cyclone_track")

    async def sunmoon(self, lat: float, lon: float) -> Any:
        return await self._get("sunmoon", lat=lat, lon=lon)
