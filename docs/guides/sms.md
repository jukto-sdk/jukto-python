# SMS integration

Use `submit_sms(phone_or_list, message)` for `SMSSubmissionResult`; `send_sms`
retains its provider-specific raw representation. See [API reference](../api/sms.md).

## Credentials and recipient formats

AlphaSMS uses an API key, GreenWeb a token, and BulkSMSBD a key/sender ID. Keep
credentials in environment/settings, never checked-in examples. The SDK preserves
phone strings and joins lists for submission; it does not normalize international
prefixes or enforce a universal phone format. Provider format, batch-size,
encoding, sender approval and content restrictions must be checked independently.
The offline samples use synthetic `01700000000` with no subscriber validation.

BulkSMSBD's legacy HTTP default is rejected unless insecure transport is explicitly
allowed. HTTPS reachability does not verify HTTPS SMS POST support. Do not use the
insecure opt-in as a default quickstart; its codes and success semantics remain
unverified. See the [contract audit](../provider-contracts.md).

## Submission, partial results and delivery

AlphaSMS's documented successful submission maps to `ACCEPTED`; it does not verify
handset delivery. BulkSMSBD's legacy integer 202 remains `UNKNOWN`. GreenWeb's
structured `SENT` maps to accepted submission, `FAILED` to failure, and unrecognized
entries remain unknown. Mixed entries produce `PARTIAL`.

GreenWeb raises `SMSBatchError` for failed or unknown batch entries. Inspect its
`normalized_result` (or raw list-compatible `results`) before deciding what to do.
Do not resend the entire batch. `response_index` describes the response order;
recipient fields may be absent and ordering against the request is not guaranteed.
An unknown recipient requires reconciliation rather than index-based guessing.
The [application example](frameworks.md) converts results into safe response
metadata and preserves partial/unknown states, without returning recipient data.

`raw`, `results`, `recipient`, and vendor messages may contain personal data;
store evidence with access controls and retention limits. Unknown timeouts may
follow a successful submission, so retrying can duplicate SMS. Jukto does not
supply a delivery-receipt API or generic idempotency/failover mechanism.
