"""Config flow for Ecoforest integration."""

from __future__ import annotations
from functools import partial

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_ALIAS

from .const import DOMAIN, MANUFACTURER
from custom_components.ecoforest_ecogeoair.api.client import EcoGeoAirApi
from custom_components.ecoforest_ecogeoair.api.exceptions import (
    EcoGeoAirAuthError,
    EcoGeoAirConnectionError,
    EcoGeoAirError,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_ALIAS): str,
    }
)


class EcoForestEcoGeoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecoforest."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                api_kwargs = {
                    "host": user_input[CONF_HOST],
                    "user": user_input[CONF_USERNAME],
                    "password": user_input[CONF_PASSWORD],
                }
                api = await self.hass.async_add_executor_job(
                    partial(EcoGeoAirApi, **api_kwargs)
                )
                await api.initialize()
            except EcoGeoAirAuthError:
                errors["base"] = "invalid_auth"
            except EcoGeoAirConnectionError:
                errors["base"] = "cannot_connect"
            except EcoGeoAirError as e:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown_exception"
            else:
                device_id = api.device.model.name
                title = f"{MANUFACTURER} {api.device.model.name}"

                if CONF_ALIAS in user_input:
                    device_id = user_input[CONF_ALIAS]
                    title = f"{title} ({user_input[CONF_ALIAS]})"

                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
