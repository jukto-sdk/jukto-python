import logging
from jukto.logger import enable_debug_logging, mask_sensitive, logger


def test_enable_debug_logging():
    handler1 = enable_debug_logging(logging.DEBUG)
    assert handler1 is not None
    assert logger.level == logging.DEBUG

    # Call a second time to exercise the branch where handler already exists
    handler2 = enable_debug_logging(logging.INFO)
    assert handler2 is handler1
    assert logger.level == logging.INFO


def test_mask_sensitive():
    payload = {
        "api_key": "secret_api_key_12345",
        "password": "pwd",  # <= 6 chars to hit "***" branch
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
    # Test dictionary with sensitive keys
    masked = mask_sensitive(payload)
    assert masked["recipient_name"] == "Mehedi"
    assert masked["api_key"] != "secret_api_key_12345"
    assert masked["api_key"] == "***"
    assert masked["password"] == "***"
    assert masked["nested"]["token"] != "bearer_jwt_token_abcdef"
    assert masked["nested"]["cod_amount"] == 500
    assert masked["list_items"][0]["client_secret"] != "top_secret_xyz"
    assert masked["list_items"][1]["item"] == "book"

    # Test top-level list
    masked_list = mask_sensitive([{"api_key": "123456789"}])
    assert masked_list[0]["api_key"] == "***"

    # Test scalar string (to hit scalar return data branch)
    assert mask_sensitive("simple_scalar") == "simple_scalar"
    assert mask_sensitive(12345) == 12345
