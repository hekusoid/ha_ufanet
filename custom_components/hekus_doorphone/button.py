"""Lock for Hekus DoorPhone integration."""
from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from datetime import datetime, timedelta

from .const import DOMAIN
from .device import DoorPhoneDevice
from .api.ufanet_api import UfanetIntercomAPI

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Добавляем каждый домофон в виде замка"""
    
    devices = hass.data[DOMAIN][entry.entry_id]['devices']
    api = hass.data[DOMAIN][entry.entry_id]['api']
    if devices is not None:
        entities = []
        for device in devices:
            entities.append(DoorPhoneLock(device, api))

        async_add_entities(entities)

class DoorPhoneLock(LockEntity):
    """
        Замок домофона.
        Открытие двери через домофон. Есть защита от повторного открытия (по умолчанию 8 секунд)
    """

    def __init__(self, doorphone: DoorPhoneDevice, api: UfanetIntercomAPI):
        # Сохраняем идентифкатор домофона        
        self._intercom_id = doorphone._intercom.id
        # Ссылка на апи уфанета для открытия
        self._ufanet_api = api
        # Само устройство домофона
        self._device = doorphone

        self._attr_unique_id = f"intercom_{self._intercom_id}_lock"
        self._attr_name = f"Door Lock"
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:door-closed-lock"

        # Состояние замка (по умолчанию закрыт)
        self._is_locked = True
        # время последнего открытия
        self._last_unlock_time: datetime | None = None
        # время в течении которого нельзя повторно открывать дверь
        self._cooldown_seconds = 8
        # текщее состояние открытия
        self._is_unlocking = False
        
    @property
    def device_info(self) -> DeviceInfo:
        """Устройство домофона, к которому привязан замок"""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.device_id)},
            name=self._device.name,
            manufacturer="Ufanet",
            model=f"Intercom (model {self._device._intercom.model})"
        )
    
    @property
    def is_locked(self) -> bool:
        """Возвращает состояние замка."""
        return self._is_locked
    
    @property
    def available(self) -> bool:
        """Доступность замка для открытия."""
        if self._is_unlocking or self._last_unlock_time is None:
            return not self._is_unlocking
        
        time_since_last_unlock = datetime.now() - self._last_unlock_time
        return time_since_last_unlock.total_seconds() >= self._cooldown_seconds
    
    async def async_unlock(self, **kwargs) -> None:
        """Открыть дверь через домофон."""
        if not self.available or self._is_unlocking:
            return

        self._is_unlocking = True
        self._is_locked = False
        self.async_write_ha_state()

        try:
            # Открываем дверь через API
            await self._ufanet_api.open_intercom(intercom_id=self._intercom_id)
            # Засекаем время открытия
            self._last_unlock_time = datetime.now()
        except Exception:
            # В случае ошибки возвращаем состояние "закрыто"
            self._is_locked = True
            raise
        finally:
            self._is_unlocking = False
            self.async_write_ha_state()
            
            # Автоматически "закрываем" замок после задержки
            self.hass.loop.call_later(
                self._cooldown_seconds, 
                lambda: self.hass.create_task(self._async_lock_after_cooldown())
            )
    
    async def async_lock(self, **kwargs) -> None:
        """Замок домофона всегда можно "закрыть" программно."""
        self._is_locked = True
        self.async_write_ha_state()
        
    async def _async_lock_after_cooldown(self) -> None:
        """Автоматически закрыть замок после периода охлаждения."""
        self._is_locked = True
        self.async_write_ha_state()

    async def _async_update_availability(self) -> None:
        """Обновить доступность замка."""
        self.async_write_ha_state()