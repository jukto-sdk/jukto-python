---
title: "Provider contract audit"
description: "Review SMS and courier contract evidence, provider capability differences and unresolved behavior before integrating Jukto."
---

# Provider contract audit

Audit date: **2026-10-10**. Verification means comparison with retrievable official documentation, not a live API transaction. No credentials, SMS submissions, shipment creation, or captured production responses were used. Unknown means unresolved, not supported by inference from existing mocks or third-party wrappers.

The numbered task sections are historical snapshots; their progress statements
describe that task's completion point. The latest capability/verification summary
appears at the end of this page. Later SDK changes do not retroactively establish
unverified upstream contracts.

## Evidence and current implementation matrix

Paths below are relative to the base URL. Unless explicitly marked verified, these are **implementation inventory**, not claims about upstream behavior. Last independently verified date is “unverified” where no authoritative specification was retrieved.

| Provider | SDK endpoints | SDK request fields/auth | SDK response handling | Official evidence and last verification |
| --- | --- | --- | --- | --- |
| AlphaSMS | `https://api.sms.net.bd/sendsms` | Form `api_key`, `msg`, `to`, optional `sender_id` | Object with `error`; documented success 0 and `data.request_id`; documented failures below | [Official API](https://sms.bd/api), 2026-10-10; verified published contract only |
| BulkSMSBD | `http://bulksmsbd.net/api/smsapi` | Form `api_key`, `type`, `number`, `senderid`, `message` | Integer `response_code`; legacy success 202 retained; all other integers raise generic ProviderError | [Provider site](https://bulksmsbd.net/) redirected to login; `/api` and `/api.php` retrieval failed; **unverified** |
| Steadfast | `https://portal.packzy.com/api/v1/create_order`, `/status_by_cid/{id}` | Headers Api-Key/Secret-Key; JSON invoice, recipient_name/phone/address, cod_amount, note | Raw JSON; integer body status >=400 mapped by adapter | [Official business page](https://steadfast.com.bd/business) confirms API offering, not this wire contract; **unverified** |
| Pathao | `https://api-hermes.pathao.com/aladdin/api/v1/issue-token`, `/orders`, `/orders/{id}/info`, `/stores`; sandbox host courier-api-sandbox.pathao.com | Token request client_id/secret and password or refresh grant; orders use Bearer auth and store_id, merchant_order_id, recipient fields/geography, delivery_type, item_type, special_instruction, item_quantity/weight, amount_to_collect | Token access_token/refresh_token/expires_in; resource responses returned raw | [Official developer panel](https://merchant.pathao.com/courier/developer-api) returned JavaScript shell; **unverified** |
| RedX | `https://openapi.redx.com.bd/v1.0.0-beta/parcel`, legacy `/parcels/tracking/{id}`; sandbox host sandbox.redx.com.bd | API-ACCESS-TOKEN Bearer; customer name/phone/address, RedX delivery_area/name and delivery_area_id, invoice, cash collection, weight, instruction, separate declared value, optional pickup_store_id | Raw JSON; create tracking_id; legacy tracking/error guards remain unverified | [Official developer specification bundle](https://redx.com.bd/_next/static/chunks/pages/developer-api-fb24bbe4344e870c.js), 2026-10-10: create fields/endpoint/auth verified; exact create weight units/types and legacy tracking contract unresolved; see task 6 |
| GreenWeb | `https://api.greenweb.com.bd/api.php` | Form token, to, message; json=1 | Per-recipient SENT/FAILED JSON list or Ok:/Error: text lines | [Official English manual](https://bdbulksms.com/bulk-sms-api-bd-english.php), linked via the portal's homepage; 2026-10-10; published JSON/text format verified, standalone text-error mappings remain legacy/unverified |

HTTP status classifications in the adapters are SDK policies, not verification of each provider's application codes. Unverified adapters still require a future authoritative audit; existing tests are implementation regressions, not certifications.

## AlphaSMS classification policy

Source: the Common Errors and Send SMS Errors sections of https://sms.bd/api, checked 2026-10-10. Recorded paraphrased semantics and test expectations are in `tests/fixtures/alphasms_contract.json`; fixtures are synthetic and retain their provenance.

| Codes | Jukto classification | Meaning |
| --- | --- | --- |
| 0 | Return response | Accepted submission, not proof of delivery |
| 403, 405 | ProviderAuthenticationError | Permission/access rejection |
| 410, 411 | ProviderAuthenticationError | Merchant/reseller account unavailable |
| 404 | ResourceNotFoundError | Missing resource |
| 409 | ProviderServerError | Upstream internal failure |
| 400, 412–416, 420 | InvalidRequestError | Parameter, scheduling, sender, message, recipient, or content rejection |
| 417 | InsufficientBalanceError | Credit depletion |
| Other integer codes | ProviderError | No documented semantics established |

These exception classes are Jukto policy, not names supplied by the provider. Permission denial and account expiration use the existing authentication category; they do not imply a token refresh will resolve the problem. A 409 application code is not assumed to be an HTTP conflict.

The official JSON example has an integer `error`; its C# examples compare against string zero. The adapter accepts canonical nonnegative ASCII decimal strings as a compatibility policy and applies the same code semantics. This is not proof that every code has been observed as a string. Bools, floats, whitespace-padded/zero-padded strings, missing codes, and non-object envelopes raise generic ProviderError. Unknown integer codes retain their code and body.

The docs also list schedule and content_id (required for bulk SMS); these are not exposed by the current adapter. Full success-data schema validation and JSON decoding normalization remain task 4, not completed here.

## Unresolved BulkSMSBD contract

Official error table, envelope schema, string-code support, and success code could not be retrieved without an account. Do not substitute another company's BulkSMS.com API or a third-party wrapper as authority. No new semantics were inferred.

The old 1002/1003/1004/1005/1006/1007/1008/1010 classifications and message-substring inference have been removed. All non-202 integer codes now raise ProviderError with the original body and code. Integer 202 is retained solely for legacy compatibility and remains explicitly **unverified**, including its acceptance/delivery meaning. String 202 and floats are not silently coerced. Unknown envelopes fail closed.

Resolution requires a provider-issued specification/API-page export or sanitized responses with recorded endpoint, API version, date, and provenance. No credentials should be included.

## RedX shipment contract: task 1 findings (superseded in part by task 6)

At the task 1 baseline, the adapter placed the full address into delivery_area, ignores recipient_area, multiplies item_weight by 1000, and sets value equal to COD. None of these choices was independently verified in this audit.

Obtain the official create-parcel schema defining geographic name/ID fields and lookup relationship, parcel_weight units/range/rounding, value meaning and requiredness, cash_collection_amount semantics, pickup-store requirements, response envelope, and error table. Do not invent delivery_area_id or change weight units based on unofficial examples. Task 1 made no RedX payload change. The task 6 section below records newly retrieved primary evidence, corrections, and remaining ambiguities.

## Compatibility changes in this task

- AlphaSMS 405 now means authentication/access failure, 417 means insufficient balance, 416 means invalid recipients, 404 means missing resource, and 409 means provider server failure.
- Undocumented AlphaSMS application codes 401/402/406/422 now raise generic ProviderError instead of guessed specific classes. Actual HTTP status handling is unchanged.
- BulkSMSBD application error codes previously classified specifically now raise generic ProviderError. Callers should catch ProviderError and retain the vendor code until the official contract is available.
- Unexpected AlphaSMS/BulkSMSBD code envelopes no longer return success-like dictionaries. Existing success responses remain raw dictionaries.
- `status_code` still carries application codes for backwards compatibility; separating HTTP status and vendor code remains task 8.
- No retries or automatic failover were added. A server error does not establish that resubmitting SMS is safe.

Task 1 is partially complete: matrix and AlphaSMS audit are complete; BulkSMSBD and RedX authoritative verification and the remaining providers' schema evidence are unresolved. Tasks 2 onward were not started.

## Task 2: credential transport policy

All six clients now reject cleartext endpoints by default, validate endpoints again
before sending, enable TLS certificate verification explicitly, and refuse all
redirects (including same-origin redirects). Invalid schemes, relative URLs, and
embedded URL credentials are rejected. This policy also covers Pathao token issue,
refresh, and authenticated replay. No client reuse or retry redesign was added.

Every concrete client accepts the keyword-only `allow_insecure_http=True` option
for deliberate legacy/local use. It permits HTTP only; it does not disable HTTPS
certificate verification or enable redirect following. Credentials and SMS content
sent over HTTP are unencrypted.

BulkSMSBD's legacy HTTP constant remains unchanged pending authoritative verification
of HTTPS **POST** support. Consequently, construction with its default HTTP endpoint
now raises JuktoConfigurationError unless explicitly opted in. HTTPS override URLs
are accepted by the transport policy but are not certified provider integrations.

A credential-free `curl --head --max-time 20 --proto '=https'` request to the exact
`https://bulksmsbd.net/api/smsapi` path on 2026-10-10 succeeded with default certificate
verification. It returned HTTP 200, Apache, and Content-Type application/json.
This establishes TLS reachability only: HEAD carries no response body and does not
verify SMS POST compatibility or application success. The public documentation
fetch for that URL failed; the provider homepage still exposes a login panel.
The endpoint-verification checkbox remains open until provider-issued documentation
or authorized, provenance-recorded sandbox evidence confirms HTTPS SMS submission.

Compatibility: existing custom HTTP endpoints and default BulkSMSBD construction
must now opt in explicitly. Prefer confirmed HTTPS endpoints. Endpoint policy
failures raise JuktoConfigurationError before HTTP requests are made.

## Task 3: logging and exception privacy

Jukto adapters emit only fixed provider/operation/event metadata and HTTP status
where available. They do not log request or response payloads, URLs, headers,
recipient data, SMS/OTP content, token responses, usernames, or underlying exception
text. No diagnostic payload-logging option is retained. `enable_debug_logging()`
changes the Jukto logger's level/handler, not this metadata-only policy.

`mask_sensitive()` now replaces complete known credential values with `***`,
regardless of value type, including nested dictionaries/lists. It returns a copy
and does not reveal credential prefixes/suffixes. This helper is not a universal
personal-data sanitizer: unknown fields and scalar strings are unchanged, and
adapters no longer use it to justify logging arbitrary payloads.

SDK-generated provider exception messages, `str`, and `repr` withhold provider
messages and underlying network-error text because these can echo credentials,
URLs, OTPs, or recipient data. Raw upstream chains are suppressed in normal
formatted tracebacks. Exception types, provider identifiers, and codes remain
available; HTTP/application classification and retry behavior are unchanged.

`error.response_body` intentionally retains the original parsed body or raw text
for deliberate investigation. Treat it as sensitive: do not print it, serialize
it into public API responses, attach it to issue reports, or log it without your
own reviewed sanitization. Explicit inspection of exception context/request objects
can likewise reveal sensitive data. Application-created JuktoError messages are
not automatically scrubbed; callers must not put secrets in those messages.

This policy covers SDK-generated diagnostics on the `jukto` logger. It does not
sanitize independently enabled HTTPX/httpcore logs, application logs, debugger
locals, or external error-reporting tools. Configure those separately. Existing
malformed-response failures outside JuktoError remain task 4; this is not a claim
that arbitrary upstream exceptions have all been normalized.

Compatibility: provider message text no longer appears in `.message`, `str(error)`,
`repr(error)`, or ordinary chained traceback output. Consumers needing that text
must deliberately inspect `response_body`; do not parse exception message strings
for error classification. Masking now yields `***` instead of credential fragments.

## Task 4: malformed responses and SMS batch outcomes

`UnexpectedProviderResponseError` extends ProviderError/JuktoError and identifies
JSON decoding or response-schema failures. Messages and normal tracebacks remain
metadata-only; response_body preserves sensitive raw text or parsed evidence.
It does not establish whether an order or SMS side effect occurred. Reconcile
before retrying. HTTP failures retain HTTP-based classification even if the error
body is a JSON scalar or array. Only JSONDecodeError/UnicodeDecodeError are caught
by the common decoder; internal TypeError and other programming failures propagate.

AlphaSMS requires its documented submission `data.request_id` on success. Its
known application errors retain task 1 mappings. Oversized or noncanonical code
strings and missing success evidence fail closed. BulkSMSBD still accepts the
unverified legacy integer 202 only; no additional success schema was invented.

Steadfast/RedX now guard their existing SDK-consumed success fields: Steadfast status
200 with consignment evidence or delivery_status, RedX tracking_id or tracking.status.
Pathao guards its existing data envelopes with consignment_id for create, order_status
for tracking, or object/list store data. These are conservative **SDK compatibility
policies**, not authoritative upstream schema certification. Unknown/missing envelopes
and Pathao error/type indicators raise UnexpectedProviderResponseError. The official
Pathao developer panel still exposes only a JavaScript shell; specific HTTP-200
application-error mappings remain unresolved and the corresponding checklist item
is open. No provider error code meanings were inferred from HTTP conventions.

Pathao token issue/refresh also reject invalid JSON/object/access-token/expiry
structures. Malformed refresh responses no longer trigger password-auth fallback;
malformed replay responses and internal programming failures are no longer swallowed
as the original 401. The broader refresh/replay policy, state atomicity, locking,
and clock redesign remain task 5. Existing missing-token responses now raise an
unexpected-response error rather than authentication failure or fallback success.

### GreenWeb evidence and compatibility

The official portal links to bdbulksms.com as its homepage. Its English manual
at https://bdbulksms.com/bulk-sms-api-bd-english.php documents the existing GreenWeb
endpoint, HTTPS, json=1, SENT/FAILED JSON entries, and Ok:/Error: text lines.
Provenance is recorded in tests/fixtures/greenweb_contract.json. Regression entries
are synthetic; no SMS transactions or demo-token submissions were performed.
Do not copy that manual's disabled TLS verification examples; Jukto's TLS policy
remains enabled.

JSON is parsed before checking status. Echoed message or statusmsg content is not
searched for error words. Lists are inspected in full, including malformed entries;
unrecognized status values are unknown, never assumed successful. The documented
json=1 option is now sent. Legacy single-object SENT/FAILED/error envelopes remain
compatible. Historical standalone text errors are restricted to anchored prefixes
and explicitly remain unverified; arbitrary plain text is rejected. Documented
Ok:/Error: lines are evaluated individually, preserving mixed text outcomes.

`SMSBatchResult` subclasses list, preserving ordered raw entries. Its sent_indices,
failed_indices, and unknown_indices refer to response positions, **not guaranteed
positions in the original recipient request**. For JSON, correlate using the original
`to` field when present, not guessed ordering. SENT is provider output, not independent
delivery confirmation. Raw entries and returned successful text may contain personal
data and must not be logged.

Successful JSON lists return SMSBatchResult (normal list operations still work).
Batches with failed or unknown entries raise SMSBatchError, a ProviderError subclass,
with `.results` and `.response_body`. Entirely unrecognized batches raise
UnexpectedProviderResponseError while retaining the raw body. No automatic retry
or failover is performed. Preserve successful entries and reconcile unknown outcomes;
do not resend the whole batch. Single successful text responses retain the legacy
string return shape; multi-line text responses use the batch representation.

```python
from jukto import SMSBatchError, UnexpectedProviderResponseError

try:
    results = client.send_sms(numbers, message)
except SMSBatchError as error:
    sent_positions = error.results.sent_indices
    failed_positions = error.results.failed_indices
    unknown_positions = error.results.unknown_indices
    # Persist outcomes privately; reconcile before any targeted retry.
except UnexpectedProviderResponseError:
    # Submission outcome is unknown. Do not automatically resend.
    pass
```

## Pathao token lifecycle and replay (task 5, 2026-10-10)

Token exchange and publication are serialized by a per-client reentrant lock.
Waiters recheck expiry under that lock; concurrent late 401 responses reuse a newer
cache generation rather than invalidating it. The cache and lock belong to one
client instance in one process: workers, other instances, and forked processes do
not coordinate. Construct clients inside each worker. Do not mutate token cache
attributes from application threads or persist `token_expiry`.

`token_expiry` is now a **monotonic deadline**, not a Unix timestamp. Lifetime starts
before the exchange request, subtracting network latency conservatively. The refresh
margin is min(60 seconds, 10% of lifetime), allowing short-lived tokens to be reused.
A nonblank access token and finite positive `expires_in` are required; no undocumented
3600-second default is supplied. A supplied refresh token must be a nonblank string;
omission preserves the previous refresh token during refresh and clears it during
password issuance. All fields are validated before publishing the new cache state.
Malformed responses and transport failures leave the prior state untouched.

Only HTTP 400 with JSON `error: "invalid_grant"` during a refresh grant triggers one
password-grant fallback. This classification follows [RFC 6749 sections 5.2 and 6](https://www.rfc-editor.org/rfc/rfc6749#section-5.2),
which defines rejection of an invalid/expired/revoked refresh token, and permits
omission or rotation of the refresh token on successful refresh. Pathao's exact
adoption of this error envelope, expiry schema, and omission behavior remains
**unverified**: its [developer portal](https://developer.pathao.com/) could not be
retrieved in this audit. These are conservative SDK policies grounded in OAuth,
not Pathao certification. Generic 400/401/403, 429/500, timeout, network, and malformed
refresh responses propagate; they never silently switch to password authentication.

GET operations replay at most once after HTTP 401, refreshing or issuing a token.
The final attempt's HTTP/timeout/network/schema error is propagated with its own
response data. No retries occur for timeouts, network failures, 5xx, or validation
errors. Shipment creation no longer automatically replays: callers receive the 401.
For integrations with independently verified guarantees that a 401 shipment request
has no side effects, `PathaoClient(..., retry_unauthorized_orders=True)` restores the
legacy single replay. This option is an explicit application assumption; Pathao's
no-side-effect-on-401 and shipment idempotency guarantees remain unresolved. An
order reference is not evidence of idempotency. Reconcile uncertain outcomes before
application retries. No live shipment or credentialed authentication was performed.

Offline lifecycle regressions cover final retry failures, transient refresh outages,
malformed token state, rotation, short lifetimes, clock jumps, concurrent expiry,
concurrent stale 401, and default refusal to replay shipment creation.

## Shipment input validation and migration (task 6, 2026-10-10)

All three adapters validate the Parcel again at submission, including mutations
made after construction, before any HTTP client or Pathao token exchange. Nonblank
string invoice/name/phone/address, positive integer quantity, finite positive numeric
weight, finite nonnegative numeric COD, and configured nonblank credentials are SDK
input policies. Booleans, numeric strings, NaN/infinity, unrepresentable numeric
magnitudes, and nonstring notes are rejected with JuktoValidationError. Error text
names fields without echoing their values. This does not verify deliverability,
phone syntax, geographic membership, vendor limits, or monetary precision.

### Pathao evidence

The provider-maintained [pathao-bridge.php makeDto serializer](https://github.com/pathao-eng/courier-woocommerce-plugin/blob/main/pathao-bridge.php)
conditionally includes city/zone/area only when supplied, rather than filling them
with 1. Jukto now follows that behavior: None omits the field; explicit values must
be positive integers. No cross-provider geography translation occurs. Parcel.store_id
uses the client default only for None; explicit zero no longer silently overrides
it. Store ID must be positive. Delivery/item type must be positive integers;
accepted enum values, weight units/range, address-dependent omission acceptance,
phone constraints, and complete provider requirements remain unresolved. A maintained
integration is narrower evidence than a normative API specification. No new vendor
limits or enums are guessed. Existing item_weight numeric serialization is retained.

### RedX evidence and corrections

The official [developer page](https://redx.com.bd/developer-api/) exposes its published
specification in [this versioned JavaScript bundle](https://redx.com.bd/_next/static/chunks/pages/developer-api-fb24bbe4344e870c.js).
Its Create Parcel specification confirms `/parcel`, `API-ACCESS-TOKEN: Bearer ...`,
a delivery-area name and integer ID, independent cash collection and declared
value for compensation, and optional pickup_store_id. Consequently create_order
now uses that endpoint/header and requires explicit `declared_value`,
`redx_delivery_area`, and `redx_delivery_area_id`. It sends optional
`redx_pickup_store_id` only when supplied. It does not use Pathao's city/zone/area
or store_id. Example prepaid inputs:

```python
parcel = Parcel(
    invoice_id="INV-1", recipient_name="Example Customer",
    recipient_phone="01700000000", recipient_address="Example street address",
    cod_amount=0, declared_value=1200,
    redx_delivery_area="Banani", redx_delivery_area_id=12, item_weight=0.5,
)
```

Area names/IDs above are illustrative; obtain matching values from RedX's own
`/areas` specification/service. Jukto validates shape, not existence or the pairing.
Declared value is never inferred from COD: existing RedX callers must now provide
it, including when COD is zero. These new optional Parcel fields are appended,
preserving existing positional arguments. Pathao/Steadfast do not serialize declared
value because a supported field has not been verified for those adapters.

**Remaining RedX ambiguity:** the create table labels weight and value as strings,
while its curl example uses numeric weight/value; the parcel-detail specification
describes returned weight in grams, but the create table ambiguously mentions kg/g.
The officially linked [WooCommerce plugin](https://wordpress.org/plugins/redx-for-woocommerce/)
(version downloaded from WordPress) uses integer weights and numeric amount/value
on its distinct `/wordpress/parcel` endpoint, so it is corroborating evidence, not
proof of identical types on `/parcel`. Jukto retains the legacy SDK convention:
item_weight in kilograms converted to integer grams, numeric cash/value. It now
rejects fractional grams instead of truncating them or inventing a 500g fallback.
Create weight units/range/rounding and exact accepted JSON number/string types still
require provider confirmation. Offline tests assert this **SDK policy**, not live
compatibility. RedX tracking endpoint/response changes are outside task 6; the legacy
`/parcels/tracking/{id}` route and guards remain unverified. The shared RedX auth
header is now the documented API-ACCESS-TOKEN for both operations.

### Evidence record and limits

`tests/fixtures/shipment_contracts.json` records source provenance and unresolved
contracts. Retrieved public-source SHA-256 digests:

- RedX bundle: `323ce7e69b14334da721aaab12b94c889b4099d393897ef64e560eae8381f70d`
- Pathao bridge: `0e8c93123adaea0b0d8fb8f1613972842038a732f0d594a49e2fd472fc940a4f`

Steadfast's specification remained inaccessible; its existing payload is unchanged,
and local validation is explicitly SDK policy. Exact provider phone formats, lengths,
amount precision/currency, and maximum quantity/weight remain unresolved across
these providers. No regex, region defaults, minimum monetary value, or undocumented
vendor limits were added. All checks were offline; no shipments were created.

## HTTP client ownership and lifecycle (task 7, 2026-10-10)

All six synchronous providers now share one transport implementation. It validates
actual target URLs, creates an owned httpx.Client lazily on the first valid operation,
and reuses it until close(). Provider-specific response inspection and exceptions
remain in the adapters. Pathao token exchange and resource replay use the same pool.
First-use initialization is synchronized; parallel requests are not serialized by
the initialization lock. Connection reuse follows [HTTPX's client model](https://www.python-httpx.org/advanced/clients/);
offline tests prove client reuse, not a measured network performance improvement.

Use a context manager or call close() when the application finishes with a provider:

```python
import httpx
from jukto import AlphaSMSClient

with AlphaSMSClient(
    api_key="example-key",
    timeout=httpx.Timeout(20, connect=5, read=15, write=10, pool=3),
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10,
                        keepalive_expiry=15),
) as sms:
    # Existing send_sms calls use this provider's single pool.
    pass
```

The constructor's existing scalar timeout remains supported; httpx.Timeout exposes
connect/read/write/pool settings. limits accepts [httpx.Limits](https://www.python-httpx.org/advanced/resource-limits/)
for owned pools, with HTTPX defaults when omitted. These settings are captured at
construction. Configure a new provider rather than mutating its timeout attribute.
Owned clients retain certificate verification and refuse redirects. There are no
SDK transport retries; Pathao's operation-specific, bounded 401 replay is unchanged.

For injection, pass keyword-only http_client to any provider:

```python
with httpx.Client() as application_client:
    with AlphaSMSClient("example-key", http_client=application_client) as sms:
        pass
    # application_client is still open here; its owner closes it.
```

Injected clients are **borrowed**. Provider close/context exit marks the provider
closed without closing that HTTPX client. Borrowed pool configuration belongs to
its owner: combining http_client with provider limits raises JuktoConfigurationError.
The SDK timeout (including the default 30 seconds) overrides the borrowed request
timeout. Redirects are explicitly disabled per request and client-level HTTPX auth
is disabled so it cannot replace provider authentication. A separately closed
borrowed client is rejected on use. Invalid injection types are configuration errors.

The application controls an injected client's TLS verification, proxies, custom
transport retries, event hooks, default headers/params, and cookies; Jukto cannot
certify those settings. Use a dedicated provider client configured for verified TLS
and no automatic retries of side-effecting requests. HTTPX merges client defaults
into requests and retains cookies, including in owned pools. Do not share a borrowed
client carrying unrelated credentials or tenant state across providers. Hooks and
custom logging also remain application-controlled.

close() is idempotent. Closing an unused owned provider does not create a pool.
Closed providers cannot be reused or re-entered; construct a new instance. Context
exit also closes owned resources when application code raises. Finish all in-flight
operations before close(); concurrent shutdown/request use is unsupported. Create
clients inside each worker process; do not fork or persist a live pool. These APIs
are synchronous and block the calling thread; native async remains task 11.

Migration: previously every operation closed its temporary pool automatically.
Long-lived application integrations now need explicit provider shutdown or context
management. Existing operation signatures and provider response shapes are unchanged.
No live requests were used to test transport ownership or pooling.

## Typed domain contracts and migration (task 8, 2026-10-10)

The raw APIs remain compatible: create_order/check_status/send_sms keep their
existing dictionaries, strings and lists. New create_shipment/check_shipment_status
and submit_sms methods return ShipmentCreationResult, ShipmentStatusResult and
SMSSubmissionResult. Common fields are provider, provider ID/request ID, Outcome,
original provider status, and raw. Outcome has ACCEPTED, DELIVERED, FAILED, PARTIAL
and UNKNOWN. Results are frozen containers, but raw data is neither copied nor
sanitized; it can contain personal information. Raw/status/recipient fields and
submission request IDs are excluded from result repr. Use raw only in deliberate,
access-controlled diagnostics. Provider IDs normalize string/integer IDs to strings.
Unknown or invalid identifiers do not establish acceptance.

[examples/normalized_shipments.py](https://github.com/jukto-sdk/jukto-python/blob/main/examples/normalized_shipments.py)
is one typed consumer for all three shipment providers, with no provider-specific
response indexing. ACCEPTED means submission/creation evidence, not delivery,
fulfillment or payment. Pathao's maintained creation consumer and RedX's published
tracking_id response support this inference; Steadfast creation remains UNKNOWN
because its success contract has not been verified. All polling vocabularies remain
UNKNOWN, including familiar strings such as Delivered: no cross-endpoint status
mapping is assumed. Original status and IDs remain accessible for application
policies and reconciliation. RedX's new typed status method uses its documented
`/parcel/info/{id}` and `parcel.status`; legacy check_status keeps its prior route.
RedX's published webhook mapped-status meanings are not assumed to certify polling
states. This intentionally does not offer verified delivered/returned/failed
shipment classifications yet.

AlphaSMS's [published submission envelope](https://sms.bd/api) supports ACCEPTED
and a submission request_id, with no per-recipient delivery claims. GreenWeb's
[published recipient output](https://bdbulksms.com/bulk-sms-api-bd-english.php) supports
SENT → ACCEPTED and FAILED → FAILED. Unrecognized entries remain UNKNOWN and mixed
outcomes become PARTIAL. SMSBatchError preserves the original list-compatible
results and adds normalized_result; SMSBatchResult.normalized exposes the same
models. Recipient identities are only response-supplied `to` values; response_index
is not an input-position correlation or resend instruction. Text-only responses
cannot supply an independently verified recipient identity. BulkSMSBD's legacy
202 remains UNKNOWN in the typed API. Full provenance is recorded in
`tests/fixtures/result_contracts.json`; no live delivery was verified.

### Error metadata and ambiguity

JuktoError adds http_status, provider_error_code, request_id, retry_after, outcome
and reconciliation_required. Legacy status_code remains unchanged for compatibility,
including its historical mixture of application and HTTP codes. New code should
use the separate fields. HTTP status comes from the final observed response;
application codes come only from existing adapter envelopes, retaining original
numeric/string representation. HTTP errors without such a field have no provider
code. Request ID uses the response's X-Request-ID when supplied, and Retry-After is
retained as the original header string, not parsed into an automatic delay. Neither
header's presence or vendor support is guaranteed; unknown provider code semantics
remain unknown. Header values and response bodies are excluded from exception
str/repr. Request-local context isolates metadata between threads and clears it
before each attempt so a final timeout cannot inherit an earlier 401's headers.

When a shipment/SMS POST was attempted, a timeout, connection failure, 5xx or malformed
response conservatively sets UNKNOWN and reconciliation_required. This flag means
reconcile with the provider, not blindly resend or switch providers. Authentication
exchange alone and read-only calls do not count as shipment/SMS attempts. Published
AlphaSMS rejection codes in HTTP 200 responses establish FAILED, except server code 409 and unknown codes.
GreenWeb batch errors expose all outcomes; unknown entries require reconciliation.
Other vendor rejection/idempotency guarantees remain unverified and therefore do
not clear uncertainty. A local validation/configuration error before sending does
not require reconciliation. No automatic retry, backoff, failover or deduplication
was added. Applications must persist operation references and provider evidence,
query their provider/dashboard after ambiguous outcomes, and apply their own durable
deduplication/reconciliation policies. References are not provider idempotency keys.

### Options, capabilities and monetary values

Parcel accepts optional PathaoOptions and RedXOptions. Typed options take precedence
over legacy flat fields for their own provider only. PathaoOptions scopes store,
city/zone/area and delivery/item type; RedXOptions scopes area name/ID and pickup
store. Legacy fields still work when the corresponding options object is absent.
capabilities describes the SDK's implemented operations/options, not production
certification, cross-provider interchangeability or delivery-status verification.
Only RedX exposes verified declared-value fields in the current adapter; only
GreenWeb exposes per-recipient submission output. No geography translation occurs.

Monetary input annotations accept Decimal, plus int/float for backward compatibility.
Use Decimal constructed from a decimal string for new integrations. Validation
compares finite, nonnegative Decimal values without converting through binary float.
For RedX, Decimal amounts are serialized as exact fixed-point strings per the
published create table. Existing int/float JSON number serialization is retained
as explicit legacy compatibility. The RedX table and curl examples disagree on
accepted number/string types; actual acceptance and monetary precision still need
vendor confirmation. Pathao/Steadfast Decimal integers serialize as exact JSON
integers; fractional Decimals fail locally until a lossless supported wire format
is verified. Legacy floats retain their previous serialization and binary-float
limitations. No currency, rounding, decimal scale or minor-unit conversion is guessed.
Nonzero declared goods value can remain independent of zero COD.

The package includes py.typed and a mypy development dependency/configuration. Run
`python -m mypy` to check the SDK and normalized consumer example. The SMS interface
now truthfully permits raw dictionary/list/string results; HTTP status handlers
are annotated NoReturn. These checks do not certify every raw provider dictionary:
the raw escape hatch deliberately uses Any. Multi-version CI, wheel installation
checks and publication gates remain the next CI/release task (currently task 10 in
the local checklist).

## SDK capabilities and verification summary

This summary describes implemented methods, not independently certified provider
behavior. Detailed evidence and dates are in the table above and task audit notes.
All clients are synchronous; payments, delivery receipt processors and generic
side-effect retries are not implemented.

| Provider | SDK operations/options | Normalized semantics and unresolved contracts |
| --- | --- | --- |
| Steadfast | Shipment creation/status | Creation and polling UNKNOWN; endpoint/schema and status vocabulary unverified |
| Pathao | Shipment creation/status, store/geography options, process-local OAuth lifecycle | Creation with ID ACCEPTED; polling UNKNOWN; provider-maintained DTO evidence supports omission of absent geography, but full error/status/replay guarantees remain unverified |
| RedX | Shipment creation/status, area options, declared value | Documented create fields/auth and typed parcel-info path; creation with ID ACCEPTED, polling UNKNOWN; exact weight units/types, Decimal wire acceptance and legacy raw tracking unresolved |
| AlphaSMS | SMS submission | Published code 0 plus request ID ACCEPTED; audited failure codes; no delivery confirmation API |
| GreenWeb | SMS submission and per-response-entry outcomes | SENT is ACCEPTED submission; FAILED/unknown preserved; partial batches raise SMSBatchError; request/response ordering and legacy standalone text-error mappings unresolved |
| BulkSMSBD | Legacy SMS submission | Legacy code 202 UNKNOWN; application-code meanings and HTTPS POST support unresolved; default HTTP refused |

`provider.capabilities` exposes SDK method availability, including shipment/SMS,
per-recipient submission, geography options and declared value. It does not certify
provider constraints, routing validity, delivery status or idempotency. See the
[logistics guide](guides/logistics.md) and [SMS guide](guides/sms.md) before adopting
these capabilities in an application.

## Native async additions (task 12, 0.1.0a1 alpha)

The six `Async*Client` classes share the same pure payload builders, response
parsers, classifications and normalized result helpers as sync clients. All
verification gaps above apply equally to async operations. No new provider
endpoint, success vocabulary or idempotency guarantee was inferred for this task.
See [native async](guides/async.md) for asyncio scope, cancellation and lifecycle.

## First payment adapter (task 13, experimental alpha)

SSLCOMMERZ hosted BDT checkout is the only payment integration. Sync/async clients
share audited parsers and validation. See the [separate payment contract matrix](payment-contracts.md)
for official v4/signature provenance, requirements and unresolved sandbox/refund
contracts. No live compatibility or provider idempotency is certified. Standalone
bKash/Nagad remain planned.
