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


def _gemini_function_call(prompt: str, tools: genai_types.Tool, system: str) -> tuple[str, dict]:
    """Function calling でどのアクションを呼ぶべきかを LLM に判断させる。
    戻り値は (関数名, 引数dict)。呼ばれなければ ("", {})。"""
    resp = _client().models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            tools=[tools],
            temperature=0.1,
            system_instruction=system,
        ),
    )
    parts = resp.candidates[0].content.parts
    for part in parts:
        if part.function_call:
            return part.function_call.name, dict(part.function_call.args or {})
    return "", {}


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
    try:
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
    except Exception as e:
        # Gemini 障害時は発言をそのまま気分として続行
        print(f"[mood_intake] Gemini 例外: {e}")
        data = {}
    mood = data.get("mood", last_msg)
    free_time = max(1, int(data.get("free_time_minutes", 90)))
    radius = _free_time_to_radius(free_time)

    # 天気を取得（失敗時は関数内部でデフォルト値にフォールバック）
    from services import get_current_weather
    w = get_current_weather(state["user_lat"], state["user_lng"])
    weather = f"{w.condition}・{w.temperature}℃"

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
        "weather": weather,
        "rejected_spot_names": [],
        "consecutive_rejects": 0,
        "time_used_minutes": 0,
        "quick_replies": [],
        "candidate_spots": [],
        "next_request_hint": "",
        "is_quick_reply": False,
    }


# ── ノード 3: スポット提案 ────────────────────────────────────

def spot_suggester_node(state: WanderMindState) -> dict:
    """例外時もマスターの台詞で回復する外側ラッパー"""
    try:
        return _spot_suggester_impl(state)
    except Exception as e:
        print(f"[spot_suggester] 例外: {e}")
        return {
            "messages": [AIMessage(content="すまんね、ちょっと耳が遠くなったみたいだ…もう一度言ってくれるかい？")]
        }


