import os
import json
import requests
from google import genai
from google.genai import types
from schemas import OutboundTourPlan, WeatherInfo, SearchIntent

# ==========================================
# 1. 天気APIの取得 (Open-Meteo)
# ==========================================
def get_current_weather(lat: float, lng: float) -> WeatherInfo:
    print(f"🌤️ [FETCH] 現在地の天気を取得中... (lat={lat}, lng={lng})")
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current_weather=true"
    try:
        res = requests.get(url, timeout=5).json()
        code = res.get("current_weather", {}).get("weathercode", 0)
        temp = res.get("current_weather", {}).get("temperature", 20.0)
        weather_condition = "雨・荒天" if code in [51,53,55,61,63,65,71,73,75,80,81,82,95,96,99] else "晴れ・曇り"
        print(f"✅ [SUCCESS] 天気: {weather_condition}, 気温: {temp}°C")
        return WeatherInfo(condition=weather_condition, temperature=temp)
    except Exception as e:
        print(f"⚠️ [WARN] 天気APIの取得に失敗しました(デフォルト値を使用): {e}")
        return WeatherInfo(condition="晴れ・曇り", temperature=20.0)

# ==========================================
# 2. Google Places API (New) の実行
# ==========================================
def fetch_nearby_places(lat: float, lng: float, api_key: str, category_type: str, transportation: str = "walk") -> list[dict]:
    print(f"📍 [FETCH] Google Places APIで周辺の「{category_type}」を検索中... (手段: {transportation})")
    
    # 交通手段によって検索半径を動的に変更
    radius = 5000.0 if transportation in ["driving", "transit"] else 1500.0
    
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.rating,places.location"
    }
    data = {
        "includedTypes": [category_type],
        "maxResultCount": 5,
        "languageCode": "ja",
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius
            }
        }
    }
    
    try:
        res = requests.post(url, headers=headers, json=data, timeout=5)
        if res.status_code != 200:
            print(f"❌ [ERROR] Google APIエラー: {res.text}")
            return []
        places = res.json().get("places", [])
        
        results = []
        for p in places:
            location_data = p.get("location", {})
            results.append({
                "place_id": p.get("id"),
                "name": p.get("displayName", {}).get("text", "不明なスポット"),
                "address": p.get("formattedAddress"),
                "rating": p.get("rating", "評価なし"),
                "location": {
                    "latitude": location_data.get("latitude", 0.0),
                    "longitude": location_data.get("longitude", 0.0)
                }
            })
        print(f"✅ [SUCCESS] 半径{radius}mから {len(results)} 件のスポットを見つけました。")
        return results
    except Exception as e:
        print(f"❌ [ERROR] Google API通信中に例外が発生しました: {e}")
        return []

# ==========================================
# 3. Directions API (移動時間の算出)
# ==========================================
def _call_routes_api(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
    mode: str, api_key: str,
) -> int | None:
    """Routes API (New) で移動時間（分）を取得。失敗時は None を返す。"""
    from datetime import datetime, timezone, timedelta

    mode_map = {"transit": "TRANSIT", "driving": "DRIVE", "walking": "WALK"}
    travel_mode = mode_map.get(mode, "DRIVE")

    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        # transit では legs.duration も必要
        "X-Goog-FieldMask": "routes.duration,routes.legs.duration,routes.distanceMeters",
    }
    body = {
        "origin":      {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}},
        "destination": {"location": {"latLng": {"latitude": dest_lat,   "longitude": dest_lng}}},
        "travelMode": travel_mode,
    }
    if travel_mode == "TRANSIT":
        dep = datetime.now(timezone.utc) + timedelta(minutes=10)
        body["departureTime"] = dep.strftime("%Y-%m-%dT%H:%M:%SZ")
        # 使用する交通機関を明示（省略すると空ルートになることがある）
        body["transitPreferences"] = {
            "allowedTravelModes": ["BUS", "SUBWAY", "TRAIN", "LIGHT_RAIL", "RAIL"]
        }

    try:
        res = requests.post(url, headers=headers, json=body, timeout=10).json()
        routes = res.get("routes", [])
        if routes:
            route = routes[0]
            # routes.duration → routes.legs[0].duration の順で取得
            duration_str = route.get("duration") or ""
            if not duration_str and route.get("legs"):
                duration_str = route["legs"][0].get("duration", "0s")
            secs = int(str(duration_str).rstrip("s"))
            return max(1, secs // 60)
        err = res.get("error", {})
        err_msg = str(err.get("message", ""))
        err_status = str(err.get("status", ""))
        print(f"[Routes API] mode={mode} routes empty | status={err_status} | msg={err_msg[:200]} | raw={str(res)[:200]}")
        return None
    except Exception as e:
        print(f"[Routes API] mode={mode} exception type={type(e).__name__}: {e}")
        return None


def _haversine_minutes(lat1: float, lng1: float, lat2: float, lng2: float, mode: str) -> int:
    """直線距離から移動時間（分）を推定するフォールバック"""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2)
    dist_km = R * 2 * math.asin(math.sqrt(a))
    speed = {"transit": 0.5, "driving": 0.6, "walking": 0.08}.get(mode, 0.4)
    return max(3, int(dist_km / speed))


