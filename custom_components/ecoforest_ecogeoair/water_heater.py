"""Water heater platform for the Ecoforest EcoGeoAir heat pump."""

from __future__ import annotations

from typing import Any, Literal

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    STATE_HEAT_PUMP,
    STATE_OFF,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ALIAS,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.client import (
    DeviceStatus,
    DHWMode,
    HeatingMode,
    HTRMode,
    TemperatureUnit,
    is_plausible_buffer_temperature,
    is_valid_sensor_reading,
)
from .const import DOMAIN, MANUFACTURER
from .coordinator import EcoGeoAirCoordinator
from .switch import _service_installed

# Endpoint 2103 exposes ATSL (max user setpoint) but no documented minimum.
# Use a conservative floor to discourage unsafe low storage temperatures.
DHW_MIN_SETPOINT_CELSIUS = 40.0

SERVICE_OPERATION_MODES = [STATE_OFF, STATE_HEAT_PUMP]
STATE_IDLE = "idle"
STATE_HTR = "htr"
STATE_COOLING = "cooling"

ServiceKind = Literal["dhw", "pool", "heating", "cooling"]


def _to_entity_temperature(
    coordinator: EcoGeoAirCoordinator, value_celsius: float
) -> float:
    """Convert a Celsius setpoint to the device/user temperature unit."""
    if coordinator.data.temperature_unit == TemperatureUnit.FAHRENHEIT:
        return value_celsius * 1.8 + 32
    return value_celsius


def _service_enabled(status: DeviceStatus, service: ServiceKind) -> bool:
    """Return True when the user has enabled the service on the device."""
    enable = status.slow_config.service_enable
    if service == "dhw":
        return enable.dhw
    if service == "pool":
        return enable.pool
    if service == "heating":
        return enable.heating
    return enable.cooling


def _service_activity(status: DeviceStatus, service: ServiceKind) -> str:
    """Return runtime activity for the hydraulic service."""
    if service == "dhw":
        if status.main.htr_mode == HTRMode.DHW:
            return STATE_HTR
        if status.energy.dhw_tank_demand:
            return "heating"
        return STATE_IDLE
    if service == "pool":
        if status.main.htr_mode == HTRMode.POOL:
            return STATE_HTR
        if status.energy.pool_circuit_demand:
            return "heating"
        return STATE_IDLE
    if service == "heating":
        if status.energy.heating_tank_demand:
            return "heating"
        return STATE_IDLE
    if status.energy.active_cooling_demand or status.energy.passive_cooling_demand:
        return STATE_COOLING
    return STATE_IDLE


def _configured_operation(status: DeviceStatus, service: ServiceKind) -> str:
    """Return the user-selected operation mode (off / heat_pump)."""
    if not _service_enabled(status, service):
        return STATE_OFF
    return STATE_HEAT_PUMP


_SERVICE_ICONS: dict[ServiceKind, tuple[str, str | None]] = {
    "dhw": ("mdi:water-boiler", "mdi:water-boiler-off"),
    "pool": ("mdi:pool-thermometer", None),
    "heating": ("mdi:radiator", "mdi:radiator-off"),
    "cooling": ("mdi:snowflake", "mdi:snowflake-off"),
}


def _service_icon(status: DeviceStatus, service: ServiceKind) -> str:
    """Return the entity icon; greyed-off styling comes from the off state."""
    on_icon, off_icon = _SERVICE_ICONS[service]
    if not _service_enabled(status, service):
        return off_icon or on_icon
    return on_icon


