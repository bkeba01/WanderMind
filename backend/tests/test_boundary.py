"""境界入力テスト (B-01 〜 B-05)

入力や状態の端・限界値・条件の切れ目でシステムが破綻しないかを検証する。
"""
import copy
import pytest
from conftest import start_session, send, graph_state, make_spot_pool

from graph import nodes
from graph.nodes import _free_time_to_radius, spot_accumulator_node


# ── B-01: 空き時間の最小/最大による半径計算 ──────────────────

def test_b01_radius_boundaries():
    assert _free_time_to_radius(30) == 1800    # 30分 → 1800m
    assert _free_time_to_radius(240) == 12000  # 半日 → 上限 12km にキャップ
    assert _free_time_to_radius(10) == 1500    # 極小 → 下限 1500m
    assert _free_time_to_radius(1000) == 12000 # 超過大 → 上限維持


# ── B-02: 未承認（0件）のままルート確定 ─────────────────────

def test_b02_finalize_with_zero_liked(patched, client):
    body0 = start_session(client).json()
    tid = body0["thread_id"]
    suggested_id = body0["current_suggestion"]["place_id"]

    # いいねを押さずにいきなり確定
    res = send(client, tid, "それでいこう")
    body = res.json()
    assert res.status_code == 200
    assert body["phase"] == "done"
    # current_suggestion が 1 件だけのルートとして採用される
    assert len(body["route_info"]["spots"]) == 1
    assert body["route_info"]["spots"][0]["place_id"] == suggested_id


# ── B-03: 検索半径縮小の限界到達（下限 1500m で収束）────────

def test_b03_radius_floor():
    """承認を繰り返しても半径は下限 1500m で止まり、負や 0 にならない"""
    pool = make_spot_pool(12)
    liked_10 = pool[:10]
    state = {
        "liked_spots": liked_10[:-1],
        "current_suggestion": liked_10[-1],
        "search_radius_m": 3600,
        "user_lat": 35.70,
        "user_lng": 139.98,
    }
    result = spot_accumulator_node(state)
    # 3600 × 0.85^9 ≈ 834m → 下限 1500m に収束
    assert result["search_radius_m"] == 1500
    assert len(result["liked_spots"]) == 10


def test_b03_radius_shrink_progression():
    """縮小係数 0.85^(n-1) が式どおりに適用される"""
    pool = make_spot_pool(5)
    state = {
        "liked_spots": pool[:2],
        "current_suggestion": pool[2],
        "search_radius_m": 3600,
        "user_lat": 35.70,
        "user_lng": 139.98,
    }
    result = spot_accumulator_node(state)
    # liked が 3 件 → int(3600 × 0.85^2) = 2600（float 誤差により切り捨て）
    assert result["search_radius_m"] == 2600


# ── B-04: テキスト入力の文字数上限 ──────────────────────────

def test_b04_very_long_message(patched, client):
    long_message = "のんびりしたい。" * 200 + "空き時間は60分くらい。"  # 約1600文字
    res = start_session(client, message=long_message)
    assert res.status_code == 200
    assert res.json()["phase"] == "collecting"
    assert res.json()["current_suggestion"] is not None


def test_b04_long_message_mid_conversation(patched, client):
    tid = start_session(client).json()["thread_id"]
    res = send(client, tid, "違う。" + "もっと別の場所がいいな。" * 100)
    assert res.status_code == 200
    assert res.json()["message"]


# ── B-05: 最大件数（10件）未満のスポットヒット ───────────────

def test_b05_few_candidates(patched, client, monkeypatch):
    small_pool = make_spot_pool(2)

    def fetch_two(lat, lng, radius_m, text_query, excluded_ids):
        return [copy.deepcopy(s) for s in small_pool if s["place_id"] not in excluded_ids]

    monkeypatch.setattr(nodes, "_fetch_spots", fetch_two)

    # 候補 2 件でも正常に提案される
    body0 = start_session(client).json()
    assert body0["current_suggestion"] is not None
    tid = body0["thread_id"]

    # 拒否 → 残り 1 件が提案される
    body1 = send(client, tid, "違う").json()
    assert body1["current_suggestion"]["place_id"] != body0["current_suggestion"]["place_id"]

    # さらに拒否 → 候補ゼロ → 謝りメッセージ（E-02 相当のフォールバック）
    body2 = send(client, tid, "違う").json()
    assert "見当たらない" in body2["message"]
