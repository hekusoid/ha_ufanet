"""Config flow for Ufanet Door Phone."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import aiohttp
import asyncio
from .api.ufanet_api import UfanetIntercomAPI

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

async def validate_credentials(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user credentials."""
    
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    
    session = aiohttp_client.async_get_clientsession(hass)

    ufanet_api = UfanetIntercomAPI(contract=username, password=password)

        
    try:
        await ufanet_api._prepare_token()
        await ufanet_api.close()

        device_id = "ufanet_doorphone_001"
            
        return {
            "title": f"Ufanet Door Phone - {username}",
            "data": {
                **data,
                CONF_DEVICE_ID: device_id,
            }
        }
            
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
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"
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