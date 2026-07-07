"""CLI eval harness over the curated base question set (#11).

This is the "Big Goal 1" completion marker: run every DB-verified question
through run_query end-to-end and report pass rate + latency, so the 7B
viability verdict is known before any UI exists. The underlying sample data
can shift between runs (row counts have changed mid-project before), so
passing checks for a sensible non-zero/non-empty result, never an exact number.

Run: cd backend && python scripts/eval_query.py
"""

import sys
import time
from pathlib import Path

# Force UTF-8 stdout: on a Windows host whose console codepage isn't UTF-8
# (e.g. GBK), printing the German question text would otherwise crash with
# UnicodeEncodeError partway through the run.
sys.stdout.reconfigure(encoding="utf-8")

# Running this file directly (not via `python -m`) only puts scripts/ on
# sys.path, not backend/ -- add backend/ so `modules`/`shared` imports resolve.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.query.engine import run_query  # noqa: E402
from modules.schema.domain_tables import DOMAIN_TABLES  # noqa: E402
from modules.schema.question_bank import get_all_entries  # noqa: E402

# Planted probes (Task: "1-2 planted out-of-scope probes") -- clearly unrelated
# to CRM data, must come back OUT_OF_SCOPE rather than a hallucinated answer.
OUT_OF_SCOPE_PROBES = [
    "Wie wird das Wetter morgen?",
    "Erzaehl mir einen Witz.",
]


def _tables_for_domains(domains: list[str]) -> list[str]:
    tables: list[str] = []
    for domain in domains:
        for table in DOMAIN_TABLES[domain]:
            if table not in tables:
                tables.append(table)
    return tables


def _is_sensible_nonzero(rows: list[dict] | None) -> bool:
    """Non-empty result; for a single row, at least one numeric column must be non-zero."""
    if not rows:
        return False
    if len(rows) > 1:
        return True
    numeric_values = [v for v in rows[0].values() if isinstance(v, (int, float))]
    return any(numeric_values) if numeric_values else True


def _row_sample(rows: list[dict] | None, limit: int = 3) -> str:
    if not rows:
        return "(no rows)"
    sample = repr(rows[:limit])
    if len(rows) > limit:
        sample += f" ... (+{len(rows) - limit} more)"
    return sample


def _build_cases() -> list[dict]:
    cases = [
        {
            "id": entry["id"],
            "question": entry["question"],
            "tables": _tables_for_domains(entry["domain"]),
            "expect_out_of_scope": False,
        }
        for entry in get_all_entries()
    ]
    cases += [
        {
            "id": f"out_of_scope_probe_{i}",
            "question": question,
            "tables": DOMAIN_TABLES["LEAD"],  # scope given to the probe; it should be refused anyway
            "expect_out_of_scope": True,
        }
        for i, question in enumerate(OUT_OF_SCOPE_PROBES, start=1)
    ]
    return cases


def _run_case(case: dict) -> dict:
    start = time.perf_counter()
    try:
        outcome = run_query(case["question"], case["tables"])
    except Exception as e:
        # A single flaky call (e.g. a transient Ollama/DB hiccup) shouldn't lose
        # the rest of a 9-question, multi-minute run -- record it and move on.
        return {**case, "status": "ERROR", "sql": None, "rows": None, "passed": False,
                "latency": time.perf_counter() - start, "error": str(e)}

    latency = time.perf_counter() - start
    if case["expect_out_of_scope"]:
        passed = outcome.status == "OUT_OF_SCOPE"
    else:
        passed = outcome.status == "SUCCESS" and _is_sensible_nonzero(outcome.rows)

    return {**case, "status": outcome.status, "sql": outcome.sql, "rows": outcome.rows,
            "passed": passed, "latency": latency, "error": None}


def main() -> None:
    cases = _build_cases()
    total = len(cases)
    results = []

    for i, case in enumerate(cases, start=1):
        print(f"[{i}/{total}] {case['id']}")
        print(f"  Q: {case['question']}")
        result = _run_case(case)
        results.append(result)
        print(f"  SQL: {result['sql']}")
        print(f"  Rows: {_row_sample(result['rows'])}")
        verdict = "PASS" if result["passed"] else "FAIL"
        error_suffix = f", error={result['error']}" if result["error"] else ""
        print(f"  Result: {verdict} (status={result['status']}, {result['latency']:.2f}s{error_suffix})")
        print()

    passed_count = sum(1 for r in results if r["passed"])
    latencies = [r["latency"] for r in results]

    print("=== Summary ===")
    print(
        f"Total: {total}  Passed: {passed_count}  Failed: {total - passed_count}  "
        f"Pass rate: {passed_count / total * 100:.1f}%"
    )
    print(
        f"Avg latency: {sum(latencies) / total:.2f}s  "
        f"Min: {min(latencies):.2f}s  Max: {max(latencies):.2f}s"
    )

    if passed_count < total:
        print()
        print("Failed cases:", ", ".join(r["id"] for r in results if not r["passed"]))


if __name__ == "__main__":
    main()
