"""Data models and enums for Ecoforest EcoGeoAir API client."""

import dataclasses
from datetime import datetime
from enum import Enum, IntEnum
from http import HTTPStatus
import json
import logging
from pathlib import Path
from typing import Any

import aiohttp
from custom_components.ecoforest_ecogeoair.const import LOCAL_TIMEOUT

from .exceptions import (
    EcoGeoAirApiError,
    EcoGeoAirAuthError,
    EcoGeoAirConnectionError,
    EcoGeoAirDeviceError,
)

URL_CGI = "/recepcion_datos_4.cgi"

_LOGGER = logging.getLogger(__name__)


class Model(Enum):
    # 1-2-5=Ecogeo, 3-4=Ecoair
    ECOGEO = "ecogeo"
    ECOAIR = "ecoair"

    @staticmethod
    def from_code(code: int) -> "Model":
        if code in [1, 2, 5]:
            return Model.ECOGEO
        elif code in [3, 4]:
            return Model.ECOAIR
        else:
            raise ValueError(f"Unknown model code: {code}")


class TemperatureUnit(IntEnum):
    CELSIUS = 0
    FAHRENHEIT = 1


class PressureUnit(IntEnum):
    BAR = 0
    PSI = 1


class AlarmStatus(Enum):
    # 0=Off, 1-4=Active, 2-3=Recurrent, 5=Blocked
    OFF = "off"
    ACTIVE = "active"
    RECURRENT = "recurrent"
    BLOCKED = "blocked"

    @staticmethod
    def from_code(code: int) -> "AlarmStatus":
        """Convert integer code to AlarmStatus enum."""
        if code == 0:
            return AlarmStatus.OFF
        if code in [1, 4]:
            return AlarmStatus.ACTIVE
        if code in [2, 3]:
            return AlarmStatus.RECURRENT
        if code == 5:
            return AlarmStatus.BLOCKED
        raise ValueError(f"Unknown alarm status code: {code}")


class MachineStatus(IntEnum):
    ON = 1
    EMERGENCY = 2
    OFF = 3


class SeasonMode(IntEnum):
    WINTER = 0
    SUMMER = 1
    MIXED = 2


class WorkingMode(IntEnum):
    OFF = 0
    ON = 1
    AUTO = 2
    REMOTE = 3


class HeatingMode(IntEnum):
    OFF = 0
    ON = 1
    DEFROST = 4


class DHWMode(IntEnum):
    OFF = 0
    ON = 1
    LEGIONELLA = 2
    DEFROST = 4


class HTRMode(IntEnum):
    OFF = 0
    DHW = 1
    POOL = 2


class ODUStatus(IntEnum):
    DISABLED = -9999
    OFF = 0
    ON = 1
    EMERGENCY = 2


class ZoneMode(IntEnum):
    OFF = 0
    HEAT = 1
    COOL = 2


@dataclasses.dataclass
class GroupStatus:
    """Data model for a Group."""

    heating_setpoint: float
    cooling_setpoint: float
    temperature: float
    regulation_percentage: float


@dataclasses.dataclass
class ZoneAmbianceStatus:
    """Data model for Zone (measurement point)."""

    temperature_setpoint: float
    temperature_current: float
    humidity: float


@dataclasses.dataclass
class TempRegulationStatus:
    """Data model for endpoint 2150."""

    boiler_status: bool
    boiler_temperature: float
    boiler_regulation: float
    chiller_status: bool
    chiller_temperature: float
    chiller_regulation: float
    heat_temperature: float
    active_cool_temperature: float
    passive_cool_temperature: float
    zones: list[ZoneAmbianceStatus]
    current_power_value: float
    power_surplus_status: bool
    power_surplus_setpoint: float
    power_limit_status: bool
    power_limit_setpoint: float


@dataclasses.dataclass
class ThermodynamicStatus:
    """Data model for endpoint 2151."""

    heating_groups: list[GroupStatus]  # Groups 1-4 data
    heat_buffer_temperature: float
    heat_buffer_setpoint: float
    heat_buffer_offset: float
    cool_buffer_temperature: float
    cool_buffer_setpoint: float
    cool_buffer_offset: float
    dhw_tank_temperature: float
    dhw_tank_setpoint: float
    dhw_tank_offset: float
    dhw_recirculation_status: bool
    dhw_recirculation_temperature: float
    dhw_recirculation_setpoint: float
    dhw_recirculation_offset: float
    pool_setpoint: float


