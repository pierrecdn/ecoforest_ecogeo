"""Support for Ecoforest sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ALIAS
from homeassistant.helpers.typing import StateType

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EcoGeoAirCoordinator
from .entity import EcoGeoApiEntity, EcoGeoApiSensorEntityDescription
from .api import client as api_module

_LOGGER = logging.getLogger(__name__)

MAPPING = {
    "main": {
        "production_circuit_pressure": {
            "entity_type": "pressure",
        },
        "ground_circuit_pressure": {
            "entity_type": "pressure",
        },
        "production_circuit_input_temperature": {
            "entity_type": "temperature",
        },
        "production_circuit_output_temperature": {
            "entity_type": "temperature",
        },
        "ground_circuit_input_temperature": {
            "entity_type": "temperature",
        },
        "ground_circuit_output_temperature": {
            "entity_type": "temperature",
        },
        "outdoor_temperature": {
            "entity_type": "temperature",
        },
        "alarm_active": {
            "entity_type": "measurement",
            "value_fn": lambda data: data.status.main.alarm_status
            != api_module.AlarmStatus.OFF,
        },
    },
    "energy": {
        "heating_power": {
            "entity_type": "power",
        },
        "cooling_power": {
            "entity_type": "power",
        },
        "total_consumption": {
            "entity_type": "power",
        },
        "cop": {
            "entity_type": "measurement",
            "type": "float",
        },
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ecoforest sensor platform."""
    coordinator: EcoGeoAirCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    device_alias = config_entry.data.get(CONF_ALIAS, None)
    entities = [
        EcoGeoAirSensor(coordinator, domain, key, definition, device_alias)
        for domain, entries in MAPPING.items()
        for key, definition in entries.items()
    ]

    # Per-zone sensors: temperature setpoint, current temperature and humidity
    for idx, val in enumerate(coordinator.data.status.energy.zone_modes):
        # Filter active zones only
        if val == 0:
            continue

        entities.extend(
            [
                EcoGeoAirSensor(
                    coordinator,
                    "temp_regulation",
                    f"{metric_name}_zone_{idx + 1}",
                    {
                        "entity_type": metric_type,
                        "value_fn": lambda data,
                        zone_idx=idx,
                        metric=metric_name: getattr(
                            coordinator.data.status.temp_regulation.zones[zone_idx],
                            metric,
                        ),
                    },
                    device_alias,
                )
                for metric_name, metric_type in [
                    ("temperature_setpoint", "temperature"),
                    ("temperature_current", "temperature"),
                    ("humidity", "humidity"),
                ]
            ]
        )

    async_add_entities(entities)


class EcoGeoAirSensor(SensorEntity, EcoGeoApiEntity):
    """Representation of an Ecoforest sensor."""

    entity_description: EcoGeoApiSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(self.data)

        domain_obj = getattr(self.data.status, self.entity_description.domain)
        return getattr(domain_obj, self.entity_description.key)