def calculate_route_times(api_key: str, start_lat: float, start_lng: float, destinations: list[dict], transportation: str) -> list[int]:
    """現在地 -> 目的地1 -> ... の各区間の移動時間（分）を Routes API (New) で取得"""
    times = []

    # 日本では transit API がデータを返さないため walking / driving のみ
    primary = "driving" if ("driving" in transportation.lower() or "車" in transportation) else "walking"
    fallback_chain = {
        "driving": ["driving", "walking"],
        "walking": ["walking"],
    }

    current_lat, current_lng = start_lat, start_lng

    for dest in destinations:
        dest_lat = dest["location"]["latitude"]
        dest_lng = dest["location"]["longitude"]

        print(f"[Routes] origin=({current_lat:.4f},{current_lng:.4f}) dest=({dest_lat:.4f},{dest_lng:.4f}) primary={primary}")

        if dest_lat == 0.0 and dest_lng == 0.0:
            est = _haversine_minutes(current_lat, current_lng, dest_lat, dest_lng, primary)
            print(f"[Routes] 目的地座標 0,0 -> 推定{est}分")
            times.append(est)
            continue

        result_mins = None
        for mode in fallback_chain.get(primary, [primary]):
            result_mins = _call_routes_api(current_lat, current_lng, dest_lat, dest_lng, mode, api_key)
            if result_mins is not None:
                print(f"[Routes] OK mode={mode} -> {result_mins}分")
                break
            print(f"[Routes] mode={mode} 失敗、次を試みる...")

        if result_mins is None:
            result_mins = _haversine_minutes(current_lat, current_lng, dest_lat, dest_lng, primary)
            print(f"[Routes] 全モード失敗 -> 推定{result_mins}分")

        times.append(result_mins)
        current_lat, current_lng = dest_lat, dest_lng

    return times


# ==========================================
# 7. Google Places Details API (New) – 写真・レビュー・価格
# ==========================================
def get_place_details(place_id: str, api_key: str) -> dict:
    """スポットの詳細情報（写真・レビュー・価格帯・滞在時間）を取得"""
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "id,displayName,photos,rating,priceLevel,reviews,editorialSummary,types,currentOpeningHours",
    }
    try:
        res = requests.get(url, headers=headers, params={"languageCode": "ja"}, timeout=8)
        if res.status_code != 200:
            print(f"[Place Details] {res.status_code}: {res.text[:200]}")
            return {}
        data = res.json()

        photo_url = None
        if data.get("photos"):
            photo_name = data["photos"][0]["name"]
            photo_url = (
                f"https://places.googleapis.com/v1/{photo_name}/media"
                f"?maxHeightPx=600&key={api_key}"
            )

        price_map = {
            "PRICE_LEVEL_FREE": 0,
            "PRICE_LEVEL_INEXPENSIVE": 1,
            "PRICE_LEVEL_MODERATE": 2,
            "PRICE_LEVEL_EXPENSIVE": 3,
            "PRICE_LEVEL_VERY_EXPENSIVE": 4,
        }
        price_level = price_map.get(data.get("priceLevel", ""), None)

        reviews = []
        for r in data.get("reviews", [])[:3]:
            text = r.get("text", {}).get("text", "")
            if text:
                reviews.append(text[:80] + ("..." if len(text) > 80 else ""))

        editorial = data.get("editorialSummary", {}).get("text", "")
        stay = _estimate_stay_minutes(data.get("types", []))

        # 営業状況（openNow が無い場所は None = 不明）
        hours = data.get("currentOpeningHours", {})
        open_now = hours.get("openNow")
        today_hours = None
        descriptions = hours.get("weekdayDescriptions", [])
        if descriptions:
            from datetime import datetime
            # weekdayDescriptions は月曜始まり
            idx = datetime.now().weekday()
            if idx < len(descriptions):
                today_hours = descriptions[idx]

        return {
            "photo_url": photo_url,
            "price_level": price_level,
            "editorial_summary": editorial,
            "review_snippets": reviews,
            "estimated_stay_minutes": stay,
            "open_now": open_now,
            "opening_hours_today": today_hours,
        }
    except Exception as e:
        print(f"[get_place_details] {e}")
        return {}


