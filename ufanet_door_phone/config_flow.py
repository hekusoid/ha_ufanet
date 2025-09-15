"""Config flow for Ufanet Door Phone."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_ID, UFANET_API_AUTH

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

async def validate_credentials(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user credentials and get device info."""
    
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    
    async with aiohttp.ClientSession() as session:
        try:
            # Аутентификация в API Ufanet
            async with session.post(
                UFANET_API_AUTH,
                json={"username": username, "password": password}
            ) as response:
                if response.status != 200:
                    raise InvalidAuth("Invalid credentials")
                
                auth_data = await response.json()
                token = auth_data.get("token")
                
                # Получение списка устройств
                async with session.get(
                    f"{UFANET_API_DEVICES}?token={token}"
                ) as devices_response:
                    if devices_response.status != 200:
                        raise CannotConnect("Cannot get devices list")
                    
                    devices = await devices_response.json()
                    doorphones = [d for d in devices if d.get("type") == "doorphone"]
                    
                    if not doorphones:
                        raise NoDevices("No doorphone devices found")
                    
                    # Используем первое найденное домофонное устройство
                    device_id = doorphones[0]["id"]
                    device_name = doorphones[0]["name"]
                    
                    return {
                        "title": f"Ufanet Door Phone - {device_name}",
                        "data": {
                            **data,
                            CONF_DEVICE_ID: device_id,
                            "token": token
                        }
                    }
                    
        except aiohttp.ClientError as err:
            raise CannotConnect(f"Cannot connect to Ufanet API: {err}") from err

class UfanetDoorPhoneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ufanet Door Phone."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_credentials(self.hass, user_input)
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoDevices:
                errors["base"] = "no_devices"
            except Exception:
                _LOGGER.exception("Unexpected exception")
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
            description_placeholders={
                "setup_url": "https://cabinet.ufanet.ru"
            },
        )

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to Ufanet API."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid authentication credentials."""

class NoDevices(HomeAssistantError):
    """Error to indicate no doorphone devices found."""