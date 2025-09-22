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

from .device import DoorPhoneDevice, create_devices
from .api.models Intercom

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_ID, CONF_LOGGER_NAME

_LOGGER = logging.getLogger(CONF_LOGGER_NAME)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

def get_mock_intercoms() -> List[Intercom]:
    mock_responce = [{'id': 109757, 'contract': None, 'role': {'id': 8, 'name': 'Домофон-калитка'}, 'camera': None, 'cctv_number': '1738053250GTF70', 'string_view': 'г. Уфа, Заки Валиди, 71', 'timeout': 10, 'disable_button': False, 'no_sound': True, 'open_in_talk': 'http', 'open_type': 'http', 'dtmf_code': '#0', 'inactivity_reason': None, 'house': 458263, 'frsi': True, 'is_fav': False, 'model': 39, 'custom_name': None, 'is_blocked': False, 'supports_key_recording': True, 'ble_support': True, 'is_support_sip_monitor': False, 'relays': [], 'private_status': 1, 'scope': 'owner'}, {'id': 103616, 'contract': None, 'role': {'id': 8, 'name': 'Домофон-калитка'}, 'camera': None, 'cctv_number': '1737985955HSN76', 'string_view': 'г. Уфа, Заки Валиди, 73', 'timeout': 10, 'disable_button': False, 'no_sound': True, 'open_in_talk': 'http', 'open_type': 'http', 'dtmf_code': '#0', 'inactivity_reason': None, 'house': 31465, 'frsi': True, 'is_fav': False, 'model': 39, 'custom_name': None, 'is_blocked': False, 'supports_key_recording': True, 'ble_support': True, 'is_support_sip_monitor': False, 'relays': [], 'private_status': 1, 'scope': 'owner'}, {'id': 103413, 'contract': 664192, 'role': {'id': 2, 'name': 'Домофон'}, 'camera': None, 'cctv_number': '1737976793GSM0', 'string_view': 'г. Уфа, Заки Валиди, 73, п.1', 'timeout': 10, 'disable_button': False, 'no_sound': True, 'open_in_talk': 'http', 'open_type': 'http', 'dtmf_code': '#0', 'inactivity_reason': None, 'house': 31465, 'frsi': True, 'is_fav': False, 'model': 39, 'custom_name': None, 'is_blocked': False, 'supports_key_recording': True, 'ble_support': True, 'is_support_sip_monitor': False, 'relays': [], 'private_status': 1, 'scope': 'owner'}]
    return [Intercom(**i) for i in mock_responce]

async def validate_credentials(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user credentials."""
    
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    
    #ufanet_api = UfanetIntercomAPI(contract=username, password=password)
        
    try:
        #await ufanet_api._prepare_token()

        #await ufanet_api.close()

        intecoms = get_mock_intercoms()

        devices = create_devices(intercoms)
            
        return {
            "title": f"Домофон Ufanet (договор №{username})",
            "data": {
                **data,
                'name': CONF_DEVICE_ID,
                devices : devices
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
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth as exp:
                errors["base"] = f"Ошибка аутентификации: {exp.args[0]}"
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