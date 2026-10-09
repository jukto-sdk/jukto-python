import logging
from jukto.logger import enable_debug_logging, mask_sensitive, logger


def test_enable_debug_logging():
    handler = enable_debug_logging(logging.DEBUG)
    assert handler is not None
    assert logger.level == logging.DEBUG


def test_mask_sensitive():
    payload = {
        "api_key": "secret_api_key_12345",
        "password": "my_password_secure",
        "recipient_name": "Mehedi",
        "nested": {
            "token": "bearer_jwt_token_abcdef",
            "cod_amount": 500,
        },
        "list_items": [
            {"client_secret": "top_secret_xyz"},
            {"item": "book"},
        ],
    }
    masked = mask_sensitive(payload)
    assert masked["recipient_name"] == "Mehedi"
    assert masked["api_key"] != "secret_api_key_12345"
    assert "..." in masked["api_key"]
    assert masked["nested"]["token"] != "bearer_jwt_token_abcdef"
    assert masked["nested"]["cod_amount"] == 500
    assert masked["list_items"][0]["client_secret"] != "top_secret_xyz"
    assert masked["list_items"][1]["item"] == "book"
