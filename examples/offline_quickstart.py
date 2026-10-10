"""An executable quickstart that cannot contact a real SMS gateway."""
import httpx
from jukto import AlphaSMSClient, SMSSubmissionResult


def run() -> SMSSubmissionResult:
    def reply(request: httpx.Request) -> httpx.Response:
        # Synthetic response matching the documented AlphaSMS success envelope.
        return httpx.Response(200, json={"error": 0, "data": {"request_id": 123}})

    with httpx.Client(transport=httpx.MockTransport(reply)) as http_client:
        with AlphaSMSClient(api_key="synthetic-example-key", http_client=http_client) as provider:
            result = provider.submit_sms("01700000000", "Synthetic offline message")
        assert not http_client.is_closed  # Borrowed client remains caller-owned.
    return result


if __name__ == "__main__":
    print(run().status.value)  # accepted means submitted, not delivered.
