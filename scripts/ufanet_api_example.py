"""Ручная проверка API Ufanet без Home Assistant.

Home Assistant не требуется: нужны только aiohttp и pydantic
(``pip install aiohttp pydantic``).

Учётные данные берутся из переменных окружения, в коде их быть не должно:

    PowerShell:
        $env:UFANET_CONTRACT="12345678"
        $env:UFANET_PASSWORD="secret"
        python scripts/ufanet_api_example.py

    bash:
        UFANET_CONTRACT=12345678 UFANET_PASSWORD=secret python scripts/ufanet_api_example.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# Каталог интеграции добавляется в sys.path, чтобы импортировать подпакет api
# напрямую: пакет hekus_doorphone/__init__.py требует Home Assistant и вне HA
# не загрузится, а api/ от Home Assistant не зависит.
INTEGRATION_DIR = (
    Path(__file__).resolve().parent.parent / "custom_components" / "hekus_doorphone"
)
sys.path.insert(0, str(INTEGRATION_DIR))

try:
    from api.exceptions import (  # noqa: E402
        BadRequestUfanetIntercomAPIError,
        UfanetIntercomAPIError,
    )
    from api.ufanet_api import UfanetIntercomAPI  # noqa: E402
except ModuleNotFoundError as err:
    raise SystemExit(
        f"Не удалось импортировать клиент API ({err.name}). "
        "Установите зависимости командой: pip install aiohttp pydantic"
    ) from err

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger("UfanetIntercom")


async def main() -> int:
    """Авторизоваться, вывести список домофонов."""
    contract = os.environ.get("UFANET_CONTRACT")
    password = os.environ.get("UFANET_PASSWORD")

    if not contract or not password:
        _LOGGER.error("Задайте переменные окружения UFANET_CONTRACT и UFANET_PASSWORD")
        return 1

    api = UfanetIntercomAPI(contract=contract, password=password)

    try:
        await api.async_authenticate()
        intercoms = await api.get_intercoms()
    except BadRequestUfanetIntercomAPIError as err:
        _LOGGER.error("Ошибка аутентификации: %s", err)
        return 1
    except UfanetIntercomAPIError as err:
        _LOGGER.error("Ошибка API Ufanet: %s", err)
        return 1
    finally:
        await api.close()

    print("Найдены следующие домофоны:")
    for intercom in intercoms:
        print(f"  {intercom.id}: {intercom.string_view} ({intercom.role.name})")

    # Дверь открывается методом api.open_intercom(intercom_id) — например,
    # для первого домофона из списка: api.open_intercom(intercoms[0].id).

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
