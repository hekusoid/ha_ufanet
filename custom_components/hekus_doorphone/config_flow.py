"""Config flow for Ufanet Door Phone."""
from __future__ import annotations

import logging
from typing import (Any, List)

import voluptuous as vol
import aiohttp
import asyncio
from .api.ufanet_api import UfanetIntercomAPI
from .api.exceptions import (BadRequestUfanetIntercomAPIError)

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client

from .device import DoorPhoneDevice, create_devices
from .api.models import Intercom

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_ID, CONF_LOGGER_NAME

_LOGGER = logging.getLogger(CONF_LOGGER_NAME)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

async def validate_credentials(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user credentials."""
    
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    
    ufanet_api = UfanetIntercomAPI(contract=username, password=password)
        
    try:
        await ufanet_api._prepare_token()

        await ufanet_api.close()

        return {
            "title": f"Домофон Ufanet (договор №{username})",
            "data": {
                **data,
                'name': CONF_DEVICE_ID,
                'token': '_mock_token_guid'                 
            }
        }
    except BadRequestUfanetIntercomAPIError as exp:
        msg = exp.args[0]['non_field_errors'][0]
        raise InvalidAuth(msg)
    except aiohttp.ClientError as err:
        raise CannotConnect(f"Cannot connect to Ufanet API: {err}") from err
    except asyncio.TimeoutError:
        raise CannotConnect("Connection timeout") from None

class UfanetDoorPhoneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ufanet Door Phone."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            try:
                info = await validate_credentials(self.hass, user_input)
            except CannotConnect as exp:
                errors["base"] = f"Ошибка подключения: {exp.args[0]}"
            except InvalidAuth as exp:
                errors["base"] = f"Ошибка аутентификации: {exp.args[0]}"
            except Exception as exp:
                _LOGGER.exception("Unexpected exception: %s", exp)
                errors["base"] = f"Unexpected exception: {exp}"
            else:
                return self.async_create_entry(
                    title=info["title"], 
                    data=info["data"]
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to Ufanet API."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid authentication credentials."""