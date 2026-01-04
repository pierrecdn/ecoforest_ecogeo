import logging
from functools import partial

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import EcoGeoAirCoordinator
from custom_components.ecoforest_ecogeoair.api.client import EcoGeoAirApi
from .api.exceptions import EcoGeoAirAuthError, EcoGeoAirConnectionError

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EcoGeoAirApi from a config entry."""
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
        return False
    except EcoGeoAirConnectionError as err:
        _LOGGER.error("Failure during connection to device")
        raise ConfigEntryNotReady from err

    coordinator = EcoGeoAirCoordinator(hass, api)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
