from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .amap import AmapClient, AmapError
from .config import Settings, get_settings
from .dify import DifyError, stream_chat
from .models import ChatRequest, RecommendationRequest, RecommendationResponse
from .recommendations import build_recommendations


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.http = httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        trust_env=False,
    )
    yield
    await app.state.http.aclose()


app = FastAPI(title="Campus Life Agent", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Internal-Token"],
)


def verify_internal_token(
    x_internal_token: str = Header(default=""),
    config: Settings = Depends(get_settings),
) -> None:
    if not config.internal_api_token or x_internal_token != config.internal_api_token:
        raise HTTPException(status_code=401, detail="无效的内部调用凭据")


@app.get("/api/health")
async def health(config: Settings = Depends(get_settings)) -> dict[str, object]:
    return {
        "status": "ok",
        "configured": {
            "dify": bool(config.dify_api_key),
            "amap": bool(config.amap_web_service_key),
            "internal_token": bool(config.internal_api_token),
        },
    }


@app.post("/api/chat")
async def chat(
    payload: ChatRequest,
    request: Request,
    config: Settings = Depends(get_settings),
) -> StreamingResponse:
    async def generate():
        try:
            async for chunk in stream_chat(payload, request.app.state.http, config):
                yield chunk
        except DifyError as exc:
            error_event = json.dumps(
                {"event": "error", "message": str(exc)}, ensure_ascii=False
            )
            yield f"data: {error_event}\n\n".encode()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post(
    "/api/recommendations",
    response_model=RecommendationResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def recommendations(
    payload: RecommendationRequest,
    request: Request,
    config: Settings = Depends(get_settings),
) -> RecommendationResponse:
    try:
        amap = AmapClient(request.app.state.http, config.amap_web_service_key)
        return await build_recommendations(payload, amap)
    except AmapError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
