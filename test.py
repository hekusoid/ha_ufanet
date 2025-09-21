from __future__ import annotations
import logging
import asyncio

from api.ufanet_api import UfanetIntercomAPI
from api.ufanet_api import Intercom
from api.exceptions import (UnknownUfanetIntercomAPIError,
                            BadRequestUfanetIntercomAPIError)

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger("UfanetIntercom")

CONTRACT = '72911989'
PASSWORD = '1411579975_'

async def main():

    ufanet_api = UfanetIntercomAPI(contract=CONTRACT, password=PASSWORD)

    try:
        await ufanet_api._prepare_token()
    except BadRequestUfanetIntercomAPIError as res:
        msg = res.args[0]['non_field_errors'][0]
        _LOGGER.error(f"Ошибка аутентификации: {msg}")
        await ufanet_api.close()
        return
    except Exception:
        return
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

class InvalidAuth(Exception):
    """Error to indicate invalid authentication credentials."""

#asyncio.run(main())

def test():
    try:
        resp = {'non_field_errors':['Mock test msg']}
        
        raise BadRequestUfanetIntercomAPIError(resp)

    except BadRequestUfanetIntercomAPIError as exp:
        msg = exp.args[0]['non_field_errors'][0]
        raise InvalidAuth(msg)

try:
    test()
except InvalidAuth as exp:
    print(f"Ошибка аутентификации: {exp.args[0]}")