def _estimate_stay_minutes(types: list) -> int:
    """場所タイプから滞在時間（分）を推定"""
    stay_map = {
        "restaurant": 60, "cafe": 45, "coffee_shop": 45, "bakery": 30,
        "museum": 90, "art_gallery": 60, "aquarium": 90, "zoo": 120,
        "park": 45, "national_park": 60,
        "amusement_park": 120, "tourist_attraction": 60,
        "shopping_mall": 60, "store": 30, "clothing_store": 45,
        "spa": 90, "gym": 60,
        "movie_theater": 120, "night_club": 120, "bar": 60,
    }
    for t in types:
        if t in stay_map:
            return stay_map[t]
    return 45

# ==========================================
# 4. 意図抽出: 気分からカテゴリへの変換 (Gemini)
# ==========================================
def analyze_mood_with_gemini(mood: str, weather_info: WeatherInfo, transportation: str, companion: str, budget: str, api_key: str) -> list[str]:
    print("🤖 [AI] Geminiに気分を分析させ、検索カテゴリを推測中...")
    client = genai.Client(api_key=api_key)
    
    weather_str = f"{weather_info.condition} (気温 {weather_info.temperature}°C)"
    
    prompt = f"""
    ユーザーの現在の状態：
    - 気分や希望: {mood}
    - 同伴者: {companion}
    - 予算感: {budget}
    - 交通手段: {transportation}
    - 現在の天気状況: {weather_str}

    ユーザーの気分や状況から判断して、目的地として最適なGoogle Places APIのカテゴリを1〜2つ選んでください。
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="あなたはユーザーの曖昧な気分を正確な検索クエリに変換するアシスタントです。",
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "categories": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "Google Places APIのカテゴリ（例: cafe, park, restaurant, library, book_store, museum, movie_theater, aquarium, spa, tourist_attraction, amusement_park, bar, shopping_mall, clothing_store, zoo, art_gallery）。最大2つまで。"
                        }
                    },
                    "required": ["categories"]
                },
                temperature=0.1
            ),
        )
        
        result_json = json.loads(response.text)
        categories = result_json.get("categories", [])
        
        if not categories:
            return ["cafe", "park"]
            
        print(f"✅ [SUCCESS] AIによる抽出カテゴリ: {categories}")
        return [cat for cat in categories]

    except Exception as e:
        print(f"❌ [ERROR] Geminiのカテゴリ推測中にエラーが発生しました: {e}")
        return ["cafe", "park"]

# ==========================================
# 5. Geminiによるプラン生成 (複数スポット対応)
# ==========================================
def generate_plan_with_gemini(
    mood: str, 
    free_time: int, 
    weather_info: WeatherInfo,
    transportation: str,
    companion: str,
    budget: str,
    places_pool: list[dict],
    api_key: str
) -> tuple[dict, list[dict]]:
    """Gemini APIを呼び出してツアープラン（複数スポット）を生成し、選ばれたスポット情報と共に返す"""
    
    print("🤖 [AI] Geminiに実在リストを送信し、ツアープランを構築中...")
    client = genai.Client(api_key=api_key)
    
    weather_str = f"{weather_info.condition} (気温 {weather_info.temperature}°C)"
    
    prompt = f"""
    ユーザーの現在の状態：
    - 気分: {mood}
    - 空き時間: {free_time}分
    - 同伴者: {companion}
    - 予算感: {budget}
    - 交通手段: {transportation}
    - 現在の天気状況: {weather_str}

    以下は、ユーザーの現在地周辺に【確実に実在する】スポットのリストです。
    このリストの中から「最大3つまで」スポットを選び、論理的な順番（A地点→B地点...）で巡るツアープランを提案してください。
    空き時間が少ない場合（例えば60分以内）は1箇所だけでも構いません。
    リストにない存在しない場所（ハルシネーション）を提案することは絶対に禁止します。
    必ず日本語で出力してください。

    【実在するスポット候補リスト】
    {json.dumps(places_pool, ensure_ascii=False, indent=2)}
    """

    # ツアープラン用のネイティブSchema定義
    tour_plan_schema = {
        "type": "OBJECT",
        "properties": {
            "plan_title": {"type": "STRING", "description": "お出かけツアープランのタイトル"},
            "expected_emotion": {"type": "STRING", "description": "このプランを終えたあとにユーザーが得られる感情"},
            "stops": {
                "type": "ARRAY",
                "description": "巡るスポットの順序リスト（最大3件まで）",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "selected_place_id": {"type": "STRING", "description": "提示した候補リストの中から選んだスポットのplace_id"},
                        "activity_proposal": {"type": "STRING", "description": "この場所で何をして過ごすかの具体的な提案"}
                    },
                    "required": ["selected_place_id", "activity_proposal"]
                }
            }
        },
        "required": ["plan_title", "expected_emotion", "stops"]
    }

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="あなたはユーザーの気分を汲み取る、優秀なタクシー運転手兼お出かけコンシェルジュです。出力は必ず日本語（Japanese）で行ってください。",
                response_mime_type="application/json",
                response_schema=tour_plan_schema,
                temperature=0.2
            ),
        )
        
        result_json = json.loads(response.text)
        
        # 選ばれたスポット群を取得
        chosen_places = []
        for stop in result_json.get("stops", []):
            place = next((p for p in places_pool if p["place_id"] == stop["selected_place_id"]), None)
            if place:
                chosen_places.append(place)
                
        if not chosen_places:
            print("⚠️ フェイルセーフ発動: Geminiがリスト外のIDを選択したため、1件目の候補を強制割り当てしました。")
            chosen_places = [places_pool[0]]
            
        return result_json, chosen_places

    except Exception as e:
        print(f"❌ [ERROR] Geminiのプラン生成中にエラーが発生しました: {e}")
        raise e

# ==========================================
# 6. フィードバックによるプラン再生成 (Refine)
# ==========================================
def refine_plan_with_gemini(
    feedback: str,
    original_mood: str,
    free_time: int,
    transportation: str,
    places_pool: list[dict],
    previous_plan_json: str,
    api_key: str
) -> tuple[dict, list[dict]]:
    """ユーザーからのフィードバックを受けて、プランを練り直す"""
    print("🤖 [AI] Geminiがユーザーのフィードバックを受け、プランを修正中...")
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    あなたは優秀なタクシー運転手兼コンシェルジュです。
    先ほど、以下のプランをお客様（空き時間{free_time}分, 手段:{transportation}, 元の気分:{original_mood}）に提案しました。

    【前回のプラン】
    {previous_plan_json}

    しかし、お客様から以下のフィードバック（要望やダメ出し）を頂きました。
    【お客様からのフィードバック】
    「{feedback}」

    このフィードバックを最優先に考慮し、以下の【実在するスポット候補リスト】の中から、先ほどとは異なる（あるいはより条件に合う）スポットを最大3つまで選び、新しいツアープランを作り直してください。
    
    【実在するスポット候補リスト】
    {json.dumps(places_pool, ensure_ascii=False, indent=2)}
    """

    # ツアープラン用のネイティブSchema定義
    tour_plan_schema = {
        "type": "OBJECT",
        "properties": {
            "plan_title": {"type": "STRING", "description": "お出かけツアープランのタイトル"},
            "expected_emotion": {"type": "STRING", "description": "このプランを終えたあとにユーザーが得られる感情"},
            "stops": {
                "type": "ARRAY",
                "description": "巡るスポットの順序リスト（最大3件まで）",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "selected_place_id": {"type": "STRING", "description": "提示した候補リストの中から選んだスポットのplace_id"},
                        "activity_proposal": {"type": "STRING", "description": "この場所で何をして過ごすかの具体的な提案"}
                    },
                    "required": ["selected_place_id", "activity_proposal"]
                }
            }
        },
        "required": ["plan_title", "expected_emotion", "stops"]
    }

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="あなたはユーザーのフィードバックを真摯に受け止める、優しいタクシー運転手です。出力は必ず日本語（Japanese）で行ってください。",
                response_mime_type="application/json",
                response_schema=tour_plan_schema,
                temperature=0.3
            ),
        )
        
        result_json = json.loads(response.text)
        
        chosen_places = []
        for stop in result_json.get("stops", []):
            place = next((p for p in places_pool if p["place_id"] == stop["selected_place_id"]), None)
            if place:
                chosen_places.append(place)
                
        if not chosen_places:
            chosen_places = [places_pool[0]]
            
        return result_json, chosen_places

    except Exception as e:
        print(f"❌ [ERROR] プラン再生成中にエラーが発生しました: {e}")
        raise e
