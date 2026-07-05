import os
import json
import uuid
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

# 環境変数の読み込み（graphモジュールのインポート前に必須）
load_dotenv(dotenv_path="../.env")

from schemas import (
    GeneratePlanRequest,
    GeneratePlanResponse,
    GeneratePlanResponseData,
    TourStop,
    Destination,
    RefinePlanRequest,
)
from services import (
    get_current_weather,
    analyze_mood_with_gemini,
    fetch_nearby_places,
    calculate_route_times,
    generate_plan_with_gemini,
    refine_plan_with_gemini,
)
from graph.builder import compiled_graph
from langchain_core.messages import HumanMessage, AIMessage

app = FastAPI(title="WanderMind API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}

def _build_response_data(plan_result: dict, chosen_places: list[dict], weather_info, request_lat, request_lng, transportation, google_key) -> GeneratePlanResponseData:
    """共通のレスポンス構築ロジック（Directions API呼び出し含む）"""
    # 移動時間の計算 (現在地 -> Spot 1 -> Spot 2 ...)
    times = calculate_route_times(
        api_key=google_key,
        start_lat=request_lat,
        start_lng=request_lng,
        destinations=chosen_places,
        transportation=transportation
    )
    
    stops = []
    # plan_result["stops"] と chosen_places は対応している
    for idx, (stop_info, place) in enumerate(zip(plan_result.get("stops", []), chosen_places)):
        stops.append(TourStop(
            destination=Destination(**place),
            activity_proposal=stop_info["activity_proposal"],
            travel_time_to_next=times[idx] if idx < len(times) else None
        ))
        
    return GeneratePlanResponseData(
        plan_title=plan_result.get("plan_title", "お出かけプラン"),
        expected_emotion=plan_result.get("expected_emotion", ""),
        stops=stops,
        weather=weather_info
    )

@app.post("/api/v1/plans/generate", response_model=GeneratePlanResponse)
def generate_plan(request: GeneratePlanRequest):
    google_key = os.getenv("GOOGLE_MAPS_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not google_key or not gemini_key:
        raise HTTPException(status_code=500, detail="API Keys are not configured correctly.")

    # 1. 天気
    weather_info = get_current_weather(request.location.latitude, request.location.longitude)
    
    # 2. カテゴリ推測
    categories = analyze_mood_with_gemini(
        request.mood, weather_info, request.transportation, request.companion, request.budget, gemini_key
    )
    
    # 3. プレイス検索 (交通手段を渡して半径を変える)
    places_pool = []
    for cat in categories:
        places_pool.extend(fetch_nearby_places(
            lat=request.location.latitude,
            lng=request.location.longitude,
            api_key=google_key,
            category_type=cat,
            transportation=request.transportation
        ))
        
    if not places_pool:
        raise HTTPException(status_code=404, detail="条件に合致するスポットが見つかりませんでした。")
        
    # 4. プラン構築
    try:
        plan_result, chosen_places = generate_plan_with_gemini(
            mood=request.mood,
            free_time=request.free_time_minutes,
            weather_info=weather_info,
            transportation=request.transportation,
            companion=request.companion,
            budget=request.budget,
            places_pool=places_pool,
            api_key=gemini_key
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"プラン生成失敗: {str(e)}")
        
    # 5. レスポンス構築
    response_data = _build_response_data(
        plan_result, chosen_places, weather_info, 
        request.location.latitude, request.location.longitude, 
        request.transportation, google_key
    )
    
    return GeneratePlanResponse(status="success", data=response_data)


@app.post("/api/v1/plans/refine", response_model=GeneratePlanResponse)
def refine_plan(request: RefinePlanRequest):
    google_key = os.getenv("GOOGLE_MAPS_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not google_key or not gemini_key:
        raise HTTPException(status_code=500, detail="API Keys are not configured correctly.")

    orig_req = request.original_request
    weather_info = request.previous_plan_data.weather
    
    # 検索をやり直して候補プールを作る（シンプル化のため再度fetch）
    categories = analyze_mood_with_gemini(
        orig_req.mood + " " + request.feedback_text, # フィードバックも加味
        weather_info, orig_req.transportation, orig_req.companion, orig_req.budget, gemini_key
    )
    
    places_pool = []
    for cat in categories:
        places_pool.extend(fetch_nearby_places(
            lat=orig_req.location.latitude,
            lng=orig_req.location.longitude,
            api_key=google_key,
            category_type=cat,
            transportation=orig_req.transportation
        ))
        
    if not places_pool:
        raise HTTPException(status_code=404, detail="再検索でスポットが見つかりませんでした。")
        
    # フィードバックによるプラン再生成
    previous_plan_json = request.previous_plan_data.model_dump_json()
    try:
        plan_result, chosen_places = refine_plan_with_gemini(
            feedback=request.feedback_text,
            original_mood=orig_req.mood,
            free_time=orig_req.free_time_minutes,
            transportation=orig_req.transportation,
            places_pool=places_pool,
            previous_plan_json=previous_plan_json,
            api_key=gemini_key
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"再生成失敗: {str(e)}")
        
    response_data = _build_response_data(
        plan_result, chosen_places, weather_info,
        orig_req.location.latitude, orig_req.location.longitude,
        orig_req.transportation, google_key
    )

    return GeneratePlanResponse(status="success", data=response_data)


# ============================================================
# 会話型チャット API（LangGraph）
# ============================================================

class StartChatRequest(BaseModel):
    message: str
    latitude: float
    longitude: float
    transportation: str = "transit"


class ContinueChatRequest(BaseModel):
    message: str
    # True: クイックリプライボタン由来（固定分類）/ False: 自由入力（Gemini function calling で意図解析）
    is_quick_reply: bool = False


class ChatResponse(BaseModel):
    thread_id: str
    message: str
    phase: str
    liked_spots: list[dict]
    route_info: Optional[dict] = None
    current_suggestion: Optional[dict] = None
    quick_replies: list[str] = []


@app.post("/api/v1/chat/session", response_model=ChatResponse)
def start_chat(request: StartChatRequest):
    """会話セッションを開始し、最初のスポット提案を返す。"""
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = compiled_graph.invoke(
            {
                "messages": [HumanMessage(content=request.message)],
                "phase": "start",
                "user_lat": request.latitude,
                "user_lng": request.longitude,
                "transportation": request.transportation,
                "initial_mood": "",
                "current_mood": "",
                "liked_spots": [],
                "suggested_place_ids": [],
                "current_suggestion": None,
                "last_reaction": "",
                "last_mood_hint": "",
                "free_time_minutes": 90,
                "search_radius_m": 5000,
                "search_center_lat": request.latitude,
                "search_center_lng": request.longitude,
                "route_info": None,
                "weather": "",
                "rejected_spot_names": [],
                "consecutive_rejects": 0,
                "time_used_minutes": 0,
                "quick_replies": [],
                "candidate_spots": [],
            },
            config=config,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"グラフ実行エラー: {str(e)}")

    ai_msg = next(
        (m for m in reversed(result["messages"]) if isinstance(m, AIMessage)), None
    )
    return ChatResponse(
        thread_id=thread_id,
        message=ai_msg.content if ai_msg else "こんにちは！どんな気分ですか？",
        phase=result.get("phase", "collecting"),
        liked_spots=result.get("liked_spots", []),
        route_info=result.get("route_info"),
        current_suggestion=result.get("current_suggestion"),
        quick_replies=result.get("quick_replies") or [],
    )


class ChatHistoryResponse(BaseModel):
    thread_id: str
    messages: list[dict]
    phase: str
    liked_spots: list[dict]
    route_info: Optional[dict] = None
    current_suggestion: Optional[dict] = None
    quick_replies: list[str] = []
    transportation: str = "walking"


@app.get("/api/v1/chat/{thread_id}", response_model=ChatHistoryResponse)
def get_chat_history(thread_id: str):
    """セッション復元用: スレッドの会話履歴と状態を返す。"""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = compiled_graph.get_state(config)
    state = snapshot.values
    if not state:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")

    messages = [
        {"role": "ai" if isinstance(m, AIMessage) else "user", "content": m.content}
        for m in state.get("messages", [])
    ]
    return ChatHistoryResponse(
        thread_id=thread_id,
        messages=messages,
        phase=state.get("phase", "collecting"),
        liked_spots=state.get("liked_spots", []),
        route_info=state.get("route_info"),
        current_suggestion=state.get("current_suggestion"),
        quick_replies=state.get("quick_replies") or [],
        transportation=state.get("transportation", "walking"),
    )


class RemoveSpotResponse(BaseModel):
    liked_spots: list[dict]
    time_used_minutes: int


@app.delete("/api/v1/chat/{thread_id}/spots/{place_id}", response_model=RemoveSpotResponse)
def remove_liked_spot(thread_id: str, place_id: str):
    """承認済みスポットの取り消し。検索中心・残り時間も再計算する。"""
    from graph.nodes import _free_time_to_radius, _centroid

    config = {"configurable": {"thread_id": thread_id}}
    snapshot = compiled_graph.get_state(config)
    state = snapshot.values
    if not state:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")

    liked = state.get("liked_spots", [])
    new_liked = [s for s in liked if s["place_id"] != place_id]
    if len(new_liked) == len(liked):
        raise HTTPException(status_code=404, detail="スポットが見つかりません")

    time_used = sum(
        s.get("estimated_stay_minutes", 45) + (s.get("travel_time_minutes") or 0)
        for s in new_liked
    )
    base_radius = _free_time_to_radius(state.get("free_time_minutes", 90))
    if new_liked:
        clat, clng = _centroid(new_liked)
        radius = max(1500, int(base_radius * (0.85 ** (len(new_liked) - 1))))
    else:
        clat, clng = state["user_lat"], state["user_lng"]
        radius = base_radius

    compiled_graph.update_state(
        config,
        {
            "liked_spots": new_liked,
            "time_used_minutes": time_used,
            "search_center_lat": clat,
            "search_center_lng": clng,
            "search_radius_m": radius,
            "candidate_spots": [],
        },
        as_node="spot_accumulator",
    )
    return RemoveSpotResponse(liked_spots=new_liked, time_used_minutes=time_used)


@app.post("/api/v1/chat/{thread_id}", response_model=ChatResponse)
def continue_chat(thread_id: str, request: ContinueChatRequest):
    """既存セッションにメッセージを送り、次のAI応答を返す。"""
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = compiled_graph.invoke(
            {
                "messages": [HumanMessage(content=request.message)],
                "is_quick_reply": request.is_quick_reply,
            },
            config=config,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"グラフ実行エラー: {str(e)}")

    ai_msg = next(
        (m for m in reversed(result["messages"]) if isinstance(m, AIMessage)), None
    )
    return ChatResponse(
        thread_id=thread_id,
        message=ai_msg.content if ai_msg else "もう一度言ってもらえる？",
        phase=result.get("phase", "collecting"),
        liked_spots=result.get("liked_spots", []),
        route_info=result.get("route_info"),
        current_suggestion=result.get("current_suggestion"),
        quick_replies=result.get("quick_replies") or [],
    )
