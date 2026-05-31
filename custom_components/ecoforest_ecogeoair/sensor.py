"""Support for Ecoforest sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ALIAS,
    UnitOfTemperature,
    UnitOfPressure,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import EcoGeoAirCoordinator
from .entity import (
    EcoGeoAirApiDomain,
    EcoGeoAirApiEntity,
    EcoGeoAirApiSensorEntityDescription,
    EcoGeoAirApiZoneSensorEntityDescription,
)
from .api import client as api_module
from .api.client import is_valid_sensor_reading


# Sensors (main circuit + energy)
SENSORS = [
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.MAIN,
        key="production_circuit_pressure",
        translation_key="production_circuit_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.MAIN,
        key="ground_circuit_pressure",
        translation_key="ground_circuit_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.MAIN,
        key="production_circuit_input_temperature",
        translation_key="production_circuit_input_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.MAIN,
        key="production_circuit_output_temperature",
        translation_key="production_circuit_output_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.MAIN,
        key="ground_circuit_input_temperature",
        translation_key="ground_circuit_input_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.MAIN,
        key="ground_circuit_output_temperature",
        translation_key="ground_circuit_output_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.MAIN,
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.MAIN,
        key="alarm_active",
        translation_key="alarm_active",
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.MAIN,
        key="active_service",
        translation_key="active_service",
        device_class=SensorDeviceClass.ENUM,
        options=[s.value for s in api_module.ActiveService],
        value_fn=lambda v: v.value if isinstance(v, api_module.ActiveService) else v,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.ENERGY,
        key="heating_power",
        translation_key="heating_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.ENERGY,
        key="cooling_power",
        translation_key="cooling_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.ENERGY,
        key="total_consumption",
        translation_key="total_consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.ENERGY,
        key="cop",
        translation_key="cop",
        state_class=SensorStateClass.MEASUREMENT,
        # Return unavailable when COP is 0 (device off, so no way to compute COP)
        value_fn=lambda v: None if v == 0 else v,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.THERMODYNAMIC,
        key="dhw_tank_temperature",
        translation_key="dhw_tank_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoGeoAirApiSensorEntityDescription(
        domain=EcoGeoAirApiDomain.THERMODYNAMIC,
        key="dhw_tank_setpoint",
        translation_key="dhw_tank_setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ecoforest sensor platform."""
    coordinator: EcoGeoAirCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    device_alias = config_entry.data.get(CONF_ALIAS, None)
    entities: list[SensorEntity] = [
        EcoGeoAirSensor(coordinator, description, device_alias)
        for description in SENSORS
    ]

    # Add per-zone sensors: temperature setpoint, current temperature and humidity
    for idx, zone in enumerate(coordinator.data.status.temp_regulation.zones):
        if not zone.is_configured:
            continue

        # Temperature setpoint
        entities.append(
            EcoGeoAirZoneSensor(
                coordinator,
                EcoGeoAirApiZoneSensorEntityDescription(
                    domain=EcoGeoAirApiDomain.TEMP_REGULATION,
                    key="temperature_setpoint",
                    zone_idx=idx,
                    translation_key="temperature_setpoint",
                    translation_placeholders={"zone": str(idx + 1)},
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                device_alias,
            )
        )

        # Current temperature
        entities.append(
            EcoGeoAirZoneSensor(
                coordinator,
                EcoGeoAirApiZoneSensorEntityDescription(
                    domain=EcoGeoAirApiDomain.TEMP_REGULATION,
                    key="temperature_current",
                    zone_idx=idx,
                    translation_key="temperature_current",
                    translation_placeholders={"zone": str(idx + 1)},
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                device_alias,
            )
        )

        # Humidity
        entities.append(
            EcoGeoAirZoneSensor(
                coordinator,
                EcoGeoAirApiZoneSensorEntityDescription(
                    domain=EcoGeoAirApiDomain.TEMP_REGULATION,
                    key="humidity",
                    zone_idx=idx,
                    translation_key="humidity",
                    translation_placeholders={"zone": str(idx + 1)},
                    device_class=SensorDeviceClass.HUMIDITY,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement="%",
                ),
                device_alias,
            )
        )

    async_add_entities(entities)


class EcoGeoAirSensor(SensorEntity, EcoGeoAirApiEntity):
    """Representation of an Ecoforest static sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        description: EcoGeoAirApiSensorEntityDescription,
        device_alias: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description, device_alias)
        # Set unit from coordinator if it's temperature/pressure
        if description.device_class == SensorDeviceClass.TEMPERATURE:
            self._attr_native_unit_of_measurement = UnitOfTemperature[
                coordinator.data.temperature_unit.name
            ]
        elif description.device_class == SensorDeviceClass.PRESSURE:
            self._attr_native_unit_of_measurement = UnitOfPressure[
                coordinator.data.pressure_unit.name
            ]

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        key = self.entity_description.key
        # Handle special case for alarm_active
        if key == "alarm_active":
            return (
                self.coordinator.data.status.main.alarm_status
                != api_module.AlarmStatus.OFF
            )

        # Get value from the domain specified in the description
        domain_obj = getattr(
            self.coordinator.data.status, self.entity_description.domain.value
        )
        api_value = getattr(domain_obj, key, None)

        # Apply value function if provided
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(api_value)

        return api_value


class EcoGeoAirZoneSensor(SensorEntity, EcoGeoAirApiEntity):
    """Representation of an Ecoforest zone sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        description: EcoGeoAirApiZoneSensorEntityDescription,
        device_alias: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description, device_alias)
        self._zone_idx = description.zone_idx
        # Extract metric name from key for data retrieval
        self._metric_name = description.key
        # Append zone info to unique_id
        self._attr_unique_id = f"{self._attr_unique_id}_zone_{self._zone_idx + 1}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        value = getattr(
            self.coordinator.data.status.temp_regulation.zones[self._zone_idx],
            self._metric_name,
        )
        return value if is_valid_sensor_reading(value) else None
