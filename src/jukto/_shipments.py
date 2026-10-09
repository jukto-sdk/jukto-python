"""Conservative SDK input policies, separate from vendor acceptance guarantees."""
from __future__ import annotations
import math
from jukto.exceptions import JuktoValidationError
from jukto.interfaces.logistics import Parcel


def require_text(value: object, field: str, provider: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise JuktoValidationError(f'{field} must be a nonblank string.', provider=provider)


def require_id(value: object, field: str, provider: str) -> None:
    if type(value) is not int or value <= 0:
        raise JuktoValidationError(f'{field} must be a positive integer.', provider=provider)


def require_number(value: object, field: str, provider: str, *, positive: bool = False) -> None:
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else value >= 0)
    except OverflowError:
        valid = False
    if not valid:
        constraint = 'positive' if positive else 'nonnegative'
        raise JuktoValidationError(f'{field} must be a finite {constraint} number.', provider=provider)


def validate_parcel(parcel: Parcel, provider: str) -> None:
    if not isinstance(parcel, Parcel):
        raise JuktoValidationError('parcel must be a Parcel.', provider=provider)
    for name in ('invoice_id','recipient_name','recipient_phone','recipient_address'):
        require_text(getattr(parcel,name),name,provider)
    require_id(parcel.item_quantity,'item_quantity',provider)
    require_number(parcel.item_weight,'item_weight',provider,positive=True)
    require_number(parcel.cod_amount,'cod_amount',provider)
    if parcel.declared_value is not None:
        require_number(parcel.declared_value,'declared_value',provider)
    if parcel.note is not None and not isinstance(parcel.note,str):
        raise JuktoValidationError('note must be a string or None.',provider=provider)
