"""Button for My Simple Integration."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .device import DoorPhoneDevice, devices_from_dict

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    devices = entry.data['devices'];
    if devices is not None:
        entities = []
        for device in devices:
            entities.append(DoorPhoneOpenButton(device))

        async_add_entities(entities)

class DoorPhoneOpenButton(ButtonEntity):
    """Representation of a Simple Button."""
    
    def __init__(self, doorphone: DoorPhoneDevice):
        """Initialize the button."""
        
        self._intercom_id = doorphone._intercom.id
        self._device = doorphone
        self._attr_name = f"Doorphone open button"
        self._attr_unique_id = f"doorphone_{self._intercom_id}_button"
        
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.device_id)},
            name=self._device.name,
            manufacturer="Ufanet",
            model="Simple Device"
        )
    
    def press(self) -> None:
        """Handle the button press."""
        # Implement your button action here
        self.hass.bus.fire("my_simple_integration_button_pressed", {
            "device_id": self._entry.entry_id
        })