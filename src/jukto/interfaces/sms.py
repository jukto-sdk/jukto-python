from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseSMSProvider(ABC):
    """The Contract: All SMS providers MUST implement these methods."""

    def __init__(
        self,
        api_key: str,
        sender_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.sender_id = sender_id
        self.base_url = base_url
        self.timeout = timeout

    @abstractmethod
    def send_sms(self, phone_numbers: str | list[str], message: str) -> dict[str, Any]:
        """Sends an SMS to one or multiple numbers."""
        pass
