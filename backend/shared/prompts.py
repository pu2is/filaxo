"""Prompt templates for LLM calls. Single source of truth — not duplicated in chat/."""

_INSTRUCTIONS = """You are a T-SQL (Microsoft SQL Server) query generator for a CRM analytics chatbot.

Rules:
- Use ONLY the tables and columns described in the schema below. Never invent a column or table.
- Follow every warning in the schema exactly (mandatory filters, masked/unusable columns, NULL columns, etc.).
- Write a single SELECT statement in T-SQL syntax (use TOP, not LIMIT).
- If the question cannot be answered with the given schema — it is unrelated to this data,
  or asks for something outside CRM analytics (e.g. weather, general knowledge, greetings) —
  respond with {"error": "OUT_OF_SCOPE"} and leave "sql"/"explanation" out.
- Otherwise respond with "sql" (the query) and a short one-sentence "explanation" of what it returns.
- Respond with JSON only, matching the given schema. No markdown code fences, no text outside the JSON."""


def build_generate_sql_prompt(
    question: str,
    schema_context: str,
    few_shots: list[str],
    last_error: str | None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> str:
    parts = [_INSTRUCTIONS, "", "# Schema", schema_context]

    if few_shots:
        parts += ["", "# Examples", "\n\n".join(few_shots)]

    # Dates are computed in Python (see modules/query/schemas.TimeRange) and injected
    # as an explicit ISO range here -- the 7B never computes "this month" itself (#24).
    if date_from and date_to:
        parts += [
            "",
            "# Time range",
            f"Restrict the query to {date_from} through {date_to} (inclusive), applied to "
            "the date/datetime column noted in the schema comments above. Use these exact "
            "dates as literals; do not compute a relative range yourself.",
        ]

    if last_error:
        parts += ["", "# Previous attempt failed with this error — fix it", last_error]

    parts += ["", "# Question", question]

    return "\n".join(parts)


_RANKING_INSTRUCTIONS = """You extract ranking parameters from a question about the schema below.
You do NOT write SQL here -- only identify what to sort by.

Respond with JSON only:
- "sort_column": the exact column name, spelled exactly as it appears in the schema below.
  Never invent a column that isn't listed there.
- "direction": "DESC" for highest/most/best/top-ranked, "ASC" for lowest/least/fewest.
- "n": how many rows the question asks for. If it says "welcher"/"welche" (which one) with
  no count, that means exactly 1. Otherwise use the stated number (e.g. "Top 5" -> 5)."""


def build_ranking_params_prompt(question: str, schema_context: str) -> str:
    return "\n".join([_RANKING_INSTRUCTIONS, "", "# Schema", schema_context, "", "# Question", question])
