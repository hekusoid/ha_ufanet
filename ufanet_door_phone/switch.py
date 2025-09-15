"""Switch platform for Ufanet Door Phone."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch platform."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    
    async_add_entities([
        UfanetDoorSwitch(api, entry)
    ])

class UfanetDoorSwitch(SwitchEntity):
    """Representation of Ufanet door switch."""
    
    def __init__(self, api, entry):
        """Initialize the switch."""
        self._api = api
        self._entry = entry
        self._attr_name = f"Ufanet Open Door"
        self._attr_unique_id = f"{DOMAIN}_{entry.data['device_id']}_switch"
        self._is_on = False
    
    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on
    
    async def async_turn_on(self, **kwargs):
        """Open the door."""
        success = await self._api.async_open_door()
        if success:
            self._is_on = True
            self.async_write_ha_state()
            # Автоматически выключаем через 2 секунды
            self.hass.loop.call_later(2, self._async_turn_off)
    
    async def _async_turn_off(self):
        """Turn off the switch."""
        self._is_on = False
        self.async_write_ha_state()
    
    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        self._is_on = False
        self.async_write_ha_state()