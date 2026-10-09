"""Offline contract regressions. Provenance: fixtures/alphasms_contract.json."""
import json
from pathlib import Path

import httpx
import pytest
import respx
import jukto

CONTRACT = json.loads((Path(__file__).parent / 'fixtures/alphasms_contract.json').read_text())


@pytest.mark.parametrize('code,meaning,exception_name', CONTRACT['errors'])
@pytest.mark.parametrize('as_string', [False, True], ids=['integer', 'string'])
@respx.mock
def test_alphasms_documented_errors(code, meaning, exception_name, as_string):
    client = jukto.AlphaSMSClient('offline-key')
    payload = {'error': str(code) if as_string else code, 'msg': 'opaque provider message'}
    route = respx.post(client.base_url).respond(200, json=payload)
    with pytest.raises(getattr(jukto, exception_name)) as caught:
        client.send_sms('01700000000', 'offline message')
    assert type(caught.value) is getattr(jukto, exception_name), meaning
    assert caught.value.provider == 'AlphaSMS'
    assert caught.value.status_code == code
    assert caught.value.response_body == payload
    assert route.call_count == 1


@pytest.mark.parametrize('code', [0, '0'])
@respx.mock
def test_alphasms_documented_success(code):
    client = jukto.AlphaSMSClient('offline-key')
    payload = {'error': code, 'msg': 'accepted', 'data': {'request_id': 123}}
    respx.post(client.base_url).respond(200, json=payload)
    assert client.send_sms('01700000000', 'offline message') == payload


@pytest.mark.parametrize('payload', [[], None, {}, {'msg': 'success'}, {'error': False},
    {'error': 0.0}, {'error': ''}, {'error': '00'}, {'error': ' 0'}, {'error': []}])
@respx.mock
def test_alphasms_unknown_code_structure_is_not_success(payload):
    client = jukto.AlphaSMSClient('offline-key')
    respx.post(client.base_url).respond(200, content=json.dumps(payload), headers={'Content-Type': 'application/json'})
    with pytest.raises(jukto.ProviderError) as caught:
        client.send_sms('01700000000', 'offline message')
    assert type(caught.value) is jukto.ProviderError
    assert caught.value.response_body == payload


@pytest.mark.parametrize('code', [401, 402, 406, 422, 999])
@respx.mock
def test_alphasms_undocumented_codes_have_no_guessed_semantics(code):
    client = jukto.AlphaSMSClient('offline-key')
    respx.post(client.base_url).respond(200, json={'error': code, 'msg': 'Insufficient balance'})
    with pytest.raises(jukto.ProviderError) as caught:
        client.send_sms('01700000000', 'offline message')
    assert type(caught.value) is jukto.ProviderError
    assert caught.value.status_code == code


@pytest.mark.parametrize('code', [1002, 1003, 1004, 1005, 1006, 1007, 1008, 1010, 1099])
@respx.mock
def test_bulksmsbd_unverified_codes_are_preserved_without_guessing(code):
    client = jukto.BulkSMSBDClient('offline-key', 'offline-sender', allow_insecure_http=True)
    payload = {'response_code': code, 'error_message': 'balance unauthorized invalid number'}
    respx.post(client.base_url).respond(200, json=payload)
    with pytest.raises(jukto.ProviderError) as caught:
        client.send_sms('01700000000', 'offline message')
    assert type(caught.value) is jukto.ProviderError
    assert caught.value.status_code == code
    assert caught.value.response_body == payload


@pytest.mark.parametrize('payload', [[], {}, {'response_code': None}, {'response_code': True},
    {'response_code': 202.0}, {'response_code': '202'}])
@respx.mock
def test_bulksmsbd_unknown_structure_is_not_success(payload):
    client = jukto.BulkSMSBDClient('offline-key', 'offline-sender', allow_insecure_http=True)
    respx.post(client.base_url).respond(200, json=payload)
    with pytest.raises(jukto.ProviderError):
        client.send_sms('01700000000', 'offline message')
