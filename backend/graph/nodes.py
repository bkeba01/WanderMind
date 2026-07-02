import os
import json
import requests
from google import genai
from google.genai import types as genai_types
from langchain_core.messages import AIMessage
from graph.state import WanderMindState


# ── Gemini ヘルパー ──────────────────────────────────────────

def _client() -> genai.Client:
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _gemini(prompt: str, system: str = "", temperature: float = 0.5) -> str:
    cfg = genai_types.GenerateContentConfig(temperature=temperature)
    if system:
        cfg.system_instruction = system
    resp = _client().models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=cfg,
    )
    return resp.text.strip()


def _gemini_json(prompt: str, schema: dict, temperature: float = 0.1) -> dict:
    resp = _client().models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction="指定されたJSONスキーマに従って出力してください。",
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
        ),
    )
    try:
        return json.loads(resp.text)
    except Exception:
        return {}


# ── 地理ユーティリティ ────────────────────────────────────────

def _centroid(spots: list) -> tuple[float, float]:
    lats = [s["location"]["latitude"] for s in spots]
    lngs = [s["location"]["longitude"] for s in spots]
    return sum(lats) / len(lats), sum(lngs) / len(lngs)


def _free_time_to_radius(minutes: int) -> int:
    """空き時間(分) → 検索半径(m)。移動に使える時間の30%・電車200m/分・片道換算。"""
    radius = int(minutes * 0.3 * 200)
    return max(1500, min(radius, 12000))


# ── Google Places API（テキスト検索）────────────────────────

def _fetch_spots(
    lat: float,
    lng: float,
    radius_m: int,
    text_query: str,
    excluded_ids: list[str],
) -> list[dict]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,"
            "places.formattedAddress,places.rating,places.location"
        ),
    }
    body = {
        "textQuery": text_query,
        "maxResultCount": 10,
        "languageCode": "ja",
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius_m),
            }
        },
    }
    try:
        res = requests.post(url, headers=headers, json=body, timeout=8)
        if res.status_code != 200:
            print(f"[Places API] {res.status_code}: {res.text[:200]}")
            return []
        spots = []
        for p in res.json().get("places", []):
            pid = p.get("id", "")
            if pid in excluded_ids:
                continue
            loc = p.get("location", {})
            spots.append({
                "place_id": pid,
                "name": p.get("displayName", {}).get("text", "不明"),
                "address": p.get("formattedAddress", ""),
                "rating": p.get("rating", "評価なし"),
                "location": {
                    "latitude": loc.get("latitude", 0.0),
                    "longitude": loc.get("longitude", 0.0),
                },
            })
        return spots
    except Exception as e:
        print(f"[fetch_spots] {e}")
        return []


# ── ノード 1: ターン振り分け ─────────────────────────────────

def turn_router_node(state: WanderMindState) -> dict:
    return {}


def route_by_phase(state: WanderMindState) -> str:
    return {"start": "start", "collecting": "collecting", "done": "done"}.get(
        state.get("phase", "start"), "start"
    )


# ── ノード 2: 気分取得 ───────────────────────────────────────

def mood_intake_node(state: WanderMindState) -> dict:
    last_msg = state["messages"][-1].content
    data = _gemini_json(
        f"ユーザー発言「{last_msg}」から気分と空き時間を抽出してください。",
        schema={
            "type": "OBJECT",
            "properties": {
                "mood": {"type": "STRING", "description": "ユーザーの気分（日本語）"},
                "free_time_minutes": {"type": "INTEGER", "description": "空き時間（分）。不明なら90"},
            },
            "required": ["mood", "free_time_minutes"],
        },
    )
    mood = data.get("mood", last_msg)
    free_time = max(1, int(data.get("free_time_minutes", 90)))
    radius = _free_time_to_radius(free_time)

    return {
        "initial_mood": mood,
        "current_mood": mood,
        "free_time_minutes": free_time,
        "search_radius_m": radius,
        "search_center_lat": state["user_lat"],
        "search_center_lng": state["user_lng"],
        "phase": "collecting",
        "liked_spots": [],
        "suggested_place_ids": [],
        "current_suggestion": None,
        "last_reaction": "",
        "last_mood_hint": "",
        "route_info": None,
    }


# ── ノード 3: スポット提案 ────────────────────────────────────

