"""正常系テスト (N-01 〜 N-06)

代表的・想定どおりの操作で、状態遷移・API呼び出し・画面表示が
期待通りに完了するかを検証する。
"""
import pytest
from conftest import start_session, send, graph_state


# ── N-01: 初回セッション生成と初期提案 ──────────────────────

def test_n01_initial_session(patched, client):
    res = start_session(client)
    assert res.status_code == 200

    body = res.json()
    assert body["phase"] == "collecting"
    assert body["thread_id"]
    assert body["message"]  # マスターのメッセージが空でない
    assert body["current_suggestion"] is not None
    assert body["current_suggestion"]["place_id"] == "p0"
    # 詳細情報が付与されている（SpotCard 表示用）
    assert body["current_suggestion"]["photo_url"]
    assert body["current_suggestion"]["travel_time_minutes"] == 7

    state = graph_state(body["thread_id"])
    assert state["free_time_minutes"] == 60
    assert state["search_radius_m"] == 3600  # 60分 × 0.3 × 200


# ── N-02: スポットの承認（APPROVE）ループ ──────────────────

def test_n02_approve_loop(patched, client):
    tid = start_session(client).json()["thread_id"]

    # 1回目の承認
    res1 = send(client, tid, "いいね")
    body1 = res1.json()
    assert res1.status_code == 200
    assert len(body1["liked_spots"]) == 1
    assert body1["liked_spots"][0]["place_id"] == "p0"
    # 新しいスポットが提案される（承認済みとは別）
    assert body1["current_suggestion"]["place_id"] != "p0"

    state1 = graph_state(tid)
    assert state1["search_radius_m"] == 3600  # liked=1 では 0.85^0 = 1（縮小なし）

    # 2回目の承認 → 半径が 0.85 倍に縮小
    res2 = send(client, tid, "いいね")
    body2 = res2.json()
    assert len(body2["liked_spots"]) == 2

    state2 = graph_state(tid)
    assert state2["search_radius_m"] == 3060  # 3600 × 0.85

    # 検索中心が liked_spots の重心に移動
    liked = state2["liked_spots"]
    expected_lat = sum(s["location"]["latitude"] for s in liked) / len(liked)
    expected_lng = sum(s["location"]["longitude"] for s in liked) / len(liked)
    assert abs(state2["search_center_lat"] - expected_lat) < 1e-9
    assert abs(state2["search_center_lng"] - expected_lng) < 1e-9


# ── N-03: スポットの拒否（REJECT）と再提案 ──────────────────

def test_n03_reject_and_resuggest(patched, client):
    body0 = start_session(client).json()
    tid = body0["thread_id"]
    first_id = body0["current_suggestion"]["place_id"]

    res = send(client, tid, "違う")
    body = res.json()
    assert res.status_code == 200
    assert body["liked_spots"] == []  # liked には追加されない
    assert body["current_suggestion"]["place_id"] != first_id  # 別スポット

    state = graph_state(tid)
    # 両方の place_id が提案済みリストに入っている（再提案防止）
    assert first_id in state["suggested_place_ids"]
    assert body["current_suggestion"]["place_id"] in state["suggested_place_ids"]


# ── N-04: 気分の途中変更（MOOD_UPDATE）──────────────────────

def test_n04_mood_update(patched, client):
    tid = start_session(client).json()["thread_id"]

    # 一度承認して検索中心を動かしておく
    send(client, tid, "いいね")

    res = send(client, tid, "もっとはしゃぎたい")
    assert res.status_code == 200
    assert res.json()["current_suggestion"] is not None

    state = graph_state(tid)
    # ボタン由来（動的クイックリプライ相当）は文言そのものが mood_hint になる
    assert state["current_mood"] == "もっとはしゃぎたい"
    # 検索中心・半径がユーザー現在地にリセット
    assert state["search_center_lat"] == 35.70
    assert state["search_center_lng"] == 139.98
    assert state["search_radius_m"] == 3600
    # 初期気分は変わらない
    assert state["initial_mood"] == "リフレッシュしたい"


# ── N-05: ルート確定とサマリー表示（FINALIZE）──────────────

def test_n05_finalize_route(patched, client):
    tid = start_session(client).json()["thread_id"]
    send(client, tid, "いいね")
    send(client, tid, "いいね")

    res = send(client, tid, "それでいこう")
    body = res.json()
    assert res.status_code == 200
    assert body["phase"] == "done"
    assert body["route_info"] is not None
    assert len(body["route_info"]["spots"]) == 2
    assert body["route_info"]["travel_times"] == [7, 7]
    assert body["route_info"]["total_travel_minutes"] == 14


# ── N-06: モバイルレスポンシブ表示 ──────────────────────────

@pytest.mark.skip(reason="フロントエンド CSS の検証。Playwright 等の E2E テストで実施")
def test_n06_mobile_responsive():
    """globals.css の @media (max-width: 767px) で
    .wander-layout が column に切り替わることを E2E で確認する。"""
