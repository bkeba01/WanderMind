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
    open_now: bool | None
    opening_hours_today: str | None


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
    weather: str                    # 例: "晴れ・曇り 24℃"
    rejected_spot_names: list[str]  # 拒否されたスポット名（クエリ生成で回避）
    consecutive_rejects: int        # 連続拒否回数（2以上で好みを聞き返す）
    time_used_minutes: int          # 承認済みスポットの滞在+移動の合計
    quick_replies: list[str]        # 最新提案に対する文脈クイックリプライ
    candidate_spots: list[Spot]     # 未提案の検索候補キャッシュ（REJECT 高速化）
    next_request_hint: str          # 会話から抽出した次の具体的要望（例:「夜ご飯」「休憩」）
    is_quick_reply: bool            # 今回のメッセージがボタン由来か（True: 固定分類 / False: LLM function calling）
