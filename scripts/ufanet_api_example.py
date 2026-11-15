"""Ручная проверка API Ufanet без Home Assistant.

Скрипт авторизуется по номеру договора и печатает список камер
видеонаблюдения с RTSP-ссылками и последние вызовы домофона. Home Assistant не
требуется: нужны только aiohttp и pydantic (``pip install aiohttp pydantic``).

Учётные данные берутся из файла .env в корне репозитория (он в .gitignore) или
из переменных окружения; переменные окружения приоритетнее:

    # .env
    UFANET_CONTRACT=12345678
    UFANET_PASSWORD=secret

    python scripts/ufanet_api_example.py            # только итоги
    python scripts/ufanet_api_example.py --debug    # плюс журнал запросов

Скрипт только читает данные: домофоны, камеры и историю вызовов. Дверь он не
открывает — open_intercom() здесь сознательно не вызывается.
"""
from __future__ import annotations

import argparse
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
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(INTEGRATION_DIR))


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

_LOGGER = logging.getLogger("UfanetIntercom")

# Сколько последних вызовов печатать
CALLS_PAGE_SIZE = 5


def _configure_logging() -> None:
    """Включить подробный журнал только по флагу --debug."""
    parser = argparse.ArgumentParser(
        description="Проверка API Ufanet без Home Assistant (только чтение)."
    )
    parser.add_argument(
        "--debug", action="store_true", help="печатать журнал HTTP-запросов"
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


async def main() -> int:
    """Авторизоваться и вывести камеры видеонаблюдения и последние вызовы."""
    contract = os.environ.get("UFANET_CONTRACT")
    password = os.environ.get("UFANET_PASSWORD")

    if not contract or not password:
        _LOGGER.error("Задайте переменные окружения UFANET_CONTRACT и UFANET_PASSWORD")
        return 1

    api = UfanetIntercomAPI(contract=contract, password=password)
    cameras = []
    history = []
    intercoms = []

    try:
        await api.async_authenticate()
        intercoms = await api.get_intercoms()
        cameras = await api.get_cameras()
        history = await api.get_call_history(page=1, page_size=CALLS_PAGE_SIZE)

        calls = []
        for call in history.results:
            try:
                links = await api.get_call_history_links(call.uuid)
            except UfanetIntercomAPIError as err:
                _LOGGER.debug("Ссылки на запись вызова %s недоступны: %s", call.uuid, err)
                links = None
            calls.append((call, links))
    except BadRequestUfanetIntercomAPIError as err:
        _LOGGER.error("Ошибка аутентификации: %s", err)
        return 1
    except UfanetIntercomAPIError as err:
        _LOGGER.error("Ошибка API Ufanet: %s", err)
        return 1
    finally:
        await api.close()


    if not intercoms:
        print("Домофоны не найдены.")
    else:
        print("Найдены следующие домофоны:")
        for intercom in intercoms:
            camera_number = intercom.cctv_number or "нет камеры"
            print(
                f"  {intercom.string_view} ({intercom.role.name}), "
                f"камера: {camera_number}"
            )

    if not cameras:
        print("Камеры не найдены.")
    else:
        print("Найдены следующие камеры:")
        for camera in cameras:
            title = camera.title or camera.address or camera.number
            print(f"  {title}: {camera.rtsp_url or 'RTSP-ссылка недоступна'}")
            if camera.screenshot_url:
                print(f"    снапшот: {camera.screenshot_url}")

    print()
    if not calls:
        print("Вызовов в истории нет.")
    else:
        print(f"Последние вызовы (всего {history.count}):")
        for call, links in calls:
            print(
                f"  {call.called_at.isoformat()} — {call.address}, "
                f"подъезд {call.porch}, кв. {call.flat}"
            )
            if links is not None:
                print(f"    превью: {links.preview}")
                print(f"    запись: {links.url}")

    # Домофоны возвращает метод api.get_intercoms(), дверь открывается методом
    # api.open_intercom(intercom_id). На реальном договоре дверь этим скриптом не
    # открывать: он предназначен только для чтения данных.

    return 0


if __name__ == "__main__":
    _configure_logging()
    raise SystemExit(asyncio.run(main()))
