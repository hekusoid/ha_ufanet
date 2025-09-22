from __future__ import annotations
import logging
import asyncio

from api.ufanet_api import UfanetIntercomAPI
from api.ufanet_api import Intercom
from api.exceptions import (UnknownUfanetIntercomAPIError,
                            BadRequestUfanetIntercomAPIError)

from device import DoorPhoneDevice, create_devices, devices_to_dict, devices_from_dict

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger("UfanetIntercom")

CONTRACT = '72911989'
PASSWORD = '1411579975'

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
 
    print('Найдены следующие домофоны:')



    #await ufanet_api.open_intercom(intercom_id=intercoms[2].id)

    #call_history = await ufanet_api.get_call_history()
    #for call in call_history.results:
    #    print(f'Call UUID: {call.uuid}, Date: {call.called_at}')

    #if call_history.results:
    #    links = await ufanet_api.get_call_history_links(uuid=call_history.results[0].uuid)
    #    print('Call history links:', links)

    await ufanet_api.close()

class InvalidAuth(Exception):
    """Error to indicate invalid authentication credentials."""

#asyncio.run(main())

def get_mock_intercoms() -> List[Intercom]:
    mock_responce = [{'id': 109757, 'contract': None, 'role': {'id': 8, 'name': 'Домофон-калитка'}, 'camera': None, 'cctv_number': '1738053250GTF70', 'string_view': 'г. Уфа, Заки Валиди, 71', 'timeout': 10, 'disable_button': False, 'no_sound': True, 'open_in_talk': 'http', 'open_type': 'http', 'dtmf_code': '#0', 'inactivity_reason': None, 'house': 458263, 'frsi': True, 'is_fav': False, 'model': 39, 'custom_name': None, 'is_blocked': False, 'supports_key_recording': True, 'ble_support': True, 'is_support_sip_monitor': False, 'relays': [], 'private_status': 1, 'scope': 'owner'}, {'id': 103616, 'contract': None, 'role': {'id': 8, 'name': 'Домофон-калитка'}, 'camera': None, 'cctv_number': '1737985955HSN76', 'string_view': 'г. Уфа, Заки Валиди, 73', 'timeout': 10, 'disable_button': False, 'no_sound': True, 'open_in_talk': 'http', 'open_type': 'http', 'dtmf_code': '#0', 'inactivity_reason': None, 'house': 31465, 'frsi': True, 'is_fav': False, 'model': 39, 'custom_name': None, 'is_blocked': False, 'supports_key_recording': True, 'ble_support': True, 'is_support_sip_monitor': False, 'relays': [], 'private_status': 1, 'scope': 'owner'}, {'id': 103413, 'contract': 664192, 'role': {'id': 2, 'name': 'Домофон'}, 'camera': None, 'cctv_number': '1737976793GSM0', 'string_view': 'г. Уфа, Заки Валиди, 73, п.1', 'timeout': 10, 'disable_button': False, 'no_sound': True, 'open_in_talk': 'http', 'open_type': 'http', 'dtmf_code': '#0', 'inactivity_reason': None, 'house': 31465, 'frsi': True, 'is_fav': False, 'model': 39, 'custom_name': None, 'is_blocked': False, 'supports_key_recording': True, 'ble_support': True, 'is_support_sip_monitor': False, 'relays': [], 'private_status': 1, 'scope': 'owner'}]
    return [Intercom(**i) for i in mock_responce]


intercoms = get_mock_intercoms()

devices = create_devices(intercoms)

conf = {'devices' : devices}

print(conf)



