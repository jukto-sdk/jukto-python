"""Typed-contract regressions; fixtures are synthetic, evidence is documented."""
from decimal import Decimal
import httpx
import pytest
import respx
import jukto

@pytest.mark.parametrize('factory,payload',[
    (lambda:jukto.PathaoClient('id','secret','user','password'),{'data':{'consignment_id':'P1'}}),
    (lambda:jukto.RedXClient('key'),{'tracking_id':'R1'}),
    (lambda:jukto.SteadfastClient('key','secret'),{'status':200,'consignment':{'consignment_id':42}}),
])
@respx.mock
def test_one_shipment_consumer_without_provider_dict_indexing(factory,payload,sample_parcel):
    c=factory()
    respx.post(c.base_url+'/aladdin/api/v1/issue-token').respond(200,json={'access_token':'token','expires_in':3600})
    respx.route().respond(200,json=payload)
    result=c.create_shipment(sample_parcel)
    assert isinstance(result,jukto.ShipmentCreationResult)
    assert result.provider_id in ('P1','R1','42')
    assert result.raw==payload
    assert result.status in (jukto.Outcome.ACCEPTED,jukto.Outcome.UNKNOWN)
    c.close()

@respx.mock
def test_unknown_shipment_status_is_preserved():
    with jukto.SteadfastClient('key','secret') as c:
        respx.route().respond(200,json={'status':200,'delivery_status':'future-provider-state'})
        result=c.check_shipment_status('id')
    assert result.status==jukto.Outcome.UNKNOWN
    assert result.provider_status=='future-provider-state'

@respx.mock
def test_sms_submission_is_not_delivery():
    with jukto.AlphaSMSClient('key') as c:
        respx.route().respond(200,json={'error':0,'data':{'request_id':123}})
        result=c.submit_sms('01700000000','offline')
    assert result.status==jukto.Outcome.ACCEPTED
    assert result.request_id=='123'
    assert result.recipients==()

@respx.mock
def test_greenweb_partial_typed_outcomes_preserve_unknowns():
    payload=[{'to':'01700000000','status':'SENT'},{'to':'01800000000','status':'FAILED'},{'status':'future'}]
    with jukto.GreenWebClient('key') as c:
        respx.route().respond(200,json=payload)
        with pytest.raises(jukto.SMSBatchError) as caught: c.submit_sms('01700000000,01800000000','offline')
    result=caught.value.normalized_result
    assert result.status==jukto.Outcome.PARTIAL
    assert [r.status for r in result.recipients]==[jukto.Outcome.ACCEPTED,jukto.Outcome.FAILED,jukto.Outcome.UNKNOWN]
    assert result.raw==payload

@respx.mock
def test_http_and_provider_codes_are_distinct_and_metadata_is_not_printed():
    with jukto.AlphaSMSClient('key') as c:
        respx.route().respond(200,json={'error':417},headers={'X-Request-ID':'private-id','Retry-After':'12'})
        with pytest.raises(jukto.InsufficientBalanceError) as caught:c.send_sms('01700000000','offline')
    e=caught.value
    assert e.status_code==417 and e.http_status==200 and e.provider_error_code==417
    assert e.request_id=='private-id' and e.retry_after=='12'
    assert 'private-id' not in str(e)+repr(e)

@respx.mock
def test_sms_timeout_is_an_ambiguous_side_effect():
    with jukto.AlphaSMSClient('key') as c:
        respx.route().mock(side_effect=httpx.ReadTimeout('offline'))
        with pytest.raises(jukto.ProviderTimeoutError) as caught:c.submit_sms('01700000000','offline')
    assert caught.value.outcome==jukto.Outcome.UNKNOWN
    assert caught.value.reconciliation_required
    assert caught.value.http_status is None

@respx.mock
def test_exact_decimal_redx_money_is_not_rounded(sample_parcel):
    sample_parcel.cod_amount=Decimal('0.100000000000000001')
    sample_parcel.declared_value=Decimal('1200.000000000000000001')
    with jukto.RedXClient('key') as c:
        route=respx.route().respond(200,json={'tracking_id':'id'})
        c.create_order(sample_parcel)
    import json
    payload=json.loads(route.calls.last.request.content)
    assert payload['cash_collection_amount']=='0.100000000000000001'
    assert payload['value']=='1200.000000000000000001'

