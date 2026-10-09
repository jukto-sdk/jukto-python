# Provider contract audit

Audit date: **2026-10-10**. Verification means comparison with retrievable official documentation, not a live API transaction. No credentials, SMS submissions, shipment creation, or captured production responses were used. Unknown means unresolved, not supported by inference from existing mocks or third-party wrappers.

## Evidence and current implementation matrix

Paths below are relative to the base URL. Unless explicitly marked verified, these are **implementation inventory**, not claims about upstream behavior. Last independently verified date is “unverified” where no authoritative specification was retrieved.

| Provider | SDK endpoints | SDK request fields/auth | SDK response handling | Official evidence and last verification |
| --- | --- | --- | --- | --- |
| AlphaSMS | `https://api.sms.net.bd/sendsms` | Form `api_key`, `msg`, `to`, optional `sender_id` | Object with `error`; documented success 0 and `data.request_id`; documented failures below | [Official API](https://sms.bd/api), 2026-10-10; verified published contract only |
| BulkSMSBD | `http://bulksmsbd.net/api/smsapi` | Form `api_key`, `type`, `number`, `senderid`, `message` | Integer `response_code`; legacy success 202 retained; all other integers raise generic ProviderError | [Provider site](https://bulksmsbd.net/) redirected to login; `/api` and `/api.php` retrieval failed; **unverified** |
| Steadfast | `https://portal.packzy.com/api/v1/create_order`, `/status_by_cid/{id}` | Headers Api-Key/Secret-Key; JSON invoice, recipient_name/phone/address, cod_amount, note | Raw JSON; integer body status >=400 mapped by adapter | [Official business page](https://steadfast.com.bd/business) confirms API offering, not this wire contract; **unverified** |
| Pathao | `https://api-hermes.pathao.com/aladdin/api/v1/issue-token`, `/orders`, `/orders/{id}/info`, `/stores`; sandbox host courier-api-sandbox.pathao.com | Token request client_id/secret and password or refresh grant; orders use Bearer auth and store_id, merchant_order_id, recipient fields/geography, delivery_type, item_type, special_instruction, item_quantity/weight, amount_to_collect | Token access_token/refresh_token/expires_in; resource responses returned raw | [Official developer panel](https://merchant.pathao.com/courier/developer-api) returned JavaScript shell; **unverified** |
| RedX | `https://openapi.redx.com.bd/v1.0.0-beta/parcels`, `/parcels/tracking/{id}`; sandbox host sandbox.redx.com.bd | Bearer; JSON customer_name/phone/address, delivery_area, merchant_invoice_id, cash_collection_amount, parcel_weight, instruction, value | Raw JSON; body status string error or integer >=400 interpreted by adapter | [Official OpenAPI host](https://openapi.redx.com.bd/) retrieval failed; [provider site](https://redx.com.bd/) exposed no specification; **unverified** |
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

## Unresolved RedX shipment contract

The current adapter places the full address into delivery_area, ignores recipient_area, multiplies item_weight by 1000, and sets value equal to COD. None of these choices was independently verified in this audit.

Obtain the official create-parcel schema defining geographic name/ID fields and lookup relationship, parcel_weight units/range/rounding, value meaning and requiredness, cash_collection_amount semantics, pickup-store requirements, response envelope, and error table. Do not invent delivery_area_id or change weight units based on unofficial examples. No RedX payload change was made; model/payload remediation belongs to task 6 once evidence is available.

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
