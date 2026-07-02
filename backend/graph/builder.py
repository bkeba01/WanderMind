from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from graph.state import WanderMindState
from graph.nodes import (
    turn_router_node,
    route_by_phase,
    mood_intake_node,
    spot_suggester_node,
    reaction_analyzer_node,
    route_reaction,
    mood_updater_node,
    spot_accumulator_node,
    route_planner_node,
    route_presenter_node,
    farewell_node,
)


def build_graph():
    builder = StateGraph(WanderMindState)

    # ── ノード登録 ──────────────────────────────────────────
    builder.add_node("turn_router", turn_router_node)
    builder.add_node("mood_intake", mood_intake_node)
    builder.add_node("spot_suggester", spot_suggester_node)
    builder.add_node("reaction_analyzer", reaction_analyzer_node)
    builder.add_node("mood_updater", mood_updater_node)
    builder.add_node("spot_accumulator", spot_accumulator_node)
    builder.add_node("route_planner", route_planner_node)
    builder.add_node("route_presenter", route_presenter_node)
    builder.add_node("farewell", farewell_node)

    # ── エントリーポイント ───────────────────────────────────
    builder.set_entry_point("turn_router")

    # ── エッジ: turn_router → phaseに応じて分岐 ────────────
    builder.add_conditional_edges(
        "turn_router",
        route_by_phase,
        {
            "start": "mood_intake",        # 初回: 気分を取得してスポット提案へ
            "collecting": "reaction_analyzer",  # 会話中: ユーザー反応を分析
            "done": "farewell",            # 終了後: 軽く返答して終わり
        },
    )

    # ── エッジ: 初回フロー ───────────────────────────────────
    builder.add_edge("mood_intake", "spot_suggester")
    builder.add_edge("spot_suggester", END)

    # ── エッジ: 反応に応じた分岐 ────────────────────────────
    #   APPROVE    → スポットを承認リストへ追加 → 次のスポットを提案
    #   REJECT     → 別のスポットをすぐ提案
    #   MOOD_UPDATE→ 気分を更新 → 新しい気分でスポットを提案
    #   FINALIZE   → ルートを計算して発表
    builder.add_conditional_edges(
        "reaction_analyzer",
        route_reaction,
        {
            "approve": "spot_accumulator",
            "reject": "spot_suggester",
            "mood_update": "mood_updater",
            "finalize": "route_planner",
        },
    )

    builder.add_edge("spot_accumulator", "spot_suggester")
    builder.add_edge("mood_updater", "spot_suggester")

    # ── エッジ: ルート計画 → 発表 → 終了 ────────────────────
    builder.add_edge("route_planner", "route_presenter")
    builder.add_edge("route_presenter", END)
    builder.add_edge("farewell", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


compiled_graph = build_graph()
