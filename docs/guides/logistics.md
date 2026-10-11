---
title: "Bangladesh Courier API Integration with Python"
description: "Integrate Steadfast, Pathao and RedX with Jukto. Learn courier setup, shipment results, provider-specific requirements and verification limits."
---

# Logistics integration

Use `create_shipment(Parcel(...))` for a `ShipmentCreationResult` and
`check_shipment_status(id)` for a `ShipmentStatusResult`. Legacy `create_order` and
`check_status` retain raw dictionaries. See [API reference](../api/logistics.md).

## Common parcel inputs

Provide a nonempty invoice, recipient name, phone and address; finite nonnegative
COD; positive integer quantity and positive finite weight. SDK weight inputs are
kilograms. Use `Decimal` for money; do not construct it from a binary float.
Whole Decimal COD values serialize exactly for Pathao/Steadfast; fractional Decimal
values are rejected until their wire format is verified. RedX Decimal money is
serialized as fixed-point text, whose upstream acceptance remains unverified.
Legacy float/int inputs remain compatible. RedX converts kg to integer grams;
exact create weight units and JSON types still require independent verification.

The SDK checks nonempty shipment phone strings, not a full Bangladesh numbering
plan. It does not convert `+880`, `880`, or local forms. Confirm the required form
in the provider specification before submitting; the synthetic examples use
`01700000000` without asserting that it is a real or reachable subscriber.

## Provider-specific setup

| Provider | Setup and routing |
| --- | --- |
| Steadfast | Your API key and secret; adapter wire schema is unverified |
| Pathao | Client ID/secret, merchant username/password, store; `PathaoOptions` for store/city/zone/area and item/delivery types |
| RedX | API access token; `RedXOptions(delivery_area=..., delivery_area_id=...)`; independent `declared_value`; optional pickup store |

City/zone/area IDs are provider-scoped. Obtain them from your provider's current
merchant/developer tools and validate relationships; a Pathao ID cannot be reused
as a RedX ID. Pathao omits unspecified geography rather than inventing ID 1; the
provider may reject incomplete routing. RedX requires its area name and ID, and
declared value is not inferred from COD, allowing nonzero goods value on prepaid
shipments. Typed options take precedence over legacy flat fields.

## One consumer

The application receives the same result model, but adapter construction and
parcel options must be configured separately. This consumer is also type-checked:

```python
--8<-- "examples/normalized_shipments.py"
```

`ACCEPTED` means submission/creation, not delivery. Steadfast creation currently
returns `UNKNOWN`; do not infer acceptance from an ID alone. All typed polling
statuses remain `UNKNOWN` while retaining `provider_status` and `raw`.

Use an owned provider in a `with` block, or close a long-lived provider after its
requests finish. Borrowed HTTPX clients are not closed by the SDK; see
[architecture](../architecture.md). Reconcile ambiguous creation errors before
resubmission. Pathao's order replay is explicitly opt-in; there are no generic
POST retries or verified idempotency guarantees. Evidence and unresolved details
are in the [provider matrix](../provider-contracts.md).
