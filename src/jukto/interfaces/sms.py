from __future__ import annotations

from abc import ABC, abstractmethod
import httpx
from jukto._transport import validate_endpoint, SyncTransport, TransportLifecycle
from typing import Any, Optional
from jukto.results import SMSSubmissionResult, sms_submission
from jukto.options import ProviderCapabilities


class BaseSMSProvider(TransportLifecycle, ABC):
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
        http_client: Optional[httpx.Client] = None,
        limits: Optional[httpx.Limits] = None,
    ) -> None:
        if base_url is not None:
            validate_endpoint(base_url, allow_insecure_http)
        self.allow_insecure_http = allow_insecure_http
        self.api_key = api_key
        self.sender_id = sender_id
        self.base_url = base_url
        self.timeout = timeout
        self._transport = SyncTransport(timeout=timeout, limits=limits, http_client=http_client,
                                        allow_insecure_http=allow_insecure_http)

    @abstractmethod
    def send_sms(self, phone_numbers: str | list[str], message: str) -> dict[str, Any] | list[Any] | str:
        """Sends an SMS to one or multiple numbers."""
        pass

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(self.provider_name, sms_submission=True,
                                    per_recipient_submission=self.provider_name == 'GreenWeb')

    def submit_sms(self, phone_numbers: str | list[str], message: str) -> SMSSubmissionResult:
        return sms_submission(self.provider_name, self.send_sms(phone_numbers, message))
