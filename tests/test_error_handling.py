from json import JSONDecodeError
import unittest
from unittest.mock import patch, MagicMock
import httpx

from jukto import (
    SteadfastClient,
    GreenWebClient,
    Parcel,
    JuktoError,
    ProviderError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderTimeoutError,
    ProviderServerError,
    InvalidRequestError,
    ResourceNotFoundError,
    InsufficientBalanceError,
)


class TestSteadfastErrorHandling(unittest.TestCase):
    def setUp(self):
        self.client = SteadfastClient(api_key="test_key", secret_key="test_secret")
        self.sample_parcel = Parcel(
            invoice_id="INV-001",
            recipient_name="Rahim Uddin",
            recipient_phone="01700000000",
            recipient_address="Dhanmondi, Dhaka",
            cod_amount=500.0,
        )

    @patch("httpx.Client.request")
    def test_authentication_error_401(self, mock_request):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.json.return_value = {"status": 401, "message": "Invalid API Key"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )
        mock_request.return_value = mock_response

        with self.assertRaises(ProviderAuthenticationError) as ctx:
            self.client.create_order(self.sample_parcel)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.provider, "Steadfast")
        self.assertIsInstance(ctx.exception, JuktoError)

    @patch("httpx.Client.request")
    def test_invalid_request_400(self, mock_request):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {"status": 400, "message": "Phone number is invalid"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )
        mock_request.return_value = mock_response

        with self.assertRaises(InvalidRequestError) as ctx:
            self.client.create_order(self.sample_parcel)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertNotIn("Phone number is invalid", str(ctx.exception))
        self.assertEqual(ctx.exception.response_body["message"], "Phone number is invalid")

    @patch("httpx.Client.request")
    def test_resource_not_found_404(self, mock_request):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.json.return_value = {"status": 404, "message": "Consignment not found"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )
        mock_request.return_value = mock_response

        with self.assertRaises(ResourceNotFoundError):
            self.client.check_status("CID-99999")

    @patch("httpx.Client.request")
    def test_server_error_500(self, mock_request):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.json.side_effect = JSONDecodeError("Not JSON", "", 0)
        mock_response.text = "Internal Server Error"
        mock_response.reason_phrase = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )
        mock_request.return_value = mock_response

        with self.assertRaises(ProviderServerError):
            self.client.check_status("CID-12345")

    @patch("httpx.Client.request")
    def test_timeout_error(self, mock_request):
        mock_request.side_effect = httpx.TimeoutException("Connection timed out")

        with self.assertRaises(ProviderTimeoutError):
            self.client.check_status("CID-12345")

    @patch("httpx.Client.request")
    def test_inline_error_status_in_200(self, mock_request):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "status": 400,
            "message": "The recipient phone must be 11 digits.",
        }
        mock_request.return_value = mock_response

        with self.assertRaises(InvalidRequestError):
            self.client.create_order(self.sample_parcel)


class TestGreenWebErrorHandling(unittest.TestCase):
    def setUp(self):
        self.client = GreenWebClient(api_key="test_greenweb_token")

    @patch("httpx.Client.post")
    def test_invalid_token_text_response(self, mock_post):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.text = "Invalid Token"
        mock_response.json.side_effect = JSONDecodeError("Not JSON", "", 0)
        mock_response.headers = {}
        mock_post.return_value = mock_response

        with self.assertRaises(ProviderAuthenticationError) as ctx:
            self.client.send_sms("01700000000", "Hello BD!")

        self.assertEqual(ctx.exception.provider, "GreenWeb")

    @patch("httpx.Client.post")
    def test_insufficient_balance(self, mock_post):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.text = "SMS rate is greater than your account balance"
        mock_response.json.side_effect = JSONDecodeError("Not JSON", "", 0)
        mock_response.headers = {}
        mock_post.return_value = mock_response

        with self.assertRaises(InsufficientBalanceError):
            self.client.send_sms("01700000000", "Hello BD!")

    @patch("httpx.Client.post")
    def test_http_status_error_500(self, mock_post):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        mock_response.reason_phrase = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_post.return_value = mock_response

        with self.assertRaises(ProviderServerError):
            self.client.send_sms("01700000000", "Hello BD!")


if __name__ == "__main__":
    unittest.main()
