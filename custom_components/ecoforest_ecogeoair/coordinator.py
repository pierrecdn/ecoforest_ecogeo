"""The ecoforest coordinator."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from custom_components.ecoforest_ecogeoair.api.client import (
    EcoGeoAirApi,
    EcoGeoAirDevice,
)
from .const import POLLING_INTERVAL
from .api.exceptions import EcoGeoAirApiError

_LOGGER = logging.getLogger(__name__)


class EcoGeoAirCoordinator(DataUpdateCoordinator[EcoGeoAirApi]):
    """DataUpdateCoordinator to gather data from device."""

    def __init__(self, hass: HomeAssistant, api: EcoGeoAirApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="ecoforest_ecogeoair",
            update_interval=POLLING_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> EcoGeoAirDevice:
        """Fetch all device and sensor data from api."""
        try:
            data = await self.api.get_device()
        except EcoGeoAirApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        _LOGGER.debug("Ecoforest data: %s", data)
        return data
