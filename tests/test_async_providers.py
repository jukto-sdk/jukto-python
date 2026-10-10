"""Offline parity and actual asyncio scheduling regressions."""
import asyncio
import httpx
import pytest
from jukto import AsyncAlphaSMSClient, AlphaSMSClient, AsyncPathaoClient

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
async def test_alpha_contract_equivalence():
    responses = [{'error': 0, 'data': {'request_id': 123}}, {'error': 417}, [], {'error': True}]
    for body in responses:
        def handler(request):
            return httpx.Response(200, json=body, headers={'X-Request-ID': 'safe-id'})
        def capture(call):
            try:
                return call()
            except Exception as exc:
                return type(exc), exc.http_status, exc.provider_error_code, exc.outcome, exc.reconciliation_required
        with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
            sync = AlphaSMSClient('synthetic', http_client=transport)
            expected = capture(lambda: sync.submit_sms('01700000000', 'synthetic'))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
            client = AsyncAlphaSMSClient('synthetic', http_client=transport)
            try:
                actual = await client.submit_sms('01700000000', 'synthetic')
            except Exception as exc:
                actual = type(exc), exc.http_status, exc.provider_error_code, exc.outcome, exc.reconciliation_required
            assert actual == expected
            await client.aclose()
            assert not transport.is_closed

@pytest.mark.anyio
async def test_pathao_refresh_single_flight():
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []
    async def handler(request):
        calls.append(request)
        entered.set()
        await release.wait()
        return httpx.Response(200, json={'access_token': 'new', 'refresh_token': 'rotated', 'expires_in': 3600})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = AsyncPathaoClient('id', 'secret', 'user', 'password', http_client=transport)
        client.refresh_token = 'old'
        tasks = [asyncio.create_task(client.get_token()) for _ in range(20)]
        await asyncio.wait_for(entered.wait(), 2)
        release.set()
        assert await asyncio.gather(*tasks) == ['new'] * 20
        assert len(calls) == 1
        assert client.refresh_token == 'rotated'
        await client.aclose()

import json
import time
from pathlib import Path
import jukto

CONTRACT = json.loads((Path(__file__).parent / 'fixtures/alphasms_contract.json').read_text())

@pytest.mark.anyio
@pytest.mark.parametrize('code,meaning,exception_name', CONTRACT['errors'])
@pytest.mark.parametrize('as_string', [False, True])
async def test_official_alpha_codes_both_interfaces(code, meaning, exception_name, as_string):
    body = {'error': str(code) if as_string else code}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))) as transport:
        client = AsyncAlphaSMSClient('synthetic', http_client=transport)
        with pytest.raises(getattr(jukto, exception_name)) as caught:
            await client.send_sms('01700000000', 'synthetic')
        assert type(caught.value) is getattr(jukto, exception_name), meaning
        assert caught.value.provider_error_code == body['error']
        assert caught.value.http_status == 200

PROVIDERS = ['AlphaSMS', 'BulkSMSBD', 'GreenWeb', 'Steadfast', 'RedX', 'Pathao']
SUCCESS = {'AlphaSMS': {'error': 0, 'data': {'request_id': 123}},
           'BulkSMSBD': {'response_code': 202}, 'GreenWeb': [{'status': 'SENT'}],
           'Steadfast': {'status': 200, 'consignment': {'consignment_id': 'id'}},
           'RedX': {'tracking_id': 'id'}, 'Pathao': {'type': 'success', 'data': {'consignment_id': 'id'}}}

def make_client(name, asynchronous, transport, **kwargs):
    cls = getattr(jukto, ('Async' if asynchronous else '') + name + 'Client')
    args = ['synthetic']
    if name in ('BulkSMSBD', 'Steadfast'): args.append('synthetic-secret')
    if name == 'Pathao': args += ['secret', 'user', 'password']
    client = cls(*args, http_client=transport, allow_insecure_http=name == 'BulkSMSBD', **kwargs)
    if name == 'Pathao':
        client.access_token, client.refresh_token, client.token_expiry = 'cached', 'refresh', time.monotonic() + 3600
    return client

