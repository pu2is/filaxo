"""
Ticket 7 spike: de-risk first-time LangGraph use before Day 1 H5, where the
real Phase 2 pipeline (generate_sql -> validate -> execute -> retry ->
narrate) gets assembled under time pressure.

Toy graph, no LLM/DB calls (see issue #7 scope) -- but shaped like the real
thing: a "generate" node that produces a candidate query, a "validate" node
that checks it, and a conditional edge that either loops back to retry or
moves on to "finish". The bad-then-good SQL is deliberately simulating the
TOP-vs-LIMIT dialect bug found during ticket #4's smoke test.

Run: python spikes/langgraph_hello.py
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph

MAX_ATTEMPTS = 3


class HelloState(TypedDict):
    attempt: int
    sql: str
    valid: bool
    log: list[str]


def generate_sql(state: HelloState) -> HelloState:
    attempt = state["attempt"] + 1
    # toy simulation: first attempt uses the wrong dialect, later ones are fixed
    sql = "SELECT * FROM t LIMIT 1" if attempt == 1 else "SELECT TOP 1 * FROM t"
    log = state["log"] + [f"[generate_sql] attempt {attempt}: {sql}"]
    return {**state, "attempt": attempt, "sql": sql, "log": log}


def validate_sql(state: HelloState) -> HelloState:
    valid = "LIMIT" not in state["sql"]
    log = state["log"] + [f"[validate_sql] valid={valid}"]
    return {**state, "valid": valid, "log": log}


def finish(state: HelloState) -> HelloState:
    outcome = "SUCCESS" if state["valid"] else "GAVE UP"
    log = state["log"] + [
        f"[finish] {outcome} after {state['attempt']} attempt(s): {state['sql']}"
    ]
    return {**state, "log": log}


def route_after_validate(state: HelloState) -> str:
    if state["valid"] or state["attempt"] >= MAX_ATTEMPTS:
        return "finish"
    return "generate_sql"  # retry cycle


def build_graph():
    builder = StateGraph(HelloState)
    builder.add_node("generate_sql", generate_sql)
    builder.add_node("validate_sql", validate_sql)
    builder.add_node("finish", finish)

    builder.set_entry_point("generate_sql")
    builder.add_edge("generate_sql", "validate_sql")
    builder.add_conditional_edges(
        "validate_sql",
        route_after_validate,
        {"generate_sql": "generate_sql", "finish": "finish"},
    )
    builder.add_edge("finish", END)

    return builder.compile()


def main() -> None:
    graph = build_graph()

    test_state: HelloState = {"attempt": 0, "sql": "", "valid": False, "log": []}
    result = graph.invoke(test_state)

    print("=== Execution log ===")
    for line in result["log"]:
        print(line)

    print("\n=== Mermaid diagram ===")
    print(graph.get_graph().draw_mermaid())


if __name__ == "__main__":
    main()
