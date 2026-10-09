"""Offline transport policy tests; these do not certify provider endpoint support."""
from unittest.mock import patch
import time

import httpx
import pytest
import respx
from jukto import (
    AlphaSMSClient, BulkSMSBDClient, GreenWebClient, PathaoClient, RedXClient,
    SteadfastClient, JuktoConfigurationError, ProviderError,
)

FACTORIES = [
    lambda **kw: AlphaSMSClient('key', **kw),
    lambda **kw: BulkSMSBDClient('key', 'sender', **kw),
    lambda **kw: GreenWebClient('key', **kw),
    lambda **kw: PathaoClient('id', 'secret', 'user', 'password', **kw),
    lambda **kw: RedXClient('key', **kw),
    lambda **kw: SteadfastClient('key', 'secret', **kw),
]


@pytest.mark.parametrize('factory', FACTORIES)
@pytest.mark.parametrize('url', ['http://local.test/api', 'ftp://local.test/api', '/api', 'https:///api'])
def test_reject_unsafe_endpoint_before_http(factory, url):
    with patch('httpx.Client') as transport:
        with pytest.raises(JuktoConfigurationError):
            factory(base_url=url)
        transport.assert_not_called()


@pytest.mark.parametrize('factory', FACTORIES)
def test_explicit_http_opt_in(factory):
    assert factory(base_url='http://local.test/api', allow_insecure_http=True).base_url == 'http://local.test/api'
    with pytest.raises(JuktoConfigurationError):
        factory(base_url='ftp://local.test/api', allow_insecure_http=True)


def test_bulk_legacy_default_requires_explicit_opt_in():
    with pytest.raises(JuktoConfigurationError):
        BulkSMSBDClient('key', 'sender')
    assert BulkSMSBDClient('key', 'sender', allow_insecure_http=True).base_url == BulkSMSBDClient.DEFAULT_URL


@pytest.mark.parametrize('factory', FACTORIES)
@respx.mock
def test_redirect_does_not_forward_credentials(factory, sample_parcel):
    client = factory(base_url='https://provider.test/api')
    if isinstance(client, PathaoClient):
        client.access_token = 'secret-token'
        client.token_expiry = time.time() + 3600
    initial = respx.route(host='provider.test').respond(307, headers={'Location': 'https://attacker.test/collect'})
    target = respx.route(host='attacker.test').respond(200, json={'error': 0})
    with pytest.raises(ProviderError):
        if isinstance(client, (AlphaSMSClient, BulkSMSBDClient, GreenWebClient)):
            client.send_sms('01700000000', 'secret-message')
        else:
            client.create_order(sample_parcel)
    assert initial.call_count == 1
    assert target.call_count == 0


@pytest.mark.parametrize('factory', FACTORIES)
@respx.mock
def test_mutated_base_url_is_rechecked_before_sending(factory, sample_parcel):
    client = factory(base_url='https://provider.test/api')
    client.base_url = 'http://local.test/api'
    with pytest.raises(JuktoConfigurationError):
        if isinstance(client, (AlphaSMSClient, BulkSMSBDClient, GreenWebClient)):
            client.send_sms('01700000000', 'message')
        else:
            client.create_order(sample_parcel)
    assert not respx.calls


def test_tls_and_redirect_settings_are_explicit():
    from jukto._transport import secure_http_client
    with patch('jukto._transport.httpx.Client') as transport:
        secure_http_client('https://provider.test', 30, False)
    transport.assert_called_once_with(timeout=30, verify=True, follow_redirects=False)


@pytest.mark.parametrize('factory', FACTORIES)
@pytest.mark.parametrize('url', ['https://user:secret@provider.test/api', 'https://provider.test:bad/api'])
def test_bad_urls_do_not_leak_embedded_credentials(factory, url):
    with pytest.raises(JuktoConfigurationError) as caught:
        factory(base_url=url)
    assert 'secret' not in str(caught.value)


@pytest.mark.parametrize('factory', FACTORIES)
@respx.mock
def test_http_opt_in_allows_explicit_legacy_request(factory, sample_parcel):
    client = factory(base_url='http://local.test/api', allow_insecure_http=True)
    if isinstance(client, PathaoClient):
        client.access_token = 'offline-token'
        client.token_expiry = time.time() + 3600
    # Deliberate transport-only simulation, not evidence of provider behavior.
    payload = {'error': 0, 'data': {'request_id': 123, 'consignment_id': '123'},
               'response_code': 202, 'status': 200, 'consignment': {'consignment_id': 123}, 'tracking_id': '123'}
    if isinstance(client, GreenWebClient):
        payload = [{'status': 'SENT'}]
    route = respx.route(host='local.test').respond(200, json=payload)
    if isinstance(client, (AlphaSMSClient, BulkSMSBDClient, GreenWebClient)):
        client.send_sms('01700000000', 'message')
    else:
        client.create_order(sample_parcel)
    assert route.call_count == 1


@pytest.mark.parametrize('refresh', [False, True])
@respx.mock
def test_pathao_auth_redirect_never_forwards_password_or_refresh_token(refresh):
    client = PathaoClient('id', 'secret', 'user', 'password', base_url='https://provider.test')
    if refresh:
        client.refresh_token = 'refresh-secret'
    respx.route(host='provider.test').respond(307, headers={'Location': 'https://attacker.test/collect'})
    target = respx.route(host='attacker.test').respond(200, json={'access_token': 'bad'})
    with pytest.raises(ProviderError):
        client.get_token()
    assert not target.called
