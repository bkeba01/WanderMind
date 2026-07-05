"""改善機能テスト (I-01 〜 I-06)

営業時間チェック・残り時間管理・拒否履歴・天気連携・
文脈クイックリプライの動作を検証する。
"""
from conftest import start_session, send, graph_state, FAKE_DETAILS

import services


# ── I-01: 営業状況が current_suggestion に付与される ─────────

def test_i01_open_now_propagated(patched, client):
    body = start_session(client).json()
    sug = body["current_suggestion"]
    assert sug["open_now"] is True
    assert sug["opening_hours_today"] == "月曜日: 9時00分～18時00分"


# ── I-02: 閉店中のスポットも正直に伝わる ────────────────────

def test_i02_closed_spot_propagated(patched, client, monkeypatch):
    closed_details = dict(FAKE_DETAILS, open_now=False)
    monkeypatch.setattr(services, "get_place_details", lambda pid, key: closed_details)

    body = start_session(client).json()
    assert body["current_suggestion"]["open_now"] is False
    # クラッシュせずメッセージも返る（閉店の言及は Gemini プロンプト側で制御）
    assert body["message"]


# ── I-03: 文脈クイックリプライがレスポンスに含まれる ─────────

def test_i03_quick_replies_returned(patched, client):
    body = start_session(client).json()
    assert body["quick_replies"] == ["☕ もっと静かな店がいい", "🍽️ 先に食事がしたい"]

    # 会話継続でも更新される
    tid = body["thread_id"]
    body2 = send(client, tid, "違う").json()
    assert len(body2["quick_replies"]) > 0


# ── I-04: 残り時間管理（承認ごとに消費時間を積算）───────────

def test_i04_time_used_accumulates(patched, client):
    tid = start_session(client).json()["thread_id"]

    send(client, tid, "いいね")
    state1 = graph_state(tid)
    # 滞在60分 + 移動7分 = 67分
    assert state1["time_used_minutes"] == 67

    send(client, tid, "いいね")
    state2 = graph_state(tid)
    assert state2["time_used_minutes"] == 134


# ── I-05: 拒否履歴の追跡と連続カウンタ ──────────────────────

def test_i05_rejected_tracking(patched, client):
    body0 = start_session(client).json()
    tid = body0["thread_id"]
    first_name = body0["current_suggestion"]["name"]

    # 1回目の拒否
    send(client, tid, "違う")
    state1 = graph_state(tid)
    assert first_name in state1["rejected_spot_names"]
    assert state1["consecutive_rejects"] == 1

    # 2回目の拒否 → カウンタ加算
    send(client, tid, "違う")
    state2 = graph_state(tid)
    assert len(state2["rejected_spot_names"]) == 2
    assert state2["consecutive_rejects"] == 2

    # 承認でカウンタがリセット（履歴は残る）
    send(client, tid, "いいね")
    state3 = graph_state(tid)
    assert state3["consecutive_rejects"] == 0
    assert len(state3["rejected_spot_names"]) == 2


# ── I-06: 天気が state に保存される ─────────────────────────

def test_i06_weather_stored(patched, client):
    tid = start_session(client).json()["thread_id"]
    state = graph_state(tid)
    assert "晴れ" in state["weather"]
    assert "24" in state["weather"]


# ── I-07: 候補キャッシュ（REJECT 時に Places API を叩かない）──

def test_i07_reject_uses_candidate_cache(patched, client, monkeypatch):
    from graph import nodes
    from conftest import make_spot_pool
    import copy

    pool = make_spot_pool()
    call_count = {"n": 0}

    def counting_fetch(lat, lng, radius_m, text_query, excluded_ids):
        call_count["n"] += 1
        return [copy.deepcopy(s) for s in pool if s["place_id"] not in excluded_ids]

    monkeypatch.setattr(nodes, "_fetch_spots", counting_fetch)

    tid = start_session(client).json()["thread_id"]
    assert call_count["n"] == 1

    # REJECT 2連続 → キャッシュから即答（API 呼び出しは増えない）
    send(client, tid, "違う")
    send(client, tid, "違う")
    assert call_count["n"] == 1

    # APPROVE → 検索中心が動くのでキャッシュ破棄 → 再フェッチ
    send(client, tid, "いいね")
    assert call_count["n"] == 2


# ── I-08: 承認済みスポットの取り消し（DELETE）────────────────

def test_i08_remove_liked_spot(patched, client):
    tid = start_session(client).json()["thread_id"]
    send(client, tid, "いいね")
    send(client, tid, "いいね")

    state = graph_state(tid)
    assert len(state["liked_spots"]) == 2
    remove_id = state["liked_spots"][0]["place_id"]

    res = client.delete(f"/api/v1/chat/{tid}/spots/{remove_id}")
    body = res.json()
    assert res.status_code == 200
    assert len(body["liked_spots"]) == 1
    assert body["liked_spots"][0]["place_id"] != remove_id
    assert body["time_used_minutes"] == 67  # 残り1件分（滞在60+移動7）

    # state 側も更新され、会話を継続できる
    state2 = graph_state(tid)
    assert len(state2["liked_spots"]) == 1
    res2 = send(client, tid, "いいね")
    assert res2.status_code == 200
    assert len(res2.json()["liked_spots"]) == 2


def test_i08_remove_unknown_spot_returns_404(patched, client):
    tid = start_session(client).json()["thread_id"]
    res = client.delete(f"/api/v1/chat/{tid}/spots/unknown-id")
    assert res.status_code == 404


# ── I-09: セッション復元（GET）──────────────────────────────

def test_i09_get_chat_history(patched, client):
    body0 = start_session(client).json()
    tid = body0["thread_id"]
    send(client, tid, "いいね")

    res = client.get(f"/api/v1/chat/{tid}")
    body = res.json()
    assert res.status_code == 200
    assert body["thread_id"] == tid
    assert body["phase"] == "collecting"
    assert len(body["liked_spots"]) == 1
    assert body["transportation"] == "walking"
    assert body["current_suggestion"] is not None
    # メッセージ履歴に user / ai 両方が含まれる
    roles = {m["role"] for m in body["messages"]}
    assert roles == {"user", "ai"}


def test_i09_get_unknown_thread_returns_404(patched, client):
    res = client.get("/api/v1/chat/no-such-thread")
    assert res.status_code == 404
