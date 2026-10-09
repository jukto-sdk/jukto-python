from __future__ import annotations

from abc import ABC, abstractmethod
import httpx
from jukto._transport import validate_endpoint, SyncTransport, TransportLifecycle
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Parcel:
    invoice_id: str
    recipient_name: str
    recipient_phone: str
    recipient_address: str
    cod_amount: float
    note: Optional[str] = None
    # Extended fields (useful for Pathao, RedX, etc.)
    recipient_city: Optional[int] = None
    recipient_zone: Optional[int] = None
    recipient_area: Optional[int] = None
    store_id: Optional[int] = None
    item_weight: float = 0.5
    item_quantity: int = 1
    item_type: int = 2  # 1: Document, 2: Parcel
    delivery_type: int = 48  # 48: Normal Delivery (Pathao default)
    # Independent goods value; never inferred from COD. RedX-only routing fields.
    declared_value: Optional[float] = None
    redx_delivery_area: Optional[str] = None
    redx_delivery_area_id: Optional[int] = None
    redx_pickup_store_id: Optional[int] = None


class BaseLogisticsProvider(TransportLifecycle, ABC):
    """The Contract: All logistics providers MUST implement these methods."""

    def __init__(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float | httpx.Timeout = 30.0,
        *,
        allow_insecure_http: bool = False,
        http_client: Optional[httpx.Client] = None,
        limits: Optional[httpx.Limits] = None,
    ) -> None:
        if base_url is not None:
            validate_endpoint(base_url, allow_insecure_http)
        self.allow_insecure_http = allow_insecure_http
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.timeout = timeout
        self._transport = SyncTransport(timeout=timeout, limits=limits, http_client=http_client,
                                        allow_insecure_http=allow_insecure_http)

    @abstractmethod
    def create_order(self, parcel: Parcel) -> dict[str, Any]:
        """Creates a new shipment/parcel."""
        pass

    @abstractmethod
    def check_status(self, consignment_id: str) -> dict[str, Any]:
        """Checks the status of a specific parcel."""
        pass
