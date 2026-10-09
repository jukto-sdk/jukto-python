from jukto.exceptions import (
    JuktoError,
    JuktoValidationError,
    JuktoConfigurationError,
    ProviderError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderServerError,
    InvalidRequestError,
    ResourceNotFoundError,
    InsufficientBalanceError,
)


def test_exception_hierarchy():
    assert issubclass(ProviderError, JuktoError)
    assert issubclass(JuktoValidationError, JuktoError)
    assert issubclass(JuktoConfigurationError, JuktoError)
    assert issubclass(ProviderAuthenticationError, ProviderError)
    assert issubclass(ProviderConnectionError, ProviderError)
    assert issubclass(ProviderTimeoutError, ProviderConnectionError)
    assert issubclass(ProviderRateLimitError, ProviderError)
    assert issubclass(ProviderServerError, ProviderError)
    assert issubclass(InvalidRequestError, ProviderError)
    assert issubclass(ResourceNotFoundError, ProviderError)
    assert issubclass(InsufficientBalanceError, ProviderError)


def test_exception_attributes_and_string_representation():
    err = ProviderAuthenticationError(
        "Invalid API Key",
        status_code=401,
        response_body={"status": 401, "message": "Unauthorized"},
        provider="Steadfast",
    )
    assert err.status_code == 401
    assert err.provider == "Steadfast"
    assert err.response_body == {"status": 401, "message": "Unauthorized"}
    assert "Invalid API Key" in str(err)
    assert "provider=Steadfast" in str(err)
    assert "status_code=401" in str(err)
    assert "ProviderAuthenticationError" in repr(err)