def _circuit_temperatures(
    status: DeviceStatus, service: ServiceKind
) -> tuple[float | None, float | None]:
    """Return live and target temperatures for heating/cooling circuit entities.

    Target is the service cutoff (TCC / TCFA on endpoint 2150), matching what
    async_set_temperature writes. Current uses the inertia buffer when installed
    and plausible (2151); otherwise production circuit output from 2148.
    """
    main = status.main
    regulation = status.temp_regulation
    thermo = status.thermodynamic
    current: float | None = None
    target: float | None = None

    if service == "heating":
        if regulation is not None and is_valid_sensor_reading(
            regulation.heat_temperature
        ):
            target = regulation.heat_temperature
        if main.heating_tank and thermo is not None:
            if is_plausible_buffer_temperature(thermo.heat_buffer_temperature):
                current = thermo.heat_buffer_temperature
        if current is None and is_valid_sensor_reading(
            main.production_circuit_output_temperature
        ):
            current = main.production_circuit_output_temperature
    elif service == "cooling":
        if regulation is not None and is_valid_sensor_reading(
            regulation.active_cool_temperature
        ):
            target = regulation.active_cool_temperature
        if main.cooling_tank and thermo is not None:
            if is_plausible_buffer_temperature(thermo.cool_buffer_temperature):
                current = thermo.cool_buffer_temperature
        if current is None and is_valid_sensor_reading(
            main.production_circuit_output_temperature
        ):
            current = main.production_circuit_output_temperature

    return current, target


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Heat Pump water heater platform."""
    coordinator: EcoGeoAirCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_id = coordinator.data.model.value
    device_alias = entry.data.get(CONF_ALIAS)
    device_name = MANUFACTURER if device_alias is None else device_alias

    async_add_entities(
        [
            HeatPumpDHWEntity(coordinator, device_id, device_name),
            HeatPumpPoolEntity(coordinator, device_id, device_name),
            HeatPumpHeatingEntity(coordinator, device_id, device_name),
            HeatPumpCoolingEntity(coordinator, device_id, device_name),
        ]
    )


class _EcoGeoAirWaterHeater(CoordinatorEntity[EcoGeoAirCoordinator], WaterHeaterEntity):
    """Shared water heater behaviour for hydraulic services."""

    _service: ServiceKind

    @property
    def available(self) -> bool:
        """Return True when the service circuit is installed on this device."""
        if not super().available:
            return False
        return _service_installed(
            self._service, self.coordinator.data.installed_features
        )


class HeatPumpDHWEntity(_EcoGeoAirWaterHeater):
    """Representation of the Domestic Hot Water tank."""

    _attr_has_entity_name = True
    _attr_translation_key = "dhw"
    _service: ServiceKind = "dhw"
    _attr_precision = PRECISION_WHOLE
    _attr_operation_list = SERVICE_OPERATION_MODES
    _attr_supported_features = (
        WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the DHW entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_dhw"
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
        """Update entity attributes from coordinator data."""
        status = self.coordinator.data.status
        dhw_config = status.slow_config.dhw

        self._attr_current_operation = _configured_operation(status, "dhw")
        self._attr_icon = _service_icon(status, "dhw")
        self._attr_extra_state_attributes = {
            "activity": _service_activity(status, "dhw"),
        }

        if status.thermodynamic is not None:
            self._attr_current_temperature = (
                status.thermodynamic.dhw_tank_temperature
            )
        elif status.zones is not None:
            self._attr_current_temperature = status.zones.dhw_temperature
        else:
            self._attr_current_temperature = None

        self._attr_target_temperature = _to_entity_temperature(
            self.coordinator, dhw_config.user_setpoint
        )
        self._attr_target_temperature_high = _to_entity_temperature(
            self.coordinator, dhw_config.htr_setpoint
        )
        self._attr_target_temperature_low = None
        self._attr_min_temp = _to_entity_temperature(
            self.coordinator, DHW_MIN_SETPOINT_CELSIUS
        )
        self._attr_max_temp = _to_entity_temperature(
            self.coordinator, dhw_config.max_setpoint
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the DHW user setpoint (2103 AS)."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.api.set_dhw_setpoint(temp)
            await self.coordinator.async_refresh_service_enable()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Enable or disable DHW (same as the service switch)."""
        if operation_mode == STATE_OFF:
            await self.async_turn_off()
        elif operation_mode == STATE_HEAT_PUMP:
            await self.async_turn_on()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn DHW on."""
        await self.coordinator.api.set_dhw_mode(DHWMode.ON)
        await self.coordinator.async_refresh_service_enable()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn DHW off."""
        await self.coordinator.api.set_dhw_mode(DHWMode.OFF)
        await self.coordinator.async_refresh_service_enable()


