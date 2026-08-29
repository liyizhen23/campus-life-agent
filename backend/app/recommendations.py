from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlencode

from .amap import AmapClient, AmapError
from .models import (
    ItinerarySegment,
    PlaceRecommendation,
    RecommendationRequest,
    RecommendationResponse,
)


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
DINING_CATEGORIES = {"美食", "餐厅", "咖啡"}
ACTIVITY_CATEGORIES = {"购物", "娱乐", "电影", "景点", "公园"}


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


def _category_group(category: str) -> str:
    if category in DINING_CATEGORIES:
        return "dining"
    if category in ACTIVITY_CATEGORIES:
        return "activity"
    return "other"


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
            "from": f"{origin[0]:.6f},{origin[1]:.6f},当前位置",
            "to": f"{destination[0]:.6f},{destination[1]:.6f},{name}",
            "mode": "car" if mode == "driving" else "walk",
            "policy": 1 if mode == "driving" else 0,
            "src": "nearby-go",
            "coordinate": "gaode",
            "callnative": 1,
        }
    )
    return f"https://uri.amap.com/navigation?{query}"


def _prepare_candidates(
    pois: Iterable[dict[str, Any]], request: RecommendationRequest, group: str
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rank, poi in enumerate(pois):
        location = str(poi.get("location") or "")
        if "," not in location:
            continue
        try:
            lng, lat = (float(part) for part in location.split(",", maxsplit=1))
        except ValueError:
            continue
        identity = str(poi.get("id") or f"{lng:.6f},{lat:.6f}")
        if identity in seen:
            continue
        seen.add(identity)
        candidate = dict(poi)
        candidate["_lng"] = lng
        candidate["_lat"] = lat
        candidate["_group"] = group
        candidate["_score"] = _score_place(
            poi,
            request.radius_meters,
            request.budget_per_person if group == "dining" else None,
            request.preferences,
            rank,
        )
        candidates.append(candidate)
    candidates.sort(key=lambda item: item["_score"], reverse=True)
    return candidates


async def _search_group(
    amap: AmapClient,
    center: tuple[float, float],
    request: RecommendationRequest,
    categories: list[str],
    group: str,
) -> list[dict[str, Any]]:
    types = list(dict.fromkeys(CATEGORY_TYPES.get(item, "080000") for item in categories))
    collected: list[dict[str, Any]] = []

    # Explicit search words are attempted first. Soft preferences deliberately do not
    # become AMap keywords: they rank results but must not erase otherwise valid POIs.
    if request.keywords:
        collected.extend(
            await amap.search_around(
                *center,
                radius_meters=request.radius_meters,
                types=types,
                keywords=request.keywords,
                limit=20,
            )
        )
    if not request.keywords or len(collected) < request.result_count:
        collected.extend(
            await amap.search_around(
                *center,
                radius_meters=request.radius_meters,
                types=types,
                keywords=[],
                limit=20,
            )
        )
    return _prepare_candidates(collected, request, group)


def _select_diverse(
    candidates_by_group: dict[str, list[dict[str, Any]]], result_count: int
) -> list[dict[str, Any]]:
    nonempty = [group for group in ("dining", "activity", "other") if candidates_by_group[group]]
    target = min(5, max(result_count, len(nonempty)))
    if "dining" in nonempty and "activity" in nonempty:
        selected = [candidates_by_group["dining"][0], candidates_by_group["activity"][0]]
        # Extra stops should enrich the play portion rather than turn one itinerary
        # into a list of restaurant alternatives before the activity stop.
        remaining = [
            *candidates_by_group["activity"][1:],
            *candidates_by_group["other"],
            *candidates_by_group["dining"][1:],
        ]
        return [*selected, *remaining[: max(0, target - len(selected))]]

    selected = [candidates_by_group[group][0] for group in nonempty]
    remaining = [item for group in nonempty for item in candidates_by_group[group][1:]]
    remaining.sort(key=lambda item: item["_score"], reverse=True)
    selected.extend(remaining[: max(0, target - len(selected))])
    selected.sort(key=lambda item: item["_score"], reverse=True)
    return selected[:target]


async def build_recommendations(
    request: RecommendationRequest, amap: AmapClient
) -> RecommendationResponse:
    origin = await amap.convert_location(
        request.longitude, request.latitude, request.coordinate_system
    )
    categories_by_group = {"dining": [], "activity": [], "other": []}
    for category in request.categories or ["美食"]:
        group = _category_group(category)
        if category not in categories_by_group[group]:
            categories_by_group[group].append(category)

    candidates_by_group: dict[str, list[dict[str, Any]]] = {
        "dining": [],
        "activity": [],
        "other": [],
    }
    warnings: list[str] = []
    search_failures: list[AmapError] = []

    if categories_by_group["dining"]:
        try:
            candidates_by_group["dining"] = await _search_group(
                amap, origin, request, categories_by_group["dining"], "dining"
            )
        except AmapError as exc:
            search_failures.append(exc)

    # For a meal + activity request, anchor the second search at the best meal so
    # nearby POIs can form an actual ordered itinerary rather than unrelated options.
    activity_center = origin
    if candidates_by_group["dining"] and categories_by_group["activity"]:
        meal = candidates_by_group["dining"][0]
        activity_center = (meal["_lng"], meal["_lat"])

    for group in ("activity", "other"):
        if not categories_by_group[group]:
            continue
        try:
            candidates_by_group[group] = await _search_group(
                amap, activity_center if group == "activity" else origin, request,
                categories_by_group[group], group,
            )
        except AmapError as exc:
            search_failures.append(exc)

    if search_failures and not any(candidates_by_group.values()):
        raise search_failures[0]
    for failure in search_failures:
        warnings.append(f"部分分类暂时无法搜索：{failure.public_detail}。")

    selected = _select_diverse(candidates_by_group, request.result_count)
    route_failures: list[AmapError] = []
    results: list[PlaceRecommendation] = []
    itinerary: list[ItinerarySegment] = []
    segment_origin = origin
    segment_origin_name = "当前位置"
    is_itinerary = bool(candidates_by_group["dining"] and candidates_by_group["activity"])

    for poi in selected:
        destination = (poi["_lng"], poi["_lat"])
        route = None
        try:
            route = await amap.route(segment_origin if is_itinerary else origin, destination, request.transport)
        except AmapError as exc:
            route_failures.append(exc)

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
        name = _text(poi.get("name")) or "未命名地点"
        route_from = segment_origin_name if is_itinerary else "当前位置"
        result = PlaceRecommendation(
            poi_id=str(poi.get("id") or ""),
            name=name,
            category=_text(poi.get("type")),
            address=_text(poi.get("address")),
            longitude=poi["_lng"],
            latitude=poi["_lat"],
            group=poi["_group"],
            route_from=route_from,
            route_status="available" if route else "straight_line_only",
            straight_distance_meters=int(straight_distance) if straight_distance is not None else None,
            route_distance_meters=route_distance,
            route_duration_minutes=route_duration,
            rating=_number(biz_ext.get("rating")),
            cost_per_person=_number(biz_ext.get("cost")),
            tags=tags[:6],
            score=score,
            navigation_url=_navigation_url(
                segment_origin if is_itinerary else origin, destination, name, request.transport
            ),
        )
        results.append(result)
        itinerary.append(
            ItinerarySegment(
                from_name=route_from,
                to_name=name,
                transport=request.transport,
                route_status=result.route_status,
                route_distance_meters=route_distance,
                route_duration_minutes=route_duration,
                straight_distance_meters=result.straight_distance_meters,
            )
        )
        if is_itinerary:
            segment_origin = destination
            segment_origin_name = name

    if not results:
        warnings.append("当前位置和筛选条件下未找到合适地点，请扩大范围或减少限制。")
    if any(item.rating is None for item in results):
        warnings.append("部分地点缺少评分；推荐未将缺失评分视为真实低分。")
    if route_failures:
        codes = list(dict.fromkeys(item.code for item in route_failures if item.code))
        code_hint = f"（错误码：{'、'.join(codes)}）" if codes else ""
        warnings.append(
            f"部分地点未取得实时路线{code_hint}；已保留地点，所示直线距离不是实际路线。"
        )

    return RecommendationResponse(
        origin={"longitude": origin[0], "latitude": origin[1], "coordinate_system": "autonavi"},
        transport=request.transport,
        radius_meters=request.radius_meters,
        duration_minutes=request.duration_minutes,
        places=results,
        itinerary=itinerary if is_itinerary else [],
        warnings=warnings,
    )