def _spot_suggester_impl(state: WanderMindState) -> dict:
    mood = state["current_mood"]
    excluded = state.get("suggested_place_ids", [])
    liked = state.get("liked_spots", [])
    center_lat = state["search_center_lat"]
    center_lng = state["search_center_lng"]
    radius = state["search_radius_m"]
    print(f"[spot_suggester] mood={mood!r} next_request_hint={state.get('next_request_hint', '')!r}")

    # 候補キャッシュ（REJECT 直後の再提案はクエリ生成も Places API も省略）
    cached = [s for s in state.get("candidate_spots", []) if s["place_id"] not in excluded]
    if cached:
        spots = cached
    else:
        # 気分からテキスト検索クエリを生成（天気・拒否履歴を加味）
        weather_note = (
            f"\n今日の天気: {state['weather']}（雨や荒天なら屋内で楽しめる場所を優先）"
            if state.get("weather") else ""
        )
        rejected = state.get("rejected_spot_names", [])
        rejected_note = (
            f"\nユーザーが断った場所: {', '.join(rejected[-5:])}（似た系統は避ける）"
            if rejected else ""
        )
        q_data = _gemini_json(
            f"気分「{mood}」にぴったりな場所の検索クエリを短く（10文字以内）。"
            f"例: 静かなカフェ、海が見える公園{weather_note}{rejected_note}",
            schema={"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]},
        )
        query = q_data.get("query", mood)

        spots = _fetch_spots(center_lat, center_lng, radius, query, excluded)

    if not spots:
        return {
            "messages": [AIMessage(content="うーん、この辺にはちょうどいい場所が見当たらないな。気分を変えてもう一度探してみようか？")],
            "candidate_spots": [],
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
    print(f"[spot_suggester] chosen={chosen['name']} liked_spots={[s['name'] for s in liked]}")

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
        "open_now": details.get("open_now"),
        "opening_hours_today": details.get("opening_hours_today"),
    })

    # マスター風メッセージ生成（詳細情報を反映）
    liked_ctx = (
        f"\n【重要】お客さんはすでに「{'・'.join(s['name'] for s in liked)}」に行くことを決めている。"
        f"紹介文の冒頭で必ずこれに触れ（例:「◯◯の次なら」「◯◯を出たあとは」）、"
        f"今回の提案がその続きの行程であることが伝わるようにしてください。"
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

    # 営業状況（閉店中なら正直に伝える）
    closed_note = ""
    if details.get("open_now") is False:
        hours_info = f"（本日: {details['opening_hours_today']}）" if details.get("opening_hours_today") else ""
        closed_note = f"\n注意: この店は今は営業時間外{hours_info}。正直に「今はもう閉まってるが」と伝えたうえで、時間が合えばの提案として紹介する。"

    # 残り時間（承認済みスポットの滞在+移動から算出）
    time_note = ""
    if liked:
        used = state.get("time_used_minutes", 0)
        remaining = state["free_time_minutes"] - used
        this_cost = chosen["estimated_stay_minutes"] + (chosen.get("travel_time_minutes") or 0)
        time_note = (
            f"\n時間の状況: 空き時間{state['free_time_minutes']}分のうち、もう約{used}分ぶん決まっている（残り約{remaining}分）。"
            f"この店は滞在+移動で約{this_cost}分。"
        )
        if remaining < this_cost:
            time_note += "残り時間的に厳しいことをやんわり伝える。"
        else:
            time_note += "残り時間を会話の中で自然に一言添える。"

    # 連続拒否時は好みを聞き返す
    ask_note = ""
    if state.get("consecutive_rejects", 0) >= 2:
        ask_note = "\n連続で断られている。「ふむ、どういうところがお好みじゃないんだい？」と好みを一言聞きつつ紹介する。"

    weather_flavor = f"\n今日の天気: {state.get('weather', '')}。自然に触れられそうなら一言添えてよい。" if state.get("weather") else ""

    m_data = _gemini_json(
        "あなたは街をよく知る老舗喫茶店のマスター。穏やかで物知りで、常連客に話しかけるような親しみやすい口調"
        "（「〜ですよ」「〜だね」「〜かね？」）。移動手段や車には言及しない。\n"
        f"{liked_ctx}気分「{mood}」のお客さんに「{chosen['name']}（{chosen['address']}）」を2〜3文で紹介してください。"
        f"{editorial_note}{review_note}{closed_note}{time_note}{ask_note}{weather_flavor}"
        f"\n「〜はどうかね？」の調子で締める。{hint}"
        f"\nあわせて、この提案に対してお客さんが返しそうな短い反応の選択肢を2〜3個生成する"
        f"（例: 「☕ もっと静かな店がいい」「🍽️ 先に食事がしたい」。絵文字1つ+10文字以内）。",
        schema={
            "type": "OBJECT",
            "properties": {
                "message": {"type": "STRING", "description": "マスターの紹介メッセージ"},
                "quick_replies": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "お客さんの反応候補 2〜3個",
                },
            },
            "required": ["message"],
        },
        temperature=0.7,
    )
    msg = m_data.get("message") or f"「{chosen['name']}」なんてのはどうかね？"
    quick_replies = m_data.get("quick_replies", [])[:3]

    return {
        "messages": [AIMessage(content=msg)],
        "current_suggestion": chosen,
        "suggested_place_ids": excluded + [chosen["place_id"]],
        "quick_replies": quick_replies,
        # 未提案の候補をキャッシュ（次の REJECT 時に API を叩かず即答）
        "candidate_spots": [s for s in spots if s["place_id"] != chosen["place_id"]],
    }


# ── ノード 4: 反応分析 ───────────────────────────────────────

# ボタン（クイックリプライ）文言 → reaction の固定マッピング。
# ボタン由来のメッセージは意図が確定しているので LLM を呼ばず即決する。
QUICK_REPLY_ACTIONS = {
    "いいね": "APPROVE",
    "違う": "REJECT",
    "それでいこう": "FINALIZE",
}


