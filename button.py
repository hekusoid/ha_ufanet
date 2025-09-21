"""Button for My Simple Integration."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    async_add_entities([MyButton(entry)])

class MyButton(ButtonEntity):
    """Representation of a Simple Button."""
    
    def __init__(self, entry: ConfigEntry):
        """Initialize the button."""
        self._entry = entry
        self._attr_name = f"{entry.data['name']} Button"
        self._attr_unique_id = f"{entry.entry_id}_button"
        
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.data["name"],
            manufacturer="My Company",
            model="Simple Device"
        )
    
    def press(self) -> None:
        """Handle the button press."""
        # Implement your button action here
        self.hass.bus.fire("my_simple_integration_button_pressed", {
            "device_id": self._entry.entry_id
        })