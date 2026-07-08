"""LEAD + CUSTOMER + NEWCAR + FINANCE + WORKSHOP scope trees (#27, #39, #40, #41):
thema -> leaf, each leaf a fixed table set + JOIN snippet + time facet. This is the D5
scope tree in its multi-theme form -- thema -> leaf, i.e. depth 2 of the max-3-level
design (no sub-sub-thema needed yet for any of these themas); consumed by the
tree-walking funnel (chat/service.py, #31).

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
- The 02-finance-billing doc (#40) repeats the exact same `Saldo`/due-date pattern:
  `CdaBuchKtoSt.Saldo`/`.FaelligDatum` (its own "overdue receivables" flagship query's
  dependencies) don't exist live either -- and this time even the doc's own *worked
  example query* for CdcTagesStartEndeK/P joins on `.CID`, which resolves 0% live,
  not just its ER diagram's claims. `CID` has now been confirmed to never be the real
  join target anywhere across three separate legacy table families (Ba*/Cdi*, Cdn*,
  Cda*/Cdc*) -- treat any future doc in this style the same way: verify the business-ID
  column empirically, never trust `CID` just because an ER block marks it `PK`.
- The 03-workshop-service doc (#41) adds a new drift KIND, distinct from "column
  doesn't exist": several columns exist exactly as documented but are almost entirely
  NULL in this sample. `CdaAuftragK.RepBeginn`/`.RepEnde` (the doc's own "unclosed
  orders"/"repair cycle time" flagship problems) are ~1%/~0.003% populated;
  `.Annahme`/`.WerkstattFertig`/`.FzgAbholDatum` are similarly near-total-NULL.
  `AuftragsDatum` (order date) is the only reliably-populated date column on this hub
  table. Also: `CdaAuftragsPos` has no `ApoId` column live despite being the doc's own
  flagship "most-used standard labor item" example query's join key -- see
  WORKSHOP.LABOR_CATALOG's notes.
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


FINANCE_TREE = ScopeTree(
    thema="FINANCE",
    label="Finanzen & Kasse",
    doc_ref="docs/02-finance-billing-erDiagram.md",
    leaves=[
        ScopeLeaf(
            id="FINANCE.OVERVIEW",
            label="Überblick",
            tables=["cobra.CdaBuchKopf"],
            join_snippet=None,
            date_facet="CdaBuchKopf.BuchDatum",
            notes=(
                "Whole-thema catch-all leaf. #40: same situation as NEWCAR (#39) -- no "
                "Cda*/Cdc*/Cdx*/SKR51* table has a declared FK constraint anywhere in "
                "`cobra` (confirmed via sys.foreign_keys across all 41 candidate tables), so "
                "every relationship in this tree is verified by live row-count join match "
                "rate. `CdaBuchKopf.RechDatum` (present on the doc's ER diagram) does not "
                "exist live -- `BuchDatum` (100% populated) is used instead."
            ),
        ),
        ScopeLeaf(
            id="FINANCE.WORKSHOP_BILLING",
            label="Werkstattabrechnung",
            tables=[
                "cobra.CdaBuchKopf",
                "cobra.CdaBuchKtoSt",
                "cobra.CdaBuchPos",
                "cobra.SKR51SachKto",
            ],
            join_snippet="""\