def parcel():
    return jukto.Parcel(invoice_id='synthetic-id', recipient_name='Synthetic', recipient_phone='01700000000',
                        recipient_address='Synthetic address', cod_amount=0, store_id=1,
                        declared_value=100, redx_delivery_area='Synthetic area', redx_delivery_area_id=1)

def submit(client, name):
    return client.submit_sms(['01700000000', '01800000000'], 'synthetic') if name in PROVIDERS[:3] else client.create_shipment(parcel())

def error_snapshot(exc):
    return (type(exc), str(exc), exc.http_status, exc.provider_error_code, exc.request_id,
            exc.retry_after, exc.outcome, exc.reconciliation_required, getattr(exc, 'normalized_result', None))

@pytest.mark.anyio
@pytest.mark.parametrize('name', PROVIDERS)
@pytest.mark.parametrize('scenario', ['success', 'empty', 'html', 'scalar', 'list', 'missing', 'inline',
                                      '401', '404', '422', '429', '500', '302', 'timeout', 'connection'])
async def test_all_provider_contracts_equivalent(name, scenario):
    requests = []
    def handler(request):
        requests.append((request.method, str(request.url), request.content,
                         {k: v for k, v in request.headers.items() if k.lower() not in ('user-agent',)}))
        if scenario == 'timeout': raise httpx.ReadTimeout('synthetic-secret', request=request)
        if scenario == 'connection': raise httpx.ConnectError('synthetic-secret', request=request)
        headers = {'X-Request-ID': 'safe-request', 'Retry-After': '5'}
        if scenario.isdecimal(): return httpx.Response(int(scenario), json={'error': 'opaque'}, headers=headers)
        if scenario in ('empty', 'html'): return httpx.Response(200, content='' if scenario == 'empty' else '<html>bad</html>', headers=headers)
        body = SUCCESS[name] if scenario == 'success' else None if scenario == 'scalar' else [] if scenario == 'list' else {'status': 422, 'error': 417, 'response_code': 1003} if scenario == 'inline' else {}
        return httpx.Response(200, json=body, headers=headers)
    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        client = make_client(name, False, transport)
        try: expected = submit(client, name)
        except jukto.JuktoError as exc: expected = error_snapshot(exc)
        client.close()
    expected_requests, requests[:] = requests[:], []
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = make_client(name, True, transport)
        try: actual = await submit(client, name)
        except jukto.JuktoError as exc: actual = error_snapshot(exc)
        assert actual == expected
        assert requests == expected_requests
        await client.aclose()
        assert not transport.is_closed

@pytest.mark.anyio
@pytest.mark.parametrize('name', PROVIDERS[3:])
async def test_status_and_invalid_input_before_http(name):
    calls = []
    body = {'Pathao': {'data': {'order_status': 'opaque'}}, 'RedX': {'parcel': {'status': 'opaque'}},
            'Steadfast': {'status': 200, 'delivery_status': 'opaque'}}[name]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(200, json=body))) as transport:
        client = make_client(name, True, transport)
        assert (await client.check_shipment_status('id')).status == jukto.Outcome.UNKNOWN
        invalid = parcel(); invalid.item_quantity = 0
        with pytest.raises(jukto.JuktoValidationError): await client.create_order(invalid)
        assert len(calls) == 1

@pytest.mark.anyio
async def test_cancelled_refresh_leader_releases_waiters_without_partial_cache():
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []
    follower_entered, follower_release = asyncio.Event(), asyncio.Event()
    async def handler(request):
        calls.append(request)
        if len(calls) == 1:
            entered.set()
            await release.wait()
        else:
            follower_entered.set(); await follower_release.wait()
        return httpx.Response(200, json={'access_token': 'new', 'refresh_token': 'rotation', 'expires_in': 3600})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = make_client('Pathao', True, transport); client.token_expiry = 0
        leader = asyncio.create_task(client.get_token())
        await asyncio.wait_for(entered.wait(), 2)
        waiter = asyncio.create_task(client.get_token())
        leader.cancel()
        with pytest.raises(asyncio.CancelledError): await leader
        assert client.access_token == 'cached' and client.refresh_token == 'refresh'
        assert client._token_generation == 0
        follower_release.set()
        assert await asyncio.wait_for(waiter, 2) == 'new'
        assert len(calls) == 2 and client._token_generation == 1

