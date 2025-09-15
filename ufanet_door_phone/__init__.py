"""The Ufanet Door Phone integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_ID, DEFAULT_SCAN_INTERVAL
from .ufanet_api import UfanetAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SWITCH, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ufanet Door Phone from a config entry."""
    
    hass.data.setdefault(DOMAIN, {})
    
    # Получаем сохраненные учетные данные
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    device_id = entry.data[CONF_DEVICE_ID]
    
    # Создаем API клиент
    api = UfanetAPI(username, password, device_id)
    
    # Создаем координатор для обновления данных
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=api.async_get_status,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )
    
    # Сохраняем данные
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "device_id": device_id
    }
    
    # Загружаем платформы
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Запускаем обновление данных
    await coordinator.async_config_entry_first_refresh()
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok