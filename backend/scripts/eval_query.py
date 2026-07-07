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
from modules.schema.leaf_question_bank import get_all_entries as get_leaf_entries  # noqa: E402
from modules.schema.leaf_question_bank import get_few_shots  # noqa: E402
from modules.schema.question_bank import get_all_entries  # noqa: E402
from modules.schema.scope_tree import resolve  # noqa: E402

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


def _run_flat_bank_eval() -> list[dict]:
    """The original Big Goal 1 eval (#11): flat DOMAIN_TABLES scope, the question_bank.yaml
    base set + 2 out-of-scope probes. Still the regression net for the live Wave-1 funnel
    (#25/#26), which doesn't use the scope tree yet -- unchanged by #30."""
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

    print("=== Flat-bank Summary (#11, Wave 1 funnel) ===")
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
    return results


# A representative single-table scope for bucket-C probes (#30): they're meant to be
# refused regardless of scope, same convention scripts/eval_query.py already used for
# OUT_OF_SCOPE_PROBES above (DOMAIN_TABLES["LEAD"]) -- LEAD.OVERVIEW is that leaf's
# equivalent single-table scope.
_PROBE_TABLES = resolve("LEAD.OVERVIEW")["tables"]


def _run_leaf_case(entry: dict) -> dict:
    tables = _PROBE_TABLES if entry["node"] == "ANY" else resolve(entry["node"])["tables"]
    # Few-shots on (#30, per-user alignment): this is what #31 will actually do once the
    # tree is wired into the funnel, so testing "cold" (no few-shot) would measure a
    # scenario that will never happen in production. Bucket A ends up seeing itself as
    # its own example (every leaf has <=3 bucket-A entries, MAX_FEW_SHOTS_PER_LEAF=3) --
    # that's intentional, not a leak: it's exactly the guidance a real question on that
    # leaf will get. Bucket B never appears in its own few-shots (only bucket A qualifies,
    # see leaf_question_bank.get_few_shots), so B's pass rate is the genuine held-out
    # generalization signal the "B/C" design was meant to produce.
    few_shots = [] if entry["node"] == "ANY" else get_few_shots(entry["node"])
    start = time.perf_counter()
    try:
        outcome = run_query(entry["question"], tables, few_shots=few_shots)
    except Exception as e:
        return {**entry, "status": "ERROR", "sql": None, "rows": None, "passed": False,
                "latency": time.perf_counter() - start, "error": str(e), "fail_reason": None}

    latency = time.perf_counter() - start
    fail_reason = None
    if entry["bucket"] == "C":
        # The one hard rule (#30): a C-question answered with data is a FAIL, full stop --
        # GAVE_UP isn't the desired refusal either, but only SUCCESS-with-rows gets this
        # specific label since that's the dangerous case (a hallucinated answer).
        passed = outcome.status == "OUT_OF_SCOPE"
        if not passed and outcome.status == "SUCCESS":
            fail_reason = "C-question answered with data"
    elif entry["bucket"] == "A":
        # Few-shot-caliber bar: must succeed AND return something real (matches every
        # bucket-A entry's yaml-recorded row_count > 0, #29).
        passed = outcome.status == "SUCCESS" and _is_sensible_nonzero(outcome.rows)
    else:  # bucket B: plausible in-domain, deliberately not few-shot-grade -- SUCCESS is
        # enough (some B entries are legitimate-empty known gaps, #29's known-gaps §9/§10).
        passed = outcome.status == "SUCCESS"

    return {**entry, "status": outcome.status, "sql": outcome.sql, "rows": outcome.rows,
            "passed": passed, "latency": latency, "error": outcome.error, "fail_reason": fail_reason}


def _print_rate_table(title: str, results: list[dict], group_key: str) -> None:
    groups: dict[str, list[dict]] = {}
    for r in results:
        groups.setdefault(r[group_key], []).append(r)

    print(f"--- {title} ---")
    for key in sorted(groups):
        group = groups[key]
        passed = sum(1 for r in group if r["passed"])
        print(f"  {key}: {passed}/{len(group)} ({passed / len(group) * 100:.1f}%)")


def _run_leaf_bank_eval() -> list[dict]:
    """#30's new eval: the per-leaf expert question bank (#29), scope resolved via
    scope_tree.resolve() instead of the flat DOMAIN_TABLES dict. Reports per-bucket and
    per-leaf pass rates -- bucket A must hit 100% before #31 wires the tree into the
    live funnel (per this ticket's acceptance criteria)."""
    entries = get_leaf_entries()
    total = len(entries)
    results = []

    for i, entry in enumerate(entries, start=1):
        print(f"[{i}/{total}] {entry['id']} (node={entry['node']}, bucket={entry['bucket']})")
        print(f"  Q: {entry['question']}")
        result = _run_leaf_case(entry)
        results.append(result)
        print(f"  SQL: {result['sql']}")
        print(f"  Rows: {_row_sample(result['rows'])}")
        verdict = "PASS" if result["passed"] else "FAIL"
        suffix = ""
        if result["error"]:
            suffix = f", error={result['error']}"
        elif result["fail_reason"]:
            suffix = f", fail_reason={result['fail_reason']}"
        print(f"  Result: {verdict} (status={result['status']}, {result['latency']:.2f}s{suffix})")
        print()

    passed_count = sum(1 for r in results if r["passed"])
    print("=== Leaf-bank Summary (#29/#30) ===")
    print(f"Total: {total}  Passed: {passed_count}  Failed: {total - passed_count}  "
          f"Pass rate: {passed_count / total * 100:.1f}%")
    print()
    _print_rate_table("Per-bucket pass rate", results, "bucket")
    print()
    _print_rate_table("Per-leaf pass rate", [r for r in results if r["node"] != "ANY"], "node")

    bucket_a = [r for r in results if r["bucket"] == "A"]
    bucket_a_rate = sum(1 for r in bucket_a if r["passed"]) / len(bucket_a) * 100
    print()
    print(f"Bucket A pass rate: {bucket_a_rate:.1f}% -- must be 100% before #31 proceeds")

    failed = [r["id"] for r in results if not r["passed"]]
    if failed:
        print()
        print("Failed cases:", ", ".join(failed))
    return results


def main() -> None:
    _run_flat_bank_eval()
    print()
    print("=" * 80)
    print()
    _run_leaf_bank_eval()


if __name__ == "__main__":
    main()
