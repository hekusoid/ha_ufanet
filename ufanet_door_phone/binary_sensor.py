"""Binary sensor platform for Ufanet Door Phone."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    async_add_entities([
        UfanetCallBinarySensor(coordinator, entry),
        UfanetDoorBinarySensor(coordinator, entry)
    ])

class UfanetCallBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of Ufanet call status."""
    
    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Ufanet Door Phone Call"
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_call"
        self._attr_device_class = "occupancy"
    
    @property
    def is_on(self):
        """Return true if there is an active call."""
        return self.coordinator.data.get("in_call", False) if self.coordinator.data else False

class UfanetDoorBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of Ufanet door status."""
    
    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Ufanet Door Status"
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_door"
        self._attr_device_class = "door"
    
    @property
    def is_on(self):
        """Return true if door is open."""
        return self.coordinator.data.get("door_open", False) if self.coordinator.data else False