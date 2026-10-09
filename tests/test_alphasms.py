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
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderError,
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
def test_alphasms_auth_errors(alphasms_client: AlphaSMSClient):
    # 401
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"error": 401, "msg": "Invalid API Key"},
        )
    )
    with pytest.raises(ProviderAuthenticationError) as exc_info:
        alphasms_client.send_sms("01711112222", "Test")
    assert exc_info.value.provider == "AlphaSMS"

    # 403
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"error": 403, "msg": "Forbidden"},
        )
    )
    with pytest.raises(ProviderAuthenticationError):
        alphasms_client.send_sms("01711112222", "Test")


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
def test_alphasms_other_error_code(alphasms_client: AlphaSMSClient):
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"error": 999, "msg": "Gateway Error"},
        )
    )

    with pytest.raises(ProviderError):
        alphasms_client.send_sms("01711112222", "Test")


@respx.mock
def test_alphasms_non_dict_data(alphasms_client: AlphaSMSClient):
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(200, json=["unexpected", "list"])
    )
    resp = alphasms_client.send_sms("01711112222", "Test")
    assert resp == {"data": ["unexpected", "list"]}


@respx.mock
def test_alphasms_http_status_errors(alphasms_client: AlphaSMSClient):
    # 401
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    with pytest.raises(ProviderAuthenticationError):
        alphasms_client.send_sms("01711112222", "Test")

    # 429
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(429, text="Rate limit")
    )
    with pytest.raises(ProviderRateLimitError):
        alphasms_client.send_sms("01711112222", "Test")

    # 422
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(422, text="Unprocessable")
    )
    with pytest.raises(InvalidRequestError):
        alphasms_client.send_sms("01711112222", "Test")

    # 500
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )
    with pytest.raises(ProviderServerError):
        alphasms_client.send_sms("01711112222", "Test")

    # 418
    respx.post(alphasms_client.base_url).mock(
        return_value=httpx.Response(418, text="Teapot")
    )
    with pytest.raises(ProviderError):
        alphasms_client.send_sms("01711112222", "Test")


@respx.mock
def test_alphasms_timeout_and_network_error(alphasms_client: AlphaSMSClient):
    respx.post(alphasms_client.base_url).mock(
        side_effect=httpx.TimeoutException("Connection timed out")
    )
    with pytest.raises(ProviderTimeoutError):
        alphasms_client.send_sms("01711112222", "Test")

    respx.post(alphasms_client.base_url).mock(
        side_effect=httpx.NetworkError("Network failed")
    )
    with pytest.raises(ProviderConnectionError):
        alphasms_client.send_sms("01711112222", "Test")
