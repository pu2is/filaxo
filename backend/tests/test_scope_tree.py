"""Unit tests for the scope-tree runtime helpers added in #30: resolve/children/is_leaf.

Data content itself (which tables are in which leaf, join snippets, etc.) is #27's job
and already covered by manual DB verification (docs/scope-trees.md) -- these tests only
cover the lookup/traversal *behavior* on top of that data.
"""

import pytest

from modules.schema.scope_tree import CUSTOMER_TREE, LEAD_TREE, ScopeTreeError, all_tables, children, is_leaf, resolve


def test_children_of_root_returns_themas():
    assert set(children([])) == {"LEAD", "CUSTOMER", "NEWCAR", "FINANCE"}


def test_children_of_thema_returns_its_leaves():
    leaves = children("LEAD")
    assert [leaf.id for leaf in leaves] == [leaf.id for leaf in LEAD_TREE.leaves]


def test_children_accepts_list_path_too():
    assert children(["LEAD"]) == children("LEAD")


def test_children_of_unknown_thema_raises():
    with pytest.raises(ScopeTreeError):
        children("BOGUS")


def test_children_of_a_leaf_is_empty():
    assert children("LEAD.SCORING") == []


def test_is_leaf_true_for_real_leaf():
    assert is_leaf("LEAD.SCORING") is True
    assert is_leaf(["CUSTOMER", "CONTACT"]) is True


def test_is_leaf_false_for_thema_only():
    assert is_leaf("LEAD") is False


def test_is_leaf_false_for_unknown_leaf():
    assert is_leaf("LEAD.BOGUS") is False


def test_is_leaf_false_for_unknown_thema():
    assert is_leaf("BOGUS.THING") is False


def test_is_leaf_never_raises_on_garbage_input():
    assert is_leaf("") is False
    assert is_leaf("LEAD.SCORING.EXTRA") is False


def test_resolve_returns_tables_join_snippet_label_facets():
    result = resolve("LEAD.SCORING")
    assert result["label"] == "Bewertung & Scoring"
    assert "cobra.CrmLead" in result["tables"]
    assert "cobra.CrmLeadScores" in result["tables"]
    assert "JOIN cobra.CrmLeadScores" in result["join_snippet"]
    assert result["facets"] == {"date_column": "CrmLeadScores.ScoredAt"}


def test_resolve_accepts_list_path():
    assert resolve(["LEAD", "SCORING"]) == resolve("LEAD.SCORING")


def test_resolve_single_table_leaf_has_no_join_snippet():
    result = resolve("LEAD.OVERVIEW")
    assert result["tables"] == ["cobra.CrmLead"]
    assert result["join_snippet"] is None


def test_resolve_thema_only_path_raises_cleanly():
    with pytest.raises(ScopeTreeError):
        resolve("LEAD")


def test_resolve_unknown_leaf_raises_cleanly():
    with pytest.raises(ScopeTreeError):
        resolve("LEAD.BOGUS")


def test_resolve_unknown_thema_raises_cleanly():
    with pytest.raises(ScopeTreeError):
        resolve("BOGUS.THING")


def test_resolve_empty_path_raises_cleanly():
    with pytest.raises(ScopeTreeError):
        resolve([])


def test_all_tables_is_union_of_every_leaf():
    tables = all_tables()
    for tree in (LEAD_TREE, CUSTOMER_TREE):
        for leaf in tree.leaves:
            for table in leaf.tables:
                assert table in tables
    assert len(tables) == len(set(tables))  # deduplicated
