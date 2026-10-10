from __future__ import annotations

from abc import ABC, abstractmethod
import httpx
from jukto._transport import validate_endpoint, SyncTransport, TransportLifecycle
from dataclasses import dataclass
from typing import Any, Optional
from decimal import Decimal
from jukto.options import PathaoOptions, RedXOptions, ProviderCapabilities
from jukto.results import ShipmentCreationResult, ShipmentStatusResult, Outcome, identifier


@dataclass
class Parcel:
    invoice_id: str
    recipient_name: str
    recipient_phone: str
    recipient_address: str
    cod_amount: Decimal | float | int
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
    declared_value: Optional[Decimal | float | int] = None
    redx_delivery_area: Optional[str] = None
    redx_delivery_area_id: Optional[int] = None
    redx_pickup_store_id: Optional[int] = None
    pathao_options: Optional[PathaoOptions] = None
    redx_options: Optional[RedXOptions] = None


class BaseLogisticsProvider(TransportLifecycle, ABC):
    provider_name: str
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

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(self.provider_name, shipment_creation=True, shipment_status=True,
                                    declared_value=self.provider_name == 'RedX',
                                    geography_options=self.provider_name in ('Pathao','RedX'))

    def create_shipment(self, parcel: Parcel) -> ShipmentCreationResult:
        raw = self.create_order(parcel)
        content = raw.get('data', {}) if self.provider_name == 'Pathao' else raw.get('consignment', {}) if self.provider_name == 'Steadfast' else raw
        provider_id = identifier(content.get('consignment_id') if self.provider_name != 'RedX' else content.get('tracking_id'))
        status = Outcome.ACCEPTED if provider_id is not None and self.provider_name in ('Pathao','RedX') else Outcome.UNKNOWN
        return ShipmentCreationResult(self.provider_name, provider_id, status,
                                      provider_status=raw.get('type',raw.get('status')), raw=raw)

    def check_shipment_status(self, consignment_id: str) -> ShipmentStatusResult:
        raw = self._status_payload(consignment_id)
        if self.provider_name == 'Pathao':
            original = raw['data']['order_status']
        elif self.provider_name == 'RedX':
            original = raw['parcel']['status']
        else:
            original = raw['delivery_status']
        # No verified status vocabulary for these polling endpoints; retain evidence.
        return ShipmentStatusResult(self.provider_name, consignment_id, Outcome.UNKNOWN,
                                    provider_status=original, raw=raw)

    def _status_payload(self, consignment_id: str) -> dict[str, Any]:
        return self.check_status(consignment_id)
