import respx
import httpx
import pytest
import time
from jukto import (
    PathaoClient,
    Parcel,
    ProviderAuthenticationError,
    InvalidRequestError,
    ResourceNotFoundError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderConnectionError,
    ProviderRateLimitError,
    JuktoValidationError,
)


@respx.mock
def test_pathao_token_issue_and_create_order(pathao_client: PathaoClient, sample_parcel: Parcel):
    # Mock token issue
    token_route = respx.post(f"{pathao_client.base_url}/aladdin/api/v1/issue-token").mock(
        return_value=httpx.Response(
            200,
            json={
                "token_type": "Bearer",
                "expires_in": 3600,
                "access_token": "mock_access_token_123",
                "refresh_token": "mock_refresh_token_456",
            },
        )
    )

    # Mock order creation
    order_route = respx.post(f"{pathao_client.base_url}/aladdin/api/v1/orders").mock(
        return_value=httpx.Response(
            200,
            json={
                "type": "success",
                "message": "Order created successfully",
                "data": {"consignment_id": "PTH-100200", "delivery_fee": 60},
            },
        )
    )

    response = pathao_client.create_order(sample_parcel)
    assert token_route.called
    assert order_route.called
    assert response["data"]["consignment_id"] == "PTH-100200"
    assert pathao_client.access_token == "mock_access_token_123"

    # Calling check_status reuses the cached token (does not re-issue token)
    respx.get(f"{pathao_client.base_url}/aladdin/api/v1/orders/PTH-100200/info").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"order_status": "Delivered"}},
        )
    )
    status_resp = pathao_client.check_status("PTH-100200")
    assert status_resp["data"]["order_status"] == "Delivered"
    assert token_route.call_count == 1  # Token was reused from cache


@respx.mock
def test_pathao_token_refresh(pathao_client: PathaoClient, sample_parcel: Parcel):
    # Set simulated expired token
    pathao_client.access_token = "old_token"
    pathao_client.refresh_token = "valid_refresh_token"
    pathao_client.token_expiry = time.time() - 100  # expired

    refresh_route = respx.post(f"{pathao_client.base_url}/aladdin/api/v1/issue-token").mock(
        return_value=httpx.Response(
            200,
            json={
                "token_type": "Bearer",
                "expires_in": 3600,
                "access_token": "new_refreshed_access_token",
                "refresh_token": "valid_refresh_token",
            },
        )
    )

    respx.post(f"{pathao_client.base_url}/aladdin/api/v1/orders").mock(
        return_value=httpx.Response(200, json={"type": "success", "data": {}})
    )

    pathao_client.create_order(sample_parcel)
    assert refresh_route.called
    assert pathao_client.access_token == "new_refreshed_access_token"


@respx.mock
def test_pathao_auth_failure_on_token(pathao_client: PathaoClient):
    respx.post(f"{pathao_client.base_url}/aladdin/api/v1/issue-token").mock(
        return_value=httpx.Response(
            401,
            json={"error": "invalid_credentials", "message": "The credentials do not match."},
        )
    )

    with pytest.raises(ProviderAuthenticationError):
        pathao_client.get_token()


def test_pathao_missing_store_id(pathao_client: PathaoClient):
    pathao_client.store_id = None
    parcel_no_store = Parcel(
        invoice_id="INV-99",
        recipient_name="Test",
        recipient_phone="01711111111",
        recipient_address="Dhaka",
        cod_amount=100.0,
        store_id=None,
    )

    with pytest.raises(JuktoValidationError):
        pathao_client.create_order(parcel_no_store)


@respx.mock
def test_pathao_get_stores(pathao_client: PathaoClient):
    pathao_client.access_token = "mock_valid_token"
    pathao_client.token_expiry = time.time() + 3600

    respx.get(f"{pathao_client.base_url}/aladdin/api/v1/stores").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"store_id": 123, "store_name": "Dhaka Main Branch"}]},
        )
    )

    stores = pathao_client.get_stores()
    assert len(stores["data"]) == 1


@respx.mock
def test_pathao_http_errors(pathao_client: PathaoClient, sample_parcel: Parcel):
    pathao_client.access_token = "mock_valid_token"
    pathao_client.token_expiry = time.time() + 3600

    # 422 Invalid Request
    respx.post(f"{pathao_client.base_url}/aladdin/api/v1/orders").mock(
        return_value=httpx.Response(422, json={"message": "Invalid recipient phone"})
    )
    with pytest.raises(InvalidRequestError):
        pathao_client.create_order(sample_parcel)

    # 404 Not Found
    respx.get(f"{pathao_client.base_url}/aladdin/api/v1/orders/NOT_FOUND/info").mock(
        return_value=httpx.Response(404, json={"message": "Order not found"})
    )
    with pytest.raises(ResourceNotFoundError):
        pathao_client.check_status("NOT_FOUND")

    # 500 Server Error
    respx.get(f"{pathao_client.base_url}/aladdin/api/v1/orders/500_ERR/info").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )
    with pytest.raises(ProviderServerError):
        pathao_client.check_status("500_ERR")

    # Timeout
    respx.get(f"{pathao_client.base_url}/aladdin/api/v1/orders/TIMEOUT/info").mock(
        side_effect=httpx.TimeoutException("Read timeout")
    )
    with pytest.raises(ProviderTimeoutError):
        pathao_client.check_status("TIMEOUT")