@dataclasses.dataclass
class ZoneStatus(GroupStatus):
    """Data model for a single zone."""


@dataclasses.dataclass
class ZonesStatus:
    """Data model for endpoint 2152."""

    zones: list[ZoneStatus]
    heating_buffer: float
    heating_buffer_setpoint: float
    heating_buffer_offset: float
    cooling_buffer: float
    cooling_buffer_setpoint: float
    cooling_buffer_offset: float
    dhw_temperature: float
    dhw_setpoint: float
    dhw_offset: float
    dhw_recirculation_status: bool
    dhw_return_temperature: float
    dhw_recirculation_temperature: float
    dhw_recirculation_offset: float
    pool_setpoint: float


@dataclasses.dataclass
class MainStatus:
    """Data model for endpoint 2148."""

    model: Model  # 1-2-5=EcoGeo, 3-4=EcoAir
    timestamp: datetime
    machine_status: MachineStatus
    alarm_status: AlarmStatus
    season_mode: SeasonMode
    working_mode: WorkingMode
    time_program_active: bool
    surplus_control_active: bool
    tariff_control_active: bool
    night_mode_active: bool
    smart_grid_status: int  # 1-4=SG modes, 5=EVU off
    consumption_control_active: bool
    production_circuit_pressure: float
    production_circuit_input_temperature: float
    production_circuit_output_temperature: float
    ground_circuit_pressure: float
    ground_circuit_input_temperature: float
    ground_circuit_output_temperature: float
    outdoor_temperature: float
    heating_mode: HeatingMode
    dhw_mode: DHWMode
    active_cooling_mode: bool
    passive_cooling_mode: bool
    pool_mode: HeatingMode
    htr_mode: HTRMode
    heating_tank: bool
    cooling_tank: bool
    extra_dhw_active: bool


@dataclasses.dataclass
class EnergyStatus:
    """Data model for endpoint 2149."""

    heating_power: int
    cooling_power: int
    electric_power_input: int
    active_cooling_demand: bool
    antifreeze_demand: bool
    dhw_tank_demand: bool
    heating_tank_demand: bool
    legionella_tank_demand: bool
    passive_cooling_demand: bool
    pool_circuit_demand: bool
    zone_modes: list[int]  # 0=Off, 1=Heat, 2=Cool, for each zone
    max_dwh_power: bool
    max_heating_power: bool
    current_consumption: int
    energy_control_type: int
    dhw_htr_active: bool
    pool_htr_active: bool

    @property
    def total_consumption(self) -> int:
        """Get electric consumption (positive value)."""
        return abs(self.electric_power_input + self.current_consumption)

    @property
    def cop(self) -> float:
        """Calculate Coefficient of Performance (COP)."""
        if self.total_consumption == 0:
            return 0
        return round(self.heating_power / self.total_consumption, 1)

    @property
    def eer(self) -> float:
        """Calculate Energy Efficiency Ratio (EER)."""
        if self.total_consumption == 0:
            return 0
        return round(self.cooling_power / self.total_consumption, 1)

    @property
    def pf(self) -> float:
        """Calculate Performance Factor (PF)."""
        if self.total_consumption == 0:
            return 0
        return (self.heating_power + self.cooling_power) / self.total_consumption


@dataclasses.dataclass
class DeviceStatus:
    """Combined status from all endpoints."""

    main: MainStatus
    energy: EnergyStatus
    thermodynamic: ThermodynamicStatus | None = None
    temp_regulation: TempRegulationStatus | None = None
    zones: ZonesStatus | None = None


@dataclasses.dataclass
class EcoGeoAirDevice:
    """Device configuration that changes rarely."""

    model: Model
    temperature_unit: TemperatureUnit
    pressure_unit: PressureUnit
    status: DeviceStatus


