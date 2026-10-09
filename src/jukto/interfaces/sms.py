from __future__ import annotations

from abc import ABC, abstractmethod
from jukto._transport import validate_endpoint
from typing import Any, Optional


class BaseSMSProvider(ABC):
    """The Contract: All SMS providers MUST implement these methods."""

    def __init__(
        self,
        api_key: str,
        sender_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        *,
        allow_insecure_http: bool = False,
    ) -> None:
        if base_url is not None:
            validate_endpoint(base_url, allow_insecure_http)
        self.allow_insecure_http = allow_insecure_http
        self.api_key = api_key
        self.sender_id = sender_id
        self.base_url = base_url
        self.timeout = timeout

    @abstractmethod
    def send_sms(self, phone_numbers: str | list[str], message: str) -> dict[str, Any]:
        """Sends an SMS to one or multiple numbers."""
        pass
