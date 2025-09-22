"""Button for My Simple Integration."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from datetime import datetime, timedelta

from .const import DOMAIN
from .device import DoorPhoneDevice, devices_from_dict
from .api.ufanet_api import UfanetIntercomAPI

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """ Добавляем каждый домофон в виде кнопки """
    
    devices = hass.data[DOMAIN][entry.entry_id]['devices']
    api = hass.data[DOMAIN][entry.entry_id]['api']
    if devices is not None:
        entities = []
        for device in devices:
            entities.append(DoorPhoneOpenButton(device, api))

        async_add_entities(entities)

class DoorPhoneOpenButton(ButtonEntity):
    """Кнопка открытия домофона.
       Только одно действие - открыть дверь. Есть защита от повторного нажатия (по умолчанию 5 секунд)
    """
    

    def __init__(self, doorphone: DoorPhoneDevice, api: UfanetIntercomAPI):
        # Сохраняем идентифкатор домофона        
        self._intercom_id = doorphone._intercom.id
        # Ссылка на апи уфанета для открытия
        self._ufanet_api = api
        # Само устройство домофона
        self._device = doorphone


        self._attr_unique_id = f"button.intercom_{self._intercom_id}_button"
        self._attr_name = f"Open door button"
        self._attr_has_entity_name = True


        # время последнего нажатия
        self._last_press_time: datetime | None = None
        # время в течении которого нельзя повторно надать кнопку
        self._cooldown_seconds = 8
        # текщее состояние кнопки
        self._is_pressing = False
        
    @property
    def device_info(self) -> DeviceInfo:
        """Устройсво домофона, к которому привязана кнопка"""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.device_id)},
            name=self._device.name,
            manufacturer="Ufanet",
            model=f"Intercom (model {self._device._intercom.model})"
        )
    
    @property
    def available(self) -> bool:
        """Доступность кнопки для нажатия. Либо нажата, либо не прошло еще время минимальной паузы"""
        if self._is_pressing or self._last_press_time is None:
            return not self._is_pressing
        
        time_since_last_press = datetime.now() - self._last_press_time
        return time_since_last_press.total_seconds() >= self._cooldown_seconds
    
    
    async def async_press(self) -> None:

        if not self.available or self._is_pressing:
            return

        self._is_pressing = True
        self.async_write_ha_state()

        try:
            # Do job
            await self._ufanet_api.open_intercom(intercom_id=self._intercom_id)
            # Засекаем время с 
            self._last_press_time = datetime.now()
        finally:
            self._is_pressing = False
            self.async_write_ha_state()
            
            # Обновляем кнопку после задержки недоступности кнопки
            self.hass.loop.call_later(
                self._cooldown_seconds, 
                lambda: self.hass.create_task(self._async_update_availability())
            )
        

    async def _async_update_availability(self) -> None:
        self.async_write_ha_state()