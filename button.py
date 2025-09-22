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
    """Set up the button platform."""
    
    devices = hass.data[DOMAIN][entry.entry_id]['devices']
    api = hass.data[DOMAIN][entry.entry_id]['api']
    if devices is not None:
        entities = []
        for device in devices:
            entities.append(DoorPhoneOpenButton(device, api))

        async_add_entities(entities)

class DoorPhoneOpenButton(ButtonEntity):
    """Representation of a Simple Button."""
    
    def __init__(self, doorphone: DoorPhoneDevice, api: UfanetIntercomAPI):
        """Initialize the button."""
        
        self._intercom_id = doorphone._intercom.id
        self._ufanetapi = api
        self._device = doorphone
        self._attr_name = f"Doorphone open button name"
        self._attr_unique_id = f"doorphone_{self._intercom_id}_button_id"

        self._last_press_time: datetime | None = None
        self._cooldown_seconds = 5
        self._is_pressing = False
        
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.device_id)},
            name=self._device.name,
            manufacturer="Ufanet",
            model=f"Intercom (model {self._device._intercom.model})"
        )
    
    @property
    def available(self) -> bool:
        """Return True if button is available for pressing."""
        if self._is_pressing or self._last_press_time is None:
            return not self._is_pressing
            
        time_since_last_press = datetime.now() - self._last_press_time
        return time_since_last_press.total_seconds() >= self._cooldown_seconds
    
    
    async def async_press(self) -> None:

        """Handle the button press."""
        if not self.available or self._is_pressing:
            return

        self._is_pressing = True
        self.async_write_ha_state()

        try:
            # Do job
            

            self._last_press_time = datetime.now()
            
        finally:
            self._is_pressing = False
            self.async_write_ha_state()
            
            # Schedule availability update after cooldown
            self.hass.loop.call_later(
                self._cooldown_seconds, 
                lambda: self.hass.create_task(self._async_update_availability())
            )
        

    async def _async_update_availability(self) -> None:
        """Update availability status after cooldown."""
        self.async_write_ha_state()