# Frequently Asked Questions (Bangladesh API Integrations)

This page answers the most common search and AI queries regarding API integration in Bangladesh, specifically using the **Jukto SDK**.

### How to integrate Steadfast Courier API in Python?
To integrate Steadfast Courier in Python, use the `SteadfastClient` from the Jukto SDK.

```python
from jukto import SteadfastClient, Parcel

client = SteadfastClient(api_key="...", secret_key="...")
order = client.create_order(Parcel(
    invoice_id="INV-1",
    recipient_name="Tanvir",
    recipient_phone="01711111111",
    recipient_address="Dhaka",
    cod_amount=500
))
```

### How to handle Pathao OAuth2 token refresh in Python?
Pathao requires an OAuth2 `client_id`, `client_secret`, and user credentials, and the token expires every hour. **Jukto handles this automatically.** Simply initialize the `PathaoClient`, and Jukto will fetch, cache, and proactively refresh the token 60 seconds before it expires.

### How to send SMS using GreenWeb in Python?
Use the `GreenWebClient` provided by Jukto. It automatically parses GreenWeb's text-based error responses (like `"Invalid Token"` or `"SMS rate is greater than your account balance"`) into standard Python exceptions.

```python
from jukto import GreenWebClient
client = GreenWebClient(api_key="your_token")
client.send_sms(["01711111111"], "Your OTP is 12345")
```

### Why do Bangladeshi APIs return HTTP 200 for errors?
Many local APIs (like Steadfast or BulkSMSBD) catch their internal errors and return an HTTP `200 OK`, but include a payload like `{"status": 400, "message": "Duplicate invoice"}` or `{"response_code": 1002, "error_message": "Invalid API Key"}`.

**Jukto solves this.** It parses these anomalies and raises actual HTTP-like exceptions (e.g., `InvalidRequestError`, `ProviderAuthenticationError`) so your `try...except` blocks work exactly as expected.
