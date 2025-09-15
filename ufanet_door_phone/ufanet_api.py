"""API client for Ufanet Door Phone."""
from __future__ import annotations

import logging
import aiohttp
from typing import Any

from .const import UFANET_API_BASE, UFANET_API_AUTH, UFANET_API_DOOR_ACTION

_LOGGER = logging.getLogger(__name__)

class UfanetAPI:
    """API client for Ufanet Door Phone."""
    
    def __init__(self, username: str, password: str, device_id: str):
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._device_id = device_id
        self._token = None
        self._session = aiohttp.ClientSession()
    
    async def async_authenticate(self) -> str:
        """Authenticate and get token."""
        try:
            async with self._session.post(
                UFANET_API_AUTH,
                json={
                    "username": self._username,
                    "password": self._password
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self._token = data.get("token")
                    return self._token
                else:
                    raise Exception(f"Authentication failed: {response.status}")
        except Exception as err:
            _LOGGER.error("Authentication error: %s", err)
            raise
    
    async def async_get_status(self) -> dict[str, Any]:
        """Get current door phone status."""
        if not self._token:
            await self.async_authenticate()
        
        try:
            async with self._session.get(
                f"{UFANET_API_BASE}/device/{self._device_id}/status",
                params={"token": self._token}
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Status request failed: {response.status}")
        except Exception as err:
            _LOGGER.error("Status request error: %s", err)
            raise
    
    async def async_open_door(self) -> bool:
        """Send open door command."""
        if not self._token:
            await self.async_authenticate()
        
        try:
            async with self._session.post(
                UFANET_API_DOOR_ACTION,
                json={
                    "device_id": self._device_id,
                    "token": self._token,
                    "action": "open"
                }
            ) as response:
                return response.status == 200
        except Exception as err:
            _LOGGER.error("Open door error: %s", err)
            raise
    
    async def async_close(self):
        """Close the session."""
        await self._session.close()