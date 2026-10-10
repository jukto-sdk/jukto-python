"""Exercise the documented application examples through offline request paths."""
import json
from pathlib import Path

import httpx
import pytest
from jukto import JuktoConfigurationError, Outcome, ProviderTimeoutError

ROOT = Path(__file__).resolve().parents[1]


def test_offline_quickstart():
    from examples.offline_quickstart import run
    assert run().status == Outcome.ACCEPTED


def test_configuration_fails_without_a_key_before_transport(monkeypatch):
    from examples.application import alpha_from_environment
    monkeypatch.delenv("JUKTO_ALPHA_API_KEY", raising=False)
    with pytest.raises(JuktoConfigurationError):
        alpha_from_environment()


@pytest.mark.parametrize("framework", ["django", "fastapi"])
@pytest.mark.parametrize("outcome", [Outcome.ACCEPTED, Outcome.UNKNOWN, Outcome.PARTIAL])
def test_request_paths_and_ownership(framework, outcome):
    from examples.fake_provider import FakeSMSProvider
    fake = FakeSMSProvider(outcome=outcome)
    response, status = request(framework, fake, {"phone": "01700000000", "message": "synthetic example"})
    assert status == 202
    assert response["status"] == outcome.value
    assert response["reconciliation_required"] == (outcome != Outcome.ACCEPTED)
    assert len(fake.calls) == 1
    assert fake.closed
    assert "synthetic example" not in json.dumps(response)


def request(framework, provider, payload):
    if framework == "fastapi":
        from fastapi.testclient import TestClient
        from examples.fastapi_app import create_app
        with TestClient(create_app(lambda: provider)) as client:
            response = client.post("/sms", json=payload)
        return response.json(), response.status_code
    from django.conf import settings
    if not settings.configured:
        settings.configure(DEFAULT_CHARSET="utf-8", SECRET_KEY="synthetic-test-only", USE_TZ=True)
    from django.test import RequestFactory
    from examples.django_view import make_sms_view
    response = make_sms_view(lambda: provider)(RequestFactory().post("/sms", data=json.dumps(payload), content_type="application/json"))
    return json.loads(response.content), response.status_code


@pytest.mark.parametrize("framework", ["django", "fastapi"])
def test_ambiguous_timeout_is_safe_and_does_not_retry(framework):
    from examples.fake_provider import FakeSMSProvider
    secret = "synthetic-upstream-secret"
    fake = FakeSMSProvider(error=ProviderTimeoutError(secret, reconciliation_required=True))
    response, status = request(framework, fake, {"phone": "01700000000", "message": "synthetic example"})
    assert status == 502
    assert response["reconciliation_required"] is True
    assert response["status"] == "unknown"
    assert secret not in json.dumps(response)
    assert len(fake.calls) == 1
    assert fake.closed


@pytest.mark.parametrize("framework", ["django", "fastapi"])
def test_invalid_input_never_calls_provider(framework):
    from examples.fake_provider import FakeSMSProvider
    fake = FakeSMSProvider()
    response, status = request(framework, fake, {"phone": "", "message": "synthetic example"})
    assert status == 400
    assert not fake.calls


def test_real_adapter_with_mock_transport_through_fastapi():
    from fastapi.testclient import TestClient
    from examples.fastapi_app import create_app
    from jukto import AlphaSMSClient
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"error": 0, "data": {"request_id": 123}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = AlphaSMSClient(api_key="synthetic-key", http_client=client)
        with TestClient(create_app(lambda: provider)) as app:
            for _ in range(2):
                assert app.post("/sms", json={"phone": "01700000000", "message": "synthetic example"}).status_code == 202
        assert len(requests) == 2
        assert not client.is_closed
        with pytest.raises(JuktoConfigurationError):
            provider.submit_sms("01700000000", "closed")


