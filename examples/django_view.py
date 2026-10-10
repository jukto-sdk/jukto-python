"""Sync Django view with request-owned provider lifetime and a factory injection seam."""
from __future__ import annotations
import json
from typing import Callable
from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST
from jukto import BaseSMSProvider, JuktoConfigurationError
from examples.application import alpha_client, notify


def configured_provider() -> BaseSMSProvider:
    return alpha_client(getattr(settings, "JUKTO_ALPHA_API_KEY", ""))


def make_sms_view(factory: Callable[[], BaseSMSProvider] = configured_provider) -> Callable[[HttpRequest], JsonResponse]:
    @require_POST
    def view(request: HttpRequest) -> JsonResponse:
        try:
            payload = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({"error": "invalid_json"}, status=400)
        try:
            # SDK calls block this sync request worker. Fresh provider per request,
            # closed even on validation or provider failures; no import-time network.
            with factory() as provider:
                body, status = notify(provider, payload)
        except JuktoConfigurationError:
            return JsonResponse({"error": "provider_configuration"}, status=503)
        return JsonResponse(body, status=status)
    return view


sms_view = make_sms_view()
