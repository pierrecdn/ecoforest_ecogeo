"""Base Entity for Ecoforest."""

from __future__ import annotations
from enum import Enum
from collections.abc import Callable

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import EcoGeoAirCoordinator
from .api.client import EcoGeoAirDevice


class EcoGeoAirApiDomain(Enum):
    """Domains for EcoGeoAir API."""

    MAIN = "main"
    ENERGY = "energy"
    THERMODYNAMIC = "thermodynamic"
    TEMP_REGULATION = "temp_regulation"
    ZONES = "zones"


@dataclass(frozen=True, kw_only=True)
class EcoGeoAirApiSensorEntityDescription(SensorEntityDescription):
    """Describes Ecogeoair sensor entity."""

    domain: EcoGeoAirApiDomain
    value_fn: Callable[[StateType], StateType] | None = None


@dataclass(frozen=True, kw_only=True)
class EcoGeoAirApiZoneSensorEntityDescription(EcoGeoAirApiSensorEntityDescription):
    """Describes Ecogeoair zone-based sensor entity."""

    zone_idx: int


class EcoGeoAirApiEntity(CoordinatorEntity[EcoGeoAirCoordinator]):
    """Common Ecogeoair entity using CoordinatorEntity."""

    _attr_has_entity_name = True
    entity_description: EcoGeoAirApiSensorEntityDescription

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        entity_description: EcoGeoAirApiSensorEntityDescription,
        device_alias: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        device_id = (
            coordinator.data.model.value if device_alias is None else device_alias
        )
        device_name = MANUFACTURER if device_alias is None else device_alias
        self._attr_unique_id = f"{device_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            model=coordinator.data.model.value,
            manufacturer=MANUFACTURER,
        )

    @property
    def data(self) -> EcoGeoAirDevice:
        """Return ecoforest data."""
        assert self.coordinator.data
        return self.coordinator.data
