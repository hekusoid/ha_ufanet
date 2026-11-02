"""Платформа sensor интеграции Ufanet Door Phone: последний вызов домофона."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UfanetDoorPhoneData
from .calls import (
    ATTR_CALLS,
    ATTR_CALLS_COUNT,
    ATTR_CALLS_TOTAL,
    ATTR_CCTV_NUMBER,
    ATTR_PREVIEW_URL,
    ATTR_RECORDING_URL,
    CallHistory,
    CallHistoryCoordinator,
    call_attributes,
    call_datetime,
    normalize_camera_number,
)
from .const import DOMAIN
from .device import DoorPhoneDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Добавляем датчик последнего вызова для каждого домофона."""
    data: UfanetDoorPhoneData = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device in data.devices:
        if not normalize_camera_number(device.cctv_number):
            _LOGGER.debug(
                "У домофона %s нет номера камеры: датчик последнего вызова "
                "не создаётся",
                device.name,
            )
            continue
        entities.append(LastCallSensor(device, data.call_coordinator))

    async_add_entities(entities)


class LastCallSensor(CoordinatorEntity[CallHistoryCoordinator], SensorEntity):
    """Датчик времени последнего вызова домофона.

    Вызов из истории договора относится к домофону, если ``camera_number``
    вызова совпадает с ``cctv_number`` домофона. Состояние — время последнего
    вызова этого домофона, в атрибуте ``calls`` лежит список его вызовов со
    ссылками на превью и запись. Список вызовов не записывается в историю
    Home Assistant: он нужен для шаблонов и карточек, а не для долгосрочной
    статистики.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "last_call"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:phone-incoming"
    _unrecorded_attributes = frozenset({ATTR_CALLS})

    def __init__(
        self, device: DoorPhoneDevice, coordinator: CallHistoryCoordinator
    ) -> None:
        """Создать датчик для указанного домофона."""
        super().__init__(coordinator)
        self._device = device
        self._cctv_number = normalize_camera_number(device.cctv_number)

        self._attr_unique_id = f"intercom_{device.intercom_id}_last_call"
        self._attr_device_info = device.device_info

    @property
    def _history(self) -> Optional[CallHistory]:
        """Вызовы этого домофона из последнего опроса истории."""
        return (self.coordinator.data or {}).get(self._cctv_number)

    @property
    def native_value(self) -> Optional[datetime]:
        """Время последнего вызова домофона."""
        history = self._history
        call = history.last_call if history is not None else None
        return call_datetime(call) if call is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Вызовы домофона и ссылки на запись и превью последнего вызова."""
        attributes: dict[str, Any] = {ATTR_CCTV_NUMBER: self._device.cctv_number}

        history = self._history
        if history is None:
            return attributes

        attributes[ATTR_CALLS_COUNT] = history.count
        attributes[ATTR_CALLS_TOTAL] = history.total_count

        last_links = history.last_links
        if last_links is not None:
            attributes[ATTR_RECORDING_URL] = last_links.url
            attributes[ATTR_PREVIEW_URL] = last_links.preview

        attributes[ATTR_CALLS] = [
            call_attributes(call, history.links.get(call.uuid))
            for call in history.calls
        ]

        return attributes

