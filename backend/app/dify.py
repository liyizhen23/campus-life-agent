from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from .config import Settings
from .models import ChatRequest


class DifyError(RuntimeError):
    pass


async def stream_chat(
    payload: ChatRequest,
    http: httpx.AsyncClient,
    settings: Settings,
) -> AsyncIterator[bytes]:
    if not settings.dify_api_key:
        raise DifyError("DIFY_API_KEY 尚未配置")

    longitude = payload.longitude if payload.longitude is not None else settings.default_longitude
    latitude = payload.latitude if payload.latitude is not None else settings.default_latitude
    request_body = {
        "inputs": {
            "longitude": f"{longitude:.6f}",
            "latitude": f"{latitude:.6f}",
            "coordinate_system": payload.coordinate_system,
            "location_accuracy": str(payload.accuracy or ""),
            "fallback_location_name": settings.default_location_name,
        },
        "query": payload.query,
        "response_mode": "streaming",
        "conversation_id": payload.conversation_id,
        "user": payload.user,
        "files": [],
    }
    request = http.build_request(
        "POST",
        f"{settings.dify_api_base_url.rstrip('/')}/chat-messages",
        headers={
            "Authorization": f"Bearer {settings.dify_api_key}",
            "Content-Type": "application/json",
        },
        json=request_body,
    )
    response = await http.send(request, stream=True)
    if response.status_code >= 400:
        body = await response.aread()
        await response.aclose()
        try:
            detail = json.loads(body).get("message")
        except (json.JSONDecodeError, AttributeError):
            detail = body.decode("utf-8", errors="replace")
        raise DifyError(detail or f"Dify 返回 HTTP {response.status_code}")

    try:
        async for chunk in response.aiter_bytes():
            yield chunk
    finally:
        await response.aclose()

