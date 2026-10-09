"""Offline lifecycle regressions; synthetic responses do not certify Pathao contracts."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
import time
import httpx
import pytest
import respx
from jukto import PathaoClient, ProviderConnectionError, ProviderTimeoutError, ProviderServerError, InvalidRequestError, UnexpectedProviderResponseError


def client():
    c = PathaoClient('id', 'secret', 'user', 'password')
    c.access_token, c.refresh_token, c.token_expiry = 'old', 'refresh', time.monotonic() + 3600
    return c


@pytest.mark.parametrize('failure,error', [(httpx.ReadTimeout('timeout'), ProviderTimeoutError), (httpx.ConnectError('network'), ProviderConnectionError), (httpx.Response(500), ProviderServerError), (httpx.Response(422), InvalidRequestError), (httpx.Response(200, text='{'), UnexpectedProviderResponseError)])
@respx.mock
def test_final_retry_error(failure, error):
    c = client()
    auth = respx.post(c.base_url + '/aladdin/api/v1/issue-token').respond(200, json={'access_token':'new','expires_in':3600})
    route = respx.get(c.base_url + '/aladdin/api/v1/stores').mock(side_effect=[httpx.Response(401), failure])
    with pytest.raises(error):
        c.get_stores()
    assert route.call_count == 2 and auth.call_count == 1


@pytest.mark.parametrize('failure,error', [(httpx.ReadTimeout('timeout'), ProviderTimeoutError), (httpx.ConnectError('network'), ProviderConnectionError), (httpx.Response(500), ProviderServerError), (httpx.Response(400, json={'error':'invalid_client'}), InvalidRequestError)])
@respx.mock
def test_refresh_outage_never_password_fallback(failure,error):
    c = client()
    c.token_expiry = 0
    route = respx.post(c.base_url + '/aladdin/api/v1/issue-token').mock(side_effect=failure)
    with pytest.raises(error):
        c.get_token()
    assert route.call_count == 1
    assert (c.access_token,c.refresh_token,c.token_expiry) == ('old','refresh',0)


@pytest.mark.parametrize('field,value', [('refresh_token',None),('refresh_token',42),('refresh_token',''),('access_token',' '),('expires_in',None),('expires_in',float('inf')),('expires_in',0)])
@respx.mock
def test_malformed_token_cannot_partially_replace_cache(field,value):
    c = client()
    c.token_expiry = 0
    payload = {'access_token':'new','refresh_token':'rotated','expires_in':3600}
    payload[field] = value
    # Infinity is representable as raw JSON by Python's decoder, not httpx's strict encoder.
    import json
    route = respx.post(c.base_url + '/aladdin/api/v1/issue-token').respond(200, text=json.dumps(payload))
    with pytest.raises(UnexpectedProviderResponseError):
        c.get_token()
    assert (c.access_token,c.refresh_token,c.token_expiry) == ('old','refresh',0)
    assert route.call_count == 1


@respx.mock
def test_concurrent_refresh_single_flight():
    c = client()
    c.token_expiry = 0
    start = Barrier(8)
    entered, release = Event(), Event()
    def response(request):
        entered.set()
        assert release.wait(5)
        return httpx.Response(200,json={'access_token':'new','refresh_token':'rotated','expires_in':3600})
    route = respx.post(c.base_url + '/aladdin/api/v1/issue-token').mock(side_effect=response)
    def call():
        start.wait(5)
        return c.get_token()
    with ThreadPoolExecutor(8) as pool:
        futures = [pool.submit(call) for _ in range(8)]
        assert entered.wait(5)
        release.set()
        assert [f.result(5) for f in futures] == ['new'] * 8
    assert route.call_count == 1
    assert c.refresh_token == 'rotated'


@respx.mock
def test_short_expiry_and_wall_clock_jump(monkeypatch):
    c = client()
    c.token_expiry = 0
    route = respx.post(c.base_url + '/aladdin/api/v1/issue-token').respond(200,json={'access_token':'short','expires_in':30})
    assert c.get_token() == 'short'
    monkeypatch.setattr(time,'time',lambda: 10**20)
    assert c.get_token() == 'short'
    assert route.call_count == 1


@respx.mock
def test_order_is_not_replayed_without_opt_in(sample_parcel):
    c = client()
    c.store_id = 123
    route = respx.post(c.base_url + '/aladdin/api/v1/orders').respond(401)
    from jukto import ProviderAuthenticationError
    with pytest.raises(ProviderAuthenticationError):
        c.create_order(sample_parcel)
    assert route.call_count == 1


@respx.mock
def test_late_concurrent_401_uses_already_refreshed_generation():
    c = client()
    both_old = Barrier(2)
    refreshed = Event()
    def auth(request):
        refreshed.set()
        return httpx.Response(200,json={'access_token':'new','refresh_token':'rotated','expires_in':3600})
    def resource(request):
        if request.headers['Authorization'] == 'Bearer old':
            index = both_old.wait(5)
            if index == 0:
                assert refreshed.wait(5)
            return httpx.Response(401)
        return httpx.Response(200,json={'data':[]})
    route = respx.post(c.base_url + '/aladdin/api/v1/issue-token').mock(side_effect=auth)
    respx.get(c.base_url + '/aladdin/api/v1/stores').mock(side_effect=resource)
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(c.get_stores) for _ in range(2)]
        assert [f.result(5) for f in futures] == [{'data':[]}] * 2
    assert route.call_count == 1
