"""Offline ownership, reuse and lifecycle tests for all adapters."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import httpx
import pytest
from jukto import AlphaSMSClient, BulkSMSBDClient, GreenWebClient, PathaoClient, RedXClient, SteadfastClient, JuktoConfigurationError, ProviderTimeoutError

FACTORIES = [AlphaSMSClient, BulkSMSBDClient, GreenWebClient, PathaoClient, RedXClient, SteadfastClient]

def make(factory, **kwargs):
    args = {BulkSMSBDClient:('key','sender'),PathaoClient:('id','secret','user','password'),SteadfastClient:('key','secret')}.get(factory,('key',))
    return factory(*args,base_url='https://provider.test',**kwargs)

def handler(request):
    if request.url.path.endswith('issue-token'):
        return httpx.Response(200,json={'access_token':'token','expires_in':3600})
    return httpx.Response(200,json={'error':0,'data':{'request_id':1,'consignment_id':'id'},'response_code':202,'status':200,'consignment':{'consignment_id':1},'tracking_id':'id'})

def invoke(c,parcel):
    if isinstance(c,(AlphaSMSClient,BulkSMSBDClient,GreenWebClient)):
        return c.send_sms('01700000000','offline message')
    return c.create_order(parcel)

def response_for(factory,request):
    return httpx.Response(200,json=[{'status':'SENT'}]) if factory is GreenWebClient else handler(request)

@pytest.mark.parametrize('factory',FACTORIES)
def test_owned_client_reused_and_closed_once(factory,sample_parcel):
    real_client=httpx.Client
    created=[]
    def build(**kwargs):
        c=real_client(transport=httpx.MockTransport(lambda r: response_for(factory,r)),**kwargs)
        created.append(c)
        return c
    with patch('jukto._transport.httpx.Client',side_effect=build):
        c=make(factory)
        invoke(c,sample_parcel)
        invoke(c,sample_parcel)
        assert len(created)==1 and not created[0].is_closed
        c.close()
        c.close()
        assert created[0].is_closed
        with pytest.raises(JuktoConfigurationError): invoke(c,sample_parcel)
        assert len(created)==1

@pytest.mark.parametrize('factory',FACTORIES)
def test_borrowed_client_survives_provider_context(factory,sample_parcel):
    requests=[]
    def respond(request):
        requests.append(request)
        return response_for(factory,request)
    with httpx.Client(transport=httpx.MockTransport(respond),follow_redirects=True) as borrowed:
        with make(factory,http_client=borrowed,timeout=httpx.Timeout(8,connect=2)) as c:
            invoke(c,sample_parcel)
            invoke(c,sample_parcel)
        assert not borrowed.is_closed
        borrowed.get('https://provider.test/independent')
        assert requests[0].extensions['timeout']['connect']==2
        with pytest.raises(JuktoConfigurationError): invoke(c,sample_parcel)

@pytest.mark.parametrize('factory',FACTORIES)
def test_context_closes_owned_client_on_exception(factory,sample_parcel):
    real_client=httpx.Client
    created=[]
    def build(**kwargs):
        c=real_client(transport=httpx.MockTransport(lambda r:response_for(factory,r)),**kwargs)
        created.append(c)
        return c
    with patch('jukto._transport.httpx.Client',side_effect=build):
        with pytest.raises(ValueError):
            with make(factory) as c:
                invoke(c,sample_parcel)
                raise ValueError('application error')
    assert created[0].is_closed

@pytest.mark.parametrize('factory',FACTORIES)
def test_mutating_operations_do_not_retry_timeouts(factory,sample_parcel):
    calls=[]
    def timeout(request):
        if request.url.path.endswith('issue-token'): return handler(request)
        calls.append(request)
        raise httpx.ReadTimeout('offline',request=request)
    with httpx.Client(transport=httpx.MockTransport(timeout)) as borrowed:
        with make(factory,http_client=borrowed) as c:
            with pytest.raises(ProviderTimeoutError): invoke(c,sample_parcel)
        assert len(calls)==1


def test_pool_options_reach_owned_client(sample_parcel):
    real_client=httpx.Client
    limits=httpx.Limits(max_connections=7,max_keepalive_connections=3,keepalive_expiry=9)
    with patch('jukto._transport.httpx.Client',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw)) as build:
        with make(SteadfastClient,limits=limits,timeout=httpx.Timeout(10,read=4)) as c:
            invoke(c,sample_parcel)
        assert build.call_args.kwargs['limits'] is limits
        assert build.call_args.kwargs['verify'] is True
        assert build.call_args.kwargs['follow_redirects'] is False


def test_lazy_initialization_single_flight(sample_parcel):
    real_client=httpx.Client
    created=[]
    def build(**kwargs):
        c=real_client(transport=httpx.MockTransport(handler),**kwargs)
        created.append(c)
        return c
    with patch('jukto._transport.httpx.Client',side_effect=build):
        with make(SteadfastClient) as c:
            with ThreadPoolExecutor(8) as pool:
                list(pool.map(lambda _:invoke(c,sample_parcel),range(8)))
        assert len(created)==1 and created[0].is_closed


@pytest.mark.parametrize('factory',FACTORIES)
def test_close_before_first_request_does_not_allocate(factory,sample_parcel):
    with patch('jukto._transport.httpx.Client') as build:
        c=make(factory)
        c.close()
        with pytest.raises(JuktoConfigurationError): invoke(c,sample_parcel)
        with pytest.raises(JuktoConfigurationError): c.__enter__()
        build.assert_not_called()


@pytest.mark.parametrize('factory',FACTORIES)
def test_borrowed_redirect_policy_overrides_client_default(factory,sample_parcel):
    calls=[]
    def redirect(request):
        calls.append(request)
        if request.url.path.endswith('issue-token'): return handler(request)
        return httpx.Response(307,headers={'Location':'https://attacker.test'})
    from jukto import ProviderError
    with httpx.Client(transport=httpx.MockTransport(redirect),follow_redirects=True) as borrowed:
        with make(factory,http_client=borrowed) as c:
            with pytest.raises(ProviderError): invoke(c,sample_parcel)
        assert all(r.url.host=='provider.test' for r in calls)


def test_borrowed_auth_defaults_do_not_replace_provider_token(sample_parcel):
    requests=[]
    def respond(request):
        requests.append(request)
        return handler(request)
    with httpx.Client(transport=httpx.MockTransport(respond),auth=('other','credentials')) as borrowed:
        with make(PathaoClient,http_client=borrowed) as c:
            invoke(c,sample_parcel)
        assert 'Authorization' not in requests[0].headers
        assert requests[1].headers['Authorization']=='Bearer token'


@pytest.mark.parametrize('kwargs',[{'http_client':object()},{'limits':object()}])
def test_invalid_injection_configuration_is_explicit(kwargs):
    with pytest.raises(JuktoConfigurationError): make(SteadfastClient,**kwargs)


def test_pool_limits_cannot_silently_override_borrowed_pool():
    with httpx.Client(transport=httpx.MockTransport(handler)) as borrowed:
        with pytest.raises(JuktoConfigurationError):
            make(SteadfastClient,http_client=borrowed,limits=httpx.Limits(max_connections=1))
        assert not borrowed.is_closed


def test_externally_closed_borrowed_client_is_rejected(sample_parcel):
    borrowed=httpx.Client(transport=httpx.MockTransport(handler))
    c=make(SteadfastClient,http_client=borrowed)
    borrowed.close()
    with pytest.raises(JuktoConfigurationError): invoke(c,sample_parcel)
    c.close()
