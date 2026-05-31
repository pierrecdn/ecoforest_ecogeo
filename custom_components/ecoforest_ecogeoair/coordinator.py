"""The ecoforest coordinator."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.ecoforest_ecogeoair.api.client import (
    EcoGeoAirApi,
    EcoGeoAirDevice,
)
from .const import POLLING_INTERVAL, SERVICE_ENABLE_POLLING_INTERVAL
from .api.exceptions import EcoGeoAirApiError

_LOGGER = logging.getLogger(__name__)


class EcoGeoAirCoordinator(DataUpdateCoordinator[EcoGeoAirDevice]):
    """DataUpdateCoordinator to gather data from device."""

    def __init__(self, hass: HomeAssistant, api: EcoGeoAirApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="ecoforest_ecogeoair",
            update_interval=POLLING_INTERVAL,
        )
        self.api = api
        self._last_service_enable_refresh: datetime | None = None
        self._force_service_enable_refresh = False

    async def async_refresh_service_enable(self) -> None:
        """Force-refresh service enable flags and update entities."""
        self._force_service_enable_refresh = True
        await self.async_request_refresh()

    async def _async_update_data(self) -> EcoGeoAirDevice:
        """Fetch all device and sensor data from api."""
        now = dt_util.utcnow()
        refresh_service_enable = self._force_service_enable_refresh
        if not refresh_service_enable and (
            self._last_service_enable_refresh is None
            or now - self._last_service_enable_refresh
            >= SERVICE_ENABLE_POLLING_INTERVAL
        ):
            refresh_service_enable = True

        self._force_service_enable_refresh = False

        try:
            data = await self.api.get_device(
                refresh_service_enable=refresh_service_enable
            )
        except EcoGeoAirApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        if refresh_service_enable:
            self._last_service_enable_refresh = now

        _LOGGER.debug("Ecoforest data: %s", data)
        return data