@pytest.mark.parametrize("framework", ["django", "fastapi"])
def test_partial_greenweb_batch_preserved_without_resending(framework):
    from jukto import GreenWebClient
    calls = []
    entries = [{"status": "SENT", "to": "01700000000"},
               {"status": "FAILED", "message": "synthetic-provider-secret"},
               {"status": "future-status"}]
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=entries)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response, status = request(framework, GreenWebClient(api_key="synthetic-key", http_client=client),
                                   {"phone": "01700000000", "message": "synthetic message"})
        assert not client.is_closed
    assert status == 202
    assert response["status"] == "partial"
    assert response["reconciliation_required"]
    assert [entry["status"] for entry in response["recipients"]] == ["accepted", "failed", "unknown"]
    assert len(calls) == 1
    assert "synthetic-provider-secret" not in json.dumps(response)
    assert "01700000000" not in json.dumps(response)


def test_django_malformed_json_and_method_do_not_construct_provider():
    from django.conf import settings
    if not settings.configured:
        settings.configure(DEFAULT_CHARSET="utf-8", SECRET_KEY="synthetic-test-only", USE_TZ=True)
    from django.test import RequestFactory
    from examples.django_view import make_sms_view
    calls = []
    view = make_sms_view(lambda: calls.append(True))
    assert view(RequestFactory().post("/sms", data="{invalid", content_type="application/json")).status_code == 400
    assert view(RequestFactory().get("/sms")).status_code == 405
    assert not calls


def test_fastapi_sync_operation_runs_outside_lifespan_thread():
    import threading
    from fastapi.testclient import TestClient
    from examples.fake_provider import FakeSMSProvider
    from examples.fastapi_app import create_app
    threads = {}
    class RecordingFake(FakeSMSProvider):
        def submit_sms(self, phone_numbers, message):
            threads["operation"] = threading.get_ident()
            return super().submit_sms(phone_numbers, message)
    fake = RecordingFake()
    def factory():
        threads["lifespan"] = threading.get_ident()
        return fake
    with TestClient(create_app(factory)) as client:
        assert client.post("/sms", json={"phone": "01700000000", "message": "synthetic"}).status_code == 202
    assert threads["operation"] != threads["lifespan"]
    assert fake.closed


def test_documentation_and_deployment_have_strict_gates():
    import yaml
    checks = yaml.load((ROOT / ".github/workflows/checks.yml").read_text(), Loader=yaml.BaseLoader)
    assert any(step.get("run") == "python -m mkdocs build --strict" for step in checks["jobs"]["check"]["steps"])
    deployment = yaml.load((ROOT / ".github/workflows/docs.yml").read_text(), Loader=yaml.BaseLoader)
    paths = deployment["on"]["push"]["paths"]
    assert {"examples/**", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md"}.issubset(paths)
    commands = "\n".join(step.get("run", "") for step in deployment["jobs"]["deploy"]["steps"])
    assert "mkdocs build --strict" in commands and "mkdocs gh-deploy --strict" in commands


@pytest.mark.parametrize("framework", ["django", "fastapi"])
def test_real_timeout_retains_ambiguity_and_never_replays(framework):
    from jukto import AlphaSMSClient
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("synthetic-secret-in-upstream-exception", request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response, status = request(framework, AlphaSMSClient(api_key="synthetic-key", http_client=client),
                                   {"phone": "01700000000", "message": "synthetic"})
        assert not client.is_closed
    assert status == 502 and response["reconciliation_required"]
    assert response["status"] == "unknown" and len(calls) == 1
    assert "synthetic-secret" not in json.dumps(response)


def test_fastapi_missing_key_fails_lifespan_startup(monkeypatch):
    from fastapi.testclient import TestClient
    from examples.fastapi_app import create_app
    monkeypatch.delenv("JUKTO_ALPHA_API_KEY", raising=False)
    with pytest.raises(JuktoConfigurationError):
        with TestClient(create_app()):
            pytest.fail("must not serve requests without configuration")


def test_django_missing_key_is_a_safe_configuration_response():
    from django.test import RequestFactory
    from examples.django_view import sms_view
    response = sms_view(RequestFactory().post("/sms", data=json.dumps({"phone": "01700000000", "message": "synthetic"}), content_type="application/json"))
    assert response.status_code == 503
    assert json.loads(response.content) == {"error": "provider_configuration"}