@pytest.mark.anyio
@pytest.mark.parametrize('failure', ['timeout', 'connection', '500', 'invalid', 'invalid_grant'])
async def test_refresh_failure_atomic_and_classified(failure):
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        if failure == 'timeout': raise httpx.ReadTimeout('opaque', request=request)
        if failure == 'connection': raise httpx.ConnectError('opaque', request=request)
        if failure == '500': return httpx.Response(500)
        if failure == 'invalid': return httpx.Response(200, json={'access_token': 'new', 'expires_in': False})
        if len(calls) == 1: return httpx.Response(400, json={'error': 'invalid_grant'})
        return httpx.Response(200, json={'access_token': 'new', 'expires_in': 3600})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = make_client('Pathao', True, transport); client.token_expiry = 0
        if failure == 'invalid_grant':
            assert await client.get_token() == 'new'
            assert [c['grant_type'] for c in calls] == ['refresh_token', 'password']
        else:
            with pytest.raises(jukto.ProviderError): await client.get_token()
            assert client.access_token == 'cached' and client.refresh_token == 'refresh' and client.token_expiry == 0
            assert len(calls) == 1

@pytest.mark.anyio
@pytest.mark.parametrize('final', ['success', 'timeout', 'connection', '500', 'invalid'])
async def test_pathao_final_retry_error_and_metadata(final):
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.path.endswith('issue-token'): return httpx.Response(200, json={'access_token': 'new', 'refresh_token': 'r', 'expires_in': 3600})
        if len(calls) == 1: return httpx.Response(401, headers={'X-Request-ID': 'original'})
        if final == 'timeout': raise httpx.ReadTimeout('opaque', request=request)
        if final == 'connection': raise httpx.ConnectError('opaque', request=request)
        return httpx.Response(500 if final == '500' else 200, json={'data': {'order_status': 'opaque'}} if final == 'success' else {}, headers={'X-Request-ID': 'final'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = make_client('Pathao', True, transport)
        if final == 'success': assert (await client.check_shipment_status('id')).status == jukto.Outcome.UNKNOWN
        else:
            cls = {'timeout': jukto.ProviderTimeoutError, 'connection': jukto.ProviderConnectionError,
                   '500': jukto.ProviderServerError, 'invalid': jukto.UnexpectedProviderResponseError}[final]
            with pytest.raises(cls) as caught: await client.check_status('id')
            assert caught.value.request_id == ('final' if final in ('500', 'invalid') else None)
        assert len(calls) == 3

@pytest.mark.anyio
async def test_stale_concurrent_401_refreshes_once():
    barrier = asyncio.Event(); old_calls = []; auth_calls = []
    async def handler(request):
        if request.url.path.endswith('issue-token'):
            auth_calls.append(request)
            return httpx.Response(200, json={'access_token': 'new', 'expires_in': 3600})
        if request.headers['Authorization'] == 'Bearer cached':
            old_calls.append(request)
            if len(old_calls) == 10: barrier.set()
            await barrier.wait()
            return httpx.Response(401)
        return httpx.Response(200, json={'data': {'order_status': 'opaque'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = make_client('Pathao', True, transport)
        results = await asyncio.wait_for(asyncio.gather(*(client.check_status(str(i)) for i in range(10))), 2)
        assert len(results) == 10 and len(auth_calls) == 1

@pytest.mark.anyio
async def test_concurrent_error_metadata_and_cancellation_are_request_local():
    entered, release = asyncio.Event(), asyncio.Event()
    async def handler(request):
        body = request.content.decode()
        if 'cancel' in body:
            entered.set(); await release.wait()
        await asyncio.sleep(0)
        return httpx.Response(200, json={'error': 417}, headers={'X-Request-ID': 'one' if 'one' in body else 'two'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = AsyncAlphaSMSClient('synthetic', http_client=transport)
        task = asyncio.create_task(client.send_sms('01700000000', 'cancel'))
        await asyncio.wait_for(entered.wait(), 2); task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        errors = await asyncio.gather(client.send_sms('01700000000', 'one'), client.send_sms('01700000000', 'two'), return_exceptions=True)
        assert [e.request_id for e in errors] == ['one', 'two']
        assert all(e.outcome == jukto.Outcome.FAILED and not e.reconciliation_required for e in errors)

@pytest.mark.anyio
async def test_owned_pool_reuse_cancel_and_cleanup(monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    instances = []; original = httpx.AsyncClient
    async def handler(request):
        if 'cancel' in request.content.decode(): entered.set(); await release.wait()
        return httpx.Response(200, json=SUCCESS['AlphaSMS'])
    class OwnedClient(original):
        def __init__(self, **kwargs):
            assert kwargs['verify'] is True and kwargs['follow_redirects'] is False
            super().__init__(transport=httpx.MockTransport(handler), **kwargs); instances.append(self)
    monkeypatch.setattr(httpx, 'AsyncClient', OwnedClient)
    provider = AsyncAlphaSMSClient('synthetic')
    with pytest.raises(asyncio.CancelledError):
        async with provider:
            await provider.send_sms('01700000000', 'first')
            task = asyncio.create_task(provider.send_sms('01700000000', 'cancel'))
            await asyncio.wait_for(entered.wait(), 2); task.cancel(); await task
    assert len(instances) == 1 and instances[0].is_closed
    await provider.aclose()
    with pytest.raises(jukto.JuktoConfigurationError): await provider.send_sms('01700000000', 'again')

@pytest.mark.anyio
async def test_cleanup_waits_even_after_repeated_cancellation():
    entered, release = asyncio.Event(), asyncio.Event()
    class SlowClose(httpx.AsyncClient):
        async def aclose(self):
            entered.set(); await release.wait(); await super().aclose()
    transport = SlowClose(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    provider = AsyncAlphaSMSClient('synthetic')
    provider._transport._client = transport
    task = asyncio.create_task(provider.aclose())
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel(); await asyncio.sleep(0); task.cancel(); await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError): await asyncio.wait_for(task, 2)
    assert transport.is_closed

@pytest.mark.anyio
@pytest.mark.parametrize('setting', ['sync_client', 'limits_borrowed', 'limits_invalid', 'http', 'closed'])
async def test_async_transport_configuration(setting):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as sync:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as borrowed:
            kwargs = {'http_client': borrowed}
            if setting == 'sync_client': kwargs['http_client'] = sync
            elif setting == 'limits_borrowed': kwargs['limits'] = httpx.Limits()
            elif setting == 'limits_invalid': kwargs = {'limits': 'bad'}
            elif setting == 'http': kwargs['base_url'] = 'http://example.invalid'
            else: await borrowed.aclose()
            with pytest.raises(jukto.JuktoConfigurationError):
                provider = AsyncAlphaSMSClient('synthetic', **kwargs)
                async with provider: pass

@pytest.mark.anyio
async def test_borrowed_auth_redirect_and_timeout_overridden():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={'Location': 'https://other.invalid'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), auth=('user', 'password'), follow_redirects=True) as borrowed:
        provider = AsyncAlphaSMSClient('synthetic', http_client=borrowed, timeout=2)
        with pytest.raises(jukto.ProviderError): await provider.send_sms('01700000000', 'synthetic')
        assert len(requests) == 1 and 'Authorization' not in requests[0].headers
        assert requests[0].extensions['timeout']['read'] == 2
        await provider.aclose(); assert not borrowed.is_closed

@pytest.mark.anyio
@pytest.mark.parametrize('name', PROVIDERS)
async def test_async_capabilities_match_sync(name):
    with httpx.Client() as sync:
        async with httpx.AsyncClient() as async_client:
            assert make_client(name, True, async_client).capabilities == make_client(name, False, sync).capabilities

@pytest.mark.anyio
@pytest.mark.parametrize('body', [[{'status': 'SENT'}, {'status': 'FAILED'}, {'status': 'opaque'}],
                                  {'status': 'error', 'message': 'synthetic-secret'},
                                  'invalid token synthetic-secret', 'ok: synthetic-secret'])
async def test_greenweb_partial_raw_and_safe_logging(body, caplog):
    import logging
    caplog.set_level(logging.DEBUG, logger='jukto')
    def handler(request):
        if isinstance(body, str): return httpx.Response(200, text=body)
        return httpx.Response(200, json=body)
    expected = None
    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        client = make_client('GreenWeb', False, transport)
        try: expected = client.submit_sms('01700000000', 'OTP 123456')
        except jukto.ProviderError as exc: expected = error_snapshot(exc)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = make_client('GreenWeb', True, transport)
        try: actual = await client.submit_sms('01700000000', 'OTP 123456')
        except jukto.ProviderError as exc: actual = error_snapshot(exc)
        assert actual == expected
    assert all(secret not in caplog.text for secret in ('synthetic-secret', '01700000000', '123456'))

@pytest.mark.anyio
async def test_pathao_cancelled_waiter_does_not_cancel_leader():
    entered, release = asyncio.Event(), asyncio.Event()
    async def handler(request):
        entered.set(); await release.wait()
        return httpx.Response(200, json={'access_token': 'new', 'expires_in': 3600})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = make_client('Pathao', True, transport); client.token_expiry = 0
        leader = asyncio.create_task(client.get_token()); await entered.wait()
        waiter = asyncio.create_task(client.get_token()); await asyncio.sleep(0); waiter.cancel()
        with pytest.raises(asyncio.CancelledError): await waiter
        release.set(); assert await leader == 'new'
        assert await client.get_token() == 'new'

@pytest.mark.anyio
async def test_async_fastapi_lifespan_dependencies_bound_concurrency():
    from examples.async_fastapi_app import create_app, get_provider
    active = 0; peak = 0; calls = 0
    gate = asyncio.Event(); entered = asyncio.Event()
    async def handler(request):
        nonlocal active, peak, calls
        active += 1; peak = max(peak, active); calls += 1
        if active == 2: entered.set()
        await gate.wait(); active -= 1
        return httpx.Response(200, json=SUCCESS['AlphaSMS'])
    borrowed = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AsyncAlphaSMSClient('synthetic', http_client=borrowed)
    app = create_app(lambda: provider, max_in_flight=2)
    async with app.router.lifespan_context(app):
        assert app.state.sms_provider is provider
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline.invalid') as http:
            tasks = [asyncio.create_task(http.post('/sms', json={'phone': '01700000000', 'message': 'synthetic'})) for _ in range(8)]
            await asyncio.wait_for(entered.wait(), 2)
            assert calls == 2
            gate.set(); responses = await asyncio.gather(*tasks)
            assert all(r.status_code == 202 and r.json()['status'] == 'accepted' for r in responses)
            assert peak == 2 and calls == 8
            assert (await http.post('/sms', json={'phone': '', 'message': 'synthetic'})).status_code == 400
    assert not borrowed.is_closed
    with pytest.raises(jukto.JuktoConfigurationError): await provider.send_sms('01700000000', 'synthetic')
    await borrowed.aclose()

@pytest.mark.anyio
@pytest.mark.parametrize('body', [{'error': 417}, [{'status': 'SENT'}, {'status': 'FAILED'}, {'status': 'opaque'}]])
async def test_async_fastapi_safe_failures(body):
    from examples.async_fastapi_app import create_app
    name = 'AlphaSMS' if isinstance(body, dict) else 'GreenWeb'
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))) as borrowed:
        provider = make_client(name, True, borrowed); app = create_app(lambda: provider)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline.invalid') as http:
                response = await http.post('/sms', json={'phone': '01700000000', 'message': 'synthetic-secret'})
                assert response.status_code == (502 if name == 'AlphaSMS' else 202)
                assert response.json()['status'] == ('failed' if name == 'AlphaSMS' else 'partial')
                assert 'synthetic-secret' not in response.text and '01700000000' not in response.text

@pytest.mark.anyio
async def test_pathao_helpers_stores_and_no_order_replay():
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path.endswith('issue-token'): return httpx.Response(200, json={'access_token': 'new', 'expires_in': 3600})
        if request.method == 'POST': return httpx.Response(401)
        return httpx.Response(200, json={'data': []})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as borrowed:
        client = make_client('Pathao', True, borrowed)
        assert await client._issue_token() == 'new'
        assert await client._refresh_access_token() == 'new'
        assert await client.get_stores() == {'data': []}
        with pytest.raises(jukto.ProviderAuthenticationError): await client.create_order(parcel())
        assert len(requests) == 4

@pytest.mark.anyio
@pytest.mark.parametrize('name', PROVIDERS[3:])
async def test_status_contract_equivalence(name):
    def handler(request):
        body = {'data': {'order_status': 'opaque'}} if name == 'Pathao' else {'status': 200, 'delivery_status': 'opaque'} if name == 'Steadfast' else {'parcel' if '/parcel/info/' in request.url.path else 'tracking': {'status': 'opaque'}}
        return httpx.Response(200, json=body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as sync:
        client = make_client(name, False, sync)
        expected, raw = client.check_shipment_status('id'), client.check_status('id')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as borrowed:
        client = make_client(name, True, borrowed)
        assert await client.check_shipment_status('id') == expected
        assert await client.check_status('id') == raw

@pytest.mark.anyio
@pytest.mark.parametrize('name', PROVIDERS)
async def test_async_logs_and_exception_strings_exclude_sensitive_data(name, caplog):
    import logging
    caplog.set_level(logging.DEBUG, logger='jukto')
    secrets = ('synthetic-secret', '01700000000', 'OTP-654321', 'Synthetic address')
    echo = ' '.join(secrets)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500, text=echo))) as borrowed:
        client = make_client(name, True, borrowed)
        with pytest.raises(jukto.ProviderServerError) as caught:
            if name in PROVIDERS[:3]: await client.send_sms(secrets[1], secrets[2])
            else: await client.create_order(parcel())
        assert all(secret not in caplog.text + str(caught.value) for secret in secrets)
        assert echo in str(caught.value.response_body)  # Explicit sensitive escape hatch.

@pytest.mark.anyio
async def test_owned_pathao_cancelled_auth_context_closes_pool(monkeypatch):
    entered = asyncio.Event(); instances = []; original = httpx.AsyncClient
    async def handler(request):
        entered.set(); await asyncio.Event().wait()
    class OwnedClient(original):
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler), **kwargs); instances.append(self)
    monkeypatch.setattr(httpx, 'AsyncClient', OwnedClient)
    provider = AsyncPathaoClient('id', 'secret', 'user', 'password')
    async def run():
        async with provider: await provider.get_token()
    task = asyncio.create_task(run()); await asyncio.wait_for(entered.wait(), 2); task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert len(instances) == 1 and instances[0].is_closed
    assert provider.access_token is None and provider.refresh_token is None and provider.token_expiry == 0

@pytest.mark.anyio
async def test_pathao_order_replay_requires_explicit_opt_in():
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.path.endswith('issue-token'): return httpx.Response(200, json={'access_token': 'new', 'expires_in': 3600})
        return httpx.Response(401) if len(calls) == 1 else httpx.Response(200, json=SUCCESS['Pathao'])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as borrowed:
        client = make_client('Pathao', True, borrowed, retry_unauthorized_orders=True)
        assert (await client.create_shipment(parcel())).status == jukto.Outcome.ACCEPTED
        assert len(calls) == 3


def test_no_sync_event_loop_bridge():
    import ast
    for path in Path('src/jukto').rglob('*.py'):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ('run_until_complete', 'to_thread'), path
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'asyncio':
                    assert node.func.attr != 'run', path
