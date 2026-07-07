"""LEAD + CUSTOMER scope trees (#27): thema -> leaf, each leaf a fixed table set +
JOIN snippet + time facet. This is the D5 scope tree in its Wave-1-covering form --
thema -> leaf, i.e. depth 2 of the max-3-level design (no sub-sub-thema needed yet
for these two themas); consumed by the future tree-walking funnel loader (#30).

Every leaf's table set and JOIN snippet was verified against the live DB
(localhost,14330) on 2026-07-07, not just against the docs/01-*-erDiagram.md text --
those diagrams have already been found to drift from the real schema (see
docs/scope-trees.md for the full ~91-table disposition log and the known-gaps list
this module's shape is built from). Two load-bearing corrections from that pass:

- Only the newer Crm* (CRM module) tables have real DB-level FK constraints. The
  legacy Ba*/Cdi* (dealer-management-system) tables have ZERO declared FK
  constraints anywhere in `cobra` -- their relationships are enforced at the
  application layer only, never the DB. Every join_snippet below that crosses a
  Ba*/Cdi* boundary is therefore verified by matching row COUNTS, not by a
  constraint the DB itself would enforce.
- CdiKundenFzg.KundenId (the doc's flagship "which customer owns which car"
  bridge) is 100% NULL across all 19,563 rows in this sample, and
  CdmKundeEmail.KUNDE_ID uses a completely different ID format than
  BaAddress.AddressId (0/168 rows match) -- both are excluded from the CUSTOMER
  tree entirely rather than offered as a leaf that would silently return nothing.
"""

from dataclasses import dataclass


@dataclass
class ScopeLeaf:
    id: str  # e.g. "LEAD.SCORING" -- also the funnel's scope_path leaf key
    label: str  # German button label
    tables: list[str]  # fully-qualified (cobra.TableName), fixed table set for this leaf
    join_snippet: str | None  # None when tables has exactly one table
    date_facet: str | None  # "Table.Column" usable for time-range filtering, or None
    notes: str | None = None  # non-obvious caveats (partial-match joins, undeclared FKs, ...)


@dataclass
class ScopeTree:
    thema: str  # matches modules.chat.service.DOMAIN_LABELS key, e.g. "LEAD"
    label: str  # German thema label
    doc_ref: str
    leaves: list[ScopeLeaf]


