"""Платформа sensor интеграции Ufanet Door Phone: последний вызов домофона."""
from __future__ import annotations

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
    ATTR_PREVIEW_URL,
    ATTR_RECORDING_URL,
    CallHistory,
    CallHistoryCoordinator,
    call_attributes,
    call_datetime,
)
from .const import DOMAIN
from .device import account_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Добавляем датчик последнего вызова домофона."""
    data: UfanetDoorPhoneData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([LastCallSensor(entry, data.call_coordinator)])


class LastCallSensor(CoordinatorEntity[CallHistoryCoordinator], SensorEntity):
    """Датчик времени последнего вызова домофона.

    Состояние — время последнего вызова, в атрибуте ``calls`` лежит список
    последних вызовов со ссылками на превью и запись. Список вызовов не
    записывается в историю Home Assistant: он нужен для шаблонов и карточек,
    а не для долгосрочной статистики.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "last_call"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:phone-incoming"
    _unrecorded_attributes = frozenset({ATTR_CALLS})

    def __init__(self, entry: ConfigEntry, coordinator: CallHistoryCoordinator) -> None:
        """Создать датчик для указанного договора."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_call"
        self._attr_device_info = account_device_info(entry)

    @property
    def _history(self) -> Optional[CallHistory]:
        """Текущий ответ API с историей вызовов."""
        return self.coordinator.data

    @property
    def native_value(self) -> Optional[datetime]:
        """Время последнего вызова."""
        history = self._history
        call = history.last_call if history is not None else None
        return call_datetime(call) if call is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Всего вызовов и список последних вызовов с ссылками на записи."""
        history = self._history
        if history is None:
            return {}

        attributes: dict[str, Any] = {ATTR_CALLS_COUNT: history.count}

        last_call = history.last_call
        last_links = history.links.get(last_call.uuid) if last_call is not None else None
        if last_links is not None:
            attributes[ATTR_RECORDING_URL] = last_links.url
            attributes[ATTR_PREVIEW_URL] = last_links.preview

        attributes[ATTR_CALLS] = [
            call_attributes(call, history.links.get(call.uuid))
            for call in history.calls
        ]

        return attributes
