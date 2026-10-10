from __future__ import annotations

from abc import ABC, abstractmethod
import httpx
from jukto._transport import validate_endpoint, AsyncTransport, AsyncTransportLifecycle
from typing import Any, Optional
from jukto.results import SMSSubmissionResult, sms_submission
from jukto.options import ProviderCapabilities


class AsyncBaseSMSProvider(AsyncTransportLifecycle, ABC):
    provider_name: str
    """The Contract: All SMS providers MUST implement these methods."""

    def __init__(
        self,
        api_key: str,
        sender_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float | httpx.Timeout = 30.0,
        *,
        allow_insecure_http: bool = False,
        http_client: Optional[httpx.AsyncClient] = None,
        limits: Optional[httpx.Limits] = None,
    ) -> None:
        if base_url is not None:
            validate_endpoint(base_url, allow_insecure_http)
        self.allow_insecure_http = allow_insecure_http
        self.api_key = api_key
        self.sender_id = sender_id
        self.base_url = base_url
        self.timeout = timeout
        self._transport = AsyncTransport(timeout=timeout, limits=limits, http_client=http_client,
                                        allow_insecure_http=allow_insecure_http)

    @abstractmethod
    async def send_sms(self, phone_numbers: str | list[str], message: str) -> dict[str, Any] | list[Any] | str:
        """Sends an SMS to one or multiple numbers."""
        pass

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(self.provider_name, sms_submission=True,
                                    per_recipient_submission=self.provider_name == 'GreenWeb')

    async def submit_sms(self, phone_numbers: str | list[str], message: str) -> SMSSubmissionResult:
        return sms_submission(self.provider_name, await self.send_sms(phone_numbers, message))

from jukto.interfaces.logistics import Parcel, shipment_creation, shipment_status
from jukto.results import ShipmentCreationResult, ShipmentStatusResult

class AsyncBaseLogisticsProvider(AsyncTransportLifecycle, ABC):
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
        http_client: Optional[httpx.AsyncClient] = None,
        limits: Optional[httpx.Limits] = None,
    ) -> None:
        if base_url is not None:
            validate_endpoint(base_url, allow_insecure_http)
        self.allow_insecure_http = allow_insecure_http
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.timeout = timeout
        self._transport = AsyncTransport(timeout=timeout, limits=limits, http_client=http_client,
                                        allow_insecure_http=allow_insecure_http)

    @abstractmethod
    async def create_order(self, parcel: Parcel) -> dict[str, Any]:
        """Creates a new shipment/parcel."""
        pass

    @abstractmethod
    async def check_status(self, consignment_id: str) -> dict[str, Any]:
        """Checks the status of a specific parcel."""
        pass

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(self.provider_name, shipment_creation=True, shipment_status=True,
                                    declared_value=self.provider_name == 'RedX',
                                    geography_options=self.provider_name in ('Pathao','RedX'))

    async def create_shipment(self, parcel: Parcel) -> ShipmentCreationResult:
        raw = await self.create_order(parcel)
        return shipment_creation(self.provider_name, raw)

    async def check_shipment_status(self, consignment_id: str) -> ShipmentStatusResult:
        raw = await self._status_payload(consignment_id)
        return shipment_status(self.provider_name, consignment_id, raw)

    async def _status_payload(self, consignment_id: str) -> dict[str, Any]:
        return await self.check_status(consignment_id)
