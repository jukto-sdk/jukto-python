import respx
import httpx
import pytest
from jukto import (
    SteadfastClient,
    Parcel,
    ProviderAuthenticationError,
    InvalidRequestError,
    ResourceNotFoundError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderRateLimitError,
)


@respx.mock
def test_steadfast_create_order_success(steadfast_client: SteadfastClient, sample_parcel: Parcel):
    respx.post(f"{steadfast_client.base_url}/create_order").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": 200,
                "message": "Order created successfully",
                "consignment": {"consignment_id": 987654, "invoice": "INV-9901"},
            },
        )
    )

    response = steadfast_client.create_order(sample_parcel)
    assert response["status"] == 200
    assert response["consignment"]["consignment_id"] == 987654


@respx.mock
def test_steadfast_check_status_success(steadfast_client: SteadfastClient):
    respx.get(f"{steadfast_client.base_url}/status_by_cid/987654").mock(
        return_value=httpx.Response(
            200,
            json={"status": 200, "delivery_status": "delivered"},
        )
    )

    response = steadfast_client.check_status("987654")
    assert response["delivery_status"] == "delivered"


@respx.mock
def test_steadfast_auth_error(steadfast_client: SteadfastClient, sample_parcel: Parcel):
    respx.post(f"{steadfast_client.base_url}/create_order").mock(
        return_value=httpx.Response(
            401,
            json={"status": 401, "message": "Unauthorized API Key"},
        )
    )

    with pytest.raises(ProviderAuthenticationError) as exc_info:
        steadfast_client.create_order(sample_parcel)

    assert exc_info.value.status_code == 401
    assert exc_info.value.provider == "Steadfast"


@respx.mock
def test_steadfast_validation_error(steadfast_client: SteadfastClient, sample_parcel: Parcel):
    respx.post(f"{steadfast_client.base_url}/create_order").mock(
        return_value=httpx.Response(
            400,
            json={"status": 400, "message": "The recipient phone must be 11 digits."},
        )
    )

    with pytest.raises(InvalidRequestError) as exc_info:
        steadfast_client.create_order(sample_parcel)

    assert exc_info.value.status_code == 400


@respx.mock
def test_steadfast_inline_error_on_200(steadfast_client: SteadfastClient, sample_parcel: Parcel):
    respx.post(f"{steadfast_client.base_url}/create_order").mock(
        return_value=httpx.Response(
            200,
            json={"status": 400, "message": "Duplicate invoice id."},
        )
    )

    with pytest.raises(InvalidRequestError):
        steadfast_client.create_order(sample_parcel)


@respx.mock
def test_steadfast_not_found(steadfast_client: SteadfastClient):
    respx.get(f"{steadfast_client.base_url}/status_by_cid/000000").mock(
        return_value=httpx.Response(
            404,
            json={"status": 404, "message": "Consignment not found"},
        )
    )

    with pytest.raises(ResourceNotFoundError):
        steadfast_client.check_status("000000")


@respx.mock
def test_steadfast_rate_limit(steadfast_client: SteadfastClient, sample_parcel: Parcel):
    respx.post(f"{steadfast_client.base_url}/create_order").mock(
        return_value=httpx.Response(429, text="Too Many Requests")
    )

    with pytest.raises(ProviderRateLimitError):
        steadfast_client.create_order(sample_parcel)


@respx.mock
def test_steadfast_server_error(steadfast_client: SteadfastClient, sample_parcel: Parcel):
    respx.post(f"{steadfast_client.base_url}/create_order").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    with pytest.raises(ProviderServerError):
        steadfast_client.create_order(sample_parcel)


@respx.mock
def test_steadfast_timeout(steadfast_client: SteadfastClient):
    respx.get(f"{steadfast_client.base_url}/status_by_cid/987654").mock(
        side_effect=httpx.TimeoutException("Read timeout")
    )

    with pytest.raises(ProviderTimeoutError):
        steadfast_client.check_status("987654")
