import os
import sys
import json
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# .envの読み込み
load_dotenv()

# ==========================================
# 1. バリデーション（入力検証）関数
# ==========================================
def validate_inputs():
    print("🔍 [CHECK] 入力値のバリデーションを開始します...")
    
    gemini_key = os.getenv("GEMINI_API_KEY")
    google_key = os.getenv("GOOGLE_MAPS_API_KEY")
    
    if not gemini_key or "your_" in gemini_key:
        print("❌ [ERROR] GEMINI_API_KEY が正しく設定されていません。")
        sys.exit(1)
    if not google_key or "your_" in google_key:
        print("❌ [ERROR] GOOGLE_MAPS_API_KEY が正しく設定されていません。")
        sys.exit(1)
        
    mood = os.getenv("USER_MOOD")
    if not mood:
        print("❌ [ERROR] USER_MOOD が空です。")
        sys.exit(1)
        
    try:
        free_time = int(os.getenv("USER_FREE_TIME_MINUTES", 0))
        if free_time <= 0:
            raise ValueError
    except ValueError:
        print("❌ [ERROR] USER_FREE_TIME_MINUTES は1以上の整数で指定してください。")
        sys.exit(1)
        
    try:
        lat = float(os.getenv("USER_LATITUDE", 0))
        lng = float(os.getenv("USER_LONGITUDE", 0))
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            raise ValueError
    except ValueError:
        print("❌ [ERROR] 緯度(USER_LATITUDE)または経度(USER_LONGITUDE)の値が範囲外です。")
        sys.exit(1)
        
    print("✅ [SUCCESS] 全ての入力値の検証をパスしました。")
    return {
        "mood": mood,
        "free_time": free_time,
        "lat": lat,
        "lng": lng,
        "google_key": google_key,
        "gemini_key": gemini_key
    }

# ==========================================
# 2. 天気APIの取得 (Open-Meteo)
# ==========================================
def get_current_weather(lat, lng):
    print("🌤️ [FETCH] 現在地の天気を取得中...")
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current_weather=true"
    try:
        res = requests.get(url, timeout=5).json()
        code = res["current_weather"]["weathercode"]
        temp = res["current_weather"]["temperature"]
        weather = "雨・荒天" if code in [51,53,55,61,63,65,71,73,75,80,81,82,95,96,99] else "晴れ・曇り"
        print(f"✅ [SUCCESS] 天気: {weather}, 気温: {temp}°C")
        return f"{weather} (気温 {temp}°C)"
    except Exception as e:
        print(f"⚠️ [WARN] 天気APIの取得に失敗しました(デフォルト値を使用): {e}")
        return "晴れ・曇り (気温 20°C)"

# ==========================================
# 3. Google Places API (New) の実行
# ==========================================
def fetch_nearby_places(lat, lng, api_key, category_type):
    print(f"📍 [FETCH] Google Places APIで周辺の「{category_type}」を検索中...")
    
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.rating"
    }
    data = {
        "includedTypes": [category_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": 1000.0
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
            results.append({
                "place_id": p.get("id"),
                "name": p.get("displayName", {}).get("text", "不明なスポット"),
                "address": p.get("formattedAddress"),
                "rating": p.get("rating", "評価なし")
            })
        print(f"✅ [SUCCESS] {len(results)} 件のスポットを見つけました。")
        return results
    except Exception as e:
        print(f"❌ [ERROR] Google API通信中に例外が発生しました: {e}")
        return []

# ==========================================
# 4. Geminiの出力形式（スキーマ）の定義
# ==========================================
class OutboundPlan(BaseModel):
    plan_title: str = Field(description="お出かけプランのタイトル")
    selected_place_id: str = Field(description="提示した候補リストの中から、最も気分に合うスポットのplace_id")
    activity_proposal: str = Field(description="その場所で何をして過ごすかの具体的な提案")
    expected_emotion: str = Field(description="このプランを終えたあとにユーザーが得られる感情")

# ==========================================
# 5. メイン処理
# ==========================================
def main():
    config = validate_inputs()
    categories = ["cafe", "park"]
    weather_info = get_current_weather(config["lat"], config["lng"])
    
    # Googleから実在の場所を取得
    raw_places_pool = []
    for cat in categories:
        raw_places_pool.extend(fetch_nearby_places(config["lat"], config["lng"], config["google_key"], cat))
        
    if not raw_places_pool:
        print("❌ [ERROR] 周辺に実在するスポットが見つかりませんでした。")
        sys.exit(1)
        
    print("🤖 [AI] Geminiに実在リストを送信し、プランを構築中...")
    
    # 最新のgoogle-genaiクライアントの初期化
    client = genai.Client(api_key=config["gemini_key"])
    
    prompt = f"""
    ユーザーの現在の状態：
    - 気分: {config["mood"]}
    - 空き時間: {config["free_time"]}分
    - 現在の天気状況: {weather_info}

    以下は、ユーザーの現在地周辺に【確実に実在する】スポットのリストです。
    必ずこのリストの中から「1つ」だけスポットを選び、ユーザーの気分と天気に最適なプランを提案してください。
    リストにない存在しない場所（ハルシネーション）を提案することは絶対に禁止します。

    【実在するスポット候補リスト】
    {json.dumps(raw_places_pool, ensure_ascii=False, indent=2)}
    """

    try:
        # gemini-2.5-flash などの最新軽量モデルを使用
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="あなたはユーザーの気分を汲み取る、優秀なお出かけコンシェルジュです。",
                response_mime_type="application/json",
                response_schema=OutboundPlan, # Pydanticによるスキーマ強制
                temperature=0.2 # 遊びを減らし、実在リストからの選択を厳密にする
            ),
        )
        
        # 結果のパース
        result_json = json.loads(response.text)
        
        print("\n==================================================")
        print("🎉 [🎉 Gemini MVP プラン生成成功！ 🎉]")
        print("==================================================")
        print(f"■ プラン名: {result_json['plan_title']}")
        
        # 実在検証
        chosen_place = next((p for p in raw_places_pool if p["place_id"] == result_json["selected_place_id"]), None)
        if chosen_place:
            print(f"■ 行く場所: {chosen_place['name']} (住所: {chosen_place['address']}) ★実在確認済")
        else:
            print("⚠️ フェイルセーフ発動: Geminiがリスト外のIDを選択したため、1件目の候補を強制割り当てしました。")
            chosen_place = raw_places_pool[0]
            print(f"■ 行く場所: {chosen_place['name']}")
            
        print(f"■ 何をするか: {result_json['activity_proposal']}")
        print(f"■ 得られる感情: {result_json['expected_emotion']}")
        print("==================================================")
        
    except Exception as e:
        print(f"❌ [ERROR] Geminiのプラン生成中にエラーが発生しました: {e}")

if __name__ == "__main__":
    main()