"""LangGraph nodes for the run_query workflow (#33) -- each one wraps a call that used
to happen inline in engine.py's retry loop, unchanged in substance.

WARNING, two non-obvious constraints on how this file imports modules.query.engine:

1. It must import the MODULE (`from modules.query import engine`), never a function
   directly (`from modules.query.engine import execute`) -- existing tests
   (test_query_engine.py) do `monkeypatch.setattr(engine, "execute", ...)`, which only
   intercepts calls made as `engine.execute(...)` at call time. A direct function import
   would bind its own name to the original function and silently stop honoring that
   monkeypatch, breaking the "#25/#31 tests untouched and passing" bar this ticket set
   for itself. Same reasoning extends to validate/is_ranking_question/
   try_ranking_query even though nothing patches those today.
2. That import must happen INSIDE each function, not at module load time. engine.py
   imports modules.workflow.graph (to build its graph), which imports this file, which
   would import engine.py right back -- a real circular import, and unlike a plain
   `import X` cycle, Python can't paper over it here because engine.py needs graph.py's
   `build_graph` *name* bound before it finishes, not just the module object. Deferring
   the `from modules.query import engine` line to call time sidesteps this entirely: by
   the time any node actually runs, every module involved has long finished loading.
   (Confirmed by hand: `python -c "from modules.workflow.graph import build_graph"` -- the
   ticket's own verify command -- raises ImportError with a module-level import here.)
"""

import asyncio

from modules.workflow.state import QueryState
from shared.exceptions import DatabaseError


def check_ranking(state: QueryState) -> QueryState:
    """Ranking questions ("top N", "welcher hat den hoechsten...") are the 7B's worst
    LIMIT-dialect failure mode (#15) -- decide once, up front, whether this question
    qualifies for the deterministic TOP-N template instead of free-form generation.
    Only for a single, unambiguous subject table -- ranking across a JOIN isn't in scope.
    """
    from modules.query import engine  # see module docstring re: lazy import

    state = dict(state)
    state["is_ranking_candidate"] = len(state["tables"]) == 1 and engine.is_ranking_question(state["question"])
    return state


def ranking_attempt(state: QueryState) -> QueryState:
    from modules.query import engine  # see module docstring re: lazy import

    state = dict(state)
    attempt = asyncio.run(
        engine.try_ranking_query(state["question"], state["tables"][0], state["schema_context"], state["provider"])
    )
    state["ranking_ok"] = attempt.ok
    if attempt.ok:
        state["status"] = "SUCCESS"
        state["sql"] = attempt.sql
        state["rows"] = attempt.rows
        state["columns"] = attempt.columns
    return state


def generate_sql(state: QueryState) -> QueryState:
    state = dict(state)
    state["attempts"] += 1
    generated = asyncio.run(
        state["provider"].generate_sql(
            state["question"],
            state["schema_context"],
            state["few_shots"],
            state["last_error"],
            state["date_from"],
            state["date_to"],
        )
    )

    if generated.error == "OUT_OF_SCOPE":
        state["status"] = "OUT_OF_SCOPE"
        state["sql"] = None
        return state

    if not generated.sql:
        state["last_error"] = "LLM returned neither sql nor an OUT_OF_SCOPE error"
        state["sql"] = None
        return state

    state["sql"] = generated.sql
    return state


def validate_sql(state: QueryState) -> QueryState:
    from modules.query import engine  # see module docstring re: lazy import

    state = dict(state)
    validated = engine.validate(state["sql"])
    if not validated.ok:
        state["last_error"] = validated.error
        state["sql"] = None
    else:
        state["sql"] = validated.sql
    return state


def execute_sql(state: QueryState) -> QueryState:
    from modules.query import engine  # see module docstring re: lazy import

    state = dict(state)
    try:
        result = engine.execute(state["sql"])
    except DatabaseError as e:
        state["last_error"] = str(e)
        state["sql"] = None
        return state

    state["status"] = "SUCCESS"
    state["rows"] = result.rows
    state["columns"] = result.columns
    return state


def give_up(state: QueryState) -> QueryState:
    state = dict(state)
    state["status"] = "GAVE_UP"
    state["error"] = state["last_error"]
    return state


def finish(state: QueryState) -> QueryState:
    """Terminal passthrough -- exists so every path (ranking success, OUT_OF_SCOPE,
    SUCCESS, GAVE_UP) converges on one node before END, which is what makes the mermaid
    export read as a single pipeline rather than four disconnected exits."""
    return state
