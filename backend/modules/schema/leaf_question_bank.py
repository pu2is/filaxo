"""Loader for the per-leaf expert question bank (leaf_question_bank.yaml, #29).

Separate from question_bank.py/.yaml on purpose: that pair serves the flat Wave-1
funnel's DOMAIN_TABLES-scoped eval set (#11), still live in production. This one is
scoped to scope_tree.py's leaf ids and isn't wired into the funnel yet (#31) -- today
it's consumed by scripts/eval_query.py's per-bucket/per-leaf summary and by
get_few_shots() below, which #31 will eventually call from the chat service.
"""

from pathlib import Path

import yaml

_BANK_PATH = Path(__file__).parent / "leaf_question_bank.yaml"

with _BANK_PATH.open("r", encoding="utf-8") as _f:
    _ENTRIES: list[dict] = yaml.safe_load(_f) or []

# "Bank != prompt" (#29): only this many of a leaf's best bucket-A entries ever become
# a few-shot, in the file's own curated order -- the rest exist for eval/chips, not prompts.
MAX_FEW_SHOTS_PER_LEAF = 3


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
