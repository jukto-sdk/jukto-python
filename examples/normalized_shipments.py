"""One application consumer for all logistics adapters; no network calls on import."""
from jukto import BaseLogisticsProvider, Parcel, ShipmentCreationResult, Outcome


def submit_shipment(provider: BaseLogisticsProvider, parcel: Parcel) -> ShipmentCreationResult:
    result = provider.create_shipment(parcel)
    if result.status == Outcome.UNKNOWN:
        # Persist raw evidence securely and reconcile with the provider before resend.
        return result
    # ACCEPTED means created/submitted, not delivered or paid.
    return result
