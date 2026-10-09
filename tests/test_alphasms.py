import respx
import httpx
import pytest
from jukto import (
    AlphaSMSClient,
    ProviderAuthenticationError,
    InsufficientBalanceError,
    InvalidRequestError,
    ProviderServerError,
    ProviderTimeoutError,
)


@respx.mock
def test_alphasms_success(alphasms_client: AlphaSMSClient):
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "error": 0,
                "msg": "Request submitted",
                "data": [{"request_id": 99881}],
            },
        )
    )

    resp = alphasms_client.send_sms(["01711112222", "01822223333"], "Test message")
    assert resp["error"] == 0
    assert resp["data"][0]["request_id"] == 99881


@respx.mock
def test_alphasms_auth_error(alphasms_client: AlphaSMSClient):
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"error": 401, "msg": "Invalid API Key"},
        )
    )

    with pytest.raises(ProviderAuthenticationError) as exc_info:
        alphasms_client.send_sms("01711112222", "Test")

    assert exc_info.value.provider == "AlphaSMS"


@respx.mock
def test_alphasms_balance_error(alphasms_client: AlphaSMSClient):
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"error": 402, "msg": "Insufficient balance in account"},
        )
    )

    with pytest.raises(InsufficientBalanceError):
        alphasms_client.send_sms("01711112222", "Test")


@respx.mock
def test_alphasms_invalid_number_error(alphasms_client: AlphaSMSClient):
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"error": 405, "msg": "Invalid mobile number"},
        )
    )

    with pytest.raises(InvalidRequestError):
        alphasms_client.send_sms("invalid_number", "Test")


@respx.mock
def test_alphasms_http_500(alphasms_client: AlphaSMSClient):
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    with pytest.raises(ProviderServerError):
        alphasms_client.send_sms("01711112222", "Test")


@respx.mock
def test_alphasms_timeout(alphasms_client: AlphaSMSClient):
    respx.post(alphasms_client.base_url).mock(
        side_effect=httpx.TimeoutException("Connection timed out")
    )

    with pytest.raises(ProviderTimeoutError):
        alphasms_client.send_sms("01711112222", "Test")