cobra.CdaBuchKopf bk
LEFT JOIN cobra.CdaBuchKtoSt kt ON kt.BUCHKOPF_ID = bk.ID
LEFT JOIN cobra.CdaBuchPos bp ON bp.BUCHKOPF_ID = bk.ID
LEFT JOIN cobra.SKR51SachKto sk ON sk.KontoNummer = kt.KtoNr""",
            date_facet="CdaBuchKopf.BuchDatum",
            notes=(
                "#40: `CdaBuchKtoSt.BUCHKOPF_ID` -> `CdaBuchKopf.ID` is 100% verified "
                "(1312094/1312098) -- same all-caps-underscored-FK-vs-CamelCase-business-key "
                "pattern as #39's NEWCAR tree; `CID` is not the join target here either. "
                "`CdaBuchKtoSt.KtoNr` -> `SKR51SachKto.KontoNummer` is only 79.2% verified "
                "(1039159/1312098) -- soft-verified, LEFT JOIN required, not every posting "
                "line resolves to a chart-of-accounts entry. WARNING: the doc's ER diagram "
                "and its own flagship 'overdue receivables' example query both depend on "
                "`CdaBuchKtoSt.Saldo` and `.FaelligDatum` -- NEITHER column exists live on "
                "CdaBuchKtoSt (confirmed via INFORMATION_SCHEMA.COLUMNS). An open balance has "
                "to be computed as `SUM(Betrag)` grouped by `SollHaben` ('S'=Soll/debit, "
                "'H'=Haben/credit) instead; the due date that DOES exist lives one level up, "
                "on `CdaBuchKopf.FaelligDatum` (only 58% populated, 75100/129966) -- join back "
                "to the header to use it. Also: `CdaBuchKopf.RechDatum` (also on the doc's ER "
                "diagram) does not exist live either, same as the OVERVIEW leaf's note."
            ),
        ),
        ScopeLeaf(
            id="FINANCE.POS_CASH",
            label="Kassenbewegungen",
            tables=[
                "cobra.CdcBewegungen",
                "cobra.CdcVerbuchung",
                "cobra.CdcBewZahlArt",
                "cobra.CdcBewBestand",
                "cobra.CdcVerknuepfung",
                "cobra.CdcBewegungAusl",
                "cobra.CdcKasse",
            ],
            join_snippet="""\
cobra.CdcBewegungen b
LEFT JOIN cobra.CdcVerbuchung vb ON vb.BewegungId = b.BewegungId
LEFT JOIN cobra.CdcBewZahlArt za ON za.BewegungId = b.BewegungId
LEFT JOIN cobra.CdcBewBestand bb ON bb.BewegungId = b.BewegungId
LEFT JOIN cobra.CdcVerknuepfung vk ON vk.BewegungId = b.BewegungId
LEFT JOIN cobra.CdcBewegungAusl ba ON ba.BewegungId = b.BewegungId
LEFT JOIN cobra.CdcKasse k ON k.KassenId = b.KassenId""",
            date_facet="CdcBewegungen.CreateDate",
            notes=(
                "#40: every `*.BewegungId -> CdcBewegungen.BewegungId` edge here is 100% "
                "verified live. `CdcKasse.KassenId` also resolves 100% but that table is 76 "
                "columns of almost entirely POS hardware/software config -- only its "
                "`Bezeichnung` (register display name) is carried in the schema card. "
                "WARNING: the doc's own 现实中容易出现的问题 table claims a reversal flag "
                "`Storno = 'J'` -- the live column is actually '0'/'1' (0 = valid, 1 = "
                "reversed; verified 7247/7498 rows are '0'), 'J' never appears at all. "
                "`CdcBewegungen.RechDatum` (the doc's suggested date facet) is only 37% "
                "populated (2779/7498); `CreateDate` (98.8%, 7407/7498) is used instead. "
                "The doc's claimed `CdcBewegungen.SollKonto`/`.HabenKonto` -> "
                "`SKR51SachKto.KontoNummer` join essentially does not resolve (0.1%/0.3% "
                "match) -- not included in the join_snippet above; treat those two columns "
                "as opaque, not a safe JOIN target to SKR51SachKto."
            ),
        ),
        ScopeLeaf(
            id="FINANCE.POS_SHIFT",
            label="Kassenschichten",
            tables=[
                "cobra.CdcKassenProt",
                "cobra.CdcTagesStartEndeK",
                "cobra.CdcTagesStartEndeP",
                "cobra.CdcKasse",
            ],
            join_snippet="""\
