"""An application boundary shared by Django and FastAPI examples."""
from __future__ import annotations
import os
from typing import Any
from jukto import AlphaSMSClient, BaseSMSProvider, JuktoConfigurationError, JuktoError, SMSBatchError, SMSSubmissionResult


def alpha_client(key: str) -> AlphaSMSClient:
    if not key or not key.strip():
        raise JuktoConfigurationError("Configure JUKTO_ALPHA_API_KEY before serving requests")
    return AlphaSMSClient(api_key=key, timeout=10.0)


def alpha_from_environment() -> AlphaSMSClient:
    return alpha_client(os.environ.get("JUKTO_ALPHA_API_KEY", ""))


def safe_result(result: SMSSubmissionResult) -> dict[str, Any]:
    # Do not expose raw responses, SMS content, credentials or recipient information.
    return {"status": result.status.value,
            "reconciliation_required": result.reconciliation_required,
            "recipients": [{"response_index": item.response_index, "status": item.status.value}
                           for item in result.recipients]}


def notify(provider: BaseSMSProvider, payload: Any) -> tuple[dict[str, Any], int]:
    if not isinstance(payload, dict) or any(not isinstance(payload.get(key), str) or not payload[key].strip()
                                          for key in ("phone", "message")):
        return {"error": "phone and message must be nonempty strings"}, 400
    try:
        result = provider.submit_sms(payload["phone"], payload["message"])
    except SMSBatchError as error:
        if error.normalized_result is not None:
            return safe_result(error.normalized_result), 202
        return {"error": "batch_result_unavailable", "status": "unknown", "reconciliation_required": True}, 502
    except JuktoError as error:
        # One attempt only. The application must persist/reconcile uncertain effects.
        return {"error": "provider_error", "status": error.outcome.value,
                "reconciliation_required": error.reconciliation_required}, 502
    return safe_result(result), 202
