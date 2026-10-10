# Django, FastAPI and dependency injection

These source-checkout examples make synchronous SMS submissions behind an
application boundary. Install the optional dependencies:

```bash
python -m pip install -e '.[dev,examples]'
python -m pytest tests/test_documentation_examples.py --no-cov
```

No credentials are read or HTTP requests made when importing the examples. Tests
inject a fake or HTTPX MockTransport. Real factories require your own AlphaSMS key;
never replace it with the synthetic test key for a live request. Framework
versions are resolved for each CI Python version; older Python environments may
resolve older framework releases. Check your framework's own supported-version
policy separately from Jukto's Python compatibility.

These endpoints demonstrate integration mechanics, not a complete messaging
service. Mount them inside your authenticated/authorized order workflow, enforce
consent and rate limits, and persist operation/outcome evidence before retrying.
Django's normal CSRF middleware should remain enabled. The examples deliberately
avoid logging or returning raw provider data; they do not implement durable
reconciliation storage or a delivery receipt processor.

## Shared application boundary

The consumer depends on `BaseSMSProvider`, makes exactly one attempt and returns
only outcome metadata. Empty inputs fail before submission. Provider phone/content
constraints still require separate validation against a verified specification.
Batch exceptions retain per-entry outcomes; ambiguous failures remain explicit.
HTTP 202 means the example processed a submission result, not guaranteed delivery.
HTTP 502 is not a safe-retry signal.

```python
--8<-- "examples/application.py"
```

## Django

Set `JUKTO_ALPHA_API_KEY = os.environ["JUKTO_ALPHA_API_KEY"]` in Django settings,
using your deployment's secret store. Mount `sms_view` in your URL configuration
with `path("sms", sms_view)`. A missing/empty key returns a safe configuration
error. This sync view blocks its request worker during SDK calls and closes a
request-owned provider on exit, including failure paths. It trades cross-request
pooling for simple ownership; use an explicitly managed worker-local lifetime if
you need reuse across requests. Do not hide initialization in `AppConfig.ready()`
without accounting for reload/fork and shutdown behavior.

[Django's view documentation](https://docs.djangoproject.com/en/5.2/topics/http/views/)
describes the request/response boundary.

```python
--8<-- "examples/django_view.py"
```

## FastAPI

Set `JUKTO_ALPHA_API_KEY` in your deployment environment. Run
`uvicorn examples.fastapi_app:app` from the source checkout. The factory runs at
lifespan startup and an absent key fails startup before serving requests. The
provider is reused across requests in one worker, then closed after serving ends.
Do not close it inside an individual request. Each process has a separate provider.

The route is a normal `def`, so FastAPI runs the blocking SDK operation in a worker
thread. Shutdown cleanup is also offloaded. For native awaited requests in the unreleased tree, use the
[async lifespan example](async.md). Follow FastAPI's
[lifespan](https://fastapi.tiangolo.com/advanced/events/) and
[sync/async guidance](https://fastapi.tiangolo.com/async/).

```python
--8<-- "examples/fastapi_app.py"
```

## Fake provider and offline request testing

This deterministic fake implements the same injection contract but its status
output is synthetic, not vendor evidence. Application tests can inject accepted,
unknown or partial outcomes and exceptions without opening a network connection.
Its call ledger records sensitive test inputs; do not log it in production.

```python
--8<-- "examples/fake_provider.py"
```

For FastAPI use `TestClient(create_app(lambda: fake))` as a context manager so
startup/shutdown run. For Django pass `make_sms_view(lambda: fake)` a
`RequestFactory` POST. The checked-in
[request tests](https://github.com/jukto-sdk/jukto-python/blob/main/tests/test_documentation_examples.py)
exercise both paths, configuration failures, partial/unknown results, one-attempt
timeouts, redacted output and ownership. Another test injects a real AlphaSMS
adapter with MockTransport to verify reuse and that borrowed clients stay open.