class HeatPumpPoolEntity(_EcoGeoAirWaterHeater):
    """Representation of the Pool Heater."""

    _attr_has_entity_name = True
    _attr_translation_key = "pool"
    _service: ServiceKind = "pool"
    _attr_precision = PRECISION_TENTHS
    _attr_operation_list = SERVICE_OPERATION_MODES
    _attr_supported_features = (
        WaterHeaterEntityFeature.ON_OFF | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the Pool entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_pool"
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
        """Update entity attributes from coordinator data."""
        status = self.coordinator.data.status

        self._attr_current_operation = _configured_operation(status, "pool")
        self._attr_icon = _service_icon(status, "pool")
        self._attr_extra_state_attributes = {
            "activity": _service_activity(status, "pool"),
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new pool target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.api.set_pool_setpoint(temp)
            await self.coordinator.async_request_refresh()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Enable or disable pool heating (same as the service switch)."""
        if operation_mode == STATE_OFF:
            await self.async_turn_off()
        elif operation_mode == STATE_HEAT_PUMP:
            await self.async_turn_on()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn pool on."""
        await self.coordinator.api.set_pool_mode(HeatingMode.ON)
        await self.coordinator.async_refresh_service_enable()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn pool off."""
        await self.coordinator.api.set_pool_mode(HeatingMode.OFF)
        await self.coordinator.async_refresh_service_enable()


class _HeatPumpCircuitEntity(_EcoGeoAirWaterHeater):
    """Shared behaviour for heating and cooling hydraulic circuits."""

    _attr_operation_list = SERVICE_OPERATION_MODES
    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = (
        WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        device_id: str,
        device_name: str,
        *,
        unique_id_suffix: str,
        translation_key: str,
    ) -> None:
        """Initialize the circuit entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_{unique_id_suffix}"
        self._attr_translation_key = translation_key
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
        """Update entity attributes from coordinator data."""
        status = self.coordinator.data.status
        current, target = _circuit_temperatures(status, self._service)

        self._attr_current_operation = _configured_operation(status, self._service)
        self._attr_icon = _service_icon(status, self._service)
        self._attr_extra_state_attributes = {
            "activity": _service_activity(status, self._service),
        }
        self._attr_current_temperature = (
            current if is_valid_sensor_reading(current) else None
        )
        self._attr_target_temperature = (
            _to_entity_temperature(self.coordinator, target)
            if target is not None and is_valid_sensor_reading(target)
            else None
        )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Enable or disable the service (same as the service switch)."""
        if operation_mode == STATE_OFF:
            await self.async_turn_off()
        elif operation_mode == STATE_HEAT_PUMP:
            await self.async_turn_on()


class HeatPumpHeatingEntity(_HeatPumpCircuitEntity):
    """Representation of the space heating hydraulic circuit."""

    _attr_has_entity_name = True
    _service: ServiceKind = "heating"

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the heating entity."""
        super().__init__(
            coordinator,
            device_id,
            device_name,
            unique_id_suffix="heating",
            translation_key="heating",
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the heating cutoff temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.api.set_heating_cutoff_setpoint(temp)
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn heating on."""
        await self.coordinator.api.set_heating_mode(HeatingMode.ON)
        await self.coordinator.async_refresh_service_enable()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn heating off."""
        await self.coordinator.api.set_heating_mode(HeatingMode.OFF)
        await self.coordinator.async_refresh_service_enable()


class HeatPumpCoolingEntity(_HeatPumpCircuitEntity):
    """Representation of the active cooling hydraulic circuit."""

    _attr_has_entity_name = True
    _service: ServiceKind = "cooling"

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the cooling entity."""
        super().__init__(
            coordinator,
            device_id,
            device_name,
            unique_id_suffix="cooling",
            translation_key="cooling",
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the active cooling cutoff temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.api.set_active_cooling_cutoff_setpoint(temp)
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn active cooling on."""
        await self.coordinator.api.set_active_cooling_mode(True)
        await self.coordinator.async_refresh_service_enable()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn active cooling off."""
        await self.coordinator.api.set_active_cooling_mode(False)
        await self.coordinator.async_refresh_service_enable()