LEAD_TREE = ScopeTree(
    thema="LEAD",
    label="Verkauf & Leads",
    doc_ref="docs/01-lead-sales-erDiagram.md",
    leaves=[
        ScopeLeaf(
            id="LEAD.OVERVIEW",
            label="Überblick",
            tables=["cobra.CrmLead"],
            join_snippet=None,
            date_facet="CrmLead.CreatedAt",
            notes="Whole-thema catch-all leaf for questions that don't need a sub-cluster.",
        ),
        ScopeLeaf(
            id="LEAD.ACTIVITY",
            label="Aktivität & Kontakt",
            tables=[
                "cobra.CrmLead",
                "cobra.CrmLeadActivity",
                "cobra.CrmLeadContactHistory",
                "cobra.CrmContactHistoryDescriptionLog",
                "cobra.CrmContactHistoryNoteLog",
                "cobra.CrmLeadConversion",
                "cobra.CrmLeadDeletionLog",
                "cobra.CrmLeadAusstattung",
                "cobra.CrmStatusLog",
            ],
            join_snippet="""\
cobra.CrmLead l
LEFT JOIN cobra.CrmLeadActivity act ON act.LeadId = l.Id
LEFT JOIN cobra.CrmLeadContactHistory ch ON ch.LeadId = l.Id
LEFT JOIN cobra.CrmContactHistoryDescriptionLog chd ON chd.ContactHistoryId = ch.Id
LEFT JOIN cobra.CrmContactHistoryNoteLog chn ON chn.ContactHistoryId = ch.Id
LEFT JOIN cobra.CrmLeadConversion conv ON conv.LeadId = l.Id
LEFT JOIN cobra.CrmLeadDeletionLog del ON del.LeadId = l.Id
LEFT JOIN cobra.CrmLeadAusstattung aus ON aus.Lead = l.Id
LEFT JOIN cobra.CrmStatusLog st ON st.record_id = l.Id""",
            date_facet="CrmLead.CreatedAt",
            notes=(
                "CrmLeadAusstattung's FK column is named `Lead`, not `LeadId` (verified live -- "
                "differs from the naming pattern every other table here uses). CrmStatusLog.record_id "
                "-> CrmLead.Id has no declared FK constraint (it's a generic column name, likely meant "
                "to log status changes for other entity types too) but resolved 100% in this sample; "
                "treat as soft-verified, not schema-guaranteed."
            ),
        ),
        ScopeLeaf(
            id="LEAD.SCORING",
            label="Bewertung & Scoring",
            tables=[
                "cobra.CrmLead",
                "cobra.CrmLeadScores",
                "cobra.CrmLeadCriterionScores",
                "cobra.CrmScoringConfigs",
                "cobra.CrmScoringCategories",
                "cobra.CrmScoringCriteria",
                "cobra.CrmScoringOptions",
                "cobra.CrmLeadTiers",
                "cobra.CrmTierActions",
            ],
            join_snippet="""\
cobra.CrmLead l
JOIN cobra.CrmLeadScores s ON s.LeadId = l.Id
LEFT JOIN cobra.CrmLeadTiers t ON t.Id = s.TierId
LEFT JOIN cobra.CrmTierActions ta ON ta.TierId = t.Id
LEFT JOIN cobra.CrmScoringConfigs cfg ON cfg.Id = s.ScoringConfigId
LEFT JOIN cobra.CrmScoringCategories cat ON cat.ScoringConfigId = cfg.Id
LEFT JOIN cobra.CrmScoringCriteria crit ON crit.CategoryId = cat.Id
LEFT JOIN cobra.CrmScoringOptions opt ON opt.CriteriaId = crit.Id
LEFT JOIN cobra.CrmLeadCriterionScores cs
    ON cs.LeadScoreId = s.Id AND cs.CriteriaId = crit.Id AND cs.OptionId = opt.Id""",
            date_facet="CrmLeadScores.ScoredAt",
            notes=(
                "Every edge here is a real DB-level FK constraint (verified via sys.foreign_keys, "
                "2026-07-07) -- the most solidly-verified leaf of the two trees. Mirrors "
                "mvp-request.md's existing LEAD.SCORING example (D5); id kept identical."
            ),
        ),
        ScopeLeaf(
            id="LEAD.TASKS",
            label="Aufgaben & Wiedervorlagen",
            tables=["cobra.CrmTasks", "cobra.CrmResubmissions"],
            join_snippet=None,
            date_facet="CrmTasks.DueDate",
            notes=(
                "Not joined to CrmLead: CrmTasks.LinkedTo resolves to CrmLead.Id for only 13/20 "
                "sample rows and CrmResubmissions.ReferenceId for just 1/3 -- both are generic "
                "polymorphic reference columns (can point at other entity types), not a safe 1:1 "
                "FK to Lead. Query each table on its own rather than assuming every row links back "
                "to a Lead."
            ),
        ),
        ScopeLeaf(
            id="LEAD.AUTOMATION",
            label="Automatisierung",
            tables=[
                "cobra.CrmScheduledActions",
                "cobra.CrmAutomationRules",
                "cobra.CrmAutomationConditions",
                "cobra.CrmAutomationActions",
            ],
            join_snippet="""\
cobra.CrmAutomationRules r
LEFT JOIN cobra.CrmScheduledActions sa ON sa.RuleId = r.Id
LEFT JOIN cobra.CrmAutomationConditions c ON c.RuleId = r.Id
LEFT JOIN cobra.CrmAutomationActions a ON a.RuleId = r.Id""",
            date_facet="CrmScheduledActions.ScheduledTime",
            notes=(
                "CrmScheduledActions.RuleId -> CrmAutomationRules.Id is a real FK constraint; "
                "CrmAutomationConditions.RuleId and CrmAutomationActions.RuleId are not declared as "
                "constraints but use the same column name/pattern (verified live 2026-07-07). "
                "CrmAutomationActionParameters was deliberately left out of this leaf -- its FK "
                "(ActionTypeId -> CrmAutomationActionTypes) is keyed by action TYPE, not by action "
                "instance, so it doesn't belong with CrmAutomationActions; the docs' "
                "表之间的连接关系 diagram has this wrong (claims a ConditionId link that doesn't "
                "exist in the live schema)."
            ),
        ),
    ],
)


