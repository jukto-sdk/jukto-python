"""Run with an isolated wheel-only interpreter, from outside the checkout."""
from importlib import metadata, resources
from pathlib import Path
import asyncio
import sys

import httpx
import jukto


async def async_smoke() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"error": 0, "data": {"request_id": 123}}))) as client:
        async with jukto.AsyncAlphaSMSClient(api_key="synthetic-wheel-key", http_client=client) as provider:
            assert (await provider.submit_sms("01700000000", "offline wheel test")).status == jukto.Outcome.ACCEPTED
        assert not client.is_closed
    for name in ("AsyncPathaoClient", "AsyncRedXClient", "AsyncSteadfastClient", "AsyncGreenWebClient", "AsyncBulkSMSBDClient"):
        assert getattr(jukto, name)


def main() -> None:
    checkout = Path(sys.argv[1]).resolve()
    installed = Path(jukto.__file__).resolve()
    prefix = Path(sys.prefix).resolve()
    assert checkout not in installed.parents, f"imported checkout: {installed}"
    assert prefix in installed.parents, f"imported outside wheel environment: {installed}"
    assert resources.files("jukto").joinpath("py.typed").is_file()
    assert metadata.version("jukto") == sys.argv[2]
    # Public imports and an offline operation exercise runtime dependencies as well.
    assert jukto.Outcome.UNKNOWN.value == "unknown"
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"error": 0, "data": {"request_id": 123}}))) as client:
        provider = jukto.AlphaSMSClient(api_key="synthetic-wheel-key", http_client=client)
        assert provider.send_sms("01700000000", "offline wheel test")["data"]["request_id"] == 123
        provider.close()
        assert not client.is_closed
    asyncio.run(async_smoke())
    print(f"Wheel {metadata.version('jukto')} imported from {installed}")


if __name__ == "__main__":
    main()
