"""Explicit provider-scoped configuration; legacy flat Parcel fields still work."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class PathaoOptions:
    store_id: Optional[int] = None
    recipient_city: Optional[int] = None
    recipient_zone: Optional[int] = None
    recipient_area: Optional[int] = None
    item_type: int = 2
    delivery_type: int = 48

@dataclass(frozen=True)
class RedXOptions:
    delivery_area: str
    delivery_area_id: int
    pickup_store_id: Optional[int] = None

@dataclass(frozen=True)
class ProviderCapabilities:
    provider: str
    shipment_creation: bool = False
    shipment_status: bool = False
    sms_submission: bool = False
    per_recipient_submission: bool = False
    declared_value: bool = False
    geography_options: bool = False
