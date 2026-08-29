from typing import Literal

from pydantic import BaseModel, Field, field_validator


TransportMode = Literal["walking", "driving"]
CoordinateSystem = Literal["gps", "autonavi", "baidu", "mapbar"]


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    accuracy: float | None = Field(default=None, ge=0)
    coordinate_system: CoordinateSystem = "gps"
    conversation_id: str = ""
    user: str = Field(min_length=1, max_length=128)


class RecommendationRequest(BaseModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    coordinate_system: CoordinateSystem = "gps"
    categories: list[str] = Field(default_factory=lambda: ["美食"])
    keywords: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    budget_per_person: float | None = Field(default=None, ge=0, le=100000)
    radius_meters: int = Field(default=3000, ge=100, le=10000)
    transport: TransportMode = "walking"
    result_count: int = Field(default=3, ge=1, le=5)
    duration_minutes: int | None = Field(default=None, ge=15, le=1440)

    @field_validator("keywords", "preferences", mode="before")
    @classmethod
    def normalize_string_lists(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
        return value

    @field_validator("categories", mode="before")
    @classmethod
    def normalize_categories(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            value = [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
        if not isinstance(value, list):
            return value

        aliases = {
            "吃饭": ["美食"],
            "餐饮": ["美食"],
            "游玩": ["景点", "娱乐", "公园"],
            "玩乐": ["景点", "娱乐", "公园"],
        }
        normalized: list[str] = []
        for item in value:
            text = str(item).strip()
            for category in aliases.get(text, [text]):
                if category and category not in normalized:
                    normalized.append(category)
        return normalized


class PlaceRecommendation(BaseModel):
    poi_id: str
    name: str
    category: str
    address: str
    longitude: float
    latitude: float
    group: Literal["dining", "activity", "other"] = "other"
    route_from: str = "当前位置"
    route_status: Literal["available", "straight_line_only"] = "straight_line_only"
    straight_distance_meters: int | None = None
    route_distance_meters: int | None = None
    route_duration_minutes: int | None = None
    rating: float | None = None
    cost_per_person: float | None = None
    tags: list[str] = Field(default_factory=list)
    score: float
    navigation_url: str


class ItinerarySegment(BaseModel):
    from_name: str
    to_name: str
    transport: TransportMode
    route_status: Literal["available", "straight_line_only"]
    route_distance_meters: int | None = None
    route_duration_minutes: int | None = None
    straight_distance_meters: int | None = None


class RecommendationResponse(BaseModel):
    origin: dict[str, float | str]
    transport: TransportMode
    radius_meters: int
    duration_minutes: int | None = None
    places: list[PlaceRecommendation]
    itinerary: list[ItinerarySegment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
