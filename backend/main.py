import os
import json
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from schemas import (
    GeneratePlanRequest, 
    GeneratePlanResponse, 
    GeneratePlanResponseData, 
    TourStop, 
    Destination,
    RefinePlanRequest
)
from services import (
    get_current_weather,
    analyze_mood_with_gemini,
    fetch_nearby_places,
    calculate_route_times,
    generate_plan_with_gemini,
    refine_plan_with_gemini
)

# 環境変数の読み込み
load_dotenv(dotenv_path="../.env")

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
