---
title: "Errors, privacy and reconciliation"
description: "Errors, privacy and reconciliation for the Jukto Python SDK. Read implementation details, integration guidance and documented limitations."
---

# Errors, privacy and reconciliation

Catch `JuktoError` for recognized SDK errors. Known provider failures receive
specific subclasses; unknown codes remain `ProviderError`, and decoding/schema
failures become `UnexpectedProviderResponseError`. A programming exception can
still escape; do not hide bugs by wrapping every exception. See the
[exception reference](../api/exceptions.md).

Use `http_status` for transport status and `provider_error_code` for application
codes. Legacy `status_code` is retained and may contain either. `request_id` and
raw `retry_after` are optional upstream metadata, not safe-to-trust identifiers or
automatic retry instructions. Absence of metadata does not prove no request ran.

## Side effects

When `error.reconciliation_required` is true, the outcome is ambiguous: a shipment
or SMS might already have been accepted. A timeout, connection failure, 500 or
malformed response is not universally proof of rejection. Persist your own
operation reference and sanitized evidence, consult provider records or support,
and reconcile before another submission. Do not automatically switch providers.
Even a false reconciliation flag does not guarantee provider-enforced idempotency.

A successful result may also be `UNKNOWN` or `PARTIAL`; inspect the result and each
recipient, not only exceptions. Polling status labels remain original evidence
until an authoritative vocabulary is verified. `ACCEPTED` never means delivered.

The [framework examples](frameworks.md) make one attempt, expose only outcome
metadata, and do not retry. Their HTTP 502 is an application response policy,
not an instruction to resend. Production applications must preserve uncertainty
in durable state and ensure their callers respect reconciliation.

## Logs

`enable_debug_logging()` logs allowlisted provider/operation/event/status metadata.
Bodies, URLs, credentials and SMS content are omitted. Normalized provider error
strings suppress raw upstream text. These protections do not sanitize third-party
HTTP logging, custom exceptions, or your own application logs.

`response_body`, result `raw` and batch evidence deliberately remain accessible and
sensitive. Never send them to a browser, paste them into an issue, or log them by
default. Remove credentials, tokens, OTPs, phone/address data, identifiers, and
query strings before reporting a problem. See [security](../security.md).
