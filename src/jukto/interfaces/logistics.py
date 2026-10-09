from __future__ import annotations

from abc import ABC, abstractmethod
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


class BaseLogisticsProvider(ABC):
    """The Contract: All logistics providers MUST implement these methods."""

    def __init__(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.timeout = timeout

    @abstractmethod
    def create_order(self, parcel: Parcel) -> dict[str, Any]:
        """Creates a new shipment/parcel."""
        pass

    @abstractmethod
    def check_status(self, consignment_id: str) -> dict[str, Any]:
        """Checks the status of a specific parcel."""
        pass
