"""LEAD + CUSTOMER + NEWCAR scope trees (#27, #39): thema -> leaf, each leaf a fixed
table set + JOIN snippet + time facet. This is the D5 scope tree in its multi-theme
form -- thema -> leaf, i.e. depth 2 of the max-3-level design (no sub-sub-thema needed
yet for any of these themas); consumed by the tree-walking funnel (chat/service.py, #31).

Every leaf's table set and JOIN snippet was verified against the live DB
(localhost,14330) on 2026-07-07, not just against the docs/0*-*-erDiagram.md text --
those diagrams have already been found to drift from the real schema (see
docs/scope-trees.md for the full disposition logs and known-gaps lists this module's
shape is built from). Load-bearing corrections from those passes:

- Only the newer Crm* (CRM module) tables have real DB-level FK constraints. The
  legacy Ba*/Cdi*/Cdn* (dealer-management-system) tables have ZERO declared FK
  constraints anywhere in `cobra` -- confirmed for Cdn* via sys.foreign_keys across
  all 77 candidate 02-newcar-sales tables, same finding as Ba*/Cdi* (#27). Their
  relationships are enforced at the application layer only, never the DB. Every
  join_snippet below that crosses one of these table families is therefore verified
  by matching row COUNTS, not by a constraint the DB itself would enforce.
- CdiKundenFzg.KundenId (the doc's flagship "which customer owns which car"
  bridge) is 100% NULL across all 19,563 rows in this sample, and
  CdmKundeEmail.KUNDE_ID uses a completely different ID format than
  BaAddress.AddressId (0/168 rows match) -- both are excluded from the CUSTOMER
  tree entirely rather than offered as a leaf that would silently return nothing.
- The 02-newcar-sales doc (#39) has more column-name drift than #27 found on 01-*:
  several columns its own flagship example queries depend on --
  `CdnFzgVerkauf.VerkaufDatum`, `CdnAuftragK.Termin`/`.LieferDatum`,
  `CdnBuchKtoSt.Saldo`, `CdnVkRech.Status` -- do not exist on the live tables at all.
  See each NEWCAR leaf's notes below and docs/scope-trees.md's Known Gaps for the
  live equivalents used instead.
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


NEWCAR_TREE = ScopeTree(
    thema="NEWCAR",
    label="Neuwagen",
    doc_ref="docs/02-newcar-sales-erDiagram.md",
    leaves=[
        ScopeLeaf(
            id="NEWCAR.OVERVIEW",
            label="Überblick",
            tables=["cobra.CdnAuftragK"],
            join_snippet=None,
            date_facet="CdnAuftragK.AuftragsDatum",
            notes=(
                "Whole-thema catch-all leaf. #39: no Cdn* table anywhere in `cobra` has a "
                "declared FK constraint (confirmed via sys.foreign_keys -- same situation as "
                "Ba*/Cdi*, zero results DB-wide across all 77 candidate tables), so every "
                "relationship in this tree is verified by live row-count join match rate, "
                "not a schema-enforced constraint."
            ),
        ),
        ScopeLeaf(
            id="NEWCAR.ORDER",
            label="Auftragsabwicklung",
            tables=[
                "cobra.CdnAuftragK",
                "cobra.CdnAuftragsPos",
                "cobra.CdnAuftragKSplitt",
                "cobra.CdnAuftragsSerAus",
                "cobra.CdnAuftragSperre",
                "cobra.CdnAuftragsSteuer",
            ],
            join_snippet="""\
