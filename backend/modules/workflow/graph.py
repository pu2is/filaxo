"""Assembles the run_query StateGraph (#33, D3) -- nodes wrap the existing generate/
validate/execute/ranking calls (nodes.py), edges replicate the old for-loop's retry/
branch logic (edges.py). `run_query`'s signature and QueryOutcome shape are unchanged;
this is purely an internal orchestration swap, timeboxed per the roadmap.

    Verkauf & Leads-style trace: check_ranking -> generate_sql -> validate_sql ->
    execute_sql -> finish, with generate_sql/validate_sql/execute_sql each able to loop
    back to generate_sql (retry) or fall to give_up once max_attempts is exhausted.
    ranking_attempt is a parallel first branch for "top N"-style questions (#15); if it
    doesn't produce a usable query it also falls through to generate_sql, never to
    give_up directly (a ranking miss isn't itself a retry-exhausting failure).

See docs/pipeline-graph.md for the actual rendered mermaid diagram.
"""

from langgraph.graph import END, StateGraph

from modules.workflow import edges, nodes
from modules.workflow.state import QueryState


def build_graph():
    builder = StateGraph(QueryState)

    builder.add_node("check_ranking", nodes.check_ranking)
    builder.add_node("ranking_attempt", nodes.ranking_attempt)
    builder.add_node("generate_sql", nodes.generate_sql)
    builder.add_node("validate_sql", nodes.validate_sql)
    builder.add_node("execute_sql", nodes.execute_sql)
    builder.add_node("give_up", nodes.give_up)
    builder.add_node("finish", nodes.finish)

    builder.set_entry_point("check_ranking")

    builder.add_conditional_edges(
        "check_ranking",
        edges.route_after_ranking_check,
        {"ranking_attempt": "ranking_attempt", "generate_sql": "generate_sql"},
    )
    builder.add_conditional_edges(
        "ranking_attempt",
        edges.route_after_ranking_attempt,
        {"finish": "finish", "generate_sql": "generate_sql"},
    )
    builder.add_conditional_edges(
        "generate_sql",
        edges.route_after_generate,
        {
            "finish": "finish",
            "validate_sql": "validate_sql",
            "generate_sql": "generate_sql",
            "give_up": "give_up",
        },
    )
    builder.add_conditional_edges(
        "validate_sql",
        edges.route_after_validate,
        {"execute_sql": "execute_sql", "generate_sql": "generate_sql", "give_up": "give_up"},
    )
    builder.add_conditional_edges(
        "execute_sql",
        edges.route_after_execute,
        {"finish": "finish", "generate_sql": "generate_sql", "give_up": "give_up"},
    )
    builder.add_edge("give_up", "finish")
    builder.add_edge("finish", END)

    return builder.compile()
