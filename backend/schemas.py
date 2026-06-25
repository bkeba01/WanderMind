from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class SearchIntent(BaseModel):
    categories: list[str] = Field(description="Google Places APIのカテゴリ（例: cafe, park, restaurant, library, book_store, museum, movie_theater, aquarium, spa, tourist_attraction, amusement_park, bar, shopping_mall, clothing_store, zoo, art_gallery）。必ずこのリストのいずれかの文字列を最大2つまで出力してください。")


# --- Request Schemas ---

class Location(BaseModel):
    latitude: float
    longitude: float

class GeneratePlanRequest(BaseModel):
    mood: str = Field(..., description="ユーザーの今の気分")
    free_time_minutes: int = Field(..., description="空き時間（分）", gt=0)
    location: Location = Field(..., description="現在地の緯度経度")
    transportation: str = Field(..., description="交通手段（walk, driving, transitなど）")
    companion: str = Field(..., description="同伴者（solo, date, familyなど）")
    budget: str = Field(..., description="予算感（save, normal, splurgeなど）")

# --- Response Schemas ---

class Destination(BaseModel):
    place_id: str
    name: str
    address: str
    rating: float | str
    location: Location

class TourStop(BaseModel):
    destination: Destination
    activity_proposal: str = Field(..., description="その場所で何をして過ごすかの具体的な提案")
    travel_time_to_next: Optional[int] = Field(None, description="次の目的地までの移動時間（分）。最後のスポットの場合はNone")

class WeatherInfo(BaseModel):
    condition: str
    temperature: float

class GeneratePlanResponseData(BaseModel):
    plan_title: str
    expected_emotion: str
    stops: List[TourStop]
    weather: WeatherInfo

class GeneratePlanResponse(BaseModel):
    status: str
    data: GeneratePlanResponseData

# --- Feedback (Refine) Schema ---

class RefinePlanRequest(BaseModel):
    original_request: GeneratePlanRequest
    feedback_text: str = Field(..., description="ユーザーからの要望（例: 「カフェを変えて」「歩きたくない」など）")
    previous_plan_data: GeneratePlanResponseData

# --- LLM Output Schema (for Gemini Structured Outputs) ---

class OutboundStop(BaseModel):
    selected_place_id: str = Field(description="提示した候補リストの中から選んだスポットのplace_id")
    activity_proposal: str = Field(description="この場所で何をして過ごすかの具体的な提案")

class OutboundTourPlan(BaseModel):
    plan_title: str = Field(description="お出かけツアープランのタイトル")
    stops: List[OutboundStop] = Field(description="巡るスポットの順序リスト（最大3件まで）")
    expected_emotion: str = Field(description="このプランを終えたあとにユーザーが得られる感情")