def reaction_analyzer_node(state: WanderMindState) -> dict:
    last_msg = state["messages"][-1].content
    is_quick_reply = state.get("is_quick_reply", False)

    if is_quick_reply:
        reaction, extra = _classify_quick_reply(last_msg)
    else:
        try:
            reaction, extra = _classify_free_text(last_msg)
        except Exception as e:
            # Gemini 障害時は OTHER（再提案）として安全に継続
            print(f"[reaction_analyzer] Gemini 例外: {e}")
            reaction, extra = "OTHER", {}

    print(
        f"[reaction_analyzer] msg={last_msg!r} quick_reply={is_quick_reply} "
        f"-> reaction={reaction} extra={extra} liked_count={len(state.get('liked_spots', []))}"
    )

    updates = {
        "last_reaction": reaction,
        "last_mood_hint": extra.get("mood_hint", ""),
    }

    # 拒否履歴の追跡（クエリ生成での回避と、連続拒否時の聞き返しに使用）
    current = state.get("current_suggestion")
    if reaction == "REJECT" and current:
        updates["rejected_spot_names"] = (
            state.get("rejected_spot_names", []) + [current["name"]]
        )
        updates["consecutive_rejects"] = state.get("consecutive_rejects", 0) + 1
    elif reaction in ("APPROVE", "APPROVE_AND_UPDATE"):
        updates["consecutive_rejects"] = 0

    return updates


def _classify_quick_reply(text: str) -> tuple[str, dict]:
    """ボタン由来のメッセージは固定マッピングで即決（Gemini 不要・確実・高速）"""
    for keyword, reaction in QUICK_REPLY_ACTIONS.items():
        if keyword in text:
            return reaction, {}
    # 動的クイックリプライ（例:「☕ もっと静かな店がいい」）は新しい要望として扱う
    return "MOOD_UPDATE", {"mood_hint": text}


def _classify_free_text(last_msg: str) -> tuple[str, dict]:
    """自由入力の chat は、Gemini の Function Calling でどのアクションかを判断させる。
    単純な5値分類ではなく、会話文に含まれる具体的な要望（例:「夜ご飯が食べたい」）を
    LLM 自身に抽出させることで、ボタンでは拾えない自由記述の意図を反映する。"""
    tools = genai_types.Tool(function_declarations=[
        genai_types.FunctionDeclaration(
            name="approve_and_continue",
            description="提案されたスポットを気に入った場合、または前提として次を尋ねている場合"
                        "（例: 「◯◯の後は」「◯◯を出て」「◯◯に行ったら」）に呼ぶ",
        ),
        genai_types.FunctionDeclaration(
            name="reject_and_continue",
            description="提案されたスポットが気に入らない場合に呼ぶ（違う、微妙、別のにして、パス）",
        ),
        genai_types.FunctionDeclaration(
            name="change_request",
            description="気分や具体的な要望を新しく伝えている場合に呼ぶ"
                        "（例: 夜ご飯が食べたい、休憩したい、もっと静かな場所がいい、もっとはしゃぎたい）",
            parameters=genai_types.Schema(
                type="OBJECT",
                properties={
                    "request_text": genai_types.Schema(
                        type="STRING", description="新しい要望を簡潔に抜き出す（例: 夜ご飯）"
                    ),
                    "approve_previous": genai_types.Schema(
                        type="BOOLEAN",
                        description="発言が直前の提案を受け入れた上での要望なら true"
                                    "（例:「よみうりランドの後は夜ご飯」→ true）",
                    ),
                },
                required=["request_text"],
            ),
        ),
        genai_types.FunctionDeclaration(
            name="finalize_route",
            description="ルートの確定を求めている場合に呼ぶ（それでいこう、決定、OK、全部でいこう）",
        ),
    ])

    name, args = _gemini_function_call(
        f"ユーザー発言:「{last_msg}」\nこの発言に対して、最も適切な関数を1つ呼び出してください。",
        tools,
        system="あなたは会話の意図を解析するアシスタント。ユーザーの発言内容から、次に取るべき"
               "アクションを1つの function call で表現してください。発言に複数の意図が含まれる"
               "場合（例: 前の提案を受け入れつつ新しい要望を言う）は change_request を優先し、"
               "approve_previous で前の提案の扱いを示してください。",
    )

    if name == "approve_and_continue":
        return "APPROVE", {}
    if name == "reject_and_continue":
        return "REJECT", {}
    if name == "change_request":
        request_text = args.get("request_text") or last_msg
        if args.get("approve_previous"):
            return "APPROVE_AND_UPDATE", {"mood_hint": request_text}
        return "MOOD_UPDATE", {"mood_hint": request_text}
    if name == "finalize_route":
        return "FINALIZE", {}
    return "OTHER", {}


