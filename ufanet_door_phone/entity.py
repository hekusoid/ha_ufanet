"""Base entity for Ufanet Door Phone."""
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

class UfanetEntity(CoordinatorEntity):
    """Base class for Ufanet entities."""
    
    def __init__(self, entry, api, device_id: str):
        """Initialize the entity."""
        super().__init__(coordinator)
        self._entry = entry
        self.api = api
        self.device_id = device_id
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=f"Ufanet Door Phone",
            manufacturer="Ufanet",
            model="Door Phone",
            via_device=(DOMAIN, self._entry.entry_id),
        )
    
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success