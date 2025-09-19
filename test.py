from __future__ import annotations
import logging
import asyncio

from api.ufanet_api import UfanetIntercomAPI
from api.ufanet_api import Intercom

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger("UfanetIntercom")

CONTRACT = '72911989'
PASSWORD = '1411579975_'

async def main():
    _LOGGER.info("Hello!")
    ufanet_api = UfanetIntercomAPI(contract=CONTRACT, password=PASSWORD)

    try:
        await ufanet_api._prepare_token()
    except:
        _LOGGER.error("Ошибка аутентификации")
        await ufanet_api.close()
        return;
    # Получение списка домофонов 
    intercoms = await ufanet_api.get_intercoms()
    print('Available intercoms:', intercoms)

    #await ufanet_api.open_intercom(intercom_id=intercoms[2].id)

    call_history = await ufanet_api.get_call_history()
    for call in call_history.results:
        print(f'Call UUID: {call.uuid}, Date: {call.called_at}')

    if call_history.results:
        links = await ufanet_api.get_call_history_links(uuid=call_history.results[0].uuid)
        print('Call history links:', links)

    await ufanet_api.close()


asyncio.run(main())