CUSTOMER_TREE = ScopeTree(
    thema="CUSTOMER",
    label="Kunden & Adressen",
    doc_ref="docs/01-customer-address-erDiagram.md",
    leaves=[
        ScopeLeaf(
            id="CUSTOMER.OVERVIEW",
            label="Überblick",
            tables=["cobra.BaAddress"],
            join_snippet=None,
            date_facet="BaAddress.CreateDate",
            notes="Whole-thema catch-all leaf for questions that don't need a sub-cluster.",
        ),
        ScopeLeaf(
            id="CUSTOMER.CONTACT",
            label="Kontaktdaten",
            tables=["cobra.BaAddress", "cobra.BaAddInfo"],
            join_snippet="""\
cobra.BaAddress a
LEFT JOIN cobra.BaAddInfo i ON i.InfoId = a.AddressId""",
            date_facet="BaAddress.CreateDate",
            notes=(
                "No DB-level FK constraint exists for this join (true of every Ba*/Cdi* table -- "
                "see module docstring); verified by row count instead: only 3347/6920 (~48%) of "
                "BaAddInfo rows resolve to a real BaAddress row. LEFT JOIN is required, not just "
                "stylistic -- an INNER JOIN would silently drop over half of BaAddInfo. "
                "BaAddInfo.InfoTypeId is also NULL for every row (pre-existing finding, #10) -- "
                "phone vs. email can't be distinguished by type."
            ),
        ),
    ],
)


TREES: dict[str, ScopeTree] = {"LEAD": LEAD_TREE, "CUSTOMER": CUSTOMER_TREE}


class ScopeTreeError(Exception):
    """Raised when a path doesn't resolve to a real thema/leaf -- never a bare KeyError/
    IndexError, so a caller (or #31's funnel) gets a message naming what WAS valid."""


def _normalize_path(path: str | list[str]) -> list[str]:
    """Accept either a dot-joined string ("LEAD.SCORING") or a list (["LEAD", "SCORING"])
    -- both notations appear in #30's own ticket text, so support both rather than
    picking one and quietly breaking the other."""
    if isinstance(path, str):
        return path.split(".") if path else []
    return list(path)


def children(path: str | list[str]) -> list[str] | list[ScopeLeaf]:
    """Return what's selectable one level below `path`.

    `children([])` -> the thema keys ("LEAD", "CUSTOMER"). `children("LEAD")` -> that
    thema's leaves. Both trees are exactly 2 levels deep (thema -> leaf) today, so a
    leaf (or deeper/bogus) path always has no further children -- #27's tree design
    allows a 3rd level for a future thema that needs sub-sub-thema drilling.
    """
    parts = _normalize_path(path)
    if not parts:
        return list(TREES.keys())
    if len(parts) == 1:
        tree = TREES.get(parts[0])
        if tree is None:
            raise ScopeTreeError(f"unknown thema {parts[0]!r} -- known themas: {list(TREES.keys())}")
        return list(tree.leaves)
    return []


def is_leaf(path: str | list[str]) -> bool:
    """True iff `path` names an existing leaf exactly. Never raises -- an unknown thema
    or a too-short/too-long path is just "not a leaf", not an error (unlike `resolve`)."""
    parts = _normalize_path(path)
    if len(parts) != 2:
        return False
    tree = TREES.get(parts[0])
    if tree is None:
        return False
    target = ".".join(parts)
    return any(leaf.id == target for leaf in tree.leaves)


def resolve(path: str | list[str]) -> dict:
    """Resolve a leaf path to {tables, join_snippet, facets, label}.

    Raises ScopeTreeError for anything that isn't an exact, existing leaf -- a thema-only
    path, an unknown thema, or an unknown leaf name all have nothing sensible to return.
    """
    parts = _normalize_path(path)
    if len(parts) != 2:
        raise ScopeTreeError(f"{'.'.join(parts) or '(empty)'!r} is not a leaf path (expected thema.leaf)")

    thema = parts[0]
    tree = TREES.get(thema)
    if tree is None:
        raise ScopeTreeError(f"unknown thema {thema!r} -- known themas: {list(TREES.keys())}")

    target = ".".join(parts)
    for leaf in tree.leaves:
        if leaf.id == target:
            return {
                "tables": list(leaf.tables),
                "join_snippet": leaf.join_snippet,
                "facets": {"date_column": leaf.date_facet} if leaf.date_facet else {},
                "label": leaf.label,
            }
    known = [leaf.id for leaf in tree.leaves]
    raise ScopeTreeError(f"unknown leaf {target!r} under thema {thema!r} -- known leaves: {known}")


def all_tables() -> list[str]:
    """Union of every leaf's tables across both trees -- extends #25's startup self-check
    (main.py) so a missing/renamed table anywhere in the tree, not just the flat Wave-1
    DOMAIN_TABLES set, fails loudly at boot instead of on first use (#30)."""
    seen: set[str] = set()
    for tree in TREES.values():
        for leaf in tree.leaves:
            seen.update(leaf.tables)
    return sorted(seen)
