import pytest
from jukto import Parcel, SteadfastClient, GreenWebClient, PathaoClient, AlphaSMSClient


@pytest.fixture
def sample_parcel() -> Parcel:
    return Parcel(
        invoice_id="INV-9901",
        recipient_name="Tanvir Ahmed",
        recipient_phone="01711112222",
        recipient_address="Banani 11, Dhaka",
        cod_amount=1500.0,
        note="Call before delivery",
        store_id=123,
    )


@pytest.fixture
def steadfast_client() -> SteadfastClient:
    return SteadfastClient(api_key="mock_sf_key", secret_key="mock_sf_secret")


@pytest.fixture
def greenweb_client() -> GreenWebClient:
    return GreenWebClient(api_key="mock_gw_token")


@pytest.fixture
def pathao_client() -> PathaoClient:
    return PathaoClient(
        client_id="mock_pathao_id",
        client_secret="mock_pathao_secret",
        username="mock_user@example.com",
        password="mock_password",
        store_id=123,
        sandbox=True,
    )


@pytest.fixture
def alphasms_client() -> AlphaSMSClient:
    return AlphaSMSClient(api_key="mock_alpha_key", sender_id="FEATHER_IT")
