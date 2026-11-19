"""Generic coordinator: one instance per data group, each with its own interval."""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IMDApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class IMDCoordinator(DataUpdateCoordinator[Any]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry,
        key: str,
        fetch: Callable[[], Awaitable[Any]],
        interval: timedelta,
    ) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN}_{key}", update_interval=interval
        )
        self._fetch = fetch

    async def _async_update_data(self) -> Any:
        try:
            return await self._fetch()
        except IMDApiError as err:
            raise UpdateFailed(str(err)) from err
