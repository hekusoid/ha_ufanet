"""Config flow for Ufanet Door Phone."""
from __future__ import annotations

import logging
from typing import Any

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

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_ID, CONF_LOGGER_NAME

_LOGGER = logging.getLogger(CONF_LOGGER_NAME)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

class ResponceMockClass():
    def __init__(self, msg: str = ''):
        self.args = [{'non_field_errors':[msg]}]



async def validate_credentials(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user credentials."""
    
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    
    #ufanet_api = UfanetIntercomAPI(contract=username, password=password)
        
    try:
        _LOGGER.warning('validate_credentials: пробуем получить токен')
        #await ufanet_api._prepare_token()

        resp = TmpClass('Mock test message')
        
        raise BadRequestUfanetIntercomAPIError(resp)

        _LOGGER.warning('validate_credentials: токен получен, закрваем апи')
        #await ufanet_api.close()

        device_id = "ufanet_doorphone_001"
            
        return {
            "title": f"Домофон Ufanet (договор №{username})",
            "data": {
                **data,
                CONF_DEVICE_ID: device_id,
            }
        }
    except BadRequestUfanetIntercomAPIError as response:
        msg = response.args[0]['non_field_errors'][0]
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
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth as exp:
                errors["base"] = exp.args[0]
            except Exception as err:
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = f"Unexpected exception: {err}"
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