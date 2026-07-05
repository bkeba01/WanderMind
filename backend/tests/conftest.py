"""WanderMind テスト共通フィクスチャ

外部 API（Gemini / Places / Routes）をすべてモックし、
LangGraph のグラフと FastAPI エンドポイントをオフラインで検証する。
"""
import os
import re
import sys
import copy

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GOOGLE_MAPS_API_KEY", "test-key")
os.environ["WANDER_CHECKPOINT"] = "memory"  # テストは SQLite でなくインメモリ

import pytest
from fastapi.testclient import TestClient

from graph import nodes
import services
from main import app
from graph.builder import compiled_graph


# ── フェイクデータ ──────────────────────────────────────────

def make_spot_pool(n: int = 10) -> list[dict]:
    """place_id p0..p(n-1) のダミースポット群"""
    return [
        {
            "place_id": f"p{i}",
            "name": f"テストカフェ{i}",
            "address": f"千葉県船橋市テスト町{i}丁目",
            "rating": 4.0 + i * 0.05,
            "location": {"latitude": 35.70 + i * 0.001, "longitude": 139.98 + i * 0.001},
        }
        for i in range(n)
    ]


FAKE_DETAILS = {
    "photo_url": "https://example.com/photo.jpg",
    "price_level": 2,
    "editorial_summary": "落ち着いた雰囲気の店",
    "review_snippets": ["静かで良い", "コーヒーが美味しい"],
    "estimated_stay_minutes": 60,
    "open_now": True,
    "opening_hours_today": "月曜日: 9時00分～18時00分",
}


# ── Gemini フェイク（プロンプト内容でディスパッチ）─────────

def _extract_quoted(prompt: str) -> str:
    m = re.search(r"「(.+?)」", prompt, re.S)
    return m.group(1) if m else ""


def fake_gemini_json(prompt: str, schema: dict, temperature: float = 0.1) -> dict:
    if "気分と空き時間を抽出" in prompt:
        text = _extract_quoted(prompt)
        m = re.search(r"(\d+)分", text)
        return {
            "mood": "リフレッシュしたい",
            "free_time_minutes": int(m.group(1)) if m else 90,
        }
    if "紹介してください" in prompt:
        return {
            "message": "いい店を見つけたよ。〜はどうかね？",
            "quick_replies": ["☕ もっと静かな店がいい", "🍽️ 先に食事がしたい"],
        }
    if "分類してください" in prompt:
        text = _extract_quoted(prompt)
        if "いいね" in text:
            return {"reaction": "APPROVE"}
        if "違う" in text:
            return {"reaction": "REJECT"}
        if "はしゃぎたい" in text:
            return {"reaction": "MOOD_UPDATE", "mood_hint": "はしゃぎたい"}
        if "それでいこう" in text:
            return {"reaction": "FINALIZE"}
        return {"reaction": "OTHER"}
    if "検索クエリ" in prompt:
        return {"query": "静かなカフェ"}
    if "インデックス" in prompt:
        return {"index": 0}
    return {}


def fake_gemini(prompt: str, system: str = "", temperature: float = 0.5) -> str:
    return "いい店を見つけたよ。〜はどうかね？"


# 自由入力（is_quick_reply=False）の意図解析。実際の _classify_free_text と
# 同じ関数名解決を模した、プロンプト内容ディスパッチのフェイク。
_REQUEST_KEYWORDS = ["夜ご飯", "食事", "休憩", "カフェ", "静かな場所", "もっと"]
_APPROVE_PREV_MARKERS = ["の後", "を出て", "行った", "終わったら", "次にどこ"]


def fake_gemini_function_call(prompt: str, tools, system: str) -> tuple[str, dict]:
    text = _extract_quoted(prompt)

    has_request = any(k in text for k in _REQUEST_KEYWORDS)
    has_approve_marker = any(k in text for k in _APPROVE_PREV_MARKERS)

    if has_request:
        request_text = next((k for k in _REQUEST_KEYWORDS if k in text), text)
        return "change_request", {
            "request_text": request_text,
            "approve_previous": has_approve_marker,
        }
    if any(k in text for k in ("いいね", "面白そう", "行きたい")):
        return "approve_and_continue", {}
    if any(k in text for k in ("違う", "微妙")):
        return "reject_and_continue", {}
    if any(k in text for k in ("それでいこう", "決定")):
        return "finalize_route", {}
    return "", {}


# ── フィクスチャ ────────────────────────────────────────────

@pytest.fixture
def spot_pool():
    return make_spot_pool()


@pytest.fixture
def patched(monkeypatch, spot_pool):
    """全外部依存をモックした状態を提供する標準フィクスチャ"""

    def fake_fetch_spots(lat, lng, radius_m, text_query, excluded_ids):
        return [copy.deepcopy(s) for s in spot_pool if s["place_id"] not in excluded_ids]

    from schemas import WeatherInfo

    monkeypatch.setattr(nodes, "_gemini_json", fake_gemini_json)
    monkeypatch.setattr(nodes, "_gemini", fake_gemini)
    monkeypatch.setattr(nodes, "_gemini_function_call", fake_gemini_function_call)
    monkeypatch.setattr(nodes, "_fetch_spots", fake_fetch_spots)
    monkeypatch.setattr(services, "get_place_details", lambda pid, key: dict(FAKE_DETAILS))
    monkeypatch.setattr(
        services, "get_current_weather",
        lambda lat, lng: WeatherInfo(condition="晴れ・曇り", temperature=24.0),
    )
    monkeypatch.setattr(
        services, "calculate_route_times",
        lambda api_key, start_lat, start_lng, destinations, transportation: [7] * len(destinations),
    )
    return monkeypatch


@pytest.fixture
def client():
    return TestClient(app)


# ── ヘルパー ────────────────────────────────────────────────

def start_session(client, message="リフレッシュしたい。空き時間は60分くらい。",
                  transportation="walking", lat=35.70, lng=139.98):
    return client.post(
        "/api/v1/chat/session",
        json={"message": message, "latitude": lat, "longitude": lng,
              "transportation": transportation},
    )


def send(client, thread_id, message, is_quick_reply=True):
    """既定はクイックリプライボタン由来（固定分類）。自由入力の意図解析を
    テストする場合は is_quick_reply=False を渡す。"""
    return client.post(
        f"/api/v1/chat/{thread_id}",
        json={"message": message, "is_quick_reply": is_quick_reply},
    )


def graph_state(thread_id) -> dict:
    """MemorySaver からスレッドの現在状態を取得"""
    return compiled_graph.get_state(
        {"configurable": {"thread_id": thread_id}}
    ).values