def spot_suggester_node(state: WanderMindState) -> dict:
    mood = state["current_mood"]
    excluded = state.get("suggested_place_ids", [])
    liked = state.get("liked_spots", [])
    center_lat = state["search_center_lat"]
    center_lng = state["search_center_lng"]
    radius = state["search_radius_m"]

    # 気分からテキスト検索クエリを生成
    q_data = _gemini_json(
        f"気分「{mood}」にぴったりな場所の検索クエリを短く（10文字以内）。例: 静かなカフェ、海が見える公園",
        schema={"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]},
    )
    query = q_data.get("query", mood)

    spots = _fetch_spots(center_lat, center_lng, radius, query, excluded)

    if not spots:
        return {
            "messages": [AIMessage(content="うーん、この辺にはちょうどいい場所が見当たらないな。気分を変えてもう一度探してみようか？")]
        }

    # Geminiで最適スポットを1つ選択
    spots_desc = json.dumps(
        [{"i": i, "name": s["name"], "address": s["address"]} for i, s in enumerate(spots[:8])],
        ensure_ascii=False,
    )
    sel = _gemini_json(
        f"気分「{mood}」に一番合うスポットのインデックスを選んでください。\n候補:\n{spots_desc}",
        schema={"type": "OBJECT", "properties": {"index": {"type": "INTEGER"}}, "required": ["index"]},
    )
    idx = min(int(sel.get("index", 0)), len(spots) - 1)
    chosen = spots[idx]

    # 詳細情報と移動時間を並列取得
    from services import get_place_details, calculate_route_times
    from concurrent.futures import ThreadPoolExecutor

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    with ThreadPoolExecutor(max_workers=2) as pool:
        details_f = pool.submit(get_place_details, chosen["place_id"], api_key)
        times_f = pool.submit(
            calculate_route_times,
            api_key, state["user_lat"], state["user_lng"], [chosen],
            state.get("transportation", "transit"),
        )
        details = details_f.result()
        t_times = times_f.result()

    chosen.update({
        "photo_url": details.get("photo_url"),
        "price_level": details.get("price_level"),
        "editorial_summary": details.get("editorial_summary"),
        "review_snippets": details.get("review_snippets", []),
        "estimated_stay_minutes": details.get("estimated_stay_minutes", 45),
        "travel_time_minutes": t_times[0] if t_times else None,
    })

    # マスター風メッセージ生成（詳細情報を反映）
    liked_ctx = (
        f"もう「{'・'.join(s['name'] for s in liked)}」が決まってるんだが、"
        if liked else ""
    )
    hint = (
        "\n（「それでいこう」って言ってくれればルートを出すよ！）"
        if len(liked) >= 2 else ""
    )
    editorial_note = f"\n店舗説明: {details['editorial_summary']}" if details.get("editorial_summary") else ""
    review_note = (
        "\nレビュー: " + "、".join(details.get("review_snippets", [])[:2])
        if details.get("review_snippets") else ""
    )
    msg = _gemini(
        f"{liked_ctx}気分「{mood}」のお客さんに「{chosen['name']}（{chosen['address']}）」を2〜3文で紹介。{editorial_note}{review_note}\n「〜はどうかね？」で締める。{hint}",
        system="あなたは街をよく知る老舗喫茶店のマスター。穏やかで、物知りで、常連客に話しかけるような親しみやすい口調。「〜ですよ」「〜だね」「〜かね？」を使う。移動手段や車には言及しない。",
        temperature=0.7,
    )

    return {
        "messages": [AIMessage(content=msg)],
        "current_suggestion": chosen,
        "suggested_place_ids": excluded + [chosen["place_id"]],
    }


# ── ノード 4: 反応分析 ───────────────────────────────────────

def reaction_analyzer_node(state: WanderMindState) -> dict:
    last_msg = state["messages"][-1].content
    data = _gemini_json(
        f"""ユーザー発言「{last_msg}」を以下のいずれかに分類してください。
APPROVE  : 興味を示した（いいね、面白そう、行きたい、いいかも）
REJECT   : 断った（違う、微妙、別のにして、パス）
MOOD_UPDATE: 気分の変化を表現（もっとはしゃぎたい、静かな所がいい、疲れた）
FINALIZE : 決定・確定（それでいこう、決定、OK、全部でいこう）
OTHER    : 上記以外""",
        schema={
            "type": "OBJECT",
            "properties": {
                "reaction": {
                    "type": "STRING",
                    "enum": ["APPROVE", "REJECT", "MOOD_UPDATE", "FINALIZE", "OTHER"],
                },
                "mood_hint": {
                    "type": "STRING",
                    "description": "MOOD_UPDATEの場合の新しい気分の説明",
                },
            },
            "required": ["reaction"],
        },
    )
    return {
        "last_reaction": data.get("reaction", "OTHER"),
        "last_mood_hint": data.get("mood_hint", ""),
    }


def route_reaction(state: WanderMindState) -> str:
    return {
        "APPROVE": "approve",
        "REJECT": "reject",
        "MOOD_UPDATE": "mood_update",
        "FINALIZE": "finalize",
    }.get(state.get("last_reaction", "OTHER"), "reject")


# ── ノード 5: 気分更新 ───────────────────────────────────────

def mood_updater_node(state: WanderMindState) -> dict:
    new_mood = state.get("last_mood_hint") or state["messages"][-1].content
    return {
        "current_mood": new_mood,
        # 気分が変わったら検索半径をリセット（広い範囲から再探索）
        "search_radius_m": _free_time_to_radius(state["free_time_minutes"]),
        "search_center_lat": state["user_lat"],
        "search_center_lng": state["user_lng"],
    }


# ── ノード 6: スポット承認・蓄積 ─────────────────────────────

def spot_accumulator_node(state: WanderMindState) -> dict:
    liked = list(state.get("liked_spots", []))
    current = state.get("current_suggestion")

    if current:
        existing_ids = {s["place_id"] for s in liked}
        if current["place_id"] not in existing_ids:
            liked.append(current)

    # liked_spots の重心を新しい検索中心に設定
    if liked:
        clat, clng = _centroid(liked)
        # スポットが増えるほど半径を絞って近場に集中させる
        new_radius = max(1500, int(state["search_radius_m"] * (0.85 ** (len(liked) - 1))))
    else:
        clat, clng = state["user_lat"], state["user_lng"]
        new_radius = state["search_radius_m"]

    return {
        "liked_spots": liked,
        "search_center_lat": clat,
        "search_center_lng": clng,
        "search_radius_m": new_radius,
    }


# ── ノード 7: ルート計画 ─────────────────────────────────────

def route_planner_node(state: WanderMindState) -> dict:
    liked = list(state.get("liked_spots", []))
    current = state.get("current_suggestion")

    # FINALIZE時にliked_spotsが空ならcurrent_suggestionを使う
    if not liked and current:
        liked = [current]

    if not liked:
        return {
            "messages": [AIMessage(content="行きたい場所をまず決めてくれよ！「いいね」って場所を教えてくれ。")]
        }

    from services import calculate_route_times

    times = calculate_route_times(
        api_key=os.getenv("GOOGLE_MAPS_API_KEY"),
        start_lat=state["user_lat"],
        start_lng=state["user_lng"],
        destinations=liked,
        transportation=state.get("transportation", "transit"),
    )

    total_travel = sum(times)
    return {
        "route_info": {
            "total_travel_minutes": total_travel,
            "spots": liked,
            "travel_times": times,
        }
    }


# ── ノード 8: ルート発表 ─────────────────────────────────────

def route_presenter_node(state: WanderMindState) -> dict:
    route = state.get("route_info", {})
    spots = route.get("spots", state.get("liked_spots", []))
    times = route.get("travel_times", [])
    total_travel = route.get("total_travel_minutes", 0)
    free_time = state["free_time_minutes"]

    course = " → ".join(s["name"] for s in spots)
    legs_str = "、".join(
        f"{spots[i]['name']}→{spots[i+1]['name']} 約{times[i]}分"
        for i in range(len(times) - 1)
    ) if len(times) > 1 else (f"移動 約{times[0]}分" if times else "移動時間不明")
    time_note = (
        f"移動だけで{total_travel}分かかるから少しタイトだな。"
        if total_travel > free_time * 0.5 else ""
    )

    msg = _gemini(
        f"""以下のルートをお客さんに発表してください。
コース: {course}
区間ごとの移動時間: {legs_str}
移動合計時間: {total_travel}分
空き時間: {free_time}分
{time_note}

コース・移動時間・交通費の目安（電車ならおおよそ距離×15円）を含め、3〜4文でテンポよく。
最後に「いい時間になりますよ」的な一言を添えて。""",
        system="あなたは街をよく知る老舗喫茶店のマスター。穏やかで物知り。常連客に話しかけるような親しみやすい口調。「〜ですよ」「〜だね」を使う。",
        temperature=0.7,
    )

    return {
        "messages": [AIMessage(content=msg)],
        "phase": "done",
    }


# ── ノード 9: 終了後対応 ─────────────────────────────────────

def farewell_node(state: WanderMindState) -> dict:
    return {
        "messages": [AIMessage(content="もうルートは決まったよ！楽しんできてね。また来たらまた話しかけてくれ。")]
    }
