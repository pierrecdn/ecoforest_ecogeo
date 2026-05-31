import logging
from functools import partial

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api.exceptions import (
    EcoGeoAirApiError,
    EcoGeoAirAuthError,
    EcoGeoAirConnectionError,
)
from .coordinator import EcoGeoAirCoordinator
from .const import DOMAIN
from custom_components.ecoforest_ecogeoair.api.client import EcoGeoAirApi

PLATFORMS = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EcoGeoAirApi from a config entry."""
    api: EcoGeoAirApi | None = None
    try:
        api_kwargs = {
            "host": entry.data[CONF_HOST],
            "user": entry.data[CONF_USERNAME],
            "password": entry.data[CONF_PASSWORD],
            # TODO: "session": async_get_clientsession(hass, verify_ssl=False),
        }
        api = await hass.async_add_executor_job(partial(EcoGeoAirApi, **api_kwargs))
        await api.initialize()
    except EcoGeoAirAuthError:
        _LOGGER.error("Failure during authentication on device")
        if api is not None:
            await api.async_close()
        return False
    except EcoGeoAirConnectionError as err:
        _LOGGER.error("Failure during connection to device")
        if api is not None:
            await api.async_close()
        raise ConfigEntryNotReady from err
    except EcoGeoAirApiError as err:
        _LOGGER.error("Failure during device setup: %s", err)
        if api is not None:
            await api.async_close()
        raise ConfigEntryNotReady from err

    coordinator = EcoGeoAirCoordinator(hass, api)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: EcoGeoAirCoordinator = hass.data[DOMAIN][entry.entry_id]
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.async_close()

    return unload_ok
