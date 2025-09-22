"""Sensor platform for Test Integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import DoorPhoneDevice

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
        
    sensors = [TestSensor()]
    async_add_entities(sensors, True)


class TestSensor(SensorEntity):
    """Representation of a Test Sensor."""
    
    _attr_has_entity_name = True
    
    def __init__(self, device: TestDevice, index: int, entry_id: str):
        """Initialize the sensor."""


        self._attr_unique_id = f"test_sensor_12345_sensor"

        self._attr_name = f"Sensor Name"
        self._attr_native_value = 1
