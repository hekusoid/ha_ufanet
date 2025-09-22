"""Binary sensor for My Simple Integration."""
from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up the binary sensor platform."""
    async_add_entities([MyBinarySensor(entry)])

class MyBinarySensor(BinarySensorEntity):
    """Representation of a Simple Binary Sensor."""
    
    def __init__(self, entry: ConfigEntry):
        """Initialize the binary sensor."""
        self._entry = entry
        self._is_on = False
        self._attr_name = f"{entry.data['name']} Sensor"
        self._attr_unique_id = f"{entry.entry_id}_sensor"
        
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.data["name"],
            manufacturer="My Company",
            model="Simple Device"
        )
    
    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._is_on
    
    def update(self):
        """Fetch new state data for the sensor."""
        # Here you would implement your actual logic
        # For demonstration, we'll just toggle the state
        self._is_on = not self._is_on