cobra.CdnAuftragK a
LEFT JOIN cobra.CdnAuftragsPos p ON p.AUFTRAGK_ID = a.ID
LEFT JOIN cobra.CdnAuftragKSplitt s ON s.AUFTRAGK_ID = a.ID
LEFT JOIN cobra.CdnAuftragsSerAus sa ON sa.AUFTRAGK_ID = a.ID
LEFT JOIN cobra.CdnAuftragSperre sp ON sp.AUFTRAGK_ID = a.ID
LEFT JOIN cobra.CdnAuftragsSteuer st ON st.AUFTRAGKSPLITT_ID = s.ID""",
            date_facet="CdnAuftragK.AuftragsDatum",
            notes=(
                "#39: the doc's ER diagram names the child FK column `AuftragId` on every one "
                "of these tables -- the live column is `AUFTRAGK_ID` (all-caps, underscored), "
                "and it references `CdnAuftragK.ID`, NOT `.CID` despite `CID` being the column "
                "every ER block marks `PK`. Verified live: AUFTRAGK_ID -> ID matches 100% on "
                "CdnAuftragsPos/CdnAuftragKSplitt/CdnAuftragSperre, 96.5% on CdnAuftragsSerAus "
                "(109985/114016) -- matching against `.CID` instead returns 0% on all four. "
                "CdnAuftragsSteuer joins one level down, to CdnAuftragKSplitt.ID (100% match), "
                "not directly to CdnAuftragK. Also: the doc's own flagship 'delivery date "
                "slippage' problem (comparing `CdnAuftragK.Termin` to `CdnFzgVerkauf."
                "VerkaufDatum`) cites two columns that do not exist on the live tables at all "
                "-- see NEWCAR.DELIVERY's notes and docs/scope-trees.md Known Gaps."
            ),
        ),
        ScopeLeaf(
            id="NEWCAR.DELIVERY",
            label="Fahrzeugauslieferung & Verkauf",
            tables=[
                "cobra.CdnFzgVerkauf",
                "cobra.CdnVkRech",
                "cobra.CdnVkRechP",
                "cobra.CdnVkPreis",
                "cobra.CdnFzgReservierung",
                "cobra.CdnInzahlg",
                "cobra.CdnPraeZusatz",
                "cobra.CdnLagerplatzHist",
                "cobra.CdnFzgUmbuchung",
                "cobra.CdnVerkaeufer",
            ],
            join_snippet="""\
cobra.CdnFzgVerkauf v
LEFT JOIN cobra.CdnVkRech r ON r.FzgVerkaufId = v.ID
LEFT JOIN cobra.CdnVkRechP rp ON rp.FZGVERKAUF_ID = v.ID
LEFT JOIN cobra.CdnVkPreis vp ON vp.FzgVerkaufId = v.ID
LEFT JOIN cobra.CdnFzgReservierung res ON res.FzgVerkaufId = v.ID
LEFT JOIN cobra.CdnInzahlg iz ON iz.FzgVerkaufid = v.ID
LEFT JOIN cobra.CdnPraeZusatz pz ON pz.FzgVerkaufId = v.ID
LEFT JOIN cobra.CdnLagerplatzHist lh ON lh.FZGVERKAUF_ID = v.ID
LEFT JOIN cobra.CdnFzgUmbuchung um ON um.FzgVerkaufId = v.ID
LEFT JOIN cobra.CdnVerkaeufer va ON va.ID = v.Verkaeufer1Id""",
            date_facet="CdnFzgVerkauf.RechDatum",
            notes=(
                "#39: `CdnFzgVerkauf.VerkaufDatum` and `CdnAuftragK.Termin`/`.LieferDatum` -- "
                "the exact columns the doc's own flagship queries and 'delivery date slippage' "
                "problem statement are built on -- do not exist on the live tables (confirmed "
                "via INFORMATION_SCHEMA.COLUMNS, not just a failed query). `AuslieferDat` "
                "(delivery date, 9525/15730 rows populated) is the closest live equivalent but "
                "only ~60% covered; `RechDatum` (invoice date, 15110/15730, ~96%) is used as "
                "this leaf's date_facet instead for better coverage -- invoicing happens "
                "essentially alongside delivery in this pipeline (发票→交车 per the doc's own "
                "narrative), so it's a reasonable proxy, but a 'delivery date' answer should "
                "say invoice date, not literally claim it's the handover date. `CdnVkRech` "
                "also lacks the doc's claimed `Status`/`Bruttobetrag`/`KundenId` columns "
                "entirely (real columns: `BetragNetto`/`BetragSteuerFrei`/`BetragMwst`, no "
                "gross total, no customer link) -- the doc's 'unbilled orders' example query "
                "(`WHERE r.Status != 'STORNO'`) cannot run as written. `CdnInzahlg.FzgVerkaufid` "
                "(inconsistent casing, verified case-insensitive) -> CdnFzgVerkauf.ID is 100% "
                "verified but only 3 rows exist -- see leaf_question_bank.yaml's known-gap "
                "note, kept per check_crm.md's own callout that this table is underused. "
                "`CdnVerkaeufer.ID` (not `.MitarbeiterId`/`.VerkaeuferNr`) is what "
                "`CdnFzgVerkauf.Verkaeufer1Id` actually resolves against (13627/13637, 99.9%); "
                "`.SuchBegriff` holds the advisor's human name ('Lastname, Firstname'), the "
                "only readable-name field on that table."
            ),
        ),
        ScopeLeaf(
            id="NEWCAR.BILLING",
            label="Rechnungsabgleich",
            tables=["cobra.CdnBuchKopf", "cobra.CdnBuchKtoSt", "cobra.CdnBuchPos"],
            join_snippet="""\