class EcoGeoAirApi:
    """Client for the EcoGeoAir API."""

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the EcoGeoAir API client."""
        self._host = host
        self._auth = aiohttp.BasicAuth(user, password)
        self._timeout = LOCAL_TIMEOUT

        # Load API mapping once at initialization
        mapping_path = Path(__file__).parent / "api_mapping.json"
        with Path.open(mapping_path, encoding="utf-8") as f:
            self._api_mapping = json.load(f)
        self._client = session
        self._device: EcoGeoAirDevice | None = None

    @property
    def device(self) -> EcoGeoAirDevice:
        """Get the device info after initialization."""
        if self._device is None:
            raise EcoGeoAirApiError("API not initialized, call initialize() first")
        return self._device

    async def initialize(self) -> None:
        """Initialize the API client (async call not doable in __init__)."""
        if self._client is None:
            self._client = aiohttp.ClientSession(
                base_url=f"http://{self._host}/", auth=self._auth
            )
        self._device = await self.get_device()

    @staticmethod
    def _extract_payload(data: str) -> list[str]:
        """Extract the payload and check for errors."""
        data_lines = data.splitlines()
        # Check if there's an error in the return (format is "error_id=XXXX" on the first line, XXXX != 0)
        try:
            error_prefix, error_value = data_lines[0].split("=")
        except ValueError as exc:
            raise EcoGeoAirApiError(
                "Unexpected API output format, no error header"
            ) from exc
        if not error_prefix.startswith("error_"):
            raise EcoGeoAirApiError("Unexpected API output format, no error header")
        try:
            error_code = int(error_value)
        except ValueError as exc:
            raise EcoGeoAirApiError(
                "Unexpected API output format, error value isn't an integer"
            ) from exc
        if error_code != 0:
            raise EcoGeoAirDeviceError(
                f"The API call returned an error, code={error_code}"
            )

        # Remove first and last line from response (first=error, last="0")
        return data_lines[1:-1]

    @staticmethod
    def _map_to_prefix(data: list[str]) -> dict[str, str]:
        # For some reason, certain endpoints return name=value output while other don't.
        # For those organized that way, this method perform a name/value dict mapping.
        try:
            return dict(data_line.split("=") for data_line in data)
        except ValueError as exc:
            raise EcoGeoAirApiError(
                "Unexpected API output format, this endpoint was supposedly"
                "using a name=value output"
            ) from exc

    async def _call(self, endpoint_identifier: int) -> list[str]:
        data = f"idOperacion={endpoint_identifier}"
        _LOGGER.debug("Sending POST to %s with data=%s", URL_CGI, data)

        if self._client is None:
            raise EcoGeoAirApiError(
                "API client not initialized, call initialize() first"
            )
        try:
            response = await self._client.post(
                URL_CGI, auth=self._auth, timeout=self._timeout, data=data
            )
        except (
            aiohttp.ConnectionTimeoutError,
            aiohttp.ServerTimeoutError,
            aiohttp.SocketTimeoutError,
        ) as cto:
            raise EcoGeoAirConnectionError from cto
        except aiohttp.ClientError as ce:
            raise EcoGeoAirConnectionError from ce

        if response.status in [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN]:
            raise EcoGeoAirAuthError(status=response.status)

        parsed_response = self._extract_payload(await response.text())
        _LOGGER.debug("Received from POST with data=%s: %s", data, parsed_response)

        return parsed_response

    def _parse_value(self, value: str, field_type: str, prefixed: bool = False) -> Any:
        """Parse a value according to its type and apply unit conversion if needed."""
        if prefixed:
            # If the response is prefixed (name=value), extract the value part
            try:
                _, value = value.split("=")
            except ValueError as exc:
                raise EcoGeoAirApiError(
                    "Unexpected API output format, this endpoint was supposedly"
                    "using a name=value output"
                ) from exc
        if value == "-":
            return None
        if field_type == "int":
            result = int(value, 16)
            return result if result <= 32768 else result - 65536
        if field_type == "float":
            return float(self._parse_value(value, "int")) / 10.0
        # Base temp/pressure units are celsius/bar, convert to base unit if needed.
        if field_type == "temperature":
            value = self._parse_value(value, "float")
            if (
                self._device
                and self._device.temperature_unit == TemperatureUnit.FAHRENHEIT
            ):
                value = value * 1.8 + 32
            return value
        if field_type == "pressure":
            value = self._parse_value(value, "float")
            if self._device and self._device.pressure_unit == PressureUnit.PSI:
                value = value * 14.5
            return value
        if field_type == "bool":
            return bool(self._parse_value(value, "int") == 1)
        raise ValueError(f"Unknown field type: {field_type}")

    def _parse_response(
        self, endpoint: str, values: list[str], prefixed: bool = False
    ) -> dict[str, Any]:
        """Parse a response according to the mapping."""
        if endpoint not in self._api_mapping:
            raise EcoGeoAirApiError(f"Unknown endpoint: {endpoint}")

        result = {}
        for idx, field in enumerate(self._api_mapping[endpoint]):
            if field["name"] == "-":  # Skip reserved fields
                continue
            if idx >= len(values):
                _LOGGER.warning("Missing value for field %s in response", field["name"])
                continue
            try:
                result[field["name"]] = self._parse_value(
                    values[idx], field["type"], prefixed=prefixed
                )
            except (ValueError, IndexError) as e:
                _LOGGER.error("Failed to parse field %s: %s", field["name"], e)
                continue
        _LOGGER.debug("Parsed response for endpoint %s: %s", endpoint, result)
        return result

    async def get_main_status(self) -> MainStatus:
        """Get main device status (endpoint 2148)."""
        values = await self._call(2148)
        data = self._parse_response("2148", values)
        return MainStatus(
            model=Model.from_code(data["lg"]),
            timestamp=datetime(
                2000 + data["cy"], data["cmo"], data["cd"], data["ch"], data["cm"]
            ),
            machine_status=MachineStatus(data["ico1"]),
            alarm_status=AlarmStatus.from_code(data["ic2"]),
            season_mode=SeasonMode(data["ic3"]),
            working_mode=WorkingMode(data["ic4"]),
            time_program_active=data["ta"],
            surplus_control_active=data["fe"],
            tariff_control_active=data["fet"],
            night_mode_active=data["fehn"],
            smart_grid_status=data["fsoe"],
            consumption_control_active=data["fcc"],
            production_circuit_pressure=data["pcc"],
            production_circuit_input_temperature=data["tic"],
            production_circuit_output_temperature=data["trc"],
            ground_circuit_pressure=data["pcp"],
            ground_circuit_input_temperature=data["tip"],
            ground_circuit_output_temperature=data["trp"],
            outdoor_temperature=data["tem"],
            heating_mode=HeatingMode(data["hpfm"]),
            dhw_mode=DHWMode(data["dpfm"]),
            active_cooling_mode=data["cpfm"],
            passive_cooling_mode=data["epmrp"],
            pool_mode=HeatingMode(data["ppfmode"]),
            htr_mode=HTRMode(data["htpfm"]),
            heating_tank=bool(data["haf"] & 2) or bool(data["haf"] & 4),
            cooling_tank=bool(data["caf"] & 2) or bool(data["caf"] & 4),
            extra_dhw_active=bool(data["ea3"]),
        )

    async def get_energy_status(self) -> EnergyStatus:
        """Get energy status (endpoint 2149)."""
        values = await self._call(2149)
        data = self._parse_response("2149", values)
        return EnergyStatus(
            heating_power=data["hui"],
            cooling_power=data["coui"],
            electric_power_input=data["weci"],
            active_cooling_demand=data["acbtd"],
            antifreeze_demand=data["abd"],
            dhw_tank_demand=data["dtd"],
            heating_tank_demand=data["hbtd"],
            legionella_tank_demand=data["ltd"],
            passive_cooling_demand=data["pcbtd"],
            pool_circuit_demand=data["pcd"],
            zone_modes=[ZoneMode(data[f"cdig{i}"]) for i in range(1, 6)],
            max_dwh_power=data["cmap"],
            max_heating_power=data["cmip"],
            current_consumption=data["cici"],
            energy_control_type=data["eccop"],
            dhw_htr_active=data["dhac"],
            pool_htr_active=data["hpdc"],
        )

    async def get_temp_regulation_status(self) -> TempRegulationStatus:
        """Get temperature regulation status (endpoint 2150)."""
        values = await self._call(2150)
        data = self._parse_response("2150", values)
        zones = [
            ZoneAmbianceStatus(
                temperature_setpoint=data[f"tsz{i}"],
                temperature_current=data[f"ttz{i}"],
                humidity=data[f"thz{i}"],
            )
            for i in range(1, 6)
        ]
        return TempRegulationStatus(
            boiler_status=data["ea2"],
            boiler_temperature=data["tica"],
            boiler_regulation=data["rc"],
            chiller_status=data["ea5"],
            chiller_temperature=data["acdt"],
            chiller_regulation=data["rac"],
            heat_temperature=data["tcc"],
            active_cool_temperature=data["tcfa"],
            passive_cool_temperature=data["tcfp"],
            zones=zones,
            current_power_value=data["pb"],
            power_surplus_status=data["scsm"],
            power_surplus_setpoint=data["scsp"],
            power_limit_status=data["clsm"],
            power_limit_setpoint=data["clsp"],
        )

    async def get_thermodynamic_status(self) -> ThermodynamicStatus:
        """Get thermodynamic status (endpoint 2151)."""
        values = await self._call(2151)
        data = self._parse_response("2151", values)

        heating_groups = [
            GroupStatus(
                heating_setpoint=data[f"hdtsg{i}"],
                cooling_setpoint=data[f"cdtsg{i}"],
                temperature=data[f"ti{i}"],
                regulation_percentage=data[f"rvz{i}"],
            )
            for i in range(1, 5)
        ]

        return ThermodynamicStatus(
            heating_groups=heating_groups,
            heat_buffer_temperature=data["ticiner"],
            heat_buffer_setpoint=data["hbtsp"],
            heat_buffer_offset=data["oic"],
            cool_buffer_temperature=data["tif"],
            cool_buffer_setpoint=data["cbtsp"],
            cool_buffer_offset=data["oif"],
            dhw_tank_temperature=data["ao"],
            dhw_tank_setpoint=data["dt"],
            dhw_tank_offset=data["dsm"],
            dhw_recirculation_status=data["dcfm"],
            dhw_recirculation_temperature=data["rc"],
            dhw_recirculation_setpoint=data["drt"],
            dhw_recirculation_offset=data["ro"],
            pool_setpoint=data["ppspf"],
        )

    async def get_zones_status(self) -> ZonesStatus:
        """Get zones status (endpoint 2152)."""
        values = await self._call(2152)
        data = self._parse_response("2152", values)
        zones = [
            ZoneStatus(
                heating_setpoint=data[f"hdtsg{i}"],
                cooling_setpoint=data[f"cdtsg{i}"],
                temperature=data[f"ti{i}"],
                regulation_percentage=data[f"rvz{i}"],
            )
            for i in range(1, 6)
        ]
        return ZonesStatus(
            zones=zones,
            heating_buffer=data["ticiner"],
            heating_buffer_setpoint=data["hbtsp"],
            heating_buffer_offset=data["oic"],
            cooling_buffer=data["tif"],
            cooling_buffer_setpoint=data["cbtsp"],
            cooling_buffer_offset=data["oif"],
            dhw_temperature=data["dt"],
            dhw_setpoint=data["dsm"],
            dhw_offset=data["ao"],
            dhw_recirculation_status=data["dcfm"],
            dhw_return_temperature=data["drt"],
            dhw_recirculation_temperature=data["rc"],
            dhw_recirculation_offset=data["ro"],
            pool_setpoint=data["ppspf"],
        )

    async def get_device_status(self) -> DeviceStatus:
        """Get complete device status from all endpoints."""
        main = await self.get_main_status()
        energy = await self.get_energy_status()
        thermodynamic = await self.get_thermodynamic_status()
        temp_regulation = await self.get_temp_regulation_status()
        zones = await self.get_zones_status()
        return DeviceStatus(
            main=main,
            energy=energy,
            thermodynamic=thermodynamic,
            temp_regulation=temp_regulation,
            zones=zones,
        )

    async def get_device(self) -> EcoGeoAirDevice:
        """Get device unit preferences (endpoint 2006)."""
        values = await self._call(2006)
        # endpoint 2006 returns key=value lines (prefixed); parse by name
        data = self._parse_response("2006", values, prefixed=True)
        # Fetch full device status
        device_status = await self.get_device_status()
        self._device = EcoGeoAirDevice(
            model=device_status.main.model,
            temperature_unit=TemperatureUnit(data["utemp"]),
            pressure_unit=PressureUnit(data["upres"]),
            status=device_status,
        )
        return self._device
