"""The Ufanet Door Phone integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_ID, DEFAULT_SCAN_INTERVAL
from .ufanet_api import UfanetAPI, UfanetAuthError, UfanetConnectionError

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Ufanet Door Phone component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ufanet Door Phone from a config entry."""
    
    hass.data.setdefault(DOMAIN, {})
    
    # Получаем сохраненные учетные данные
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    device_id = entry.data.get(CONF_DEVICE_ID)
    
    # Создаем API клиент
    api = UfanetAPI(username, password, device_id)
    
    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            # Простая проверка подключения
            status = await api.async_get_status()
            _LOGGER.debug("API status: %s", status)
            return status
        except UfanetAuthError as err:
            raise ConfigEntryAuthFailed from err
        except UfanetConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
    
    # Создаем координатор для обновления данных
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )
    
    # Сохраняем данные
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "device_id": device_id
    }
    
    # Запускаем обновление данных для проверки подключения
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        await api.async_close()
        raise
    except Exception as err:
        await api.async_close()
        raise ConfigEntryNotReady from err
    
    # Обработчик для закрытия соединения при остановке HA
    async def async_shutdown(event):
        """Shutdown the integration."""
        await api.async_close()
    
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, async_shutdown)
    )
    
    _LOGGER.info("Ufanet Door Phone integration setup successfully for user: %s", username)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["api"].async_close()
    
    return True