@respx.mock
def test_redx_typed_status_uses_documented_info_contract():
    with jukto.RedXClient('key') as c:
        route=respx.get(c.base_url+'/parcel/info/id').respond(200,json={'parcel':{'tracking_id':'id','status':'future'}})
        result=c.check_shipment_status('id')
    assert route.called and result.provider_status=='future'
    assert result.status==jukto.Outcome.UNKNOWN

@respx.mock
def test_provider_options_are_scoped_and_override_legacy_values(sample_parcel):
    sample_parcel.redx_options=jukto.RedXOptions('RedX area',22,33)
    sample_parcel.pathao_options=jukto.PathaoOptions(store_id=44,recipient_city=55)
    with jukto.RedXClient('key') as c:
        route=respx.route().respond(200,json={'tracking_id':'id'})
        c.create_shipment(sample_parcel)
    import json
    data=json.loads(route.calls.last.request.content)
    assert data['delivery_area']=='RedX area' and data['delivery_area_id']==22 and data['pickup_store_id']==33
    assert 'recipient_city' not in data
    assert c.capabilities.declared_value
    assert not jukto.AlphaSMSClient('key').capabilities.per_recipient_submission

@pytest.mark.parametrize('factory',[lambda:jukto.PathaoClient('id','secret','user','password',store_id=123),lambda:jukto.SteadfastClient('key','secret')])
def test_unverified_fractional_decimal_serialization_fails_before_http(factory,sample_parcel):
    sample_parcel.cod_amount=Decimal('0.1')
    from unittest.mock import patch
    with factory() as c, patch('httpx.Client') as client:
        with pytest.raises(jukto.JuktoValidationError):c.create_shipment(sample_parcel)
        client.assert_not_called()

@respx.mock
def test_malformed_creation_requires_reconciliation(sample_parcel):
    with jukto.SteadfastClient('key','secret') as c:
        respx.route().respond(200,text='<html>unknown</html>')
        with pytest.raises(jukto.UnexpectedProviderResponseError) as caught:c.create_shipment(sample_parcel)
    assert caught.value.http_status==200
    assert caught.value.reconciliation_required and caught.value.outcome==jukto.Outcome.UNKNOWN

@respx.mock
def test_final_retry_metadata_does_not_keep_original_401():
    with jukto.PathaoClient('id','secret','user','password') as c:
        respx.post(c.base_url+'/aladdin/api/v1/issue-token').respond(200,json={'access_token':'token','expires_in':3600})
        respx.get(c.base_url+'/aladdin/api/v1/stores').mock(side_effect=[httpx.Response(401,headers={'X-Request-ID':'old'}),httpx.Response(500,headers={'X-Request-ID':'final'})])
        with pytest.raises(jukto.ProviderServerError) as caught:c.get_stores()
    assert caught.value.http_status==500 and caught.value.request_id=='final'
    assert not caught.value.reconciliation_required

@respx.mock
def test_documented_rejection_is_failed_not_ambiguous():
    with jukto.AlphaSMSClient('key') as c:
        respx.route().respond(200,json={'error':417})
        with pytest.raises(jukto.InsufficientBalanceError) as caught:c.submit_sms('01700000000','offline')
    assert caught.value.outcome==jukto.Outcome.FAILED
    assert not caught.value.reconciliation_required

@respx.mock
def test_unverified_bulk_success_remains_unknown():
    with jukto.BulkSMSBDClient('key','sender',base_url='https://provider.test') as c:
        respx.route().respond(200,json={'response_code':202})
        result=c.submit_sms('01700000000','offline')
    assert result.status==jukto.Outcome.UNKNOWN
    assert result.provider_status==202

@respx.mock
def test_pathao_options_and_decimal_integer_payload(sample_parcel):
    sample_parcel.pathao_options=jukto.PathaoOptions(store_id=44,recipient_city=55)
    sample_parcel.cod_amount=Decimal('10000000000000000001')
    with jukto.PathaoClient('id','secret','user','password') as c:
        respx.post(c.base_url+'/aladdin/api/v1/issue-token').respond(200,json={'access_token':'token','expires_in':3600})
        route=respx.post(c.base_url+'/aladdin/api/v1/orders').respond(200,json={'data':{'consignment_id':'id'}})
        result=c.create_shipment(sample_parcel)
    import json
    payload=json.loads(route.calls.last.request.content)
    assert payload['store_id']==44 and payload['recipient_city']==55
    assert 'recipient_zone' not in payload and payload['amount_to_collect']==10000000000000000001
    assert result.status==jukto.Outcome.ACCEPTED

