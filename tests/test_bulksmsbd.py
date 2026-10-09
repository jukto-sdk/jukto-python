import respx
import httpx
import pytest
from jukto import (
    BulkSMSBDClient,
    ProviderAuthenticationError,
    InsufficientBalanceError,
    InvalidRequestError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderError,
)


@pytest.fixture
def bulksmsbd_client() -> BulkSMSBDClient:
    return BulkSMSBDClient(api_key="mock_bsms_key", sender_id="FEATHER_IT")


@respx.mock
def test_bulksmsbd_send_sms_success(bulksmsbd_client: BulkSMSBDClient):
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"response_code": 202, "message": "Success", "success_message": "Submitted"},
        )
    )

    resp = bulksmsbd_client.send_sms(["01711112222", "01822223333"], "Test")
    assert resp["response_code"] == 202


@respx.mock
def test_bulksmsbd_auth_errors(bulksmsbd_client: BulkSMSBDClient):
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"response_code": 1002, "error_message": "Invalid API Key"},
        )
    )
    with pytest.raises(ProviderAuthenticationError):
        bulksmsbd_client.send_sms("01711112222", "Test")


@respx.mock
def test_bulksmsbd_balance_errors(bulksmsbd_client: BulkSMSBDClient):
    # 1003
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"response_code": 1003, "error_message": "Insufficient Balance"},
        )
    )
    with pytest.raises(InsufficientBalanceError):
        bulksmsbd_client.send_sms("01711112222", "Test")

    # 1007 with balance
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"response_code": 1007, "error_message": "Account balance is too low"},
        )
    )
    with pytest.raises(InsufficientBalanceError):
        bulksmsbd_client.send_sms("01711112222", "Test")

    # 1007 with no balance mention
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"response_code": 1007, "error_message": "Unauthorized access"},
        )
    )
    with pytest.raises(ProviderAuthenticationError):
        bulksmsbd_client.send_sms("01711112222", "Test")


@respx.mock
def test_bulksmsbd_invalid_request(bulksmsbd_client: BulkSMSBDClient):
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"response_code": 1005, "error_message": "Invalid Mobile Number"},
        )
    )
    with pytest.raises(InvalidRequestError):
        bulksmsbd_client.send_sms("123", "Test")

    # Other error code
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"response_code": 1099, "error_message": "Unknown code"},
        )
    )
    with pytest.raises(ProviderError):
        bulksmsbd_client.send_sms("01711112222", "Test")
        
@respx.mock
def test_bulksmsbd_non_dict_data(bulksmsbd_client: BulkSMSBDClient):
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(200, json=["unexpected", "list"])
    )
    resp = bulksmsbd_client.send_sms("01711112222", "Test")
    assert resp == {"data": ["unexpected", "list"]}


@respx.mock
def test_bulksmsbd_http_errors(bulksmsbd_client: BulkSMSBDClient):
    # 401
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    with pytest.raises(ProviderAuthenticationError):
        bulksmsbd_client.send_sms("01711112222", "Test")

    # 429
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(429, text="Rate Limit")
    )
    with pytest.raises(ProviderRateLimitError):
        bulksmsbd_client.send_sms("01711112222", "Test")

    # 400
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(400, text="Bad Request")
    )
    with pytest.raises(InvalidRequestError):
        bulksmsbd_client.send_sms("01711112222", "Test")

    # 500
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(500, text="Server Error")
    )
    with pytest.raises(ProviderServerError):
        bulksmsbd_client.send_sms("01711112222", "Test")

    # 418
    respx.post(bulksmsbd_client.base_url).mock(
        return_value=httpx.Response(418, text="Teapot")
    )
    with pytest.raises(ProviderError):
        bulksmsbd_client.send_sms("01711112222", "Test")


@respx.mock
def test_bulksmsbd_timeout_and_network_error(bulksmsbd_client: BulkSMSBDClient):
    respx.post(bulksmsbd_client.base_url).mock(
        side_effect=httpx.TimeoutException("Timeout")
    )
    with pytest.raises(ProviderTimeoutError):
        bulksmsbd_client.send_sms("01711112222", "Test")

    respx.post(bulksmsbd_client.base_url).mock(
        side_effect=httpx.NetworkError("Network error")
    )
    with pytest.raises(ProviderConnectionError):
        bulksmsbd_client.send_sms("01711112222", "Test")
