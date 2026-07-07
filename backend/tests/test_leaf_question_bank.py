"""Unit tests for the per-leaf question bank loader (#29 data, #30 loader).

The main thing worth pinning down with a test: held-out exclusion is absolute -- a
bucket B/C or unverified entry must never leak into get_few_shots(), since that's
what stops eval-only/known-gap questions from accidentally becoming a generate_sql
example.
"""

from modules.schema.leaf_question_bank import (
    MAX_FEW_SHOTS_PER_LEAF,
    MAX_SUGGESTIONS_PER_LEAF,
    get_all_entries,
    get_few_shots,
    get_suggestions,
)


def test_get_all_entries_has_every_bucket():
    entries = get_all_entries()
    buckets = {e["bucket"] for e in entries}
    assert buckets == {"A", "B", "C"}


def test_few_shots_never_include_bucket_b_or_c():
    all_entries = get_all_entries()
    b_and_c_questions = {e["question"] for e in all_entries if e["bucket"] != "A"}

    for node in {e["node"] for e in all_entries}:
        for shot in get_few_shots(node):
            assert not any(q in shot for q in b_and_c_questions), f"held-out question leaked into {node}'s few-shots"


def test_few_shots_never_include_unverified_entries():
    all_entries = get_all_entries()
    unverified_questions = {e["question"] for e in all_entries if not e["verified"]}

    for node in {e["node"] for e in all_entries}:
        for shot in get_few_shots(node):
            assert not any(q in shot for q in unverified_questions)


def test_few_shots_capped_at_max_per_leaf():
    for node in {e["node"] for e in get_all_entries()}:
        assert len(get_few_shots(node)) <= MAX_FEW_SHOTS_PER_LEAF


def test_few_shots_for_known_leaf_is_nonempty():
    shots = get_few_shots("LEAD.SCORING")
    assert len(shots) >= 2  # #29's acceptance criterion: every leaf has >=2 bucket-A entries
    assert all("-- Frage:" in s for s in shots)


def test_few_shots_accepts_list_path():
    assert get_few_shots(["LEAD", "SCORING"]) == get_few_shots("LEAD.SCORING")


def test_few_shots_for_bucket_c_node_is_empty():
    # "ANY" (bucket C probes) has no bucket-A entries by construction.
    assert get_few_shots("ANY") == []


def test_few_shots_for_unknown_node_is_empty():
    assert get_few_shots("NOPE.NOPE") == []


def test_every_leaf_from_scope_tree_has_at_least_two_few_shots():
    from modules.schema.scope_tree import TREES

    for tree in TREES.values():
        for leaf in tree.leaves:
            shots = get_few_shots(leaf.id)
            assert len(shots) >= 2, f"{leaf.id} has fewer than 2 bucket-A few-shots"


# --- get_suggestions (D8, #36) ----------------------------------------------------------


def test_suggestions_include_every_bucket_a_entry():
    # LEAD.SCORING has 3 bucket-A entries (one of them even carries its own `note`, which
    # must NOT exclude it -- `note` only gates bucket B, per the ticket).
    suggestions = get_suggestions("LEAD.SCORING")
    a_ids = {e["id"] for e in get_all_entries() if e["node"] == "LEAD.SCORING" and e["bucket"] == "A"}
    assert a_ids <= {s["id"] for s in suggestions}


def test_suggestions_exclude_known_gap_bucket_b():
    # lead_scoring_active_configs is bucket B with a `note` -- a known-gap entry, excluded.
    suggestions = get_suggestions("LEAD.SCORING")
    assert "lead_scoring_active_configs" not in {s["id"] for s in suggestions}


def test_suggestions_include_bucket_b_without_note():
    # lead_scoring_tier_actions is bucket B with no `note` -- included.
    suggestions = get_suggestions("LEAD.SCORING")
    assert "lead_scoring_tier_actions" in {s["id"] for s in suggestions}


def test_suggestions_never_include_bucket_c():
    all_entries = get_all_entries()
    c_questions = {e["question"] for e in all_entries if e["bucket"] == "C"}

    for node in {e["node"] for e in all_entries}:
        for s in get_suggestions(node):
            assert s["question"] not in c_questions


def test_suggestions_capped_at_max_per_leaf():
    for node in {e["node"] for e in get_all_entries()}:
        assert len(get_suggestions(node)) <= MAX_SUGGESTIONS_PER_LEAF


def test_suggestions_accepts_list_path():
    assert get_suggestions(["LEAD", "SCORING"]) == get_suggestions("LEAD.SCORING")


def test_suggestions_for_known_leaf_is_nonempty():
    assert len(get_suggestions(["LEAD", "SCORING"])) > 0


def test_suggestions_for_bucket_c_node_is_empty():
    assert get_suggestions("ANY") == []


def test_suggestions_for_unknown_node_is_empty():
    assert get_suggestions("NOPE.NOPE") == []


def test_every_leaf_from_scope_tree_has_nonempty_suggestions():
    from modules.schema.scope_tree import TREES

    for tree in TREES.values():
        for leaf in tree.leaves:
            assert len(get_suggestions(leaf.id)) > 0, f"{leaf.id} has no suggestion entries"
