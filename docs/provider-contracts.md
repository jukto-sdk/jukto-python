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
| GreenWeb | `https://api.greenweb.com.bd/api.php` | Form token, to, message, json | Text/JSON/list; heuristic text and status error inspection | [Official portal](https://api.greenweb.com.bd/) returned login page; **unverified** |

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
