"""Base Entity for Ecoforest."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfPower,
    UnitOfPressure,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, MANUFACTURER
from .coordinator import EcoGeoAirCoordinator
from .api.client import EcoGeoAirApi


@dataclass
class EcoGeoAirDevice:
    is_supported: bool
    model_name: str
    state: EcoGeoAirApi | None = None

    @classmethod
    def build(cls, model_name: str, data: EcoGeoAirApi) -> EcoGeoAirDevice:
        return EcoGeoAirDevice(is_supported=True, model_name=model_name, state=data)


@dataclass(frozen=True, kw_only=True)
class EcoGeoApiSensorEntityDescription(SensorEntityDescription):
    """Describes Ecogeoair sensor entity."""

    domain: str
    value_fn: Callable[[EcoGeoAirDevice], StateType] | None = None


class EcoGeoApiEntity(CoordinatorEntity[EcoGeoAirCoordinator]):
    """Common Ecogeoair entity using CoordinatorEntity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        domain: str,
        key: str,
        definition: dict[str, str],
        device_alias: str,
    ) -> None:
        """Initialize device information."""
        device_class = None
        native_unit_of_measurement = None
        if definition["entity_type"] == "temperature":
            device_class = SensorDeviceClass.TEMPERATURE
            native_unit_of_measurement = UnitOfTemperature[
                coordinator.data.temperature_unit.name
            ]
        elif definition["entity_type"] == "pressure":
            device_class = SensorDeviceClass.PRESSURE
            native_unit_of_measurement = UnitOfPressure[
                coordinator.data.pressure_unit.name
            ]
        elif definition["entity_type"] == "power":
            device_class = SensorDeviceClass.POWER
            native_unit_of_measurement = UnitOfPower.WATT
        # elif definition["entity_type"] == "measurement":
        #    device_class = SensorDeviceClass.MEASUREMENT
        elif definition["entity_type"] == "enum":
            device_class = SensorDeviceClass.ENUM

        # Determine appropriate state class for measurements
        state_class = None
        if definition.get("entity_type") == "measurement":
            state_class = SensorStateClass.MEASUREMENT

        self.entity_description = EcoGeoApiSensorEntityDescription(
            domain=domain,
            key=key,
            translation_key=key,
            value_fn=definition.get("value_fn")
            if isinstance(definition, dict)
            else None,
            native_unit_of_measurement=native_unit_of_measurement,
            device_class=device_class,
            state_class=state_class,
        )
        device_id = (
            coordinator.data.model.value if device_alias is None else device_alias
        )
        device_name = MANUFACTURER if device_alias is None else device_alias

        id = f"{device_id}_{key}"
        self._attr_unique_id = id
        self.entity_id = f"sensor.{id}"

        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            model=coordinator.data.model.value,
            manufacturer=MANUFACTURER,
        )

    @property
    def data(self) -> EcoGeoAirApi:
        """Return ecoforest data."""
        assert self.coordinator.data
        return self.coordinator.data
