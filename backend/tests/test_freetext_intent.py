"""自由入力の意図解析テスト (F-01 〜 F-05)

ボタン（クイックリプライ）とチャット自由入力を区別し、自由入力は
Gemini の Function Calling で意図を判断する仕組みを検証する。

回帰対象のバグ: 「よみうりランドを行ったあとに、次にどこ行く。
よみうりランド行き終わったら夜ご飯食べに行きたい。」のような、
前の提案を承認しつつ新しい具体的要望を伝える複合発言が、
liked_spots への追加にも次の検索クエリにも反映されていなかった。
"""
from conftest import start_session, send, graph_state
from graph import nodes


# ── F-01: ボタン由来は固定分類（Gemini function calling を呼ばない）──

def test_f01_quick_reply_does_not_call_function_calling(patched, client, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("quick reply では function calling を呼んではいけない")

    monkeypatch.setattr(nodes, "_gemini_function_call", fail_if_called)

    tid = start_session(client).json()["thread_id"]
    res = send(client, tid, "いいね", is_quick_reply=True)
    assert res.status_code == 200
    assert len(res.json()["liked_spots"]) == 1


# ── F-02: 自由入力の複合発言（承認 + 新要望）が両方反映される ────

def test_f02_free_text_approve_and_new_request(patched, client):
    body0 = start_session(client).json()
    tid = body0["thread_id"]
    first_name = body0["current_suggestion"]["name"]

    msg = "よみうりランドを行ったあとに、次にどこ行く。よみうりランド行き終わったら夜ご飯食べに行きたい。"
    res = send(client, tid, msg, is_quick_reply=False)
    body = res.json()
    assert res.status_code == 200

    # 前の提案が liked_spots に追加されている（見逃されていた挙動）
    assert len(body["liked_spots"]) == 1
    assert body["liked_spots"][0]["name"] == first_name

    # 新しい要望が current_mood / next_request_hint に反映されている
    state = graph_state(tid)
    assert "夜ご飯" in state["current_mood"]
    assert "夜ご飯" in state["next_request_hint"]


# ── F-03: 自由入力の単純な新要望（承認マーカーなし）────────────

def test_f03_free_text_request_without_approval(patched, client):
    tid = start_session(client).json()["thread_id"]

    res = send(client, tid, "もっと静かな場所がいい", is_quick_reply=False)
    body = res.json()
    assert res.status_code == 200
    # 承認マーカーがないので liked_spots には追加されない
    assert body["liked_spots"] == []

    state = graph_state(tid)
    assert "静かな場所" in state["current_mood"]


# ── F-04: 自由入力でも通常の承認・拒否・確定は機能する ───────────

def test_f04_free_text_approve_reject_finalize(patched, client):
    tid = start_session(client).json()["thread_id"]

    res1 = send(client, tid, "いいですね、行きたいです", is_quick_reply=False)
    assert len(res1.json()["liked_spots"]) == 1

    res2 = send(client, tid, "うーん違うかな", is_quick_reply=False)
    assert len(res2.json()["liked_spots"]) == 1  # 増えない

    res3 = send(client, tid, "それで決定でお願いします", is_quick_reply=False)
    assert res3.json()["phase"] == "done"


# ── F-05: 未知の発言は OTHER として安全に再提案される ────────────

def test_f05_free_text_unknown_falls_back_to_other(patched, client):
    tid = start_session(client).json()["thread_id"]
    res = send(client, tid, "ところで今日は何曜日？", is_quick_reply=False)
    assert res.status_code == 200
    assert res.json()["message"]
    assert res.json()["liked_spots"] == []
