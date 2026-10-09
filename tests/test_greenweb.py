import respx
import httpx
import pytest
from jukto import (
    GreenWebClient,
    ProviderAuthenticationError,
    InsufficientBalanceError,
    InvalidRequestError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderError,
    ProviderRateLimitError,
)


@respx.mock
def test_greenweb_send_sms_success_list(greenweb_client: GreenWebClient):
    respx.post(greenweb_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json=[{"to": "01711112222", "status": "SENT", "msgid": "123456"}],
        )
    )

    result = greenweb_client.send_sms(["01711112222", "01811112222"], "Hello BD")
    assert isinstance(result, list)
    assert result[0]["status"] == "SENT"


@respx.mock
def test_greenweb_invalid_token_text(greenweb_client: GreenWebClient):
    respx.post(greenweb_client.base_url).mock(
        return_value=httpx.Response(200, text="Invalid Token")
    )

    with pytest.raises(ProviderAuthenticationError) as exc_info:
        greenweb_client.send_sms("01711112222", "Test")

    assert exc_info.value.provider == "GreenWeb"


@respx.mock
def test_greenweb_insufficient_balance_text(greenweb_client: GreenWebClient):
    respx.post(greenweb_client.base_url).mock(
        return_value=httpx.Response(200, text="SMS rate is greater than your account balance")
    )

    with pytest.raises(InsufficientBalanceError):
        greenweb_client.send_sms("01711112222", "Test")


@respx.mock
def test_greenweb_invalid_number_text(greenweb_client: GreenWebClient):
    respx.post(greenweb_client.base_url).mock(
        return_value=httpx.Response(200, text="Invalid Number")
    )

    with pytest.raises(InvalidRequestError):
        greenweb_client.send_sms("123", "Test")


@respx.mock
def test_greenweb_json_error_status(greenweb_client: GreenWebClient):
    # Test JSON list with error status
    respx.post(greenweb_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json=[{"status": "error", "message": "Sender ID not permitted"}],
        )
    )

    with pytest.raises(ProviderError):
        greenweb_client.send_sms("01711112222", "Test")


@respx.mock
def test_greenweb_json_dict_error_status(greenweb_client: GreenWebClient):
    # Test JSON dict with error status
    respx.post(greenweb_client.base_url).mock(
        return_value=httpx.Response(
            200,
            json={"status": "error", "message": "System Maintenance"},
        )
    )

    with pytest.raises(ProviderError):
        greenweb_client.send_sms("01711112222", "Test")


@respx.mock
def test_greenweb_http_status_errors(greenweb_client: GreenWebClient):
    # 401
    respx.post(greenweb_client.base_url).mock(
        return_value=httpx.Response(401, text="Unauthorized token")
    )
    with pytest.raises(ProviderAuthenticationError):
        greenweb_client.send_sms("01711112222", "Test")

    # 429
    respx.post(greenweb_client.base_url).mock(
        return_value=httpx.Response(429, text="Rate limit exceeded")
    )
    with pytest.raises(ProviderRateLimitError):
        greenweb_client.send_sms("01711112222", "Test")


@respx.mock
def test_greenweb_server_error_500(greenweb_client: GreenWebClient):
    respx.post(greenweb_client.base_url).mock(
        return_value=httpx.Response(502, text="Bad Gateway")
    )

    with pytest.raises(ProviderServerError):
        greenweb_client.send_sms("01711112222", "Test")


@respx.mock
def test_greenweb_timeout(greenweb_client: GreenWebClient):
    respx.post(greenweb_client.base_url).mock(
        side_effect=httpx.TimeoutException("Connect timed out")
    )

    with pytest.raises(ProviderTimeoutError):
        greenweb_client.send_sms("01711112222", "Test")
