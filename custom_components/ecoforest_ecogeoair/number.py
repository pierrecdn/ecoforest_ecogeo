"""Number platform for Ecoforest DHW configuration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ALIAS, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import EcoGeoAirCoordinator
from .water_heater import DHW_MIN_SETPOINT_CELSIUS, _to_entity_temperature


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ecoforest number entities."""
    coordinator: EcoGeoAirCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_id = coordinator.data.model.value
    device_alias = entry.data.get(CONF_ALIAS)
    device_name = MANUFACTURER if device_alias is None else device_alias

    async_add_entities([DhwHtrSetpointNumber(coordinator, device_id, device_name)])


class DhwHtrSetpointNumber(CoordinatorEntity[EcoGeoAirCoordinator], NumberEntity):
    """HTR opportunistic DHW setpoint (2103 ATSH / register 6104)."""

    _attr_has_entity_name = True
    _attr_translation_key = "dhw_htr_setpoint"
    _attr_icon = "mdi:heat-wave"
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1.0

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_dhw_htr_setpoint"
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
        """Update limits and value from coordinator data."""
        dhw = self.coordinator.data.status.slow_config.dhw
        self._attr_native_unit_of_measurement = UnitOfTemperature[
            self.coordinator.data.temperature_unit.name
        ]
        self._attr_native_min_value = _to_entity_temperature(
            self.coordinator, DHW_MIN_SETPOINT_CELSIUS
        )
        self._attr_native_max_value = _to_entity_temperature(
            self.coordinator, dhw.max_setpoint
        )
        self._attr_native_value = _to_entity_temperature(
            self.coordinator, dhw.htr_setpoint
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the HTR setpoint on the device."""
        await self.coordinator.api.set_dhw_htr_setpoint(value)
        await self.coordinator.async_refresh_service_enable()
