import respx
import httpx
import pytest
from jukto import (
    RedXClient,
    Parcel,
    ProviderAuthenticationError,
    InvalidRequestError,
    ResourceNotFoundError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderError,
)


@pytest.fixture
def redx_client() -> RedXClient:
    return RedXClient(api_key="mock_redx_token", sandbox=True)


@respx.mock
def test_redx_create_order_success(redx_client: RedXClient, sample_parcel: Parcel):
    respx.post(f"{redx_client.base_url}/parcel").mock(
        return_value=httpx.Response(
            200,
            json={"tracking_id": "REDX-88231", "message": "Parcel created successfully"},
        )
    )

    resp = redx_client.create_order(sample_parcel)
    assert resp["tracking_id"] == "REDX-88231"


@respx.mock
def test_redx_check_status_success(redx_client: RedXClient):
    respx.get(f"{redx_client.base_url}/parcels/tracking/REDX-88231").mock(
        return_value=httpx.Response(
            200,
            json={"tracking": {"status": "in_transit"}},
        )
    )

    resp = redx_client.check_status("REDX-88231")
    assert resp["tracking"]["status"] == "in_transit"


@respx.mock
def test_redx_auth_error_401(redx_client: RedXClient, sample_parcel: Parcel):
    respx.post(f"{redx_client.base_url}/parcel").mock(
        return_value=httpx.Response(401, json={"message": "Unauthorized token"})
    )

    with pytest.raises(ProviderAuthenticationError) as exc_info:
        redx_client.create_order(sample_parcel)

    assert exc_info.value.provider == "RedX"


@respx.mock
def test_redx_not_found_404(redx_client: RedXClient):
    respx.get(f"{redx_client.base_url}/parcels/tracking/REDX-99999").mock(
        return_value=httpx.Response(404, json={"message": "Tracking ID not found"})
    )

    with pytest.raises(ResourceNotFoundError):
        redx_client.check_status("REDX-99999")


@respx.mock
def test_redx_invalid_request_400(redx_client: RedXClient, sample_parcel: Parcel):
    respx.post(f"{redx_client.base_url}/parcel").mock(
        return_value=httpx.Response(422, json={"message": "Delivery area is required"})
    )

    with pytest.raises(InvalidRequestError):
        redx_client.create_order(sample_parcel)


@respx.mock
def test_redx_rate_limit_429(redx_client: RedXClient, sample_parcel: Parcel):
    respx.post(f"{redx_client.base_url}/parcel").mock(
        return_value=httpx.Response(429, text="Too Many Requests")
    )

    with pytest.raises(ProviderRateLimitError):
        redx_client.create_order(sample_parcel)


@respx.mock
def test_redx_server_error_500(redx_client: RedXClient, sample_parcel: Parcel):
    respx.post(f"{redx_client.base_url}/parcel").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    with pytest.raises(ProviderServerError):
        redx_client.create_order(sample_parcel)


@respx.mock
def test_redx_other_http_error(redx_client: RedXClient, sample_parcel: Parcel):
    respx.post(f"{redx_client.base_url}/parcel").mock(
        return_value=httpx.Response(418, text="I'm a teapot")
    )

    with pytest.raises(ProviderError):
        redx_client.create_order(sample_parcel)


@respx.mock
def test_redx_inline_errors(redx_client: RedXClient, sample_parcel: Parcel):
    # Inline 401
    respx.post(f"{redx_client.base_url}/parcel").mock(
        return_value=httpx.Response(200, json={"status": "error", "message": "Unauthorized access"})
    )
    with pytest.raises(ProviderAuthenticationError):
        redx_client.create_order(sample_parcel)

    # Inline 404
    respx.post(f"{redx_client.base_url}/parcel").mock(
        return_value=httpx.Response(200, json={"status": 404, "message": "Not Found"})
    )
    with pytest.raises(ResourceNotFoundError):
        redx_client.create_order(sample_parcel)

    # Inline 400
    respx.post(f"{redx_client.base_url}/parcel").mock(
        return_value=httpx.Response(200, json={"status": 400, "message": "Invalid address"})
    )
    with pytest.raises(InvalidRequestError):
        redx_client.create_order(sample_parcel)

    # Inline general
    respx.post(f"{redx_client.base_url}/parcel").mock(
        return_value=httpx.Response(200, json={"status": 500, "message": "Failed"})
    )
    with pytest.raises(ProviderError):
        redx_client.create_order(sample_parcel)


@respx.mock
def test_redx_timeout_and_network_error(redx_client: RedXClient, sample_parcel: Parcel):
    respx.post(f"{redx_client.base_url}/parcel").mock(
        side_effect=httpx.TimeoutException("Timeout")
    )
    with pytest.raises(ProviderTimeoutError):
        redx_client.create_order(sample_parcel)

    respx.post(f"{redx_client.base_url}/parcel").mock(
        side_effect=httpx.NetworkError("Network failed")
    )
    with pytest.raises(ProviderConnectionError):
        redx_client.create_order(sample_parcel)
