"""The Ufanet Door Phone integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import (List)

from homeassistant.config_entries import ConfigEntry 
from homeassistant.const import EVENT_HOMEASSISTANT_STOP 
from homeassistant.core import HomeAssistant 
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed 
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed 

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_ID, DEFAULT_SCAN_INTERVAL, CONF_LOGGER_NAME
from .api.ufanet_api import UfanetIntercomAPI
from .api.models import Intercom
from .api.exceptions import UnauthorizedUfanetIntercomAPIError, ClientConnectorUfanetIntercomAPIError

from .device import DoorPhoneDevice, create_devices

_LOGGER = logging.getLogger(CONF_LOGGER_NAME)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Ufanet Door Phone component."""
    hass.data.setdefault(DOMAIN, {})
    return True

def get_mock_intercoms() -> List[Intercom]:
    mock_responce = [{'id': 109757, 'contract': None, 'role': {'id': 8, 'name': 'Домофон-калитка'}, 'camera': None, 'cctv_number': '1738053250GTF70', 'string_view': 'г. Уфа, Заки Валиди, 71', 'timeout': 10, 'disable_button': False, 'no_sound': True, 'open_in_talk': 'http', 'open_type': 'http', 'dtmf_code': '#0', 'inactivity_reason': None, 'house': 458263, 'frsi': True, 'is_fav': False, 'model': 39, 'custom_name': None, 'is_blocked': False, 'supports_key_recording': True, 'ble_support': True, 'is_support_sip_monitor': False, 'relays': [], 'private_status': 1, 'scope': 'owner'}, {'id': 103616, 'contract': None, 'role': {'id': 8, 'name': 'Домофон-калитка'}, 'camera': None, 'cctv_number': '1737985955HSN76', 'string_view': 'г. Уфа, Заки Валиди, 73', 'timeout': 10, 'disable_button': False, 'no_sound': True, 'open_in_talk': 'http', 'open_type': 'http', 'dtmf_code': '#0', 'inactivity_reason': None, 'house': 31465, 'frsi': True, 'is_fav': False, 'model': 39, 'custom_name': None, 'is_blocked': False, 'supports_key_recording': True, 'ble_support': True, 'is_support_sip_monitor': False, 'relays': [], 'private_status': 1, 'scope': 'owner'}, {'id': 103413, 'contract': 664192, 'role': {'id': 2, 'name': 'Домофон'}, 'camera': None, 'cctv_number': '1737976793GSM0', 'string_view': 'г. Уфа, Заки Валиди, 73, п.1', 'timeout': 10, 'disable_button': False, 'no_sound': True, 'open_in_talk': 'http', 'open_type': 'http', 'dtmf_code': '#0', 'inactivity_reason': None, 'house': 31465, 'frsi': True, 'is_fav': False, 'model': 39, 'custom_name': None, 'is_blocked': False, 'supports_key_recording': True, 'ble_support': True, 'is_support_sip_monitor': False, 'relays': [], 'private_status': 1, 'scope': 'owner'}]
    return [Intercom(**i) for i in mock_responce]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ufanet Door Phone from a config entry."""
    
    hass.data.setdefault(DOMAIN, {})
    
    # Получаем сохраненные учетные данные
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    #device_id = entry.data.get(CONF_DEVICE_ID)
    
    # Создаем API клиент
    ufanet_api = UfanetIntercomAPI(contract=username, password=password)
    
    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            # Простая проверка подключения
            status = 'mock OK status' # await api.async_get_status()
            _LOGGER.debug("API status: %s", status)
            return status
        except UnauthorizedUfanetIntercomAPIError as err:
            raise ConfigEntryAuthFailed from err
        except ClientConnectorUfanetIntercomAPIError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
    
    # Создаем координатор для обновления данных
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )
    
    intercoms = get_mock_intercoms()

    devices = create_devices(intercoms)

    _LOGGER.warning(f'Setup entry {entry.entry_id}')

    # Сохраняем данные
    hass.data[DOMAIN][entry.entry_id] = {
        "api": ufanet_api,
        "coordinator": coordinator,
        devices: devices
        #"device_id": device_id
    }
    
    # Запускаем обновление данных для проверки подключения
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        await ufanet_api.async_close()
        raise
    except Exception as err:
        await ufanet_api.async_close()
        raise ConfigEntryNotReady from err
    
    # Обработчик для закрытия соединения при остановке HA
    async def async_shutdown(event):
        """Shutdown the integration."""
        await ufanet_api.async_close()
    
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, async_shutdown)
    )
    
    _LOGGER.warning("Ufanet Door Phone integration setup successfully for user: %s", username)
    
    await hass.config_entries.async_forward_entry_setups(entry, ["button"])

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["api"].close()
        await hass.config_entries.async_unload_platforms(entry, ["button"])
    
    return True