@respx.mock
def test_request_metadata_is_isolated_between_threads():
    from concurrent.futures import ThreadPoolExecutor
    def response(request):
        body=request.content.decode()
        marker='first' if 'first' in body else 'second'
        return httpx.Response(429,headers={'X-Request-ID':marker,'Retry-After':'5'},json={})
    with jukto.AlphaSMSClient('key') as c:
        respx.route().mock(side_effect=response)
        def call(marker):
            try:c.submit_sms('01700000000',marker)
            except jukto.ProviderRateLimitError as e:return e.request_id
        with ThreadPoolExecutor(2) as pool:
            assert list(pool.map(call,['first','second']))==['first','second']

@respx.mock
def test_no_response_final_retry_clears_metadata():
    with jukto.PathaoClient('id','secret','user','password') as c:
        respx.post(c.base_url+'/aladdin/api/v1/issue-token').respond(200,json={'access_token':'token','expires_in':3600})
        respx.get(c.base_url+'/aladdin/api/v1/stores').mock(side_effect=[httpx.Response(401,headers={'X-Request-ID':'old'}),httpx.ReadTimeout('offline')])
        with pytest.raises(jukto.ProviderTimeoutError) as caught:c.get_stores()
    assert caught.value.http_status is None and caught.value.request_id is None

@respx.mock
def test_raw_method_compatibility_and_typed_batch_view():
    with jukto.GreenWebClient('key') as c:
        respx.route().respond(200,json=[{'status':'SENT','to':'01700000000'}])
        raw=c.send_sms('01700000000','offline')
    assert isinstance(raw,list)
    assert raw.normalized.status==jukto.Outcome.ACCEPTED
    assert raw.normalized.recipients[0].response_index==0
    assert '01700000000' not in repr(raw.normalized)

@pytest.mark.parametrize('status,normalized',[('SENT','accepted'),('FAILED','failed'),('future-status','unknown')])
def test_recorded_greenweb_semantics(status,normalized):
    from jukto.results import sms_submission
    from pathlib import Path
    import json
    evidence=json.loads((Path(__file__).parent/'fixtures/result_contracts.json').read_text())
    assert {'provider_status':status,'normalized':normalized} in evidence['greenweb']
    result=sms_submission('GreenWeb',[{'status':status}])
    assert result.recipients[0].status.value==normalized

@respx.mock
def test_unknown_creation_id_never_claims_acceptance(sample_parcel):
    with jukto.PathaoClient('id','secret','user','password') as c:
        respx.post(c.base_url+'/aladdin/api/v1/issue-token').respond(200,json={'access_token':'token','expires_in':3600})
        respx.post(c.base_url+'/aladdin/api/v1/orders').respond(200,json={'data':{'consignment_id':True}})
        result=c.create_shipment(sample_parcel)
    assert result.provider_id is None and result.status==jukto.Outcome.UNKNOWN
    assert result.reconciliation_required

@respx.mock
def test_pathao_polling_status_vocabulary_remains_unknown():
    with jukto.PathaoClient('id','secret','user','password') as c:
        respx.post(c.base_url+'/aladdin/api/v1/issue-token').respond(200,json={'access_token':'token','expires_in':3600})
        respx.get(c.base_url+'/aladdin/api/v1/orders/id/info').respond(200,json={'data':{'order_status':'Delivered'}})
        result=c.check_shipment_status('id')
    assert result.status==jukto.Outcome.UNKNOWN and result.provider_status=='Delivered'

@respx.mock
def test_server_http_status_overrides_embedded_rejection_for_ambiguity():
    with jukto.AlphaSMSClient('key') as c:
        respx.route().respond(500,json={'error':417})
        with pytest.raises(jukto.ProviderServerError) as caught:c.submit_sms('01700000000','offline')
    assert caught.value.http_status==500
    assert caught.value.provider_error_code==417
    assert caught.value.outcome==jukto.Outcome.UNKNOWN
    assert caught.value.reconciliation_required