cobra.CdnBuchKopf bk
LEFT JOIN cobra.CdnBuchKtoSt kt ON kt.BUCHKOPF_ID = bk.ID
LEFT JOIN cobra.CdnBuchPos bp ON bp.BUCHKOPF_ID = bk.ID""",
            date_facet="CdnBuchKopf.BuchDatum",
            notes=(
                "#39: `CdnBuchKopf.VkRechId` (the doc's claimed link back to CdnVkRech, on "
                "both the ER diagram AND the supplementary CdnBuchPos section) does not exist "
                "live -- CdnBuchKopf links to the order side only, via `AUFTRAGK_ID`/"
                "`AUFTRAGKSPLITT_ID` (both -> CdnAuftragK.ID/CdnAuftragKSplitt.ID, 100% match), "
                "never directly to an invoice row. `CdnBuchKtoSt.Saldo` (the doc's 'unbilled "
                "orders' example query filters on `b.Saldo > 0`) also does not exist -- an open "
                "balance has to be computed from `SUM(Betrag)` grouped by `SollHaben` ('S' = "
                "Soll/debit, 'H' = Haben/credit) instead, there is no precomputed running "
                "balance column. `BUCHKOPF_ID` -> `CdnBuchKopf.ID` verified 100% for both "
                "CdnBuchKtoSt (289137 rows) and CdnBuchPos (160034 rows)."
            ),
        ),
        ScopeLeaf(
            id="NEWCAR.PURCHASING",
            label="Fahrzeugeinkauf",
            tables=[
                "cobra.CdnEinkKopf",
                "cobra.CdnEinkPos",
                "cobra.CdnEkBuchKopf",
                "cobra.CdnEkBuchKtoSt",
            ],
            join_snippet="""\
cobra.CdnEinkKopf ek
LEFT JOIN cobra.CdnEinkPos ep ON ep.EinkKopfId = ek.EinkKopfId
LEFT JOIN cobra.CdnEkBuchKopf ebk ON ebk.EINKKOPF_ID = ek.EinkKopfId
LEFT JOIN cobra.CdnEkBuchKtoSt ebs ON ebs.EKBUCHKOPF_ID = ebk.ID""",
            date_facet="CdnEinkKopf.RechngDatum",
            notes=(
                "#39: the doc's diagram claims `CdnEinkPos }o--o| CdnAuftragK : \"FzgStammId"
                "(via Fzg)\"` -- CdnEinkPos has no FzgStammId column at all (live schema), so "
                "this cross-link to the sales order does not exist; CdnEinkPos only joins up "
                "to its own header, `CdnEinkKopf.EinkKopfId` (99.96% match, 142392/142448) -- "
                "note this is the business key, not `.CID` or a doc-style `.ID` (CdnEinkKopf "
                "has no `ID` column). `CdnEkBuchKopf`/`CdnEkBuchKtoSt` (the purchasing-side "
                "mirror of NEWCAR.BILLING's settlement cluster) link back to CdnEinkKopf via "
                "`EINKKOPF_ID` at 91-94% match -- soft-verified, slightly below the ~100% seen "
                "elsewhere in this tree, but the only candidate key and consistent with the "
                "table's small size (35/149 rows). `EinkPosTyp = '0'` empirically marks the "
                "vehicle-itself line (avg cost ~14,354 vs. hundreds for other codes) vs. "
                "accessories/fees on other codes -- an observed pattern, not a decoded "
                "dictionary (no CdnEinkPosTyp-style lookup table was found in this candidate "
                "set)."
            ),
        ),
    ],
)


TREES: dict[str, ScopeTree] = {"LEAD": LEAD_TREE, "CUSTOMER": CUSTOMER_TREE, "NEWCAR": NEWCAR_TREE}


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