cobra.CdcTagesStartEndeK k
LEFT JOIN cobra.CdcTagesStartEndeP p ON p.TAGESSTARTENDEK_ID = k.ID
LEFT JOIN cobra.CdcKassenProt prot ON prot.KassenId = k.KassenId
LEFT JOIN cobra.CdcKasse ks ON ks.KassenId = k.KassenId""",
            date_facet="CdcTagesStartEndeK.CreateDate",
            notes=(
                "#40: `CdcTagesStartEndeP.TAGESSTARTENDEK_ID` -> `CdcTagesStartEndeK.ID` is "
                "100% verified (5248/5248) -- but the doc's OWN worked example query in "
                "02-finance-billing-erDiagram.md joins on `k.CID` instead, which resolves "
                "0% (0/5248). This is the same CID-is-never-the-real-key pattern #39 found "
                "everywhere else in this table family, just this time the doc's own example "
                "(not only its ER diagram) gets it wrong too -- don't trust a doc-provided "
                "worked query here any more than the ER diagram itself. `ProtArten` on "
                "CdcKassenProt is a status/event-type code with no verified dictionary in "
                "this candidate set."
            ),
        ),
        ScopeLeaf(
            id="FINANCE.POS_ORDERS",
            label="Kassen-Eigenaufträge",
            tables=[
                "cobra.CdcAuftragK",
                "cobra.CdcAuftragsPos",
                "cobra.CdcAuftragsSteuer",
                "cobra.CdcBuchKopf",
                "cobra.CdcBuchKtoSt",
            ],
            join_snippet="""\
cobra.CdcAuftragK a
LEFT JOIN cobra.CdcAuftragsPos p ON p.AUFTRAGK_ID = a.ID
LEFT JOIN cobra.CdcAuftragsSteuer st ON st.AUFTRAGK_ID = a.ID
LEFT JOIN cobra.CdcBuchKopf bk ON bk.AUFTRAGK_ID = a.ID
LEFT JOIN cobra.CdcBuchKtoSt bkt ON bkt.BUCHKOPF_ID = bk.ID""",
            date_facet="CdcAuftragK.BelegDatum",
            notes=(
                "#40: small, self-contained mirror of the CdnAuftragK/CdnBuchKopf pattern "
                "(#39) for POS-only direct sales (no full workshop order) -- every edge here "
                "is 100% verified live (AUFTRAGK_ID -> CdcAuftragK.ID, BUCHKOPF_ID -> "
                "CdcBuchKopf.ID). `CdcAuftragK.Storno` is NOT the doc's claimed 'J'/'N' flag "
                "either -- real values are '0' (not reversed, 30/47 rows) / '1'/'2'/'3' "
                "(17/47 rows total, different reversal states with no verified dictionary "
                "distinguishing them)."
            ),
        ),
    ],
)


WORKSHOP_TREE = ScopeTree(
    thema="WORKSHOP",
    label="Werkstatt & Service",
    doc_ref="docs/03-workshop-service-erDiagram.md",
    leaves=[
        ScopeLeaf(
            id="WORKSHOP.OVERVIEW",
            label="Überblick",
            tables=["cobra.CdaAuftragK"],
            join_snippet=None,
            date_facet="CdaAuftragK.AuftragsDatum",
            notes=(
                "Whole-thema catch-all leaf. #41: same zero-declared-FK situation as "
                "NEWCAR/FINANCE (#39/#40). `Geloescht` IS a real column here (unlike "
                "CdnAuftragK, #39) but its values are '0'/'1' (127805/133681 are '0'), NOT "
                "the doc's own problem-statement table's implied `'J'` -- same drift pattern "
                "already found on `Storno` in FINANCE (#40)."
            ),
        ),
        ScopeLeaf(
            id="WORKSHOP.ORDER",
            label="Auftragsabwicklung",
            tables=[
                "cobra.CdaAuftragK",
                "cobra.CdaAuftragsPos",
                "cobra.CdaAuftragKSplitt",
                "cobra.CdaAuftragSperre",
                "cobra.CdaAuftragsSteuer",
                "cobra.CdaAuftragWiAd",
                "cobra.CdaAuftragsJob",
                "cobra.CdaAuftragsStGrp",
            ],
            join_snippet="""\
