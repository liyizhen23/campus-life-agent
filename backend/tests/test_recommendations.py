from urllib.parse import parse_qs, urlparse

import pytest

from app.amap import AmapError
from app.models import RecommendationRequest
from app.recommendations import build_recommendations


DINING_POIS = [
    {
        "id": "food-1",
        "name": "测试川菜馆 <不可信>",
        "type": "餐饮服务;中餐厅;川菜",
        "address": "测试路1号",
        "location": "116.330000,40.010000",
        "distance": "600",
        "tag": "辣,适合聚餐",
        "biz_ext": {"rating": "4.7", "cost": "58"},
    },
    {
        "id": "food-2",
        "name": "较远餐厅",
        "type": "餐饮服务;中餐厅",
        "address": "测试路2号",
        "location": "116.350000,40.020000",
        "distance": "2400",
        "biz_ext": {"rating": "4.0", "cost": "120"},
    },
]

ACTIVITY_POIS = [
    {
        "id": "play-1",
        "name": "湖畔公园",
        "type": "风景名胜;公园广场;公园",
        "address": "游玩路8号",
        "location": "116.335000,40.012000",
        "distance": "480",
        "tag": "散步,风景",
        "biz_ext": {"rating": "4.6"},
    }
]


class FakeAmap:
    def __init__(self):
        self.searches = []
        self.routes = []

    async def convert_location(self, longitude, latitude, coordinate_system):
        return longitude + 0.001, latitude + 0.001

    async def search_around(self, longitude, latitude, **kwargs):
        self.searches.append(((longitude, latitude), kwargs))
        types = kwargs["types"]
        return ACTIVITY_POIS if any(item.startswith(("08", "11", "06")) for item in types) else DINING_POIS

    async def route(self, origin, destination, mode):
        self.routes.append((origin, destination, mode))
        return {"distance": 800, "duration": 720}


@pytest.mark.asyncio
async def test_build_recommendations_prefers_nearby_budget_match_and_safe_navigation_url():
    amap = FakeAmap()
    request = RecommendationRequest(
        longitude=116.326,
        latitude=40.003,
        coordinate_system="autonavi",
        categories=["美食"],
        preferences=["辣"],
        budget_per_person=80,
        radius_meters=3000,
        result_count=2,
    )

    result = await build_recommendations(request, amap)

    assert result.places[0].name == "测试川菜馆 <不可信>"
    assert result.places[0].route_duration_minutes == 12
    assert result.places[0].route_status == "available"
    assert result.places[0].cost_per_person == 58
    query = parse_qs(urlparse(result.places[0].navigation_url).query)
    assert query["to"][0].endswith(",测试川菜馆 <不可信>")
    assert query["mode"] == ["walk"]
    assert query["coordinate"] == ["gaode"]
    assert query["callnative"] == ["1"]


@pytest.mark.asyncio
async def test_preferences_rank_but_do_not_become_hard_amap_keywords():
    amap = FakeAmap()
    await build_recommendations(
        RecommendationRequest(
            longitude=116.326,
            latitude=40.003,
            categories=["美食"],
            preferences=["安静"],
        ),
        amap,
    )

    assert amap.searches[0][1]["keywords"] == []


@pytest.mark.asyncio
async def test_meal_and_activity_are_searched_separately_and_form_segmented_itinerary():
    amap = FakeAmap()
    result = await build_recommendations(
        RecommendationRequest(
            longitude=116.326,
            latitude=40.003,
            coordinate_system="autonavi",
            categories=["吃饭", "游玩"],
            radius_meters=3000,
            result_count=2,
            duration_minutes=180,
        ),
        amap,
    )

    assert [place.group for place in result.places] == ["dining", "activity"]
    assert result.duration_minutes == 180
    assert amap.searches[0][0] == (116.327, 40.004)
    assert amap.searches[1][0] == (116.33, 40.01)
    assert result.itinerary[0].from_name == "当前位置"
    assert result.itinerary[1].from_name == result.places[0].name
    assert amap.routes[1][0] == (result.places[0].longitude, result.places[0].latitude)


@pytest.mark.asyncio
async def test_explicit_keyword_zero_results_falls_back_to_category_search():
    class KeywordFallbackAmap(FakeAmap):
        async def search_around(self, longitude, latitude, **kwargs):
            self.searches.append(((longitude, latitude), kwargs))
            return [] if kwargs["keywords"] else DINING_POIS

    amap = KeywordFallbackAmap()
    result = await build_recommendations(
        RecommendationRequest(
            longitude=116.326,
            latitude=40.003,
            categories=["美食"],
            keywords=["不存在的精确词"],
        ),
        amap,
    )

    assert len(amap.searches) == 2
    assert amap.searches[1][1]["keywords"] == []
    assert result.places


@pytest.mark.asyncio
async def test_route_failure_keeps_place_and_labels_straight_line_fallback():
    class RouteFailureAmap(FakeAmap):
        async def route(self, origin, destination, mode):
            raise AmapError("USER_DAILY_QUERY_OVER_LIMIT", operation="route", code="10044")

    result = await build_recommendations(
        RecommendationRequest(longitude=116.326, latitude=40.003), RouteFailureAmap()
    )

    assert result.places
    assert result.places[0].route_status == "straight_line_only"
    assert result.places[0].route_distance_meters is None
    assert result.places[0].straight_distance_meters == 600
    assert "直线距离不是实际路线" in result.warnings[-1]
    assert "10044" in result.warnings[-1]


@pytest.mark.asyncio
async def test_empty_search_returns_warning():
    class EmptyAmap(FakeAmap):
        async def search_around(self, *args, **kwargs):
            return []

    result = await build_recommendations(
        RecommendationRequest(longitude=116.326, latitude=40.003), EmptyAmap()
    )

    assert result.places == []
    assert "扩大范围" in result.warnings[0]
