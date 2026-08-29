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

    @field_validator("categories", "keywords", "preferences", mode="before")
    @classmethod
    def normalize_string_lists(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
        return value


class PlaceRecommendation(BaseModel):
    poi_id: str
    name: str
    category: str
    address: str
    longitude: float
    latitude: float
    straight_distance_meters: int | None = None
    route_distance_meters: int | None = None
    route_duration_minutes: int | None = None
    rating: float | None = None
    cost_per_person: float | None = None
    tags: list[str] = Field(default_factory=list)
    score: float
    navigation_url: str


class RecommendationResponse(BaseModel):
    origin: dict[str, float | str]
    transport: TransportMode
    radius_meters: int
    places: list[PlaceRecommendation]
    warnings: list[str] = Field(default_factory=list)

