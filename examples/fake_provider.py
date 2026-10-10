"""Deterministic fake for application tests, not evidence of a vendor contract."""
from __future__ import annotations
from typing import Any, Optional
from jukto import BaseSMSProvider, JuktoConfigurationError, JuktoError, Outcome, SMSRecipientResult, SMSSubmissionResult


class FakeSMSProvider(BaseSMSProvider):
    provider_name = "ExampleFake"

    def __init__(self, outcome: Outcome = Outcome.ACCEPTED, error: Optional[JuktoError] = None) -> None:
        super().__init__(api_key="synthetic-fake-key")
        self.outcome = outcome
        self.error = error
        self.calls: list[tuple[str | list[str], str]] = []
        self.closed = False

    def submit_sms(self, phone_numbers: str | list[str], message: str) -> SMSSubmissionResult:
        if self.closed:
            raise JuktoConfigurationError("Fake provider is closed")
        self.calls.append((phone_numbers, message))
        if self.error is not None:
            raise self.error
        recipients = (SMSRecipientResult(0, Outcome.ACCEPTED), SMSRecipientResult(1, Outcome.UNKNOWN)) if self.outcome == Outcome.PARTIAL else ()
        return SMSSubmissionResult(self.provider_name, self.outcome, recipients=recipients, raw={"synthetic": True})

    def send_sms(self, phone_numbers: str | list[str], message: str) -> dict[str, Any]:
        return {"status": self.submit_sms(phone_numbers, message).status.value, "synthetic": True}

    def close(self) -> None:
        self.closed = True
        super().close()
