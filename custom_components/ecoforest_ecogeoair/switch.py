"""Switch platform for Ecoforest EcoGeoAir."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ALIAS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.client import DHWMode, HeatingMode, InstalledFeatures, MachineStatus
from .const import DOMAIN, MANUFACTURER
from .coordinator import EcoGeoAirCoordinator


@dataclass(frozen=True, kw_only=True)
class EcoGeoAirSwitchEntityDescription(SwitchEntityDescription):
    """Describes an EcoGeoAir switch entity."""

    key: str


SWITCHES = [
    EcoGeoAirSwitchEntityDescription(
        key="machine",
        translation_key="machine",
    ),
    EcoGeoAirSwitchEntityDescription(
        key="dhw",
        translation_key="dhw",
    ),
    EcoGeoAirSwitchEntityDescription(
        key="pool",
        translation_key="pool",
    ),
    EcoGeoAirSwitchEntityDescription(
        key="heating",
        translation_key="heating",
    ),
    EcoGeoAirSwitchEntityDescription(
        key="cooling",
        translation_key="cooling",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ecoforest switch platform."""
    coordinator: EcoGeoAirCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    device_alias = config_entry.data.get(CONF_ALIAS)
    device_id = (
        coordinator.data.model.value if device_alias is None else device_alias
    )

    entities = [
        EcoGeoAirSwitch(coordinator, desc, device_id, device_alias) for desc in SWITCHES
    ]
    async_add_entities(entities)


class EcoGeoAirSwitch(CoordinatorEntity[EcoGeoAirCoordinator], SwitchEntity):
    """Representation of an Ecoforest switch entity."""

    entity_description: EcoGeoAirSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EcoGeoAirCoordinator,
        description: EcoGeoAirSwitchEntityDescription,
        device_id: str,
        device_alias: str | None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"
        device_name = MANUFACTURER if device_alias is None else device_alias
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            model=coordinator.data.model.value,
            manufacturer=MANUFACTURER,
        )

    @property
    def available(self) -> bool:
        """Return True if the service is installed on this device."""
        if not super().available:
            return False

        key = self.entity_description.key
        if key == "machine":
            return True

        features = self.coordinator.data.installed_features
        return _service_installed(key, features)

    @property
    def is_on(self) -> bool:
        """Return true when the user has enabled the feature on the device."""
        key = self.entity_description.key

        if key == "machine":
            return (
                self.coordinator.data.status.main.machine_status == MachineStatus.ON
            )

        enable = self.coordinator.data.status.slow_config.service_enable
        if key == "dhw":
            return enable.dhw
        if key == "pool":
            return enable.pool
        if key == "heating":
            return enable.heating
        if key == "cooling":
            return enable.cooling
        return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        api = self.coordinator.api
        key = self.entity_description.key
        if key == "machine":
            await api.set_machine_status(MachineStatus.ON)
        elif key == "dhw":
            await api.set_dhw_mode(DHWMode.ON)
        elif key == "pool":
            await api.set_pool_mode(HeatingMode.ON)
        elif key == "heating":
            await api.set_heating_mode(HeatingMode.ON)
        elif key == "cooling":
            await api.set_active_cooling_mode(True)
        if key == "machine":
            await self.coordinator.async_request_refresh()
        else:
            await self.coordinator.async_refresh_service_enable()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        api = self.coordinator.api
        key = self.entity_description.key
        if key == "machine":
            await api.set_machine_status(MachineStatus.OFF)
        elif key == "dhw":
            await api.set_dhw_mode(DHWMode.OFF)
        elif key == "pool":
            await api.set_pool_mode(HeatingMode.OFF)
        elif key == "heating":
            await api.set_heating_mode(HeatingMode.OFF)
        elif key == "cooling":
            await api.set_active_cooling_mode(False)
        if key == "machine":
            await self.coordinator.async_request_refresh()
        else:
            await self.coordinator.async_refresh_service_enable()


def _service_installed(key: str, features: InstalledFeatures) -> bool:
    """Return True when the device supports the service circuit."""
    if key == "dhw":
        return features.dhw
    if key == "pool":
        return features.pool
    if key == "heating":
        return features.heating
    if key == "cooling":
        return features.cooling
    return True
