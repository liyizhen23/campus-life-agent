import hashlib
import hmac
import json

import pytest
from fastapi import HTTPException

from app.main import _travel_cards, _verified_route_points


def test_route_map_signature_limits_coordinates_without_exposing_secret():
    points = "116.326000,40.003000;116.330000,40.010000"
    secret = "test-secret"
    signature = hmac.new(
        secret.encode(), points.encode(), hashlib.sha256
    ).hexdigest()

    assert _verified_route_points(points, signature, secret) == [
        (116.326, 40.003),
        (116.33, 40.01),
    ]
    with pytest.raises(HTTPException):
        _verified_route_points(points, "bad-signature", secret)


def test_mcp_visual_cards_include_map_transport_and_only_https_images():
    payload = {
        "transport": "walking",
        "route_map_path": "/api/route-map?points=signed&sig=value",
        "itinerary": [
            {
                "from_name": "当前位置",
                "to_name": "测试公园",
                "route_duration_minutes": 12,
                "route_distance_meters": 800,
                "planning_duration_minutes": 12,
            }
        ],
        "places": [
            {
                "name": "测试]（不可信）",
                "image_urls": ["https://store.is.autonavi.com/photo.jpg"],
            },
            {"name": "坏图", "image_urls": ["javascript:alert(1)"]},
        ],
    }
    cards = _travel_cards(json.dumps(payload, ensure_ascii=False), "https://guide.example.com")

    assert "https://guide.example.com/api/route-map?" in cards
    assert "🚶 步行" in cards
    assert "https://store.is.autonavi.com/photo.jpg" in cards
    assert "javascript:" not in cards
