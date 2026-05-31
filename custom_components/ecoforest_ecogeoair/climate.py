"""Support for Ecoforest climate entities."""

from __future__ import annotations

import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, CONF_ALIAS, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.client import (
    SeasonMode,
    ZoneMode,
    is_valid_sensor_reading,
    season_mode_to_option,
)
from .const import DOMAIN, MANUFACTURER
from .coordinator import EcoGeoAirCoordinator

_LOGGER = logging.getLogger(__name__)


def zone_runtime_to_hvac_action(
    zone_mode: ZoneMode | int,
    *,
    season_mode: SeasonMode,
    cooling_installed: bool,
) -> HVACAction:
    """Map cdig runtime demand to hvac_action for one room."""
    zone_mode = ZoneMode(zone_mode)
    if zone_mode == ZoneMode.HEAT:
        if season_mode == SeasonMode.SUMMER:
            return HVACAction.IDLE
        return HVACAction.HEATING

    if zone_mode == ZoneMode.COOL:
        if season_mode == SeasonMode.WINTER or not cooling_installed:
            return HVACAction.IDLE
        return HVACAction.COOLING

    return HVACAction.IDLE


def display_hvac_mode(
    action: HVACAction,
    season_mode: SeasonMode,
    *,
    cooling_installed: bool,
) -> HVACMode:
    """Return a read-only HVAC mode for UI coloring without mode control."""
    if action == HVACAction.HEATING:
        return HVACMode.HEAT
    if action == HVACAction.COOLING:
        return HVACMode.COOL
    if season_mode == SeasonMode.SUMMER and cooling_installed:
        return HVACMode.COOL
    return HVACMode.HEAT


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ecoforest climate platform."""
    coordinator: EcoGeoAirCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    device_alias = config_entry.data.get(CONF_ALIAS, None)
    entities = []

    temp_regulation = coordinator.data.status.temp_regulation
    if temp_regulation is None:
        _LOGGER.debug("No temperature regulation data; skipping climate entities")
        return

    zone_modes = coordinator.data.status.energy.zone_modes
    _LOGGER.debug("Zone modes: %s", zone_modes)
    for idx, zone in enumerate(temp_regulation.zones):
        zone_mode = zone_modes[idx]
        _LOGGER.debug(
            "Zone %d mode: %s, configured: %s",
            idx,
            zone_mode,
            zone.is_configured,
        )
        if not zone.is_configured:
            _LOGGER.debug("Skipping zone %d (not configured)", idx)
            continue

        _LOGGER.debug("Adding climate entity for zone %d", idx)
        entities.append(
            EcoGeoAirClimate(
                coordinator,
                zone_idx=idx,
                device_alias=device_alias,
            )
        )

    _LOGGER.debug("Adding %d climate entities", len(entities))
    async_add_entities(entities)


class EcoGeoAirClimate(CoordinatorEntity[EcoGeoAirCoordinator], ClimateEntity):
    """Room climate for one configured zone (setpoint + runtime action)."""

    _attr_has_entity_name = True
    _attr_hvac_modes: list[HVACMode] = []
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_translation_key = "zone_climate"

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        zone_idx: int,
        device_alias: str | None,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._zone_idx = zone_idx

        device_id = (
            coordinator.data.model.value if device_alias is None else device_alias
        )
        device_name = MANUFACTURER if device_alias is None else device_alias

        self._attr_unique_id = f"{device_id}_zone_{zone_idx + 1}_climate"
        self._attr_translation_placeholders = {"zone": str(zone_idx + 1)}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            model=coordinator.data.model.value,
            manufacturer=MANUFACTURER,
        )
        self._attr_temperature_unit = UnitOfTemperature[
            coordinator.data.temperature_unit.name
        ]
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
        """Refresh climate state from coordinator data."""
        status = self.coordinator.data.status
        season_mode = status.main.season_mode
        cooling_installed = self.coordinator.data.installed_features.cooling
        zone_mode = status.energy.zone_modes[self._zone_idx]

        hvac_action = zone_runtime_to_hvac_action(
            zone_mode,
            season_mode=season_mode,
            cooling_installed=cooling_installed,
        )
        self._attr_hvac_action = hvac_action
        self._attr_hvac_mode = display_hvac_mode(
            hvac_action,
            season_mode,
            cooling_installed=cooling_installed,
        )

        tr = status.temp_regulation
        if tr is None or self._zone_idx >= len(tr.zones):
            self._attr_current_temperature = None
            self._attr_target_temperature = None
            self._attr_current_humidity = None
            self._attr_extra_state_attributes = {
                "season_mode": season_mode_to_option(season_mode),
            }
            return

        zone = tr.zones[self._zone_idx]
        current = zone.temperature_current
        target = zone.temperature_setpoint
        self._attr_current_temperature = (
            current if is_valid_sensor_reading(current) else None
        )
        self._attr_target_temperature = (
            target if is_valid_sensor_reading(target) else None
        )
        self._attr_current_humidity = (
            zone.humidity if is_valid_sensor_reading(zone.humidity) else None
        )
        self._attr_extra_state_attributes = {
            "season_mode": season_mode_to_option(season_mode),
        }

    async def async_set_temperature(self, **kwargs) -> None:
        """Set the room temperature setpoint for this zone."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.api.set_zone_heating_setpoint(
                self._zone_idx + 1, temperature
            )
            await self.coordinator.async_request_refresh()
