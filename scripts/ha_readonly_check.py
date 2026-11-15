"""Проверка реального Home Assistant строго в режиме чтения.

Скрипт выполняет только GET-запросы к REST API Home Assistant и печатает
версию ядра, состояние интеграции hekus_doorphone и список её сущностей.
Ни один запрос не меняет состояние Home Assistant: POST-запросы, вызовы
сервисов, перезагрузка и включение отладки здесь не используются.

Параметры подключения берутся из .env в корне репозитория (он в .gitignore)
или из переменных окружения:

    HA_URL=https://192.168.1.100:8123
    HA_TOKEN=<долгоживущий токен доступа>
    HA_VERIFY_SSL=0     # локальный сертификат Home Assistant самоподписанный

Токен и адрес в вывод не попадают.
"""
from __future__ import annotations

import asyncio
import os
import ssl
from pathlib import Path
from typing import Any

import aiohttp

REPO_ROOT = Path(__file__).resolve().parent.parent

# Домен интеграции и платформы, сущности которых она создаёт.
DOMAIN = "hekus_doorphone"
ENTITY_DOMAINS = ("lock", "sensor", "image")

# Маркеры в entity_id, friendly_name или атрибутах: по ним сущности относятся
# к интеграции даже при переименовании устройства пользователем.
ENTITY_MARKERS = ("last_call", "door_lock", "hekus", "ufanet")

# Состояния, которые Home Assistant выставляет вместо реальных данных.
BAD_STATES = ("unavailable", "unknown")


def load_dotenv(path: Path) -> None:
    """Заполнить окружение значениями из .env, не перетирая уже заданные."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        # Переменная, выставленная в оболочке, важнее содержимого файла.
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv(REPO_ROOT / ".env")


def _ssl_context(verify_ssl: bool) -> ssl.SSLContext:
    """Контекст по умолчанию или без проверки сертификата локального HA."""
    context = ssl.create_default_context()
    if not verify_ssl:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


async def _async_get_json(session: aiohttp.ClientSession, url: str) -> Any:
    """GET-запрос к REST API Home Assistant — других методов не используем."""
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json(content_type=None)


def _is_integration_entity(state: dict[str, Any]) -> bool:
    """Относится ли состояние к сущностям нашей интеграции."""
    entity_id = str(state.get("entity_id") or "")
    if entity_id.split(".", 1)[0] not in ENTITY_DOMAINS:
        return False
    haystack = f"{entity_id} {state.get('attributes') or {}}".lower()
    return any(marker in haystack for marker in ENTITY_MARKERS)


async def main() -> int:
    """Прочитать состояние Home Assistant и напечатать сущности интеграции."""
    base_url = os.environ.get("HA_URL", "").rstrip("/")
    token = os.environ.get("HA_TOKEN", "")
    verify_ssl = os.environ.get("HA_VERIFY_SSL", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )

    if not base_url or not token:
        print("Задайте HA_URL и HA_TOKEN в .env или в переменных окружения.")
        return 1

    headers = {"Authorization": f"Bearer {token}"}
    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(ssl=_ssl_context(verify_ssl))

    async with aiohttp.ClientSession(
        headers=headers, timeout=timeout, connector=connector
    ) as session:
        try:
            # Три GET-запроса: проверка связи, конфигурация ядра и состояния.
            ping = await _async_get_json(session, f"{base_url}/api/")
            config = await _async_get_json(session, f"{base_url}/api/config")
            states = await _async_get_json(session, f"{base_url}/api/states")
        except aiohttp.ClientResponseError as err:
            # 401 — просроченный или отозванный токен, 404 — неверный адрес.
            print(f"Home Assistant ответил ошибкой HTTP {err.status} ({err.message})")
            return 1
        except aiohttp.ClientError as err:
            print(f"Home Assistant недоступен по адресу из HA_URL: {err}")
            return 1

    message = ping.get("message") if isinstance(ping, dict) else ping
    print(f"REST API: {message}")
    print(f"Версия Home Assistant: {config.get('version')}")
    print(f"Часовой пояс: {config.get('time_zone')}")
    print(f"Состояние ядра: {config.get('state')}")

    components = list(config.get("components") or [])
    loaded = sorted(
        component
        for component in components
        if component == DOMAIN or component.startswith(f"{DOMAIN}.")
    )
    if loaded:
        print(f"Интеграция загружена: {', '.join(loaded)}")
    else:
        print(f"Интеграция {DOMAIN} не загружена: компонентов в /api/config нет.")

    entities = sorted(
        (state for state in states if _is_integration_entity(state)),
        key=lambda state: str(state.get("entity_id")),
    )

    print()
    if not entities:
        print("Сущности интеграции не найдены.")
        return 0

    print(f"Сущности интеграции ({len(entities)}):")
    for domain in ENTITY_DOMAINS:
        count = sum(
            1
            for state in entities
            if str(state.get("entity_id") or "").startswith(f"{domain}.")
        )
        print(f"  {domain}: {count}")
    print()

    for state in entities:
        attributes = state.get("attributes") or {}
        name = attributes.get("friendly_name") or ""
        print(f"  {state.get('entity_id')} = {state.get('state')} {name}".rstrip())

    broken = [state for state in entities if state.get("state") in BAD_STATES]
    print()
    if broken:
        print(f"Недоступных или неизвестных состояний: {len(broken)}")
        for state in broken:
            print(f"  {state.get('entity_id')}")
    else:
        print("Недоступных сущностей нет.")

    # Журнал ошибок в новых версиях Home Assistant не отдаётся по REST:
    # GET /api/error_log отвечает 404, события запрашиваются по WebSocket
    # (system_log/list). Скрипт этого не делает и остаётся только на чтение.

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

