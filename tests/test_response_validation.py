"""Offline response regressions; provider evidence is recorded in docs/provider-contracts.md."""
import json
import time
from unittest.mock import patch

import httpx
import pytest
import respx
import jukto

NAMES = ['AlphaSMS', 'BulkSMSBD', 'GreenWeb', 'Steadfast', 'RedX', 'Pathao']


def client_for(name):
    kw = {'base_url': 'https://provider.test'}
    if name == 'Pathao':
        c = jukto.PathaoClient('id', 'secret', 'user', 'password', **kw)
        c.access_token = 'offline-token'
        c.token_expiry = time.monotonic() + 3600
        return c
    if name == 'BulkSMSBD':
        return jukto.BulkSMSBDClient('key', 'sender', **kw)
    if name == 'Steadfast':
        return jukto.SteadfastClient('key', 'secret', **kw)
    return getattr(jukto, name + 'Client')('key', **kw)


def invoke(c, name):
    if name in ['AlphaSMS', 'BulkSMSBD', 'GreenWeb']:
        return c.send_sms('01700000000', 'offline message')
    return c.create_order(jukto.Parcel('inv', 'name', '01700000000', 'address', 10, store_id=123, declared_value=10, redx_delivery_area='Banani', redx_delivery_area_id=12))


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('content', ['', '<html>Maintenance</html>', '{broken', 'null', 'true', '42', '"text"', '[]', '{}'])
@respx.mock
def test_unknown_success_response_is_normalized(name, content):
    c = client_for(name)
    route = respx.route(host='provider.test').respond(200, content=content)
    with pytest.raises(jukto.UnexpectedProviderResponseError) as caught:
        invoke(c, name)
    assert caught.value.provider == name
    assert caught.value.status_code == 200
    assert route.call_count == 1  # No replay of ambiguous side effects.


@pytest.mark.parametrize('name,payload', [
    ('AlphaSMS', {'error': 0}), ('AlphaSMS', {'error': 0, 'data': {}}),
    ('Steadfast', {'status': 200}), ('RedX', {'message': 'success'}),
    ('Pathao', {'type': 'success'}), ('Pathao', {'type': 'error', 'message': 'failure'}),
    ('GreenWeb', {'status': 'unrecognized'}),
])
@respx.mock
def test_missing_or_unrecognized_success_fields(name, payload):
    respx.route(host='provider.test').respond(200, json=payload)
    with pytest.raises(jukto.UnexpectedProviderResponseError):
        invoke(client_for(name), name)


@pytest.mark.parametrize('name', NAMES)
@respx.mock
def test_internal_programming_errors_are_not_wrapped(name):
    respx.route(host='provider.test').respond(200, json={})
    with patch('httpx.Response.json', side_effect=TypeError('internal bug')):
        with pytest.raises(TypeError, match='internal bug'):
            invoke(client_for(name), name)


@pytest.mark.parametrize('refresh', [False, True])
@pytest.mark.parametrize('content', ['{broken', '[]', 'null', '{}', '{"access_token": []}'])
@respx.mock
def test_pathao_bad_token_envelope_does_not_fallback(refresh, content):
    c = client_for('Pathao')
    c.access_token = None
    c.refresh_token = 'refresh-token' if refresh else None
    route = respx.route(host='provider.test').respond(200, content=content)
    with pytest.raises(jukto.UnexpectedProviderResponseError):
        c.get_token()
    assert route.call_count == 1


@respx.mock
def test_pathao_retry_malformed_json_is_not_reported_as_authentication_failure():
    c = client_for('Pathao')
    c.refresh_token = 'refresh-token'
    c.retry_unauthorized_orders = True
    respx.post('https://provider.test/aladdin/api/v1/issue-token').respond(200, json={'access_token': 'new', 'expires_in': 3600})
    respx.post('https://provider.test/aladdin/api/v1/orders').mock(side_effect=[httpx.Response(401), httpx.Response(200, text='{broken')])
    with pytest.raises(jukto.UnexpectedProviderResponseError):
        invoke(c, 'Pathao')


# Official GreenWeb English manual: per-recipient SENT/FAILED; fixtures synthetic.
@pytest.mark.parametrize('statuses', [['SENT', 'FAILED'], ['FAILED', 'SENT'], ['FAILED', 'FAILED'], ['SENT', 'unknown']])
@respx.mock
def test_greenweb_batch_preserves_every_result(statuses):
    c = client_for('GreenWeb')
    payload = [{'to': str(i), 'status': status, 'statusmsg': 'opaque'} for i, status in enumerate(statuses)]
    route = respx.route(host='provider.test').respond(200, json=payload)
    with pytest.raises(jukto.SMSBatchError) as caught:
        invoke(c, 'GreenWeb')
    assert caught.value.results == payload
    assert caught.value.response_body == payload
    assert caught.value.results.sent_indices == tuple(i for i,s in enumerate(statuses) if s == 'SENT')
    assert caught.value.results.failed_indices == tuple(i for i,s in enumerate(statuses) if s == 'FAILED')
    assert caught.value.results.unknown_indices == tuple(i for i,s in enumerate(statuses) if s == 'unknown')
    assert route.call_count == 1


