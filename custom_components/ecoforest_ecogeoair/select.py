"""Select platform for Ecoforest machine settings."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ALIAS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.client import (
    SEASON_MODE_OPTIONS,
    USER_SEASON_MODE_OPTIONS,
    option_to_season_mode,
    season_mode_to_option,
)
from .const import DOMAIN, MANUFACTURER
from .coordinator import EcoGeoAirCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ecoforest select entities."""
    coordinator: EcoGeoAirCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_id = coordinator.data.model.value
    device_alias = entry.data.get(CONF_ALIAS)
    device_name = MANUFACTURER if device_alias is None else device_alias

    async_add_entities([EcoGeoAirSeasonSelect(coordinator, device_id, device_name)])


class EcoGeoAirSeasonSelect(CoordinatorEntity[EcoGeoAirCoordinator], SelectEntity):
    """Global winter / summer / auto season program (register 6101)."""

    _attr_has_entity_name = True
    _attr_translation_key = "season_mode"

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the season select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_season_mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            model=coordinator.data.model.value,
            manufacturer=MANUFACTURER,
        )
        self._update_attrs()

    async def async_added_to_hass(self) -> None:
        """Run when the entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _update_attrs(self) -> None:
        """Refresh the current season and selectable options."""
        season_mode = self.coordinator.data.status.main.season_mode
        current = season_mode_to_option(season_mode)
        options = list(USER_SEASON_MODE_OPTIONS)
        if current in SEASON_MODE_OPTIONS and current not in options:
            options.append(current)
        self._attr_options = options
        self._attr_current_option = current if current in options else None

    async def async_select_option(self, option: str) -> None:
        """Set the machine season program."""
        await self.coordinator.api.set_season_mode(option_to_season_mode(option))
        await self.coordinator.async_request_refresh()
