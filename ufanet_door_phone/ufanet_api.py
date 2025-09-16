"""API client for Ufanet Door Phone."""
from __future__ import annotations

import logging
import aiohttp
from typing import Any
from asyncio import timeout as async_timeout

_LOGGER = logging.getLogger(__name__)

# Временные URL для тестирования
UFANET_API_BASE = "https://httpbin.org"
UFANET_API_AUTH = f"{UFANET_API_BASE}/post"
UFANET_API_DEVICES = f"{UFANET_API_BASE}/get"
UFANET_API_DOOR_ACTION = f"{UFANET_API_BASE}/post"

class UfanetAuthError(Exception):
    """Authentication error."""

class UfanetConnectionError(Exception):
    """Connection error."""

class UfanetAPI:
    """API client for Ufanet Door Phone."""
    
    def __init__(self, username: str, password: str, device_id: str = None):
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._device_id = device_id or "test_device"
        self._token = None
        self._session = None
    
    async def async_authenticate(self) -> str:
        """Authenticate and get token."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        
        try:
            async with async_timeout(30):
                async with self._session.post(
                    UFANET_API_AUTH,
                    json={
                        "username": self._username,
                        "password": self._password
                    }
                ) as response:
                    if response.status == 200:
                        # Для тестирования возвращаем mock токен
                        self._token = "test_token_12345"
                        return self._token
                    elif response.status in [401, 403]:
                        raise UfanetAuthError("Authentication failed")
                    else:
                        raise UfanetConnectionError(f"API error: {response.status}")
        except aiohttp.ClientError as err:
            raise UfanetConnectionError(f"Connection error: {err}") from err
        except asyncio.TimeoutError:
            raise UfanetConnectionError("Connection timeout") from None
    
    async def async_get_status(self) -> dict[str, Any]:
        """Get current door phone status."""
        if not self._token:
            await self.async_authenticate()
        
        try:
            async with async_timeout(30):
                # Для тестирования возвращаем mock данные
                return {
                    "in_call": False,
                    "door_open": False,
                    "last_call": "2025-09-16T10:00:00",
                    "signal_strength": 80,
                    "battery_level": 95
                }
                
        except aiohttp.ClientError as err:
            raise UfanetConnectionError(f"Connection error: {err}") from err
        except asyncio.TimeoutError:
            raise UfanetConnectionError("Connection timeout") from None
    
    async def async_open_door(self) -> bool:
        """Send open door command."""
        if not self._token:
            await self.async_authenticate()
        
        try:
            async with async_timeout(30):
                # Для тестирования всегда возвращаем успех
                _LOGGER.debug("Simulating door open command for device %s", self._device_id)
                return True
                
        except aiohttp.ClientError as err:
            raise UfanetConnectionError(f"Open door error: {err}") from err
        except asyncio.TimeoutError:
            raise UfanetConnectionError("Connection timeout") from None
    
    async def async_close(self):
        """Close the session."""
        if self._session:
            await self._session.close()
            self._session = None
        self._token = None