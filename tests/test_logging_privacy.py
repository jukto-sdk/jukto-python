"""Exercise actual adapter log and exception paths with synthetic sensitive data."""
import logging
import time
import traceback

import httpx
import pytest
import respx
import jukto
from jukto.logger import mask_sensitive

SECRETS = ['private-key-ZZ99', 'private-password-XX88', 'private-token-AA77',
           '01798765432', 'OTP-684921', 'House-Secret-42', 'merchant-private@example.test']
ECHO = ' '.join(SECRETS)
PROVIDERS = ['AlphaSMS', 'BulkSMSBD', 'GreenWeb', 'Steadfast', 'RedX', 'Pathao']


def make_client(name):
    options = {'base_url': 'https://provider.test/api?private=' + SECRETS[0]}
    if name == 'Pathao':
        c = jukto.PathaoClient(SECRETS[0], SECRETS[0], SECRETS[-1], SECRETS[1], **options)
        c.access_token = SECRETS[2]
        c.token_expiry = time.time() + 3600
        return c
    if name == 'Steadfast':
        return jukto.SteadfastClient(SECRETS[0], SECRETS[0], **options)
    if name == 'BulkSMSBD':
        return jukto.BulkSMSBDClient(SECRETS[0], 'sender', **options)
    return getattr(jukto, name + 'Client')(SECRETS[0], **options)


def invoke(c, name):
    if name in ['AlphaSMS', 'BulkSMSBD', 'GreenWeb']:
        return c.send_sms(SECRETS[3], SECRETS[4])
    return c.create_order(jukto.Parcel('invoice-private', 'private-name', SECRETS[3], SECRETS[5], 10, store_id=123))


@pytest.mark.parametrize('name', PROVIDERS)
@pytest.mark.parametrize('mode', ['success', 'http_error', 'timeout', 'network'])
@respx.mock
def test_adapter_logs_and_exceptions_exclude_sensitive_values(name, mode, caplog):
    c = make_client(name)
    payload = {'error': 0, 'response_code': 202, 'status': 'success', 'message': ECHO,
               'data': {'access_token': SECRETS[2], 'address': SECRETS[5]}}
    route = respx.route(host='provider.test')
    if mode == 'success':
        route.respond(200, json=payload)
    elif mode == 'http_error':
        route.respond(422, json={'error': ECHO, 'message': ECHO})
    else:
        route.mock(side_effect=(httpx.ReadTimeout if mode == 'timeout' else httpx.ConnectError)(ECHO))
    with caplog.at_level(logging.DEBUG, logger='jukto'):
        if mode == 'success':
            invoke(c, name)
            rendered = ''
        else:
            with pytest.raises(jukto.JuktoError) as caught:
                invoke(c, name)
            rendered = str(caught.value) + repr(caught.value) + caught.value.message
            rendered += ''.join(traceback.format_exception(caught.value))
            if mode == 'http_error':
                assert ECHO in str(caught.value.response_body)
    records = '\n'.join(r.getMessage() for r in caplog.records if r.name == 'jukto')
    assert records
    for secret in SECRETS:
        assert secret not in records + rendered


@pytest.mark.parametrize('name,payload', [
    ('AlphaSMS', {'error': 417, 'msg': ECHO}),
    ('BulkSMSBD', {'response_code': 1007, 'error_message': ECHO}),
    ('GreenWeb', {'status': 'error', 'message': ECHO}),
    ('Steadfast', {'status': 422, 'message': ECHO}),
    ('RedX', {'status': 'error', 'message': ECHO}),
])
@respx.mock
def test_inline_errors_keep_raw_body_out_of_logs_and_exception_strings(name, payload, caplog):
    c = make_client(name)
    respx.route(host='provider.test').respond(200, json=payload)
    with caplog.at_level(logging.DEBUG, logger='jukto'):
        with pytest.raises(jukto.ProviderError) as caught:
            invoke(c, name)
    assert caught.value.response_body == payload
    rendered = caplog.text + str(caught.value) + repr(caught.value)
    for secret in SECRETS:
        assert secret not in rendered


@pytest.mark.parametrize('value', [SECRETS[0], 123456, [SECRETS[0]], {'nested': SECRETS[0]}, None])
def test_sensitive_values_fully_redacted_regardless_of_type(value):
    original = {'AUTHORIZATION': value}
    assert mask_sensitive(original) == {'AUTHORIZATION': '***'}
    assert original['AUTHORIZATION'] == value


@respx.mock
def test_pathao_token_issue_and_refresh_logs_are_private(caplog):
    c = make_client('Pathao')
    c.access_token = None
    c.refresh_token = SECRETS[2]
    respx.route(host='provider.test').mock(side_effect=[
        httpx.Response(401, json={'message': ECHO}),
        httpx.Response(200, json={'access_token': SECRETS[2], 'refresh_token': SECRETS[1], 'expires_in': 3600}),
    ])
    with caplog.at_level(logging.DEBUG, logger='jukto'):
        c.get_token()
    for secret in SECRETS:
        assert secret not in caplog.text


@pytest.mark.parametrize('prefix', ['Invalid Token', 'SMS rate exceeds account balance', 'Invalid number', 'Error'])
@respx.mock
def test_greenweb_raw_text_errors_are_private(prefix, caplog):
    c = make_client('GreenWeb')
    respx.route(host='provider.test').respond(200, text=prefix + ' ' + ECHO)
    with caplog.at_level(logging.DEBUG, logger='jukto'):
        with pytest.raises(jukto.ProviderError) as caught:
            invoke(c, 'GreenWeb')
    assert ECHO in caught.value.response_body
    for secret in SECRETS:
        assert secret not in caplog.text + str(caught.value) + repr(caught.value)


@respx.mock
def test_debug_helper_console_and_exception_logging_are_private(monkeypatch, capsys):
    from jukto.logger import logger, enable_debug_logging
    monkeypatch.setattr(logger, 'handlers', [logging.NullHandler()])
    monkeypatch.setattr(logger, 'level', logging.WARNING)
    enable_debug_logging()
    c = make_client('AlphaSMS')
    respx.route(host='provider.test').respond(422, json={'message': ECHO})
    try:
        invoke(c, 'AlphaSMS')
    except jukto.JuktoError:
        logger.exception('Adapter operation failed')
    output = capsys.readouterr().err
    assert 'provider=AlphaSMS' in output
    for secret in SECRETS:
        assert secret not in output


@respx.mock
def test_pathao_password_auth_failure_keeps_body_private(caplog):
    c = make_client('Pathao')
    c.access_token = None
    respx.route(host='provider.test').respond(401, json={'message': ECHO})
    with caplog.at_level(logging.DEBUG, logger='jukto'):
        with pytest.raises(jukto.ProviderAuthenticationError) as caught:
            c.get_token()
    assert caught.value.response_body == {'message': ECHO}
    rendered = caplog.text + ''.join(traceback.format_exception(caught.value))
    for secret in SECRETS:
        assert secret not in rendered
