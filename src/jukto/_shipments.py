"""Conservative SDK input policies, separate from vendor acceptance guarantees."""
from __future__ import annotations
import math
from decimal import Decimal
from dataclasses import replace
from typing import Any
from jukto.options import PathaoOptions, RedXOptions
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
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and (value > 0 if positive else value >= 0)
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
    require_money(parcel.cod_amount,'cod_amount',provider)
    if parcel.declared_value is not None:
        require_money(parcel.declared_value,'declared_value',provider)
    if parcel.note is not None and not isinstance(parcel.note,str):
        raise JuktoValidationError('note must be a string or None.',provider=provider)


def require_money(value: object, field: str, provider: str) -> Decimal:
    if type(value) not in (int, float, Decimal):
        raise JuktoValidationError(f'{field} must be a finite nonnegative monetary amount.', provider=provider)
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise JuktoValidationError(f'{field} must be a finite nonnegative monetary amount.', provider=provider)
    return number


def wire_amount(value: object, provider: str) -> Any:
    number = require_money(value, 'amount', provider)
    if provider == 'RedX' and isinstance(value, Decimal):
        # Official create table permits strings; preserve every supplied decimal digit.
        return format(number, 'f')
    if isinstance(value, Decimal):
        if number != number.to_integral_value():
            raise JuktoValidationError('Fractional Decimal wire amounts are not verified for this provider.', provider=provider)
        return int(number)
    # Existing numeric float/int serialization retained as explicit legacy compatibility.
    return value


def resolve_options(parcel: Parcel, provider: str) -> Parcel:
    if not isinstance(parcel, Parcel):
        raise JuktoValidationError('parcel must be a Parcel.', provider=provider)
    if provider == 'Pathao' and parcel.pathao_options is not None:
        if not isinstance(parcel.pathao_options, PathaoOptions):
            raise JuktoValidationError('pathao_options must be PathaoOptions.', provider=provider)
        options = parcel.pathao_options
        return replace(parcel, store_id=options.store_id, recipient_city=options.recipient_city,
                       recipient_zone=options.recipient_zone, recipient_area=options.recipient_area,
                       item_type=options.item_type, delivery_type=options.delivery_type)
    if provider == 'RedX' and parcel.redx_options is not None:
        if not isinstance(parcel.redx_options, RedXOptions):
            raise JuktoValidationError('redx_options must be RedXOptions.', provider=provider)
        redx = parcel.redx_options
        return replace(parcel, redx_delivery_area=redx.delivery_area,
                       redx_delivery_area_id=redx.delivery_area_id, redx_pickup_store_id=redx.pickup_store_id)
    return parcel
