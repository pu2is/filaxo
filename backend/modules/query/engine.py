"""The vertical slice: run_query(question, tables) -> QueryOutcome.

#33 (D3): the retry/branch logic that used to be a plain Python for-loop right in this
function is now a LangGraph StateGraph (modules/workflow/{state,nodes,edges,graph}.py),
invoked once per call. run_query's signature and QueryOutcome's shape are unchanged --
this was a pure internal orchestration swap, not a behavior change (see
docs/pipeline-graph.md for the graph itself, scripts/eval_query.py for the before/after
parity proof).

execute/validate/is_ranking_question/try_ranking_query stay imported here (not moved
into modules/workflow/nodes.py) even though this module no longer calls them directly --
nodes.py deliberately calls them as `engine.execute(...)` etc. (a module-attribute
lookup, not a function import) specifically so existing tests' `monkeypatch.setattr(
engine, "execute", ...)` keeps intercepting calls after the swap. Removing these imports
would silently break that.
"""

from dataclasses import dataclass, field
from typing import Literal

from modules.query.executor import execute
from modules.query.ranking import is_ranking_question, try_ranking_query
from modules.query.schemas import TimeRange
from modules.query.validator import validate
from modules.schema.schema_cards import get_schema_context
from modules.workflow.graph import build_graph
from shared.llm import LLMProvider, OllamaProvider

Status = Literal["SUCCESS", "OUT_OF_SCOPE", "GAVE_UP"]


@dataclass
class QueryOutcome:
    status: Status
    sql: str | None = None
    # SUCCESS with rows == [] is a legitimate, distinct outcome from GAVE_UP -- a
    # query that ran fine and found nothing must never be reported as a failure (#24).
    rows: list[dict] | None = None
    columns: list[dict] | None = None
    error: str | None = None
    tables_used: list[str] = field(default_factory=list)


_GRAPH = build_graph()


def run_query(
    question: str,
    tables: list[str],
    max_attempts: int = 3,
    provider: LLMProvider | None = None,
    time_range: TimeRange | None = None,
    few_shots: list[str] | None = None,
) -> QueryOutcome:
    if provider is None:
        provider = OllamaProvider()
    # `few_shots` is additive (#30): the flat Wave-1 funnel still has no domain<->table
    # reverse mapping (#10/#11) so it never passes any and generate_sql runs without them,
    # same as before; a leaf-scoped caller can now pass modules.schema.leaf_question_bank
    # .get_few_shots(node) here once #31 wires the tree into the funnel.
    if few_shots is None:
        few_shots = []
    schema_context = get_schema_context(tables)
    # NOTE: the ranking path doesn't consume time_range yet -- prompt-level time bounds
    # only apply to the generate_sql path (#24 scope; see modules/workflow/nodes.py).
    date_from = time_range.date_from if time_range else None
    date_to = time_range.date_to if time_range else None

    final_state = _GRAPH.invoke({
        "question": question,
        "tables": tables,
        "max_attempts": max_attempts,
        "provider": provider,
        "schema_context": schema_context,
        "few_shots": few_shots,
        "date_from": date_from,
        "date_to": date_to,
        "is_ranking_candidate": False,
        "ranking_ok": False,
        "attempts": 0,
        "sql": None,
        "last_error": None,
        "status": None,
        "rows": None,
        "columns": None,
        "error": None,
    })

    return QueryOutcome(
        status=final_state["status"],
        sql=final_state["sql"],
        rows=final_state["rows"],
        columns=final_state["columns"],
        error=final_state["error"],
        tables_used=tables,
    )
