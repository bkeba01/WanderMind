"""異常系テスト (E-01 〜 E-06)

想定外の入力・通信障害・外部 API の不具合が起きても、
アプリがクラッシュせずに安全に耐えられるかを検証する。
"""
import pytest
import requests as _requests
from conftest import start_session, send, graph_state

from graph import nodes
import services
from services import calculate_route_times, _haversine_minutes


class FakeResp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


ORIGIN = (35.70, 139.98)
DEST = {"location": {"latitude": 35.75, "longitude": 140.00}}


# ── E-01: Routes API の失敗とフォールバックチェーン ─────────

def test_e01_routes_api_success(monkeypatch):
    """正常時: Routes API の duration がそのまま分に変換される"""
    monkeypatch.setattr(
        services.requests, "post",
        lambda url, headers=None, json=None, timeout=None: FakeResp(
            {"routes": [{"duration": "1800s"}]}
        ),
    )
    times = calculate_route_times("key", *ORIGIN, [DEST], "driving")
    assert times == [30]


def test_e01_routes_api_network_failure_falls_back_to_haversine(monkeypatch):
    """通信断: 例外でもクラッシュせず Haversine 推定値を返す"""
    def raise_error(*args, **kwargs):
        raise _requests.ConnectionError("network down")

    monkeypatch.setattr(services.requests, "post", raise_error)

    times = calculate_route_times("key", *ORIGIN, [DEST], "walking")
    expected = _haversine_minutes(
        ORIGIN[0], ORIGIN[1],
        DEST["location"]["latitude"], DEST["location"]["longitude"],
        "walking",
    )
    assert times == [expected]
    assert times[0] > 0


def test_e01_routes_api_empty_routes_falls_back(monkeypatch):
    """routes が空（ZERO_RESULTS 相当）でも Haversine にフォールバック"""
    monkeypatch.setattr(
        services.requests, "post",
        lambda url, headers=None, json=None, timeout=None: FakeResp({}),
    )
    times = calculate_route_times("key", *ORIGIN, [DEST], "driving")
    assert len(times) == 1
    assert times[0] > 0


def test_e01_zero_coordinates_skipped(monkeypatch):
    """目的地座標が (0,0) の場合は API を呼ばず推定値でスキップ"""
    def should_not_be_called(*args, **kwargs):
        raise AssertionError("API を呼んではいけない")

    monkeypatch.setattr(services.requests, "post", should_not_be_called)

    zero_dest = {"location": {"latitude": 0.0, "longitude": 0.0}}
    times = calculate_route_times("key", *ORIGIN, [zero_dest], "walking")
    assert len(times) == 1
    assert times[0] > 0


# ── E-02: Places API のゼロヒット ───────────────────────────

def test_e02_zero_spots(patched, client, monkeypatch):
    monkeypatch.setattr(nodes, "_fetch_spots", lambda *a, **k: [])

    res = start_session(client)
    body = res.json()
    assert res.status_code == 200
    # ハルシネーションせず、正直に「見当たらない」と伝える
    assert "見当たらない" in body["message"]
    assert body["current_suggestion"] is None
    assert body["phase"] == "collecting"  # 会話は継続可能


# ── E-03: Gemini の JSON 解析失敗 ───────────────────────────

def test_e03_broken_gemini_json(patched, client, monkeypatch):
    """壊れた JSON（空 dict）でもデフォルト値で会話が継続する"""
    monkeypatch.setattr(nodes, "_gemini_json", lambda *a, **k: {})

    # セッション開始: mood はユーザー発言そのまま、時間はデフォルト 90 分
    res = start_session(client, message="のんびりしたい")
    body = res.json()
    assert res.status_code == 200
    assert body["current_suggestion"] is not None

    state = graph_state(body["thread_id"])
    assert state["free_time_minutes"] == 90  # デフォルト値
    assert state["search_radius_m"] == 5400  # 90 × 0.3 × 200

    # 会話継続（自由入力）: function call が該当なしなら OTHER → 再提案として安全に処理
    monkeypatch.setattr(nodes, "_gemini_function_call", lambda *a, **k: ("", {}))
    res2 = send(client, body["thread_id"], "ふーん", is_quick_reply=False)
    assert res2.status_code == 200
    assert res2.json()["message"]
    assert res2.json()["liked_spots"] == []  # 誤って承認されない


def test_e03_gemini_api_exception_recovers_with_persona(patched, client, monkeypatch):
    """Gemini API 自体の例外もノードレベルで回復し、マスターの台詞で返る（500 にしない）"""
    def raise_error(*args, **kwargs):
        raise RuntimeError("Gemini unavailable")

    monkeypatch.setattr(nodes, "_gemini_json", raise_error)

    res = start_session(client)
    body = res.json()
    assert res.status_code == 200  # 500 にならない
    assert body["message"]  # マスターのフォールバック台詞
    assert body["phase"] == "collecting"  # 会話は継続可能


def test_e03_reaction_analyzer_exception_recovers(patched, client, monkeypatch):
    """自由入力中の Gemini function calling 例外は OTHER（再提案）として安全に処理される"""
    tid = start_session(client).json()["thread_id"]

    def raise_error(*args, **kwargs):
        raise RuntimeError("Gemini unavailable")

    monkeypatch.setattr(nodes, "_gemini_function_call", raise_error)

    res = send(client, tid, "いいですね、そこにしましょう", is_quick_reply=False)
    assert res.status_code == 200
    assert res.json()["message"]
    # 例外時は APPROVE と判定されないので liked には入らない
    assert res.json()["liked_spots"] == []


# ── E-04: 通信遅延中の二重送信 ──────────────────────────────

@pytest.mark.skip(reason="フロントエンドの isLoading ガードの検証。E2E テストで実施")
def test_e04_double_submit():
    """ChatWindow のボタン disabled={isLoading} と
    handleSend 冒頭の isLoading ガードを E2E で確認する。"""


# ── E-05: 位置情報の取得拒否 ────────────────────────────────

@pytest.mark.skip(reason="ブラウザ Geolocation API の検証。E2E テストで実施。"
                         "期待値: エラーメッセージ表示＋transport 選択に戻り再試行可能")
def test_e05_geolocation_denied():
    """page.tsx の getLocation() 失敗時に catch でエラーメッセージを表示し、
    setupStep を 'transport' に戻して再試行できることを E2E で確認する。"""


# ── E-06: 完了（phase="done"）後の追加メッセージ ─────────────

def test_e06_message_after_done(patched, client):
    tid = start_session(client).json()["thread_id"]
    send(client, tid, "いいね")
    body_done = send(client, tid, "それでいこう").json()
    assert body_done["phase"] == "done"

    # 確定後にさらにメッセージを送る → farewell 固定応答
    res = send(client, tid, "ありがとう！")
    body = res.json()
    assert res.status_code == 200
    assert body["phase"] == "done"  # フェーズは変わらない
    assert "ルートは決まった" in body["message"]

    # route_info が壊れていないこと
    state = graph_state(tid)
    assert state["route_info"] is not None
