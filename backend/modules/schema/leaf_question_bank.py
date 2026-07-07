"""Loader for the per-leaf expert question bank (leaf_question_bank.yaml, #29).

Separate from question_bank.py/.yaml on purpose: that pair serves the flat Wave-1
funnel's DOMAIN_TABLES-scoped eval set (#11), still live in production. This one is
scoped to scope_tree.py's leaf ids and is consumed by scripts/eval_query.py's
per-bucket/per-leaf summary, by get_few_shots() (called from chat/service.py's
_answer_question, #31), and by get_suggestions() below (called from _ready_prompt, D8/#36).
"""

from pathlib import Path

import yaml

_BANK_PATH = Path(__file__).parent / "leaf_question_bank.yaml"

with _BANK_PATH.open("r", encoding="utf-8") as _f:
    _ENTRIES: list[dict] = yaml.safe_load(_f) or []

# "Bank != prompt" (#29): only this many of a leaf's best bucket-A entries ever become
# a few-shot, in the file's own curated order -- the rest exist for eval/chips, not prompts.
MAX_FEW_SHOTS_PER_LEAF = 3

# D8/#36: cap on the Frage-Empfehlung panel, same rationale as MAX_FEW_SHOTS_PER_LEAF --
# a suggestion chip list is meant to be a short nudge, not the whole bank.
MAX_SUGGESTIONS_PER_LEAF = 5


def get_all_entries() -> list[dict]:
    """Return every entry (all buckets, all nodes) -- used by the eval harness, which
    needs B and C too, unlike get_few_shots below."""
    return list(_ENTRIES)


def get_few_shots(node: str | list[str]) -> list[str]:
    """Return up to MAX_FEW_SHOTS_PER_LEAF formatted question->SQL blocks for one leaf.

    Held-out exclusion is absolute: only bucket "A" AND verified=True entries qualify --
    a B/C entry, or an unverified one, must never reach a generate_sql prompt regardless
    of how it's tagged otherwise. `node` accepts either "LEAD.SCORING" or ["LEAD","SCORING"]
    (matches modules.schema.scope_tree's path convention).
    """
    target = node if isinstance(node, str) else ".".join(node)
    matches = [e for e in _ENTRIES if e["node"] == target and e["bucket"] == "A" and e["verified"]]
    matches = matches[:MAX_FEW_SHOTS_PER_LEAF]
    return [f"-- Frage: {e['question']}\n{e['reference_sql'].strip()}" for e in matches]


def get_suggestions(node: str | list[str]) -> list[dict]:
    """Return up to MAX_SUGGESTIONS_PER_LEAF entries for the D8 Frage-Empfehlung panel:
    every bucket-A entry, plus bucket-B entries that aren't a "known gap" (no `note`).
    Bucket C and any noted B entry are excluded.

    Unlike get_few_shots, `verified` is NOT filtered on: a suggestion only offers the
    question text for the user to click, which the LLM re-generates SQL for at that
    point -- the stored reference_sql's verification status only matters where it's
    actually injected into a prompt (get_few_shots).
    """
    target = node if isinstance(node, str) else ".".join(node)
    matches = [
        e
        for e in _ENTRIES
        if e["node"] == target and (e["bucket"] == "A" or (e["bucket"] == "B" and "note" not in e))
    ]
    return matches[:MAX_SUGGESTIONS_PER_LEAF]
