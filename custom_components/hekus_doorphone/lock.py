"""Платформа lock интеграции Ufanet Door Phone."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import UfanetDoorPhoneData
from .api.exceptions import UfanetIntercomAPIError
from .api.models import Intercom
from .api.ufanet_api import UfanetIntercomAPI
from .const import DOMAIN, UNLOCK_COOLDOWN
from .device import DoorPhoneDevice, intercom_attributes

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Добавляем каждый домофон в виде замка."""
    data: UfanetDoorPhoneData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        DoorPhoneLock(device, data.api, data.coordinator) for device in data.devices
    )



class DoorPhoneLock(LockEntity):
    """Замок домофона.

    Открытие двери через домофон. Состояние двери недоступно через API,
    поэтому сущность работает в режиме assumed_state, а повторное открытие
    ограничено периодом ``UNLOCK_COOLDOWN``.
    """

    _attr_has_entity_name = True
    _attr_assumed_state = True
    _attr_translation_key = "door_lock"
    _attr_icon = "mdi:door-closed-lock"

    def __init__(
        self,
        doorphone: DoorPhoneDevice,
        api: UfanetIntercomAPI,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Создать замок для указанного домофона."""
        self._device = doorphone
        self._intercom_id: int = doorphone.intercom_id
        self._ufanet_api = api
        self._coordinator = coordinator

        self._attr_unique_id = f"intercom_{self._intercom_id}_lock"
        self._attr_is_locked = True

        self._last_unlock: datetime | None = None
        self._relock_cancel: CALLBACK_TYPE | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Устройство домофона, к которому привязан замок."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.device_id)},
            name=self._device.name,
            manufacturer="Ufanet",
            model=self._device.model,
        )

    @property
    def _intercom(self) -> Intercom | None:
        """Актуальное описание домофона из координатора."""
        data = self._coordinator.data or {}
        return data.get(self._intercom_id)

    @property
    def available(self) -> bool:
        """Домофон доступен, если API отвечает и вызов не заблокирован."""
        if not self._coordinator.last_update_success:
            return False

        intercom = self._intercom
        if intercom is None:
            return False

        return not intercom.is_blocked and not intercom.disable_button

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Атрибуты для автоматизаций: параметры домофона и последнее открытие."""
        attributes: dict[str, Any] = {
            "intercom_id": self._intercom_id,
            "last_unlock": self._last_unlock.isoformat() if self._last_unlock else None,
        }

        intercom = self._intercom
        if intercom is not None:
            attributes["address"] = intercom.string_view
            attributes["role"] = intercom.role.name
            # Остальные параметры домофона, не задействованные в логике интеграции
            attributes.update(intercom_attributes(intercom))

        return attributes

    async def async_unlock(self, **kwargs: Any) -> None:
        """Открыть дверь через домофон."""
        remaining = self._cooldown_remaining
        if remaining > 0:
            _LOGGER.debug(
                "Домофон %s открывали %.0f с назад, повторное открытие пропущено",
                self._device.name,
                UNLOCK_COOLDOWN - remaining,
            )
            return

        try:
            result = await self._ufanet_api.open_intercom(self._intercom_id)
        except UfanetIntercomAPIError as err:
            raise HomeAssistantError(
                f"Не удалось открыть домофон {self._device.name}: {err}"
            ) from err

        if not result:
            _LOGGER.warning("Ufanet не подтвердил открытие домофона %s", self._device.name)

        self._last_unlock = dt_util.utcnow()
        self._attr_is_locked = False
        self.async_write_ha_state()
        self._schedule_relock()

    async def async_lock(self, **kwargs: Any) -> None:
        """Программно "закрыть" замок."""
        self._cancel_relock()
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Отменить отложенное закрытие при удалении сущности."""
        self._cancel_relock()
        await super().async_will_remove_from_hass()

    @property
    def _cooldown_remaining(self) -> float:
        """Сколько секунд ещё нельзя открывать дверь повторно."""
        if self._last_unlock is None:
            return 0.0

        elapsed = (dt_util.utcnow() - self._last_unlock).total_seconds()
        return max(0.0, UNLOCK_COOLDOWN - elapsed)

    def _schedule_relock(self) -> None:
        """Запланировать автоматическое "закрытие" замка."""
        self._cancel_relock()
        self._relock_cancel = async_call_later(
            self.hass, UNLOCK_COOLDOWN, self._handle_relock
        )

    def _cancel_relock(self) -> None:
        """Отменить запланированное закрытие замка."""
        if self._relock_cancel is not None:
            self._relock_cancel()
            self._relock_cancel = None

    @callback
    def _handle_relock(self, _now: datetime) -> None:
        """Вернуть замок в состояние "закрыто" после периода охлаждения."""
        self._relock_cancel = None
        self._attr_is_locked = True
        self.async_write_ha_state()

