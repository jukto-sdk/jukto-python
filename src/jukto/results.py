"""Interim list-compatible batch results. Raw entries may contain personal data."""
from __future__ import annotations
from typing import Any


class SMSBatchResult(list[Any]):
    """Preserve ordered raw results, including failed and unrecognized entries.

    SENT describes provider submission output, not independently verified delivery.
    Indices refer to response entries, not necessarily original request positions.
    """

    @property
    def sent_indices(self) -> tuple[int, ...]:
        return tuple(i for i, item in enumerate(self) if isinstance(item, dict) and item.get('status') == 'SENT')

    @property
    def failed_indices(self) -> tuple[int, ...]:
        return tuple(i for i, item in enumerate(self) if isinstance(item, dict) and item.get('status') == 'FAILED')

    @property
    def unknown_indices(self) -> tuple[int, ...]:
        known = set(self.sent_indices + self.failed_indices)
        return tuple(i for i in range(len(self)) if i not in known)

    @property
    def normalized(self) -> SMSSubmissionResult:
        return sms_submission('GreenWeb', self)


from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Outcome(str, Enum):
    ACCEPTED = 'accepted'
    DELIVERED = 'delivered'
    FAILED = 'failed'
    PARTIAL = 'partial'
    UNKNOWN = 'unknown'


@dataclass(frozen=True)
class ShipmentCreationResult:
    provider: str
    provider_id: Optional[str]
    status: Outcome
    provider_status: Any = field(default=None, repr=False)
    raw: Any = field(default=None, repr=False)

    @property
    def reconciliation_required(self) -> bool:
        return self.status == Outcome.UNKNOWN


@dataclass(frozen=True)
class ShipmentStatusResult:
    provider: str
    provider_id: str
    status: Outcome
    provider_status: Any = field(default=None, repr=False)
    raw: Any = field(default=None, repr=False)


@dataclass(frozen=True)
class SMSRecipientResult:
    response_index: int
    status: Outcome
    recipient: Optional[str] = field(default=None, repr=False)
    provider_id: Optional[str] = field(default=None, repr=False)
    provider_status: Any = field(default=None, repr=False)
    raw: Any = field(default=None, repr=False)


@dataclass(frozen=True)
class SMSSubmissionResult:
    provider: str
    status: Outcome
    request_id: Optional[str] = field(default=None, repr=False)
    recipients: tuple[SMSRecipientResult, ...] = ()
    provider_status: Any = field(default=None, repr=False)
    raw: Any = field(default=None, repr=False)

    @property
    def reconciliation_required(self) -> bool:
        return self.status == Outcome.UNKNOWN or any(r.status == Outcome.UNKNOWN for r in self.recipients)


def aggregate_outcomes(outcomes: tuple[Outcome, ...]) -> Outcome:
    distinct = set(outcomes)
    return next(iter(distinct)) if len(distinct) == 1 else Outcome.PARTIAL if distinct else Outcome.UNKNOWN


def identifier(value: Any) -> Optional[str]:
    return str(value) if type(value) in (str, int) and str(value).strip() else None


def sms_submission(provider: str, raw: Any) -> SMSSubmissionResult:
    if provider == 'AlphaSMS':
        return SMSSubmissionResult(provider, Outcome.ACCEPTED, identifier(raw['data']['request_id']),
                                   provider_status=raw.get('error'), raw=raw)
    if provider != 'GreenWeb':
        # BulkSMSBD legacy success semantics are unverified.
        return SMSSubmissionResult(provider, Outcome.UNKNOWN, provider_status=raw.get('response_code'), raw=raw)
    entries = raw if isinstance(raw, list) else [raw]
    recipients = []
    for index, entry in enumerate(entries):
        if isinstance(entry, dict):
            status = entry.get('status')
            outcome = {'SENT': Outcome.ACCEPTED, 'FAILED': Outcome.FAILED}.get(status, Outcome.UNKNOWN) if isinstance(status, str) else Outcome.UNKNOWN
            recipients.append(SMSRecipientResult(index, outcome, identifier(entry.get('to')),
                                                provider_status=status, raw=entry))
        else:
            outcome = Outcome.ACCEPTED if isinstance(entry, str) and entry.lower().startswith('ok:') else Outcome.UNKNOWN
            recipients.append(SMSRecipientResult(index, outcome, raw=entry))
    return SMSSubmissionResult(provider, aggregate_outcomes(tuple(r.status for r in recipients)),
                               recipients=tuple(recipients), raw=raw)