cobra.CdaAuftragK a
LEFT JOIN cobra.CdaAuftragsPos p ON p.AUFTRAGK_ID = a.ID
LEFT JOIN cobra.CdaAuftragKSplitt s ON s.AUFTRAGK_ID = a.ID
LEFT JOIN cobra.CdaAuftragSperre sp ON sp.AUFTRAGK_ID = a.ID
LEFT JOIN cobra.CdaAuftragsSteuer st ON st.AUFTRAGKSPLITT_ID = s.ID
LEFT JOIN cobra.CdaAuftragWiAd wa ON wa.AUFTRAGK_ID = a.ID
LEFT JOIN cobra.CdaAuftragsJob j ON j.AUFTRAGK_ID = a.ID
LEFT JOIN cobra.CdaAuftragsStGrp stg ON stg.AUFTRAGK_ID = a.ID""",
            date_facet="CdaAuftragK.AuftragsDatum",
            notes=(
                "#41: all seven child edges verified 99.7-100% live against "
                "`CdaAuftragK.ID` (AUFTRAGK_ID) or `CdaAuftragKSplitt.ID` "
                "(AUFTRAGKSPLITT_ID, for CdaAuftragsSteuer only -- one level down, same "
                "pattern as NEWCAR/FINANCE's *Steuer tables). WARNING: this doc's own "
                "flagship problems ('工单未关闭'/unclosed orders, average repair-cycle time) "
                "both depend on `RepBeginn`/`RepEnde` -- these columns exist exactly as "
                "documented, but are essentially unpopulated in this sample: RepBeginn is "
                "1408/133681 (~1%), RepEnde is 4/133681 (~0.003%), and every other "
                "workshop-workflow timestamp (`Annahme`, `WerkstattFertig`, "
                "`FzgAbholDatum`) is similarly near-total-NULL (153, 2, and 0 populated "
                "rows respectively). Only `AuftragsDatum` (order-creation date, "
                "99.998% populated) and `Termin` (scheduled appointment, ~88%) have real "
                "coverage -- `AuftragsDatum` is used as this leaf's date facet; do not "
                "build a 'how long did the repair take' or 'which orders are still open' "
                "answer from RepBeginn/RepEnde, the data to answer it barely exists in "
                "this sample. `CdaAuftragsPosMont` (171k rows, doc's claimed "
                "'installation/assembly line items') is excluded from this leaf -- it has "
                "no `AUFTRAGK_ID` column at all live (only `AuftragsId` INT, a soft 99.7% "
                "match to `CdaAuftragK.AuftragsId` rather than the clean varchar-`ID` "
                "pattern used everywhere else in this tree)."
            ),
        ),
        ScopeLeaf(
            id="WORKSHOP.WARRANTY_CLAIMS",
            label="Garantieanträge",
            tables=["cobra.CdaFIGaKopf", "cobra.CdaFIGaFall"],
            join_snippet="""\
cobra.CdaFIGaKopf gk
LEFT JOIN cobra.CdaFIGaFall gf ON gf.FIGAKOPF_ID = gk.ID""",
            date_facet="CdaFIGaKopf.AntragsDatum",
            notes=(
                "#41: workshop-side warranty CLAIM records (one application + its case-"
                "detail lines) -- distinct from theme 10's warranty CONFIG/dictionary "
                "tables (`CdwFIAktion`/`CdwFIGwArt`), which this doc cross-references but "
                "does not own (see cross-theme FK note below). WARNING: the doc's ER "
                "diagram claims `CdaFIGaKopf }o--|| CdaAuftragK : \"AUFTRAGK_ID\"` and "
                "`CdaFIGaFall }o--|| CdaFIGaKopf : \"FallNr\"` -- NEITHER matches live. The "
                "real edges are `CdaFIGaKopf.AUFTRAGKSPLITT_ID -> CdaAuftragKSplitt.ID` "
                "(99.9%, one level down from the order header, same pattern as "
                "CdaAuftragsSteuer in WORKSHOP.ORDER -- not joined into this leaf directly "
                "to keep it self-contained) and `CdaFIGaFall.FIGAKOPF_ID -> "
                "CdaFIGaKopf.ID` (100%, 28262/28273) -- `FallNr` is CdaFIGaFall's own "
                "identifier column, not a column CdaFIGaKopf even has. Also: "
                "`CdaFIGaKopf.GaArt` (the ticket's own cross-reference to "
                "`CdwFIGwArt.GarArt`, warranty theme #44) does not exist on this table at "
                "all -- a similarly-spelled `GwArt` column exists instead, but on a "
                "DIFFERENT table (`CdaGenGaKopf`, excluded here as system/test data, only "
                "1 row). Flagging for whoever picks up #44 rather than guessing at the "
                "right relationship now."
            ),
        ),
        ScopeLeaf(
            id="WORKSHOP.PACKAGES",
            label="Reparaturpakete & Verrechnung",
            tables=[
                "cobra.CdaPaketKopf",
                "cobra.CdaPaketPos",
                "cobra.CdaVerrechSatz",
                "cobra.CdaVerrechSatzGrup",
            ],
            join_snippet="""\
