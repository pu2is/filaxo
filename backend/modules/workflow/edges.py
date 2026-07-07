"""Conditional-edge routing for the run_query workflow (#33) -- each function reads
QueryState and names the next node; graph.py passes the {return-value: node-name}
mapping to add_conditional_edges, so the actual dispatch is LangGraph's job, not this
file's. Together these replicate engine.py's old for-loop retry/branch logic exactly.
"""

from modules.workflow.state import QueryState


def route_after_ranking_check(state: QueryState) -> str:
    return "ranking_attempt" if state["is_ranking_candidate"] else "generate_sql"


def route_after_ranking_attempt(state: QueryState) -> str:
    # A hallucinated/invalid sort_column falls through to the normal generate_sql path
    # rather than failing outright (#15) -- this is the ranking node's only exit besides
    # straight success.
    return "finish" if state["ranking_ok"] else "generate_sql"


def route_after_generate(state: QueryState) -> str:
    if state["status"] == "OUT_OF_SCOPE":
        return "finish"
    if state["sql"] is None:
        return _retry_or_give_up(state)
    return "validate_sql"


def route_after_validate(state: QueryState) -> str:
    if state["sql"] is None:
        return _retry_or_give_up(state)
    return "execute_sql"


def route_after_execute(state: QueryState) -> str:
    if state["status"] == "SUCCESS":
        return "finish"
    return _retry_or_give_up(state)


def _retry_or_give_up(state: QueryState) -> str:
    """Shared by every failure path: the old for-loop's exit condition, translated to a
    graph edge -- retry generate_sql from scratch, or give up once max_attempts is
    reached. `attempts` is incremented once per generate_sql node visit, not here."""
    return "give_up" if state["attempts"] >= state["max_attempts"] else "generate_sql"
