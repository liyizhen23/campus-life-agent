import pytest

from app.models import RecommendationRequest
from app.recommendations import build_recommendations


class FakeAmap:
    async def convert_location(self, longitude, latitude, coordinate_system):
        return longitude + 0.001, latitude + 0.001

    async def search_around(self, *args, **kwargs):
        return [
            {
                "id": "poi-1",
                "name": "测试川菜馆",
                "type": "餐饮服务;中餐厅;川菜",
                "address": "测试路1号",
                "location": "116.330000,40.010000",
                "distance": "600",
                "tag": "辣,适合聚餐",
                "biz_ext": {"rating": "4.7", "cost": "58"},
            },
            {
                "id": "poi-2",
                "name": "较远餐厅",
                "type": "餐饮服务;中餐厅",
                "address": "测试路2号",
                "location": "116.350000,40.020000",
                "distance": "2400",
                "biz_ext": {"rating": "4.0", "cost": "120"},
            },
        ]

    async def route(self, origin, destination, mode):
        return {"distance": 800, "duration": 720} if destination[0] < 116.34 else {
            "distance": 3000,
            "duration": 2700,
        }


@pytest.mark.asyncio
async def test_build_recommendations_prefers_nearby_budget_match():
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

    result = await build_recommendations(request, FakeAmap())

    assert result.places[0].name == "测试川菜馆"
    assert result.places[0].route_duration_minutes == 12
    assert result.places[0].cost_per_person == 58
    assert result.places[0].navigation_url.startswith("https://uri.amap.com/navigation?")


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

