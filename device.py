"""Device representation for Test Integration."""

from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class TestDevice:
    """Representation of a test device."""
    
    device_id: str
    name: str
    sensor_value: int = 0
    
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
    def from_dict(cls, data: Dict[str, Any]) -> 'TestDevice':
        """Create device from dictionary."""
        device = cls(
            device_id=data['device_id'],
            name=data['name'],
            sensor_value=data.get('sensor_value', 0)
        )
        return device


def create_devices(integration_name: str) -> List[TestDevice]:
    """Create three test devices."""
    devices = []
    
    for i in range(1, 4):
        device = TestDevice(
            device_id=f"{integration_name}_device_{i}",
            name=f"{integration_name} Device {i}"
        )
        devices.append(device)
    
    return devices


def devices_to_dict(devices: List[TestDevice]) -> List[Dict[str, Any]]:
    """Convert list of devices to list of dictionaries."""
    return [device.to_dict() for device in devices]


def devices_from_dict(devices_data: List[Dict[str, Any]]) -> List[TestDevice]:
    """Create list of devices from list of dictionaries."""
    return [TestDevice.from_dict(data) for data in devices_data]