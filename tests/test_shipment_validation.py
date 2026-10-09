"""Offline SDK input-policy tests; provider evidence recorded separately."""
from dataclasses import replace
from unittest.mock import patch
import json
import math
import pytest
import respx
import httpx
from jukto import Parcel, PathaoClient, RedXClient, SteadfastClient, JuktoValidationError


@pytest.fixture(params=['Pathao','RedX','Steadfast'])
def provider(request):
    if request.param == 'Pathao':
        return PathaoClient('id','secret','user','password',store_id=123)
    if request.param == 'RedX':
        return RedXClient('key')
    return SteadfastClient('key','secret')


@pytest.mark.parametrize('field,value', [
    ('recipient_name',' '),('recipient_phone',None),('recipient_address',''),
    ('invoice_id',42),('item_quantity',0),('item_quantity',True),('item_quantity',1.5),
    ('item_weight',0),('item_weight',-1),('item_weight',float('nan')),
    ('item_weight',float('inf')),('item_weight',True),('cod_amount',-1),
    ('cod_amount',float('nan')),('cod_amount',float('inf')),('cod_amount',True),
])
def test_invalid_input_never_opens_transport(provider,sample_parcel,field,value):
    parcel=replace(sample_parcel,**{field:value})
    with patch('httpx.Client') as transport:
        with pytest.raises(JuktoValidationError):
            provider.create_order(parcel)
        transport.assert_not_called()


@pytest.mark.parametrize('field,value',[('recipient_city',0),('recipient_zone',True),('recipient_area','1'),('store_id',0)])
def test_pathao_invalid_id_does_not_use_defaults(sample_parcel,field,value):
    c=PathaoClient('id','secret','user','password',store_id=123)
    with patch('httpx.Client') as transport:
        with pytest.raises(JuktoValidationError):
            c.create_order(replace(sample_parcel,**{field:value}))
        transport.assert_not_called()


@respx.mock
def test_pathao_omits_missing_geography_and_preserves_explicit_ids(sample_parcel):
    c=PathaoClient('id','secret','user','password',store_id=123)
    respx.post(c.base_url+'/aladdin/api/v1/issue-token').respond(200,json={'access_token':'token','expires_in':3600})
    route=respx.post(c.base_url+'/aladdin/api/v1/orders').respond(200,json={'data':{'consignment_id':'id'}})
    c.create_order(sample_parcel)
    payload=json.loads(route.calls.last.request.content)
    assert not {'recipient_city','recipient_zone','recipient_area'} & payload.keys()
    c.create_order(replace(sample_parcel,recipient_city=12,recipient_zone=23,recipient_area=34))
    payload=json.loads(route.calls.last.request.content)
    assert [payload[f'recipient_{x}'] for x in ['city','zone','area']] == [12,23,34]
    assert payload['item_weight']==0.5 and payload['item_quantity']==1


@pytest.mark.parametrize('field', ['client_id','client_secret','username','password'])
def test_pathao_blank_configuration_rejected_before_auth(field,sample_parcel):
    c=PathaoClient('id','secret','user','password',store_id=123)
    setattr(c,field,' ')
    with patch('httpx.Client') as transport:
        with pytest.raises(JuktoValidationError): c.create_order(sample_parcel)
        transport.assert_not_called()


@pytest.mark.parametrize('field,value',[
    ('declared_value',None),('declared_value',-1),('declared_value',float('nan')),
    ('redx_delivery_area',None),('redx_delivery_area',' '),
    ('redx_delivery_area_id',None),('redx_delivery_area_id',False),
    ('redx_pickup_store_id',0),('item_weight',0.0001),
])
def test_redx_requires_independent_value_and_routing(sample_parcel,field,value):
    c=RedXClient('key')
    with patch('httpx.Client') as transport:
        with pytest.raises(JuktoValidationError): c.create_order(replace(sample_parcel,**{field:value}))
        transport.assert_not_called()


@respx.mock
def test_redx_prepaid_payload_separates_value_and_provider_geography(sample_parcel):
    c=RedXClient('key')
    route=respx.post(c.base_url+'/parcel').respond(200,json={'tracking_id':'id'})
    c.create_order(replace(sample_parcel,cod_amount=0,declared_value=1200,redx_pickup_store_id=45,
                           recipient_city=99,recipient_zone=98,recipient_area=97,item_weight=0.75))
    payload=json.loads(route.calls.last.request.content)
    assert payload == {
        'customer_name':sample_parcel.recipient_name,'customer_phone':sample_parcel.recipient_phone,
        'customer_address':sample_parcel.recipient_address,'delivery_area':'Banani','delivery_area_id':12,
        'merchant_invoice_id':sample_parcel.invoice_id,'cash_collection_amount':0,
        'parcel_weight':750,'instruction':sample_parcel.note,'value':1200,'pickup_store_id':45,
    }
    assert route.calls.last.request.headers['API-ACCESS-TOKEN']=='Bearer key'


@pytest.mark.parametrize('kind',['RedX','Steadfast'])
def test_empty_provider_key_never_sends(kind,sample_parcel):
    c=RedXClient(' ') if kind=='RedX' else SteadfastClient('key',' ')
    with patch('httpx.Client') as transport:
        with pytest.raises(JuktoValidationError): c.create_order(sample_parcel)
        transport.assert_not_called()


@pytest.mark.parametrize('field,value', [('note',42),('item_weight',10**400),('declared_value',True)])
def test_nonserializable_or_overflowing_values_fail_before_http(provider,sample_parcel,field,value):
    with patch('httpx.Client') as transport:
        with pytest.raises(JuktoValidationError): provider.create_order(replace(sample_parcel,**{field:value}))
        transport.assert_not_called()


@respx.mock
def test_redx_wire_fields_follow_recorded_primary_evidence(sample_parcel):
    from pathlib import Path
    contract=json.loads((Path(__file__).parent/'fixtures/shipment_contracts.json').read_text())['redx']
    c=RedXClient('key')
    route=respx.post(c.base_url+contract['create_endpoint']).respond(200,json={'tracking_id':'id'})
    c.create_order(sample_parcel)
    assert set(contract['required_fields']) <= json.loads(route.calls.last.request.content).keys()
    assert route.calls.last.request.headers[contract['authentication_header']]=='Bearer key'


@respx.mock
def test_redx_exact_gram_conversion_does_not_depend_on_float_multiplication(sample_parcel):
    c=RedXClient('key')
    route=respx.post(c.base_url+'/parcel').respond(200,json={'tracking_id':'id'})
    c.create_order(replace(sample_parcel,item_weight=1.001))
    assert json.loads(route.calls.last.request.content)['parcel_weight']==1001