def route_reaction(state: WanderMindState) -> str:
    return {
        "APPROVE": "approve",
        "REJECT": "reject",
        "MOOD_UPDATE": "mood_update",
        "APPROVE_AND_UPDATE": "approve_and_update",
        "FINALIZE": "finalize",
    }.get(state.get("last_reaction", "OTHER"), "reject")


# ── ノード 5: 気分更新 ───────────────────────────────────────

def mood_updater_node(state: WanderMindState) -> dict:
    new_mood = state.get("last_mood_hint") or state["messages"][-1].content
    return {
        "current_mood": new_mood,
        "next_request_hint": new_mood,
        # 気分が変わったら検索半径をリセット（広い範囲から再探索）
        "search_radius_m": _free_time_to_radius(state["free_time_minutes"]),
        "search_center_lat": state["user_lat"],
        "search_center_lng": state["user_lng"],
        # 気分が変わったので候補キャッシュを破棄
        "candidate_spots": [],
    }


# ── ノード 5b: 承認 + 要望更新（複合） ─────────────────────────

def approve_and_update_node(state: WanderMindState) -> dict:
    """前の提案を承認しつつ、新しい要望に気分を更新する複合アクション。
    例:「よみうりランドの後は夜ご飯」→ よみうりランドを liked_spots に追加し、
    次の検索は「夜ご飯」を反映したクエリで行う。"""
    acc_updates = spot_accumulator_node(state)
    new_mood = state.get("last_mood_hint") or state["messages"][-1].content
    print(f"[approve_and_update] liked に追加しつつ要望更新 -> {new_mood!r}")
    return {
        **acc_updates,
        "current_mood": new_mood,
        "next_request_hint": new_mood,
    }


# ── ノード 6: スポット承認・蓄積 ─────────────────────────────

def spot_accumulator_node(state: WanderMindState) -> dict:
    liked = list(state.get("liked_spots", []))
    current = state.get("current_suggestion")

    if current:
        existing_ids = {s["place_id"] for s in liked}
        if current["place_id"] not in existing_ids:
            liked.append(current)

    print(f"[spot_accumulator] liked_spots={[s['name'] for s in liked]}")

    # liked_spots の重心を新しい検索中心に設定
    if liked:
        clat, clng = _centroid(liked)
        # スポットが増えるほど半径を絞って近場に集中させる
        new_radius = max(1500, int(state["search_radius_m"] * (0.85 ** (len(liked) - 1))))
    else:
        clat, clng = state["user_lat"], state["user_lng"]
        new_radius = state["search_radius_m"]

    # 承認済みスポットの滞在+移動の合計（残り時間の計算に使用）
    time_used = sum(
        s.get("estimated_stay_minutes", 45) + (s.get("travel_time_minutes") or 0)
        for s in liked
    )

    return {
        "liked_spots": liked,
        "search_center_lat": clat,
        "search_center_lng": clng,
        "search_radius_m": new_radius,
        "time_used_minutes": time_used,
        # 検索中心が動いたので候補キャッシュを破棄
        "candidate_spots": [],
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

    try:
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
    except Exception as e:
        # Gemini 障害時もルート自体は確定させ、素の情報で発表する
        print(f"[route_presenter] Gemini 例外: {e}")
        msg = f"ルートが決まりましたよ。{course}（移動合計 約{total_travel}分）。いい時間になりますよ。"

    return {
        "messages": [AIMessage(content=msg)],
        "phase": "done",
    }


# ── ノード 9: 終了後対応 ─────────────────────────────────────

def farewell_node(state: WanderMindState) -> dict:
    return {
        "messages": [AIMessage(content="もうルートは決まったよ！楽しんできてね。また来たらまた話しかけてくれ。")]
    }
