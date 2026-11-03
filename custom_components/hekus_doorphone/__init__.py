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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry
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
from .const import (
    CONF_EXCLUDED_INTERCOMS,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .device import (
    DoorPhoneDevice,
    create_devices,
    excluded_intercom_ids,
    intercom_id_from_identifiers,
)

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

    excluded = excluded_intercom_ids(entry.options)
    devices = [
        device
        for device in create_devices(list(coordinator.data.values()))
        if device.intercom_id not in excluded
    ]
    if excluded:
        _LOGGER.debug(
            "Ufanet Door Phone: домофоны %s исключены пользователем и пропущены",
            sorted(excluded),
        )

    # Устройства, которых больше нет в аккаунте, интеграция не удаляет сама:
    # сбой API не должен стоить пользователю истории. В лог лишь пишется
    # подсказка, что такое устройство можно удалить вручную.
    _log_devices_missing_in_account(hass, entry, set(coordinator.data))

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
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    _LOGGER.debug(
        "Ufanet Door Phone: найдено домофонов — %s (договор %s)",
        len(devices),
        username,
    )

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Разрешить удаление устройства и не создавать его снова.

    Home Assistant вызывает этот хук, когда пользователь удаляет устройство
    интеграции. Устройство удаляется вместе с сущностями, а номер домофона
    попадает в список исключённых: следующий запуск не восстановит устройство.
    """
    intercom_id = intercom_id_from_identifiers(device_entry.identifiers)
    if intercom_id is None:
        return False

    excluded = excluded_intercom_ids(entry.options) | {intercom_id}
    hass.config_entries.async_update_entry(
        entry,
        options={**entry.options, CONF_EXCLUDED_INTERCOMS: sorted(excluded)},
    )
    _LOGGER.debug(
        "Ufanet Door Phone: домофон %s удалён и исключён из интеграции",
        intercom_id,
    )
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Перезагрузить запись после смены набора домофонов в опциях."""
    await hass.config_entries.async_reload(entry.entry_id)


def _log_devices_missing_in_account(
    hass: HomeAssistant, entry: ConfigEntry, known_ids: set[int]
) -> None:
    """Подсказать в логе устройства, которых больше нет в аккаунте Ufanet."""
    if not known_ids:
        # Пустой ответ API — вероятнее сбой, чем пустой аккаунт: не шумим.
        return

    registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(registry, entry.entry_id):
        intercom_id = intercom_id_from_identifiers(device_entry.identifiers)
        if intercom_id is None or intercom_id in known_ids:
            continue
        _LOGGER.debug(
            "Ufanet Door Phone: домофона %s больше нет в аккаунте, устройство %s "
            "можно удалить вручную",
            intercom_id,
            device_entry.id,
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузить запись конфигурации."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data: UfanetDoorPhoneData | None = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data is not None:
            await data.api.close()

    return unload_ok