@respx.mock
def test_greenweb_success_content_is_not_interpreted_as_error():
    payload = [{'to': '01700000000', 'status': 'SENT', 'message': 'Your account balance is insufficient; invalid token', 'statusmsg': 'sent'}]
    respx.route(host='provider.test').respond(200, json=payload)
    result = invoke(client_for('GreenWeb'), 'GreenWeb')
    assert isinstance(result, list)
    assert result == payload
    assert result.sent_indices == (0,)


@respx.mock
def test_greenweb_text_batch_preserves_success_and_failure():
    respx.route(host='provider.test').respond(200, text='Ok: SMS accepted\nError: Invalid Number')
    with pytest.raises(jukto.SMSBatchError) as caught:
        invoke(client_for('GreenWeb'), 'GreenWeb')
    assert caught.value.results.sent_indices == (0,)
    assert caught.value.results.failed_indices == (1,)
    assert len(caught.value.results) == 2


@pytest.mark.parametrize('name,content', [('Steadfast', '{"status":200,"consignment":{"message":"ok"}}'),
    ('RedX', '{"tracking": {"message":"ok"}}'), ('Pathao', '{"data": {"message":"ok"}}'),
    ('AlphaSMS', '{"error":0,"data":{"request_id":true}}'),
    ('AlphaSMS', '{"error":0,"data":{"request_id":null}}'),
    ('AlphaSMS', '{"error":"' + '9' * 5000 + '"}')])
@respx.mock
def test_nested_success_schema_and_oversized_codes_are_rejected(name, content):
    c = client_for(name)
    respx.route(host='provider.test').respond(200, content=content)
    with pytest.raises(jukto.UnexpectedProviderResponseError):
        invoke(c, name)


@pytest.mark.parametrize('refresh', [False, True])
@pytest.mark.parametrize('expiry', [None, True, [], 'not-a-number', 'nan', 'inf', -1])
@respx.mock
def test_pathao_invalid_expiry_is_a_schema_failure(refresh, expiry):
    c = client_for('Pathao')
    c.access_token = None
    c.refresh_token = 'refresh' if refresh else None
    route = respx.route(host='provider.test').respond(200, json={'access_token': 'token', 'expires_in': expiry})
    with pytest.raises(jukto.UnexpectedProviderResponseError):
        c.get_token()
    assert route.call_count == 1


@pytest.mark.parametrize('phase', ['refresh', 'replay'])
@respx.mock
def test_pathao_programming_failure_is_not_hidden_by_fallback(phase):
    c = client_for('Pathao')
    c.refresh_token = 'refresh'
    c.retry_unauthorized_orders = True
    if phase == 'refresh':
        c.access_token = None
        respx.route(host='provider.test').respond(200, json={})
        with patch('httpx.Response.json', side_effect=TypeError('internal bug')):
            with pytest.raises(TypeError, match='internal bug'):
                c.get_token()
    else:
        respx.post('https://provider.test/aladdin/api/v1/issue-token').respond(200, json={'access_token': 'new', 'expires_in': 3600})
        respx.post('https://provider.test/aladdin/api/v1/orders').mock(side_effect=[httpx.Response(401), httpx.Response(200, json={})])
        with patch.object(c, '_inspect_response', side_effect=TypeError('internal bug')):
            with pytest.raises(TypeError, match='internal bug'):
                invoke(c, 'Pathao')


@pytest.mark.parametrize('payload', [[{'status':'SENT'}, 42], [{'status':'FAILED'}, None], {'status':'FAILED'}])
@respx.mock
def test_greenweb_malformed_entries_do_not_discard_known_outcomes(payload):
    respx.route(host='provider.test').respond(200, json=payload)
    with pytest.raises(jukto.SMSBatchError) as caught:
        invoke(client_for('GreenWeb'), 'GreenWeb')
    assert caught.value.response_body == payload
    assert len(caught.value.results) == (len(payload) if isinstance(payload, list) else 1)


@respx.mock
def test_greenweb_documented_json_mode_is_requested():
    from urllib.parse import parse_qs
    route = respx.route(host='provider.test').respond(200, json=[{'status':'SENT'}])
    invoke(client_for('GreenWeb'), 'GreenWeb')
    assert parse_qs(route.calls.last.request.content.decode())['json'] == ['1']
