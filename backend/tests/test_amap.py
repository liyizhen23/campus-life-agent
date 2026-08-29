import httpx
import pytest

from app.amap import AmapClient, AmapError


@pytest.mark.asyncio
async def test_amap_error_preserves_business_error_code_without_request_secrets():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "0", "info": "DAILY_QUERY_OVER_LIMIT", "infocode": "10003"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = AmapClient(http, "secret-value-must-not-appear")
        with pytest.raises(AmapError) as raised:
            await client.route((116.3, 40.0), (116.31, 40.01), "walking")

    assert raised.value.code == "10003"
    assert raised.value.operation == "/v3/direction/walking"
    assert "10003" in raised.value.public_detail
    assert "secret-value-must-not-appear" not in str(raised.value)


@pytest.mark.asyncio
async def test_route_without_paths_is_a_diagnosable_failure():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "1", "route": {"paths": []}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = AmapClient(http, "not-a-real-key")
        with pytest.raises(AmapError) as raised:
            await client.route((116.3, 40.0), (116.31, 40.01), "walking")

    assert raised.value.code == "NO_ROUTE"
