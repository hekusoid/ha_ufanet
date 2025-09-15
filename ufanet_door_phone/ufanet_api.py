"""API client for Ufanet Door Phone."""
from __future__ import annotations

import logging
import aiohttp
from typing import Any
from asyncio import timeout as async_timeout

from .const import UFANET_API_BASE, UFANET_API_AUTH, UFANET_API_DOOR_ACTION

_LOGGER = logging.getLogger(__name__)

class UfanetAuthError(Exception):
    """Authentication error."""

class UfanetConnectionError(Exception):
    """Connection error."""

class UfanetAPI:
    """API client for Ufanet Door Phone."""
    
    def __init__(self, username: str, password: str, device_id: str):
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._device_id = device_id
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
                        data = await response.json()
                        self._token = data.get("token")
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
                async with self._session.get(
                    f"{UFANET_API_BASE}/device/{self._device_id}/status",
                    params={"token": self._token}
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status in [401, 403]:
                        self._token = None  # Сбрасываем токен для повторной аутентификации
                        raise UfanetAuthError("Token expired")
                    else:
                        raise UfanetConnectionError(f"Status request failed: {response.status}")
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
                async with self._session.post(
                    UFANET_API_DOOR_ACTION,
                    json={
                        "device_id": self._device_id,
                        "token": self._token,
                        "action": "open"
                    }
                ) as response:
                    return response.status == 200
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