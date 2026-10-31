"""Модели данных API домофонов Ufanet."""
from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel


class Token(BaseModel):
    """Пара JWT-токенов из ответа auth_by_contract."""

    access: str
    refresh: str
    exp: int


class Role(BaseModel):
    """Какой именно домофон (дверь подъезда, калитка, ворота)."""

    id: int
    name: str


class Intercom(BaseModel):
    """Домофон, доступный в аккаунте Ufanet."""

    id: int
    contract: Optional[int]
    role: Role
    camera: Optional[str]
    cctv_number: str
    string_view: str
    timeout: int
    disable_button: bool
    no_sound: bool
    open_in_talk: str
    open_type: str
    dtmf_code: str
    inactivity_reason: Optional[str]
    house: int
    frsi: bool
    is_fav: bool
    model: int
    custom_name: Optional[str]
    is_blocked: bool
    supports_key_recording: bool
    ble_support: bool
    is_support_sip_monitor: bool
    relays: Optional[List]
    private_status: int
    scope: str


class Servers(BaseModel):
    """Серверы, обслуживающие камеру видеонаблюдения."""

    server: bool
    domain: str
    screenshot_domain: str
    vendor_name: str


class Camera(BaseModel):
    """Камера видеонаблюдения, доступная аккаунту Ufanet.

    Часть полей может прийти ``null`` (например, у публичных городских камер
    нет ``servers`` и ``token_r``), поэтому они объявлены необязательными.
    """

    number: Union[int, str]
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    title: Optional[str] = None
    address: Optional[str] = None
    token_l: Optional[str] = None
    token_r: Optional[str] = None
    servers: Optional[Servers] = None
    inactivity_period: Optional[Union[str, int]] = None
    type: Union[int, str]

    @property
    def rtsp_url(self) -> Optional[str]:
        """RTSP-ссылка на живой поток камеры.

        ``token_l`` — живой JWT камеры, поэтому ссылку нужно периодически
        обновлять повторным запросом списка камер. ``tracks=v1a1`` запрашивает
        у Flussonic видео- и аудиодорожку.
        """
        if self.servers is None or not self.token_l:
            return None
        return (
            f"rtsp://{self.servers.domain}/{self.number}"
            f"?token={self.token_l}&tracks=v1a1"
        )

    @property
    def screenshot_url(self) -> Optional[str]:
        """Ссылка на актуальный снапшот камеры."""
        if self.servers is None or not self.token_l:
            return None
        return (
            f"https://{self.servers.screenshot_domain}"
            f"/api/v0/screenshots/{self.number}~600.jpg?token={self.token_l}"
        )


class HistoryResult(BaseModel):
    """Один вызов домофона из истории."""

    uuid: str
    house_id: int
    address: str
    porch: str
    flat: str
    called_at: datetime
    camera_number: str
    skud_mac: str
    timezone: str


class History(BaseModel):
    """Постраничная история вызовов домофона."""

    count: int
    next: Optional[str]
    previous: Optional[str]
    results: List[HistoryResult]


class HistoryData(BaseModel):
    """Ссылки на запись и превью конкретного вызова."""

    url: str
    preview: str
