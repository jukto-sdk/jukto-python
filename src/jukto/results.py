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
