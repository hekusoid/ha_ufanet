"""Device representation for Test Integration."""

from dataclasses import dataclass
from typing import List, Dict, Any
from .api.models import Intercom

@dataclass
class DoorPhoneDevice:
    """Домофон от Ufanet"""

    def __init__(self, intercom: Intercom):
        self._intercom = intercom
        self.device_id = f'ufanet_doorphone_{intercom.id}'
        self.name = f"{intercom.string_view} ({intercom.role.name})"
        sensor_value = 0
    
  
    def increment_sensor(self):
        """Increment sensor value."""
        self.sensor_value += 1
        return self.sensor_value
    
    def reset_sensor(self):
        """Reset sensor value."""
        self.sensor_value = 0
        return self.sensor_value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert device to dictionary for storage."""
        return {
            'device_id': self.device_id,
            'name': self.name,
            'sensor_value': self.sensor_value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DoorPhoneDevice':
        """Create device from dictionary."""
        device = cls(
            device_id=data['device_id'],
            name=data['name'],
            sensor_value=data.get('sensor_value', 0)
        )
        return device


def create_devices(intercoms: List[Intercom]) -> List[DoorPhoneDevice]:
    """Create three test devices."""

    devices = []

    for intercom in intercoms:
        device = DoorPhoneDevice(intercom)
        devices.append(device)

    return devices


def devices_to_dict(devices: List[DoorPhoneDevice]) -> List[Dict[str, Any]]:
    """Convert list of devices to list of dictionaries."""
    return [device.to_dict() for device in devices]


def devices_from_dict(devices_data: List[Dict[str, Any]]) -> List[DoorPhoneDevice]:
    """Create list of devices from list of dictionaries."""
    return [DoorPhoneDevice.from_dict(data) for data in devices_data]