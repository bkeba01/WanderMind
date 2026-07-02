from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages


class SpotBase(TypedDict):
    place_id: str
    name: str
    address: str
    rating: float | str
    location: dict  # {"latitude": float, "longitude": float}


class Spot(SpotBase, total=False):
    photo_url: str | None
    price_level: int | None
    editorial_summary: str | None
    review_snippets: list
    estimated_stay_minutes: int
    travel_time_minutes: int | None


class WanderMindState(TypedDict):
    messages: Annotated[list, add_messages]
    phase: Literal["start", "collecting", "done"]
    user_lat: float
    user_lng: float
    free_time_minutes: int
    transportation: str
    initial_mood: str
    current_mood: str
    liked_spots: list[Spot]
    suggested_place_ids: list[str]
    current_suggestion: Spot | None
    search_center_lat: float
    search_center_lng: float
    search_radius_m: int
    last_reaction: str
    last_mood_hint: str
    route_info: dict | None
