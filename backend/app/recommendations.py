from __future__ import annotations

import asyncio
import math
from typing import Any
from urllib.parse import urlencode

from .amap import AmapClient, AmapError
from .models import PlaceRecommendation, RecommendationRequest, RecommendationResponse


CATEGORY_TYPES = {
    "美食": "050000",
    "餐厅": "050000",
    "咖啡": "050500",
    "购物": "060000",
    "娱乐": "080000",
    "电影": "080600",
    "景点": "110000",
    "公园": "110100",
}


def _number(value: Any) -> float | None:
    try:
        if value in (None, "", []):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item)
    return str(value or "")


def _score_place(
    poi: dict[str, Any], radius: int, budget: float | None, preferences: list[str], rank: int
) -> float:
    distance = _number(poi.get("distance")) or radius
    distance_score = max(0.0, 1 - distance / max(radius, 1))

    biz_ext = poi.get("biz_ext") if isinstance(poi.get("biz_ext"), dict) else {}
    rating = _number(biz_ext.get("rating"))
    rating_score = rating / 5 if rating is not None else 0.5

    cost = _number(biz_ext.get("cost"))
    if budget is None or cost is None:
        budget_score = 0.5
    elif cost <= budget:
        budget_score = 1.0
    else:
        budget_score = max(0.0, 1 - (cost - budget) / max(budget, 1))

    searchable = " ".join(
        [_text(poi.get("name")), _text(poi.get("tag")), _text(poi.get("type"))]
    ).lower()
    preference_score = (
        sum(1 for item in preferences if item.lower() in searchable) / len(preferences)
        if preferences
        else 0.5
    )
    source_rank_score = max(0.0, 1 - rank / 20)
    return round(
        100
        * (
            0.35 * distance_score
            + 0.20 * rating_score
            + 0.20 * budget_score
            + 0.15 * preference_score
            + 0.10 * source_rank_score
        ),
        1,
    )


def _navigation_url(
    origin: tuple[float, float], destination: tuple[float, float], name: str, mode: str
) -> str:
    query = urlencode(
        {
            "from": f"{origin[0]},{origin[1]},当前位置",
            "to": f"{destination[0]},{destination[1]},{name}",
            "mode": "car" if mode == "driving" else "walk",
            "policy": 1,
            "src": "nearby-go",
            "callnative": 1,
        }
    )
    return f"https://uri.amap.com/navigation?{query}"


async def build_recommendations(
    request: RecommendationRequest, amap: AmapClient
) -> RecommendationResponse:
    origin = await amap.convert_location(
        request.longitude, request.latitude, request.coordinate_system
    )
    types = list(
        dict.fromkeys(CATEGORY_TYPES.get(category, "080000") for category in request.categories)
    )
    keywords = list(dict.fromkeys([*request.keywords, *request.preferences]))
    pois = await amap.search_around(
        *origin,
        radius_meters=request.radius_meters,
        types=types,
        keywords=keywords,
        limit=20,
    )

    candidates: list[dict[str, Any]] = []
    for rank, poi in enumerate(pois):
        location = str(poi.get("location") or "")
        if "," not in location:
            continue
        try:
            lng, lat = (float(part) for part in location.split(",", maxsplit=1))
        except ValueError:
            continue
        candidate = dict(poi)
        candidate["_lng"] = lng
        candidate["_lat"] = lat
        candidate["_score"] = _score_place(
            poi,
            request.radius_meters,
            request.budget_per_person,
            request.preferences,
            rank,
        )
        candidates.append(candidate)

    candidates.sort(key=lambda item: item["_score"], reverse=True)
    route_candidates = candidates[: min(8, len(candidates))]

    async def fetch_route(poi: dict[str, Any]) -> dict[str, int] | None:
        try:
            return await amap.route(origin, (poi["_lng"], poi["_lat"]), request.transport)
        except AmapError:
            return None

    routes = await asyncio.gather(*(fetch_route(poi) for poi in route_candidates))

    results: list[PlaceRecommendation] = []
    for poi, route in zip(route_candidates, routes, strict=True):
        biz_ext = poi.get("biz_ext") if isinstance(poi.get("biz_ext"), dict) else {}
        tag_text = _text(poi.get("tag"))
        tags = [item.strip() for item in tag_text.replace("，", ",").split(",") if item.strip()]
        straight_distance = _number(poi.get("distance"))
        route_distance = route["distance"] if route else None
        route_duration = math.ceil(route["duration"] / 60) if route else None
        score = poi["_score"]
        if route_duration is not None:
            route_score = max(0.0, 1 - route_duration / 60)
            score = round(0.8 * score + 20 * route_score, 1)
        results.append(
            PlaceRecommendation(
                poi_id=str(poi.get("id") or ""),
                name=_text(poi.get("name")) or "未命名地点",
                category=_text(poi.get("type")),
                address=_text(poi.get("address")),
                longitude=poi["_lng"],
                latitude=poi["_lat"],
                straight_distance_meters=int(straight_distance) if straight_distance else None,
                route_distance_meters=route_distance,
                route_duration_minutes=route_duration,
                rating=_number(biz_ext.get("rating")),
                cost_per_person=_number(biz_ext.get("cost")),
                tags=tags[:6],
                score=score,
                navigation_url=_navigation_url(
                    origin, (poi["_lng"], poi["_lat"]), _text(poi.get("name")), request.transport
                ),
            )
        )

    results.sort(key=lambda item: item.score, reverse=True)
    warnings: list[str] = []
    if not results:
        warnings.append("当前位置和筛选条件下未找到合适地点，请扩大范围或减少限制。")
    if any(item.rating is None for item in results):
        warnings.append("部分地点缺少评分；推荐未将缺失评分视为真实低分。")
    if any(item.route_duration_minutes is None for item in results):
        warnings.append("部分地点未取得实时路线，展示距离仅供参考。")

    return RecommendationResponse(
        origin={"longitude": origin[0], "latitude": origin[1], "coordinate_system": "autonavi"},
        transport=request.transport,
        radius_meters=request.radius_meters,
        places=results[: request.result_count],
        warnings=warnings,
    )
