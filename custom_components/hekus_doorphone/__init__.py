"""Интеграция Ufanet Door Phone для Home Assistant."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.exceptions import (
    BadRequestUfanetIntercomAPIError,
    ClientConnectorUfanetIntercomAPIError,
    TimeoutUfanetIntercomAPIError,
    UnauthorizedUfanetIntercomAPIError,
)
from .api.models import Intercom
from .api.ufanet_api import UfanetIntercomAPI
from .calls import CallHistoryCoordinator
from .const import CONF_PASSWORD, CONF_USERNAME, DEFAULT_SCAN_INTERVAL, DOMAIN
from .device import DoorPhoneDevice, create_devices

_LOGGER = logging.getLogger(__name__)

PLATFORMS: List[Platform] = [Platform.IMAGE, Platform.LOCK, Platform.SENSOR]

IntercomsData = Dict[int, Intercom]


@dataclass
class UfanetDoorPhoneData:
    """Данные интеграции, привязанные к config entry."""

    api: UfanetIntercomAPI
    coordinator: DataUpdateCoordinator
    call_coordinator: CallHistoryCoordinator
    devices: List[DoorPhoneDevice]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Инициализировать интеграцию Ufanet Door Phone."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настроить интеграцию по записи конфигурации."""
    hass.data.setdefault(DOMAIN, {})

    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]

    # Сессию предоставляет Home Assistant, закрывать её интеграция не должна.
    api = UfanetIntercomAPI(
        contract=username,
        password=password,
        session=async_get_clientsession(hass),
        logger_name=f"{DOMAIN}.api",
    )

    try:
        await api.async_authenticate()
    except (BadRequestUfanetIntercomAPIError, UnauthorizedUfanetIntercomAPIError) as err:
        raise ConfigEntryAuthFailed(
            f"Не удалось авторизоваться в Ufanet для договора {username}: {err}"
        ) from err
    except (ClientConnectorUfanetIntercomAPIError, TimeoutUfanetIntercomAPIError) as err:
        raise ConfigEntryNotReady(f"Ufanet API недоступен: {err}") from err

    async def async_update_data() -> IntercomsData:
        """Обновить список домофонов аккаунта."""
        try:
            intercoms = await api.get_intercoms()
        except UnauthorizedUfanetIntercomAPIError as err:
            raise ConfigEntryAuthFailed(
                f"Токен Ufanet для договора {username} больше не действителен"
            ) from err
        except (ClientConnectorUfanetIntercomAPIError, TimeoutUfanetIntercomAPIError) as err:
            raise UpdateFailed(f"Ошибка обмена с Ufanet API: {err}") from err
        return {intercom.id: intercom for intercom in intercoms}

    coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    # Первый опрос: поднимет ConfigEntryAuthFailed / ConfigEntryNotReady сам.
    await coordinator.async_config_entry_first_refresh()

    devices = create_devices(list(coordinator.data.values()))

    # История вызовов опрашивается отдельным координатором со своим интервалом
    # и не должна блокировать работу замков: если эндпоинт истории недоступен,
    # интеграция продолжает работу, а координатор повторит опрос по расписанию.
    call_coordinator = CallHistoryCoordinator(
        hass,
        api,
        username,
        [device.cctv_number for device in devices],
    )
    try:
        await call_coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        _LOGGER.warning("История вызовов Ufanet пока недоступна: %s", err)

    hass.data[DOMAIN][entry.entry_id] = UfanetDoorPhoneData(
        api=api,
        coordinator=coordinator,
        call_coordinator=call_coordinator,
        devices=devices,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("Ufanet Door Phone: найдено домофонов — %s (договор %s)",
                  len(devices), username)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузить запись конфигурации."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data: UfanetDoorPhoneData | None = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data is not None:
            await data.api.close()

    return unload_ok