cobra.CdaPaketKopf pk
LEFT JOIN cobra.CdaPaketPos pp ON pp.PaketKopf_ID = pk.ID
LEFT JOIN cobra.CdaVerrechSatz vs ON vs.VerrechSatzNr = pp.VerrechSatzNr
LEFT JOIN cobra.CdaVerrechSatzGrup vg ON vg.VerrechSatzGrupId = vs.VerrechSatzGrupId""",
            date_facet="CdaPaketKopf.CreateDate",
            notes=(
                "#41: `CdaPaketPos.PaketKopf_ID -> CdaPaketKopf.ID` is 100% verified "
                "(4454/4454); `.VerrechSatzNr -> CdaVerrechSatz.VerrechSatzNr` is 75.1% "
                "(3344/4454, soft-verified); `CdaVerrechSatz.VerrechSatzGrupId -> "
                "CdaVerrechSatzGrup.VerrechSatzGrupId` is 90.9% (2400/2640). Data quirk "
                "worth knowing before writing a 'rate by group' question: 8 of the 11 rate "
                "groups (`VerrechSatzGrupId` 2-9) share an EXACTLY IDENTICAL rate schedule "
                "(same min/max/avg to the cent) -- verified live, not a query bug -- so "
                "grouping by `CdaVerrechSatzGrup.Bezeichnung` (mostly brand names, e.g. "
                "'Fiat PKW'/'Alfa Romeo'/'Lancia') and averaging the rate returns the same "
                "number for most brands. A 'how many rate groups exist' or 'total/average "
                "package price' question avoids this; a 'compare rates across brands' "
                "question would technically run but read as suspiciously uniform."
            ),
        ),
        ScopeLeaf(
            id="WORKSHOP.LABOR_CATALOG",
            label="Standardarbeitswerte",
            tables=["cobra.CdaApo", "cobra.CdaFIApoZusatz"],
            join_snippet="""\
cobra.CdaApo a
LEFT JOIN cobra.CdaFIApoZusatz z ON z.ApoId = a.ApoId""",
            date_facet="CdaApo.CreateDate",
            notes=(
                "#41: standalone reference catalog, deliberately NOT joined to "
                "`CdaAuftragsPos` (actual usage) -- the doc's own flagship 'most-used "
                "standard labor items' example query joins on `p.ApoId = a.ApoId`, but "
                "`CdaAuftragsPos` has no `ApoId` column at all live (verified via "
                "INFORMATION_SCHEMA.COLUMNS), and its `SachNr` column (the only other "
                "candidate) matches 0/641188 `CdaApo.ApoId` values -- there is no live, "
                "verifiable way to compute 'how often was this standard labor item used' "
                "in this sample; `CdaFIApoZusatz.ApoId -> CdaApo.ApoId` (100%, "
                "16875/16875) is the only relationship in this leaf that does resolve. "
                "WARNING: `CdaApo.Zeit` (standard time) and `.Preis` (standard price) are "
                "both zero for ~99.7% of rows (16879/16929 have `Zeit = 0`; 16884/16929 "
                "have `Preis = 0`) -- an 'average standard time/price' question would be "
                "dominated by placeholder zero rows and is not offered; see "
                "leaf_question_bank.yaml's known-gap note instead."
            ),
        ),
    ],
)


TREES: dict[str, ScopeTree] = {
    "LEAD": LEAD_TREE,
    "CUSTOMER": CUSTOMER_TREE,
    "NEWCAR": NEWCAR_TREE,
    "FINANCE": FINANCE_TREE,
    "WORKSHOP": WORKSHOP_TREE,
}


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
