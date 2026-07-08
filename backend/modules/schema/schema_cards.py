"""Deterministic schema supply for LEAD + CUSTOMER + NEWCAR + FINANCE (mvp-request D2 —
replaces vector RAG for MVP1).

Compressed DDL cards + semantic notes, assembled by get_schema_context(tables) into the
generate_sql prompt's schema_context. All column names verified against the live DB
(localhost,14330) on 2026-07-06, not just against docs/01-*-erDiagram.md — those docs have
already been found to drift from the real schema (see [[project-lead-customer-data-reality]]
in project memory), so this module treats the DB as ground truth.

Two caveats baked into the cards themselves (per issue #10's explicit ask), both verified
live rather than assumed from docs:

- CrmLead.Status / Priority / Source / LeadType hold masked opaque codes (e.g. "A1B2C3D4"),
  not readable strings like "Converted" — never filter/group by them for a human-facing answer.
- BaAddInfo.InfoTypeId is NULL for every row — phone vs. email etc. can't be told apart by type.

A third caveat that ISN'T from the ticket but is load-bearing for the JOIN snippet below:
CrmLead.KundenId does not resolve to any real BaAddress.AddressId in this sample data (checked
directly, zero-padded, and cast-to-int — see project memory for the full trail). The snippet
still uses the documented FK (that's what the ticket asks for, and it's the correct relationship
by design even though this sample's Lead rows aren't linked to real customer records yet) and
uses LEFT JOIN specifically because it degrades gracefully here: all leads still come back, just
with every ba.* column NULL, rather than silently returning zero rows.

#28 extends this file with a card for every table in every LEAD/CUSTOMER scope-tree leaf
(see backend/modules/schema/scope_tree.py, docs/scope-trees.md) — all verified live on
2026-07-07. Two more load-bearing discoveries from that pass, upgrading the "masked opaque
code" story above rather than contradicting it:

- The "masked" CrmLead columns (and several new ones below — CrmTasks.Priority,
  CrmAutomationConditions.FieldId/OperatorId, CrmAutomationActions.ActionTypeId,
  CrmLeadDeletionLog.DeletionReasonId) are NOT actually unreadable: each is a real FK to a
  small lookup dictionary (excluded from the scope tree as "system", see scope-trees.md) whose
  Name/Label column gives the human-readable value (e.g. CrmLead.Status 'A1B2C3D4' ->
  CrmLeadStatus.Name 'Neu'). None of those dictionary tables get a card here (#28's scope is
  tree-included tables only) — this is flagged as a future few-shot/JOIN opportunity, not
  implemented, since resolving it would mean teaching generate_sql a new JOIN pattern, which
  is a prompt-design change outside a "write cards" ticket.
- CrmLeadAusstattung's FK to CrmLead is a column literally named `Lead`, not `LeadId` like
  every other table here. CrmTasks.TaskType empirically reuses CrmContactType's Id space
  (18/20 sample rows match) despite the unrelated name — noted as a warning, not asserted as
  a real relationship (no declared constraint, no doc support, could be coincidence at this
  sample size).

#39 extends this file with a card for every table in every NEWCAR scope-tree leaf — all
verified live on 2026-07-08. The Cdn* (new-car) tables have no declared FK constraints
anywhere either (same as Ba*/Cdi*, confirmed via sys.foreign_keys), but drift further from
their source doc than #28's LEAD/CUSTOMER pass found: several columns the doc's own ER
diagram and flagship example queries depend on — CdnFzgVerkauf.VerkaufDatum,
CdnAuftragK.Termin/.LieferDatum, CdnAuftragK.Geloescht, CdnVkRech.Status/Bruttobetrag/
KundenId, CdnBuchKopf.VkRechId, CdnBuchKtoSt.Saldo, CdnInzahlg.Inzahlgpreis,
CdnFzgReservierung's claimed FzgStammId, CdnEinkPos's claimed FzgStammId — do not exist on
the live tables at all, confirmed via INFORMATION_SCHEMA.COLUMNS, not just a failed query.
Every NEWCAR card below flags this per-table where it applies; see
docs/scope-trees.md's NEWCAR Known Gaps for the full account.

#40 extends this file with a card for every table in every FINANCE scope-tree leaf — all
verified live on 2026-07-08, same zero-declared-FK situation as NEWCAR. The doc repeats
#39's exact "Saldo/due-date column doesn't exist" pattern almost verbatim: CdaBuchKtoSt.
Saldo/.FaelligDatum (its own "overdue receivables" flagship query's dependencies),
CdaBuchKopf.RechDatum, CdcBewegungen.RechDatum (only ~37% populated in practice, CreateDate
used instead) all don't exist or aren't reliably populated. New this time: CdcBewegungen/
CdcAuftragK's Storno column is claimed as a 'J'/'N' flag in the doc's own problem-statement
table but is actually '0'/'1'/'2'/'3' live ('J' never appears at all), and even the doc's
own *worked example query* for CdcTagesStartEndeK/P joins on `.CID` — which resolves 0%
live, the same CID-is-never-the-real-key pattern #39 found, this time in the doc's actual
SQL sample rather than just its ER diagram.
"""

_CARDS: dict[str, str] = {
    "cobra.CrmLead": """\
-- cobra.CrmLead: Sales Lead master table, core table of the LEAD domain
-- MANDATORY FILTER: WHERE IsDeleted = 0 (soft-delete flag)
-- WARNING: Status/Priority/Source/LeadType hold masked opaque codes (e.g. "A1B2C3D4"),
--   not readable strings like "Converted" -- don't filter/group by them for a human answer.
CrmLead(
  Id PK,
  FirstName, LastName, Email, PhoneNumber,
  Score INT,           -- lead score, NULL for most rows
  Brand, Model,        -- vehicle brand/model of interest, plain text, safe to filter
  AssignedToEmployee,  -- salesperson responsible
  FirstResponseTime DATETIME2, LastActivityDate DATETIME2, CreatedAt DATETIME2,
  KundenId,            -- FK -> BaAddress.AddressId (most leads currently unlinked)
  FzgStammId,          -- FK -> CdvFzgStamm.CID (outside LEAD/CUSTOMER scope)
  IsDeleted BIT
)""",
    "cobra.CrmLeadActivity": """\
-- cobra.CrmLeadActivity: follow-up/contact history for a lead (calls, emails, visits, etc.)
-- No IsDeleted of its own; filter via the related CrmLead instead (l.IsDeleted = 0)
CrmLeadActivity(
  Id PK,
  LeadId,          -- FK -> CrmLead.Id
  Type,            -- activity type (call/email/visit), plain text
  Date DATETIME2,
  Result,          -- plain text
  CreatedAt DATETIME2
)""",
    "cobra.CrmLeadScores": """\
-- cobra.CrmLeadScores: AI scoring result for a lead; a lead can have multiple scoring runs
-- IsActive = 1 marks the current valid score; no IsDeleted of its own
CrmLeadScores(
  Id PK,
  LeadId,          -- FK -> CrmLead.Id
  TotalScore INT,
  ScoredAt DATETIME2,
  IsActive BIT     -- 1 = currently active score
)""",
    "cobra.BaAddress": """\
-- cobra.BaAddress: customer/address master data, core table of the CUSTOMER domain
-- There is no separate "customer" object -- the address itself IS the customer;
-- AddressId is referenced system-wide as KundenId
-- WARNING: this table has no IsDeleted/Geloescht column, and no Name1/Name2-style
--   name column either (verified directly against the DB on 2026-07-06 -- differs
--   from some older doc drafts)
BaAddress(
  AddressId PK,         -- system-wide customer identifier
  Street, StreetNo, PostCode, City, Country, Region,
  CreateDate DATETIME   -- creation date, use for "new customers per month" questions
)""",
    "cobra.BaAddInfo": """\
-- cobra.BaAddInfo: additional contact info for an address (phone/email/IBAN etc.), one-to-many
-- WARNING: InfoTypeId is NULL for every row (verified) -- phone vs. email vs.
--   other cannot be distinguished via InfoTypeId.
BaAddInfo(
  InfoNr PK,
  InfoId,          -- FK -> BaAddress.AddressId
  InfoTypeId,      -- always NULL, see warning above
  InfoValue        -- raw contact value, format not standardized
)""",
    # --- LEAD.ACTIVITY leaf (#28) ------------------------------------------------------
    "cobra.CrmLeadContactHistory": """\
-- cobra.CrmLeadContactHistory: contact-history log for a lead (calls/emails/visits + notes)
-- No IsDeleted of its own; filter via the related CrmLead instead (l.IsDeleted = 0)
CrmLeadContactHistory(
  Id PK,
  LeadId,          -- FK -> CrmLead.Id
  ContactType, ContactDate DATETIME2,
  Subject, Description, Duration, Result, Notes, NextAction,
  CustomerId,      -- FK -> BaAddress.AddressId (cross-theme, may not resolve)
  OutlookEventId, OutlookMessageId, OutlookMailbox,
  ProspectId,      -- FK -> CrmProspect.Id (excluded, #27)
  CreatedAt DATETIME2, CreatedBy, UpdatedAt DATETIME2, UpdatedBy
)""",
    "cobra.CrmContactHistoryDescriptionLog": """\
-- cobra.CrmContactHistoryDescriptionLog: edit history of a CrmLeadContactHistory's Description
-- No IsDeleted of its own; filter via CrmLeadContactHistory -> CrmLead
CrmContactHistoryDescriptionLog(
  Id PK,
  ContactHistoryId,   -- FK -> CrmLeadContactHistory.Id
  Description, CreatedAt DATETIME2, CreatedBy,
  IsInitialVersion BIT
)""",
    "cobra.CrmContactHistoryNoteLog": """\
-- cobra.CrmContactHistoryNoteLog: edit history of a CrmLeadContactHistory's Notes
-- No IsDeleted of its own; filter via CrmLeadContactHistory -> CrmLead
CrmContactHistoryNoteLog(
  Id PK,
  ContactHistoryId,   -- FK -> CrmLeadContactHistory.Id
  Note, CreatedAt DATETIME2, CreatedBy,
  IsInitialVersion BIT
)""",
    "cobra.CrmLeadConversion": """\
-- cobra.CrmLeadConversion: one row per lead that converted to a customer (deal closed)
-- No IsDeleted of its own; filter via the related CrmLead instead (l.IsDeleted = 0)
CrmLeadConversion(
  Id PK,
  LeadId,          -- FK -> CrmLead.Id
  CustomerId,      -- FK -> BaAddress.AddressId (cross-theme; may not resolve, see CrmLead card)
  ConversionDate DATETIME2,
  ConversionReason, Notes
)""",
    "cobra.CrmLeadDeletionLog": """\
-- cobra.CrmLeadDeletionLog: audit trail of soft-deleted leads (who/why/when)
-- WARNING: DeletionReasonId is a masked code -- FK -> CrmDeletionReason.Id (excluded dictionary, #27)
CrmLeadDeletionLog(
  Id PK,
  LeadId,             -- FK -> CrmLead.Id (points at a now-IsDeleted=1 lead)
  DeletionReasonId,   -- masked code, see warning
  DeletionComment, DeletedBy, DeletedAt DATETIME2,
  CanRestore BIT
)""",
    "cobra.CrmLeadAusstattung": """\
-- cobra.CrmLeadAusstattung: vehicle-equipment checkboxes for what a lead wants
-- WARNING: FK column to CrmLead is named `Lead`, not `LeadId` (verified live).
CrmLeadAusstattung(
  Id PK,
  Bezeichnung,     -- freeform label
  Klimaanlage, Navigationssystem, Sitzheizung, Ledersitze, ... (~26 more BIT flags,
  -- German equipment names, 1 = requested; full list omitted for token budget, #28),
  Lead,            -- FK -> CrmLead.Id (NOT "LeadId", see warning)
  CreateDate DATETIME2, ModifyDate DATETIME2, CreateUser, ModifyUser
)""",
    "cobra.CrmStatusLog": """\
-- cobra.CrmStatusLog: generic old_value -> new_value change log; record_id -> CrmLead.Id in
--   this sample (100% match, #27) but has no declared FK -- generic name, may log other
--   entity types too. old_value/new_value are masked codes when logging CrmLead.Status
--   (see CrmLead card) -- not readable without a CrmLeadStatus JOIN.
CrmStatusLog(
  Id PK,
  record_id, old_value, new_value,
  modify_user, modify_datetime DATETIME2,
  linked_Record_Id
)""",
    # --- LEAD.SCORING leaf (#28) --------------------------------------------------------
    "cobra.CrmLeadCriterionScores": """\
-- cobra.CrmLeadCriterionScores: per-criterion point breakdown of one CrmLeadScores run
CrmLeadCriterionScores(
  Id PK,
  LeadScoreId,   -- FK -> CrmLeadScores.Id
  CriteriaId,    -- FK -> CrmScoringCriteria.Id
  OptionId,      -- FK -> CrmScoringOptions.Id, nullable (some criteria are freeform)
  CustomValue,   -- freeform answer when no OptionId was picked
  Points INT,
  ScoredAt DATETIME2
)""",
    "cobra.CrmScoringConfigs": """\
-- cobra.CrmScoringConfigs: scoring-rule-set header; a lead is scored under one active config
-- MANDATORY FILTER: WHERE IsDeleted = 0 (soft-delete flag, own to this table)
CrmScoringConfigs(
  Id PK,
  Name, Description,
  IsActive BIT, Version INT,
  CreatedAt DATETIME2, CreatedBy, LastModified DATETIME2, LastModifiedBy,
  IsDeleted BIT
)""",
    "cobra.CrmScoringCategories": """\
-- cobra.CrmScoringCategories: scoring dimensions under one CrmScoringConfigs (e.g. "Budget")
CrmScoringCategories(
  Id PK,
  ScoringConfigId,  -- FK -> CrmScoringConfigs.Id
  Name, Description,
  MaxPoints INT, DisplayOrder INT, IsActive BIT,
  CreatedAt DATETIME2, LastModified DATETIME2
)""",
    "cobra.CrmScoringCriteria": """\
-- cobra.CrmScoringCriteria: individual scoring questions under one CrmScoringCategories
CrmScoringCriteria(
  Id PK,
  CategoryId,   -- FK -> CrmScoringCategories.Id
  Name, Description, CriteriaType,
  IsRequired BIT, DisplayOrder INT, IsActive BIT,
  CreatedAt DATETIME2, LastModified DATETIME2
)""",
    "cobra.CrmScoringOptions": """\
-- cobra.CrmScoringOptions: selectable answer options for one CrmScoringCriteria, each worth Points
CrmScoringOptions(
  Id PK,
  CriteriaId,  -- FK -> CrmScoringCriteria.Id
  Label, Value,
  Points INT, DisplayOrder INT, IsActive BIT,
  CreatedAt DATETIME2, LastModified DATETIME2
)""",
    "cobra.CrmLeadTiers": """\
-- cobra.CrmLeadTiers: score-range tier definitions (e.g. Hot/Warm/Cold bands)
-- WARNING: Priority is plain lowercase text ('high'/'medium'/'low') -- verified live that it
--   does NOT resolve against CrmPriority (0/9 match); despite the shared name these are two
--   unrelated vocabularies (CrmPriority uses German 'Hoch'/'Mittel'/'Niedrig'). Safe to
--   filter/group on directly, it is not a masked code.
CrmLeadTiers(
  Id PK,
  ScoringConfigId,   -- FK -> CrmScoringConfigs.Id
  Name, MinPoints INT, MaxPoints INT, Color,
  Priority,          -- plain text ('high'/'medium'/'low'), see warning
  ContactTimeframeHours INT,   -- SLA: contact within N hours of entering this tier
  DisplayOrder INT, IsActive BIT,
  CreatedAt DATETIME2, LastModified DATETIME2
)""",
    "cobra.CrmTierActions": """\
-- cobra.CrmTierActions: automated action triggered when a lead enters a CrmLeadTiers tier
CrmTierActions(
  Id PK,
  TierId,        -- FK -> CrmLeadTiers.Id
  ActionType,
  Config,        -- freeform (JSON-ish), not parsed here
  DisplayOrder INT, IsActive BIT,
  CreatedAt DATETIME2, LastModified DATETIME2
)""",
    # --- LEAD.TASKS leaf (#28) -----------------------------------------------------------
    "cobra.CrmTasks": """\
-- cobra.CrmTasks: to-do items, optionally linked to a lead
-- WARNING: LinkedTo is a polymorphic reference -- resolved to CrmLead.Id for only 13/20
--   sample rows (#27); do not assume every task links to a Lead.
-- WARNING: Priority is a masked opaque code -- FK -> CrmPriority.Id (not joined here, see
--   module docstring).
-- WARNING: TaskType empirically matches CrmContactType.Id for 18/20 sample rows -- an
--   undeclared, unofficial reuse of that dictionary (verified live, not documented
--   anywhere else); treat as a hint, not a guaranteed relationship.
CrmTasks(
  Id PK,
  Title, Description, AssignedTo,
  Priority,          -- masked code, see warning
  DueDate DATE, DueTime TIME, EstimatedDuration INT,
  LinkedTo,          -- polymorphic, often -> CrmLead.Id, see warning
  CreatedDate DATETIME2, CreatedBy, ModifiedDate DATETIME2, ModifiedBy,
  IsActive BIT,
  TaskType,          -- see warning
  OutlookEventId
)""",
    "cobra.CrmResubmissions": """\
-- cobra.CrmResubmissions: follow-up/Wiedervorlage reminders, optionally linked to a lead/task/activity
-- MANDATORY FILTER: WHERE IsDeleted = 0 (soft-delete flag, own to this table)
-- Status is plain readable text ('pending'/'completed') -- safe to filter directly.
-- WARNING: ReferenceId is polymorphic -- ReferenceType ('Lead'/'Task'/'Activity'/NULL) says
--   which table it points at; resolved to CrmLead.Id for only 1/3 sample rows with
--   ReferenceType='Lead' (#27). Always check ReferenceType before assuming a JOIN target.
CrmResubmissions(
  Id PK,
  CreatedBy, AssignedTo,
  ReminderDate DATE, ReminderTime TIME,
  Title, Notes,
  ReferenceType,   -- 'Lead' | 'Task' | 'Activity' | NULL, see warning
  ReferenceId,     -- polymorphic, see warning
  Status,          -- 'pending' | 'completed', plain text
  CompletedAt DATETIME2, CompletedBy,
  CreatedAt DATETIME2, ModifiedAt DATETIME2, ModifiedBy,
  IsDeleted BIT,
  DeletedAt DATETIME2, DeletedBy,
  IsPriority BIT
)""",
    # --- LEAD.AUTOMATION leaf (#28) -------------------------------------------------------
    "cobra.CrmScheduledActions": """\
-- cobra.CrmScheduledActions: a queued/executed automation run for one lead under one rule
CrmScheduledActions(
  Id PK,
  LeadId,       -- FK -> CrmLead.Id
  RuleId,       -- FK -> CrmAutomationRules.Id
  ScheduledTime DATETIME2,
  Executed BIT, ExecutedAt DATETIME2,
  CreateUser, CreateDate DATETIME2
)""",
    "cobra.CrmAutomationRules": """\
-- cobra.CrmAutomationRules: automation rule definition header (conditions + actions attach here)
CrmAutomationRules(
  Id PK,
  Name, IsActive BIT,
  CreateUser, CreateDate DATETIME, ModifyDate DATETIME, ModifyUser,
  RuleType, IsGlobal BIT, OwnedByUser
)""",
    "cobra.CrmAutomationConditions": """\
-- cobra.CrmAutomationConditions: one trigger condition for a CrmAutomationRules rule
-- RuleId has no declared FK constraint (verified live -- same column/pattern as
--   CrmScheduledActions.RuleId, which IS a real constraint; see LEAD.AUTOMATION leaf note
--   in scope_tree.py)
-- WARNING: FieldId / OperatorId are masked opaque codes -- FK -> CrmAutomationConditionFields.Id
--   / CrmAutomationOperators.Id (both verified 100% live; dictionaries not joined here, see
--   module docstring)
CrmAutomationConditions(
  Id PK,
  RuleId,          -- -> CrmAutomationRules.Id, see note above
  FieldId, OperatorId,   -- masked codes, see warning
  Value1, Value2, LogicalOperator, OrderIndex INT,
  CreateUser, CreateDate DATETIME, ModifyDate DATETIME, ModifyUser
)""",
    "cobra.CrmAutomationActions": """\
-- cobra.CrmAutomationActions: one action executed when a CrmAutomationRules rule fires
-- RuleId has no declared FK constraint (verified live, same situation as
--   CrmAutomationConditions.RuleId -- see that card)
-- WARNING: ActionTypeId is a masked opaque code -- FK -> CrmAutomationActionTypes.Id
--   (verified 100% live; dictionary not joined here, see module docstring)
CrmAutomationActions(
  Id PK,
  RuleId,         -- -> CrmAutomationRules.Id, see note above
  ActionTypeId,   -- masked code, see warning
  OrderIndex INT,
  CreateUser, CreateDate DATETIME, ModifyDate DATETIME, ModifyUser
)""",
    # --- NEWCAR tree (#39) -- verified live 2026-07-08. No Cdn* table anywhere has a
    # declared FK constraint (same situation as Ba*/Cdi*, see module docstring); every
    # relationship below was verified by row-count join match rate, not sys.foreign_keys.
    # Several columns the source doc's own ER diagram and example queries depend on do not
    # exist live at all -- flagged per-card below, not just in scope_tree.py's leaf notes.
    "cobra.CdnAuftragK": """\
-- cobra.CdnAuftragK: New-car sales order header, hub table of the NEWCAR domain (Neuwagenauftrag)
-- WARNING: no soft-delete/Geloescht column exists live (the ER doc claims one) -- there is
--   no "deleted" flag to filter on for this table.
-- WARNING: AngStatus is a status code with no verified dictionary in this candidate set.
CdnAuftragK(
  CID,                      -- internal row surrogate key -- NOT what child tables reference, see ID
  ID,                       -- real business key, referenced by every child table as AUFTRAGK_ID
  AuftragsId INT,           -- human-facing order number (not globally unique)
  KundenId,                 -- FK -> BaAddress.AddressId (cross-theme, CUSTOMER, out of D5 scope)
  FzgStammId,               -- FK -> CdvFzgStamm.CID (cross-theme, VEHICLE, out of D5 scope)
  KundenBeraterId,          -- sales advisor/consultant identifier
  AuftragsDatum DATETIME2,  -- order date, ~100% populated -- date facet for OVERVIEW/ORDER
  Marke, Typ, ModellBez,    -- brand/type/model, plain text, safe to filter/group
  FahrgestellNr,            -- VIN
  AmtlKennz,                -- license plate
  KmStand INT,              -- odometer at order time -- GW/used-vehicle contracts route through
                             -- this same table (see GwVertragsArt), don't assume every row is 0 km
  GwVertragsArt,            -- '' | '0' | '1', mostly empty in this sample -- unreliable as a filter
  AngStatus SMALLINT        -- order status code, see WARNING above
)""",
    "cobra.CdnAuftragsPos": """\
-- cobra.CdnAuftragsPos: order line items (vehicle + accessories + fees) under one CdnAuftragK
CdnAuftragsPos(
  CID, ID,
  AUFTRAGK_ID,        -- FK -> CdnAuftragK.ID (NOT .CID -- verified live, 100% match)
  AUFTRAGKSPLITT_ID,  -- FK -> CdnAuftragKSplitt.ID
  PosNr INT,
  PosArtId,           -- line-type code, no verified dictionary in this candidate set
  SachNr,             -- part/article number
  Anzahl DECIMAL,
  VKPreis DECIMAL, EKPreis DECIMAL, RabProz DECIMAL, RabBetrag DECIMAL, PosBetrag DECIMAL,
  CreateDate DATETIME2
)""",
    "cobra.CdnAuftragKSplitt": """\
-- cobra.CdnAuftragKSplitt: billing/payment split for one CdnAuftragK -- also carries a full
--   duplicate copy of the customer's invoice address (legacy print-layout pattern), omitted
--   below for token budget (~90 of its 116 live columns are Rech*/address fields)
CdnAuftragKSplitt(
  CID, ID,
  AUFTRAGK_ID,          -- FK -> CdnAuftragK.ID (100% match, verified live)
  KundenId,             -- FK -> BaAddress.AddressId (cross-theme)
  Status INT,           -- payment/split status code, no verified dictionary
  RechNr INT, RechDatum DATETIME2,
  BetragNetto DECIMAL, BetragBrutto DECIMAL,
  ZahlArtId,            -- payment method code
  CreateDate DATETIME2
)""",
    "cobra.CdnAuftragsSerAus": """\
-- cobra.CdnAuftragsSerAus: OEM serial-number/external-reference lines reported per order (114k rows)
CdnAuftragsSerAus(
  CID, ID,
  AUFTRAGK_ID,   -- FK -> CdnAuftragK.ID (96.5% match, 109985/114016 -- soft-verified, not 100%)
  AuftragsId INT,
  SerAusId, Bezeichnung,
  CreateDate DATETIME2
)""",
    "cobra.CdnAuftragSperre": """\
-- cobra.CdnAuftragSperre: order lock/unlock EVENT LOG -- NOT a "currently locked" flag table
-- WARNING: SperrKz = '1' means locked, '0' means released; 16853 of 16863 rows are '0'
--   (i.e. this is mostly release events), so COUNT(*) massively overcounts "how many
--   orders are locked now" -- filter WHERE SperrKz = 1 for current state (10 rows).
CdnAuftragSperre(
  CID,
  AUFTRAGK_ID,   -- FK -> CdnAuftragK.ID (100% match, verified live)
  SperrArt,      -- lock-type code ('K'/'B'/'R' observed, no verified dictionary)
  SperrKz,       -- '1' = locked, '0' = released, see WARNING
  Benutzer, Zeit DATETIME2
)""",
    "cobra.CdnAuftragsSteuer": """\
-- cobra.CdnAuftragsSteuer: tax breakdown lines for one CdnAuftragKSplitt
CdnAuftragsSteuer(
  CID, ID,
  AUFTRAGKSPLITT_ID,   -- FK -> CdnAuftragKSplitt.ID (100% match -- NOT CdnAuftragK directly)
  SteuerId SMALLINT,
  Prozent DECIMAL, Basis DECIMAL, Betrag DECIMAL,
  CreateDate DATETIME2
)""",
    "cobra.CdnFzgVerkauf": """\
-- cobra.CdnFzgVerkauf: vehicle delivery/sale record, hub of the NEWCAR.DELIVERY leaf
--   (170 live columns total, key subset below)
-- WARNING: the doc's ER diagram lists a "VerkaufDatum" column -- it does NOT exist live at
--   all (confirmed via INFORMATION_SCHEMA.COLUMNS). Use RechDatum (invoice date, ~96%
--   populated) or AuslieferDat (delivery date, only ~60% populated) instead.
CdnFzgVerkauf(
  CID, ID,                     -- ID is the real business key, referenced by every child table below
  FzgStammId,                  -- FK -> CdvFzgStamm.CID (cross-theme)
  FgstNr,                      -- VIN
  VKRECH_ID,                   -- FK -> CdnVkRech.VkRechId (100% match)
  Verkaeufer1Id, Verkaeufer2Id,-- FK -> CdnVerkaeufer.ID (99.9% match for Verkaeufer1Id)
  KaeuferId,                   -- buyer identifier
  RechDatum DATETIME2,         -- invoice date, best date-column coverage -- this leaf's date facet
  AuslieferDat DATETIME2,      -- delivery/handover date, only ~60% populated, see WARNING
  KomplettPreis DECIMAL, PrsGesamt DECIMAL, PrsGesamtBrutto DECIMAL,
  NachlGesamtProz DECIMAL, NachlGesamtBetrag DECIMAL,  -- total discount %, amount
  Lagerplatz,                  -- storage-location code, plain text (matches CdnLagerplatzHist.Lagerplatz)
  AuftragsStatus SMALLINT,     -- status code, no verified dictionary
  CreateDate DATETIME2
)""",
    "cobra.CdnVkRech": """\
-- cobra.CdnVkRech: new-car sales invoice header
-- WARNING: the doc claims Status/Bruttobetrag/KundenId columns -- none exist live. Real
--   columns are BetragNetto/BetragSteuerFrei/BetragMwst (no precomputed gross total) and
--   there is no customer link at all on this table (go via CdnFzgVerkauf/CdnAuftragK instead).
CdnVkRech(
  CID,
  VkRechId,          -- business key, referenced by CdnFzgVerkauf.VKRECH_ID and CdnVkRechP.VKRECH_ID
  AuftragKId,        -- FK -> CdnAuftragK.ID (100% match)
  AuftragKSplittId,  -- FK -> CdnAuftragKSplitt.ID (100% match)
  FzgVerkaufId,      -- FK -> CdnFzgVerkauf.ID (100% match)
  RechNr, RechDat DATETIME2,   -- NOTE: column is RechDat, not RechDatum (that's CdnFzgVerkauf's column)
  BetragNetto DECIMAL, BetragSteuerFrei DECIMAL, BetragMwst DECIMAL,
  CreateDate DATETIME2
)""",
    "cobra.CdnVkRechP": """\
-- cobra.CdnVkRechP: sales-invoice line items (vehicle vs. accessory vs. discount, via PosArtId)
CdnVkRechP(
  CID, ID,
  VKRECH_ID,      -- FK -> CdnVkRech.VkRechId
  FZGVERKAUF_ID,  -- FK -> CdnFzgVerkauf.ID
  PosArtId,       -- line-type code, no verified dictionary
  VKPreis DECIMAL, EKPreis2 DECIMAL, RabBetrag DECIMAL, EinstWert DECIMAL,
  CreateDate DATETIME2
)""",
    "cobra.CdnVkPreis": """\
-- cobra.CdnVkPreis: historical price snapshot for one CdnFzgVerkauf (multiple rows per
--   vehicle as pricing evolves -- initial quote vs. final invoice, per PreisArt)
CdnVkPreis(
  CID,
  FzgVerkaufId,   -- FK -> CdnFzgVerkauf.ID (100% match)
  PreisArt,       -- snapshot type/stage code
  PrsDatum DATETIME2,
  KomplettPreis DECIMAL, PrsGesamt DECIMAL, PrsGesamtBrutto DECIMAL,
  NachlFahrzeug DECIMAL, NachlGesamt DECIMAL,
  CreateDate DATETIME2
)""",
    "cobra.CdnFzgReservierung": """\
-- cobra.CdnFzgReservierung: vehicle reservation (customer holds a car before delivery), 83 rows
-- WARNING: the doc's own example query joins this table to CdvFzgStamm via FzgStammId --
--   that column does not exist here; the only vehicle link is FzgVerkaufId.
CdnFzgReservierung(
  CID, ID,
  FzgVerkaufId,   -- FK -> CdnFzgVerkauf.ID (100% match)
  KundenId,       -- FK -> BaAddress.AddressId (cross-theme)
  VerkaeuferId,   -- advisor identifier
  ReserviergDat DATETIME2,
  CreateDate DATETIME2
)""",
    "cobra.CdnInzahlg": """\
-- cobra.CdnInzahlg: trade-in (old car accepted against a new-car purchase) -- only 3 rows in
--   this sample. docs/check_crm.md flags this table as valuable and entirely unused --
--   kept as its own bucket-A/B pair despite the thin data, see leaf_question_bank.yaml.
-- WARNING: the doc's example query references "Inzahlgpreis" -- the real column is AnkPreis.
CdnInzahlg(
  CID, ID,
  FzgVerkaufid,   -- FK -> CdnFzgVerkauf.ID (100% match; lowercase "id", same column)
  Kilometer INT, Tacho INT,
  AnkPreis DECIMAL   -- trade-in purchase price (NOT "Inzahlgpreis")
)""",
    "cobra.CdnPraeZusatz": """\
-- cobra.CdnPraeZusatz: manufacturer subsidy/bonus add-on per delivered vehicle (Prämie)
CdnPraeZusatz(
  CID, ID,
  FzgVerkaufId,   -- FK -> CdnFzgVerkauf.ID (99.8% match, 15218/15245)
  ZinsFreiTage INT, ZinsFreiBeginn DATETIME2,
  BHdlZinsFreiTage INT, BHdlZinsFreiBeginn DATETIME2
)""",
    "cobra.CdnLagerplatzHist": """\
-- cobra.CdnLagerplatzHist: vehicle storage-location change history (move in/out of a lot/bay)
CdnLagerplatzHist(
  CID, ID,
  FZGVERKAUF_ID,   -- FK -> CdnFzgVerkauf.ID (100% match)
  Lagerplatz,      -- storage location, plain text code
  Datum DATETIME2, Uhrzeit DATETIME2
)""",
    "cobra.CdnFzgUmbuchung": """\
-- cobra.CdnFzgUmbuchung: vehicle inventory re-numbering (old car-number -> new car-number), 46 rows
CdnFzgUmbuchung(
  CID, ID,
  FzgVerkaufId,   -- FK -> CdnFzgVerkauf.ID (100% match)
  WagenNr_Alt, WagenNr,
  BuchungsDatum DATETIME2
)""",
    "cobra.CdnVerkaeufer": """\
-- cobra.CdnVerkaeufer: sales advisor master table (80 rows)
CdnVerkaeufer(
  CID,
  ID,             -- business key, referenced by CdnFzgVerkauf.Verkaeufer1Id/Verkaeufer2Id (99.9% match)
  SuchBegriff,    -- human-readable name, "Lastname, Firstname" -- the ONLY readable-name field
  VerkaeuferNr,   -- short staff number, not a name
  Team, ProvisionsArt, VerkaeuferArt
)""",
    "cobra.CdnBuchKopf": """\
-- cobra.CdnBuchKopf: new-car settlement/booking document header
-- WARNING: the doc claims a VkRechId column linking to CdnVkRech -- it does NOT exist live;
--   this table links to the order side only (AUFTRAGK_ID/AUFTRAGKSPLITT_ID), never
--   directly to an invoice row.
CdnBuchKopf(
  CID, ID,
  AUFTRAGK_ID,        -- FK -> CdnAuftragK.ID (100% match)
  AUFTRAGKSPLITT_ID,  -- FK -> CdnAuftragKSplitt.ID (100% match)
  BelegNr INT, BuchDatum DATETIME2,
  Betrag DECIMAL, SollHaben,  -- 'S' = Soll/debit, 'H' = Haben/credit
  Status,             -- document status, no verified dictionary
  Fehler INT,         -- error flag, 0 for every row in this sample
  CreateDate DATETIME2
)""",
    "cobra.CdnBuchKtoSt": """\
-- cobra.CdnBuchKtoSt: open-item/account-statement lines under one CdnBuchKopf (289k rows)
-- WARNING: the doc's "unbilled orders" example query filters on a Saldo column -- it does
--   NOT exist live. Compute an open balance as SUM(Betrag) grouped by SollHaben instead;
--   there is no precomputed running-balance column.
CdnBuchKtoSt(
  CID,
  BUCHKOPF_ID,         -- FK -> CdnBuchKopf.ID (100% match)
  AUFTRAGKSPLITT_ID, AUFTRAGSPOS_ID,   -- also link directly to the order-splitt/position level
  KtoNr,               -- account number
  SollHaben,           -- 'S' = Soll/debit, 'H' = Haben/credit -- use to compute open balance
  Betrag DECIMAL,
  CreateDate DATETIME2
)""",
    "cobra.CdnBuchPos": """\
-- cobra.CdnBuchPos: booking-document line items under one CdnBuchKopf (160k rows -- the
--   largest table the 02-newcar-sales doc itself flags as a "重要遗漏" / important omission)
CdnBuchPos(
  CID, ID,
  BUCHKOPF_ID,          -- FK -> CdnBuchKopf.ID (100% match)
  AUFTRAGKSPLITT_ID, AUFTRAGSPOS_ID,  -- also link directly to the order-splitt/position level
  Status,               -- posting status, no verified dictionary
  VerbuchungsKz,        -- posting marker code
  CreateDate DATETIME2
)""",
    "cobra.CdnEinkKopf": """\
-- cobra.CdnEinkKopf: vehicle purchase order header (dealer buying from the OEM/manufacturer)
CdnEinkKopf(
  CID,
  EinkKopfId,         -- business key -- NOTE: this table has no "ID" column at all, unlike most others here
  FzgVerkaufId,       -- FK -> CdnFzgVerkauf.ID (100% match, 38193/38204)
  KundenId,           -- FK -> BaAddress.AddressId (cross-theme)
  Lieferant, KreditorId,           -- supplier identifiers
  RechngNr, RechngDatum DATETIME2, -- invoice number/date, ~99.9% populated -- this leaf's date facet
  ReSuNetto DECIMAL, ReSuMwst DECIMAL, ReSuBrutto DECIMAL,
  Verbuchung INT,     -- posted flag (1 = posted; only 11/38204 rows in this sample)
  EkSachKto INT,      -- accounting-code dictionary reference, not joined here
  CreateDate DATETIME2
)""",
    "cobra.CdnEinkPos": """\
-- cobra.CdnEinkPos: purchase order line items under one CdnEinkKopf (142k rows)
-- WARNING: the doc's ER diagram claims a link to CdnAuftragK via FzgStammId ("via Fzg") --
--   this table has no FzgStammId column live; the only relationship is up to CdnEinkKopf.
CdnEinkPos(
  CID,
  EinkPosId,
  EinkKopfId,   -- FK -> CdnEinkKopf.EinkKopfId (99.96% match, 142392/142448)
  EinkPosTyp,   -- line-type code -- '0' empirically marks the vehicle-itself line (avg
                -- EkPreis ~14,354 vs. hundreds for other codes), not a verified dictionary
  EkPreis DECIMAL, EkPreisGeplant DECIMAL,
  CreateDate DATETIME2
)""",
    "cobra.CdnEkBuchKopf": """\
-- cobra.CdnEkBuchKopf: purchasing-side settlement document header (mirrors CdnBuchKopf, but
--   for what the dealer owes the OEM rather than what the customer owes the dealer), 35 rows
CdnEkBuchKopf(
  CID, ID,
  FZGVERKAUF_ID,   -- FK -> CdnFzgVerkauf.ID (91.4% match, 32/35 -- soft-verified)
  EINKKOPF_ID,     -- FK -> CdnEinkKopf.EinkKopfId (94.3% match, 33/35 -- soft-verified)
  BelegNr, BuchDatum DATETIME2,
  Betrag DECIMAL, SollHaben,
  Status,
  CreateDate DATETIME2
)""",
    "cobra.CdnEkBuchKtoSt": """\
-- cobra.CdnEkBuchKtoSt: open-item lines under one CdnEkBuchKopf (149 rows)
CdnEkBuchKtoSt(
  CID, ID,
  EKBUCHKOPF_ID,           -- FK -> CdnEkBuchKopf.ID (100% match)
  EINKKOPF_ID, EINKPOS_ID, -- also link directly to the purchase order/position level
  KtoNr, SollHaben, Betrag DECIMAL,
  CreateDate DATETIME2
)""",
    # --- FINANCE tree (#40) -- verified live 2026-07-08. Same zero-declared-FK situation
    # as NEWCAR (#39): every relationship below was verified by row-count join match rate.
    # The doc's own "overdue receivables" flagship query and ER diagram both depend on
    # columns that don't exist live -- flagged per-card below.
    "cobra.CdaBuchKopf": """\
-- cobra.CdaBuchKopf: workshop-order settlement document header, hub of the FINANCE domain
-- WARNING: the doc's ER diagram lists a "RechDatum" column -- it does NOT exist live.
--   Use BuchDatum (100% populated) instead.
CdaBuchKopf(
  CID,
  ID,                       -- real business key, referenced by CdaBuchKtoSt/CdaBuchPos as BUCHKOPF_ID
  AUFTRAGK_ID,              -- FK -> CdaAuftragK.ID (cross-theme, WORKSHOP, out of D5 scope)
  AUFTRAGKSPLITT_ID,        -- FK -> workshop order-splitt (cross-theme)
  BuchDatum DATETIME2,      -- booking date, ~100% populated -- date facet for this leaf
  FaelligDatum DATETIME2,   -- due date, only ~58% populated (75100/129966)
  SollHaben,                -- 'S' = Soll/debit, 'H' = Haben/credit
  Betrag DECIMAL,
  Status,                   -- document status code, no verified dictionary
  Fehler INT,               -- error flag
  CreateDate DATETIME2
)""",
    "cobra.CdaBuchKtoSt": """\
-- cobra.CdaBuchKtoSt: open-item/account-statement lines under one CdaBuchKopf (1.31M
--   rows -- the largest table in this sample, the core of dealer receivables reconciliation)
-- WARNING: the doc's ER diagram and its own "overdue receivables (>30/60/90 days)" example
--   query both depend on Saldo and FaelligDatum columns on THIS table -- neither exists
--   live. Compute an open balance as SUM(Betrag) grouped by SollHaben instead; the due
--   date that does exist lives one level up, on CdaBuchKopf.FaelligDatum (join back via
--   BUCHKOPF_ID) -- and that's only ~58% populated, so an "overdue" answer is necessarily
--   partial coverage, not a complete accounts-receivable aging report.
CdaBuchKtoSt(
  CID,
  BUCHKOPF_ID,       -- FK -> CdaBuchKopf.ID (100% match, 1312094/1312098)
  AUFTRAGKSPLITT_ID, AUFTRAGSPOS_ID,  -- also link directly to the order-splitt/position level
  KtoNr,             -- FK -> SKR51SachKto.KontoNummer (79.2% match, 1039159/1312098 -- soft-verified)
  SollHaben,         -- 'S' = Soll/debit, 'H' = Haben/credit -- use to compute open balance
  Betrag DECIMAL,
  CreateDate DATETIME2
)""",
    "cobra.CdaBuchPos": """\
-- cobra.CdaBuchPos: settlement-document line items under one CdaBuchKopf (548k rows)
CdaBuchPos(
  CID, ID,
  BUCHKOPF_ID,          -- FK -> CdaBuchKopf.ID (100% match)
  AUFTRAGKSPLITT_ID, AUFTRAGSPOS_ID,  -- also link directly to the order-splitt/position level
  Status,               -- posting status, no verified dictionary
  VerbuchungsKz,        -- posting marker code
  CreateDate DATETIME2
)""",
    "cobra.SKR51SachKto": """\
-- cobra.SKR51SachKto: SKR51 (Standardkontenrahmen 51 -- German automotive-dealer standard
--   chart of accounts) master data -- the account-number-to-name dictionary
SKR51SachKto(
  CID,
  KontoNummer,     -- business key, referenced by CdaBuchKtoSt.KtoNr (79.2% match)
  Bezeichnung,     -- human-readable account name, e.g. "Lohnerlöse PKW"
  KontoArt,        -- account-type code, no verified dictionary
  KostenArt, KostenStelle,
  CreateDate DATETIME2
)""",
    "cobra.CdcBewegungen": """\
-- cobra.CdcBewegungen: POS cash-register transaction (one row per till movement), hub of
--   the FINANCE.POS_CASH leaf
-- WARNING: the doc's own 现实中容易出现的问题 table claims a "Storno = 'J'" reversal flag --
--   the live values are '0' (valid, 7247/7498 rows) / '1' (reversed, 251/7498), 'J' never
--   appears. WARNING: RechDatum (the doc's suggested date column) is only ~37% populated
--   (2779/7498) -- CreateDate (~99%, 7407/7498) is used as this leaf's date facet instead.
CdcBewegungen(
  CID,
  BewegungId,       -- business key, referenced by every child table below
  KassenId,         -- FK -> CdcKasse.KassenId (100% match)
  BewegungsArt,     -- movement-type code, no verified dictionary
  Bediener,         -- cashier/operator name, plain text
  KundenId,         -- FK -> BaAddress.AddressId (cross-theme, CUSTOMER, out of D5 scope)
  Betrag DECIMAL, ZahlBetrag DECIMAL,
  SollKonto, HabenKonto,  -- WARNING: do NOT join to SKR51SachKto.KontoNummer -- match
                          -- rate is 0.1%/0.3%, essentially unresolvable in this sample
  RechDatum DATETIME2,    -- only ~37% populated, see WARNING above
  CreateDate DATETIME2,   -- ~99% populated -- this leaf's date facet
  Storno,                 -- '0' = valid, '1' = reversed, see WARNING above
  StornoDatum DATETIME2   -- 0% populated in this sample
)""",
    "cobra.CdcVerbuchung": """\
-- cobra.CdcVerbuchung: accounting-posting entry generated from one CdcBewegungen movement
CdcVerbuchung(
  CID,
  BewegungId,   -- FK -> CdcBewegungen.BewegungId (100% match)
  KassenId,
  SollKonto, HabenKonto,  -- same caveat as CdcBewegungen -- not a verified JOIN to SKR51SachKto
  Betrag DECIMAL,
  Status,       -- posting status, no verified dictionary
  CreateDate DATETIME2
)""",
    "cobra.CdcBewZahlArt": """\
-- cobra.CdcBewZahlArt: payment-method breakdown for one CdcBewegungen movement (a single
--   sale can be split across multiple payment methods)
CdcBewZahlArt(
  CID,
  BewegungId,   -- FK -> CdcBewegungen.BewegungId (100% match)
  ZahlArtId,    -- payment-method code -- no dictionary joined here (CdcZahlArten excluded,
                -- #40 -- system config), group/filter on the raw code
  Betrag DECIMAL,
  CreateDate DATETIME2
)""",
    "cobra.CdcBewBestand": """\
-- cobra.CdcBewBestand: cash-register balance snapshot after one CdcBewegungen movement,
--   by register + payment method -- the basis for a "current balance" answer
CdcBewBestand(
  CID, ID,
  Storno,       -- '0' = valid snapshot; filter WHERE Storno = '0' for current state
  KassenId,     -- FK -> CdcKasse.KassenId
  BewegungId,   -- FK -> CdcBewegungen.BewegungId (100% match)
  ZahlArtId,    -- payment-method code, no dictionary joined here
  Bestand DECIMAL,  -- balance amount after this movement
  CreateDate DATETIME2
)""",
    "cobra.CdcVerknuepfung": """\
-- cobra.CdcVerknuepfung: links a POS cash movement to an external reference (a workshop
--   order or invoice number) -- ZuAuftragsNr/ZuRechNr are plain numeric pointers, not
--   verified FKs to any specific table in this candidate set (cross-theme, polymorphic-ish)
CdcVerknuepfung(
  CID,
  BewegungId,     -- FK -> CdcBewegungen.BewegungId (100% match)
  ZuAuftragsNr,   -- external order number, unverified cross-theme pointer
  ZuRechNr,       -- external invoice number, unverified cross-theme pointer
  Betrag DECIMAL,
  CreateDate DATETIME2
)""",
    "cobra.CdcBewegungAusl": """\
-- cobra.CdcBewegungAusl: foreign-currency add-on info for one CdcBewegungen movement (51 rows)
CdcBewegungAusl(
  CID,
  BewegungId,   -- FK -> CdcBewegungen.BewegungId (100% match)
  StornoGrund,  -- reversal-reason code, no verified dictionary
  CreateDate DATETIME2
)""",
    "cobra.CdcKasse": """\
-- cobra.CdcKasse: cash-register master table (9 rows; 76 live columns total, almost all
--   POS hardware/software/TSE-compliance config -- only the business-relevant subset below)
CdcKasse(
  CID,
  KassenId,      -- business key, referenced by CdcBewegungen/CdcKassenProt/CdcTagesStartEndeK
  Bezeichnung,   -- human-readable register name -- the only field worth surfacing in an answer
  Status SMALLINT,
  CreateDate DATETIME2
)""",
    "cobra.CdcKassenProt": """\
-- cobra.CdcKassenProt: cash-register operation log (open/close/X-report/Z-report events, 19k rows)
CdcKassenProt(
  CID,
  KassenId,      -- FK -> CdcKasse.KassenId (100% match)
  Bediener,      -- operator name, plain text
  ProtArten INT, -- event-type code, no verified dictionary
  CreateDate DATETIME2
)""",
    "cobra.CdcTagesStartEndeK": """\
-- cobra.CdcTagesStartEndeK: daily cash-register open/close session header
-- WARNING: the doc's own worked example query joins this table's CID column to
--   CdcTagesStartEndeP.TAGESSTARTENDEK_ID -- that resolves 0% live. Use ID instead
--   (100% match) -- CID is never the real join target anywhere in this table family
--   (#39, #40).
CdcTagesStartEndeK(
  CID,
  ID,               -- real business key, referenced by CdcTagesStartEndeP.TAGESSTARTENDEK_ID
  KassenId,         -- FK -> CdcKasse.KassenId
  StartEndeNr INT,  -- session sequence number
  Typ,              -- open/close type code
  Bediener,         -- operator name, plain text
  CreateDate DATETIME2  -- ~100% populated -- this leaf's date facet
)""",
    "cobra.CdcTagesStartEndeP": """\
-- cobra.CdcTagesStartEndeP: daily cash-register session lines, one row per payment method
--   under one CdcTagesStartEndeK
CdcTagesStartEndeP(
  CID, ID,
  TAGESSTARTENDEK_ID,  -- FK -> CdcTagesStartEndeK.ID (100% match, NOT .CID -- see that card)
  ZahlArtId,           -- payment-method code, no dictionary joined here
  BetrStart DECIMAL, BetrAct DECIMAL, BetrEnd DECIMAL,
  UmsatzTag DECIMAL,   -- daily turnover for this payment method
  CreateDate DATETIME2
)""",
    "cobra.CdcAuftragK": """\
-- cobra.CdcAuftragK: POS-only direct-sale order header (small sales that skip the full
--   workshop-order flow), 47 rows -- mirrors CdnAuftragK's role (#39) but for POS
-- WARNING: Storno is NOT the doc's claimed 'J'/'N' flag -- real values are '0' (not
--   reversed, 30/47 rows) / '1'/'2'/'3' (17/47 rows, different reversal states with no
--   verified dictionary distinguishing them).
CdcAuftragK(
  CID,
  ID,              -- real business key, referenced by every child table below as AUFTRAGK_ID
  KundenId,        -- FK -> BaAddress.AddressId (cross-theme, CUSTOMER, out of D5 scope)
  KundenName,      -- plain-text customer name snapshot (denormalized, may not match BaAddress)
  BelegDatum DATETIME2,  -- ~100% populated -- this leaf's date facet
  BetragNetto DECIMAL, BetragBrutto DECIMAL,
  Bediener,        -- cashier/operator name, plain text
  Storno,          -- see WARNING above
  CreateDate DATETIME2
)""",
    "cobra.CdcAuftragsPos": """\
-- cobra.CdcAuftragsPos: line items under one CdcAuftragK (57 live columns total, key subset below)
CdcAuftragsPos(
  CID, ID,
  AUFTRAGK_ID,   -- FK -> CdcAuftragK.ID (100% match)
  PosNr INT,
  SachNr,        -- part/article number
  Anzahl DECIMAL,
  VKPreisNetto DECIMAL, VKPreisBrutto DECIMAL, EKPreis DECIMAL,
  PosBetragNetto DECIMAL, PosBetragBrutto DECIMAL,
  CreateDate DATETIME2
)""",
    "cobra.CdcAuftragsSteuer": """\
-- cobra.CdcAuftragsSteuer: tax breakdown lines for one CdcAuftragK
CdcAuftragsSteuer(
  CID, ID,
  AUFTRAGK_ID,   -- FK -> CdcAuftragK.ID (100% match)
  SteuerId SMALLINT,
  Prozent DECIMAL, Basis DECIMAL, Betrag DECIMAL,
  CreateDate DATETIME2
)""",
    "cobra.CdcBuchKopf": """\
-- cobra.CdcBuchKopf: settlement-document header for one CdcAuftragK (POS-side mirror of
--   CdaBuchKopf), 34 rows
CdcBuchKopf(
  CID, ID,
  AUFTRAGK_ID,   -- FK -> CdcAuftragK.ID (100% match)
  KassenId,
  BelegDatum DATETIME2,
  Betrag DECIMAL,
  Status,        -- document status, no verified dictionary
  Fehler INT,
  CreateDate DATETIME2
)""",
    "cobra.CdcBuchKtoSt": """\
-- cobra.CdcBuchKtoSt: open-item lines under one CdcBuchKopf (74 rows)
CdcBuchKtoSt(
  CID, ID,
  BUCHKOPF_ID,   -- FK -> CdcBuchKopf.ID (100% match)
  AUFTRAGK_ID,   -- also links directly to the order level
  SollKonto, HabenKonto,
  Betrag DECIMAL,
  Status,        -- posting status, no verified dictionary
  CreateDate DATETIME2
)""",
}

# Structured mirror of the column lists inside _CARDS above (deliberately excludes
# masked columns like Status/Priority/Source/LeadType, same reasoning as the cards
# themselves) -- used by modules/query/ranking.py to whitelist an LLM-provided
# sort_column before it's interpolated into a SQL template. Keep in sync with _CARDS
# if a card's column list ever changes.
_COLUMNS: dict[str, list[str]] = {
    "cobra.CrmLead": [
        "Id", "FirstName", "LastName", "Email", "PhoneNumber", "Score", "Brand", "Model",
        "AssignedToEmployee", "FirstResponseTime", "LastActivityDate", "CreatedAt",
        "KundenId", "FzgStammId", "IsDeleted",
    ],
    "cobra.CrmLeadActivity": ["Id", "LeadId", "Type", "Date", "Result", "CreatedAt"],
    "cobra.CrmLeadScores": ["Id", "LeadId", "TotalScore", "ScoredAt", "IsActive"],
    "cobra.BaAddress": [
        "AddressId", "Street", "StreetNo", "PostCode", "City", "Country", "Region", "CreateDate",
    ],
    "cobra.BaAddInfo": ["InfoNr", "InfoId", "InfoTypeId", "InfoValue"],
    "cobra.CrmLeadContactHistory": [
        "Id", "LeadId", "ContactType", "ContactDate", "Subject", "Description", "Duration",
        "Result", "Notes", "NextAction", "CustomerId", "OutlookEventId", "OutlookMessageId",
        "OutlookMailbox", "ProspectId", "CreatedAt", "CreatedBy", "UpdatedAt", "UpdatedBy",
    ],
    "cobra.CrmContactHistoryDescriptionLog": [
        "Id", "ContactHistoryId", "Description", "CreatedAt", "CreatedBy", "IsInitialVersion",
    ],
    "cobra.CrmContactHistoryNoteLog": [
        "Id", "ContactHistoryId", "Note", "CreatedAt", "CreatedBy", "IsInitialVersion",
    ],
    "cobra.CrmLeadConversion": [
        "Id", "LeadId", "CustomerId", "ConversionDate", "ConversionReason", "Notes",
    ],
    # DeletionReasonId excluded -- masked code, same policy as CrmLead.Status/Priority/... above.
    "cobra.CrmLeadDeletionLog": ["Id", "LeadId", "DeletionComment", "DeletedBy", "DeletedAt", "CanRestore"],
    "cobra.CrmLeadAusstattung": [
        "Id", "Bezeichnung", "Klimaanlage", "Navigationssystem", "Sitzheizung", "Einparkhilfe",
        "Rueckfahrkamera", "Ledersitze", "Schiebedach", "Panoramadach", "Allradantrieb",
        "Automatikgetriebe", "Tempomat", "AdaptiverTempomat", "Spurhalteassistent",
        "Totwinkelassistent", "Notbremsassistent", "HeadUpDisplay", "AndroidAuto", "AppleCarPlay",
        "BluetoothFreisprecheinrichtung", "DABRadio", "PremiumSoundSystem", "ElektrischeSitze",
        "Sitzbelueftung", "Massagesitze", "AmbienteBeleuchtung", "MatrixLED", "Anhängerkupplung",
        "Standheizung", "KeylessGo", "ElektrischeHeckklappe", "Lead", "CreateDate", "ModifyDate",
        "CreateUser", "ModifyUser",
    ],
    "cobra.CrmStatusLog": [
        "Id", "record_id", "old_value", "new_value", "modify_user", "modify_datetime", "linked_Record_Id",
    ],
    "cobra.CrmLeadCriterionScores": [
        "Id", "LeadScoreId", "CriteriaId", "OptionId", "CustomValue", "Points", "ScoredAt",
    ],
    "cobra.CrmScoringConfigs": [
        "Id", "Name", "Description", "IsActive", "Version", "CreatedAt", "CreatedBy",
        "LastModified", "LastModifiedBy", "IsDeleted",
    ],
    "cobra.CrmScoringCategories": [
        "Id", "ScoringConfigId", "Name", "Description", "MaxPoints", "DisplayOrder", "IsActive",
        "CreatedAt", "LastModified",
    ],
    "cobra.CrmScoringCriteria": [
        "Id", "CategoryId", "Name", "Description", "CriteriaType", "IsRequired", "DisplayOrder",
        "IsActive", "CreatedAt", "LastModified",
    ],
    "cobra.CrmScoringOptions": [
        "Id", "CriteriaId", "Label", "Value", "Points", "DisplayOrder", "IsActive", "CreatedAt",
        "LastModified",
    ],
    "cobra.CrmLeadTiers": [
        "Id", "ScoringConfigId", "Name", "MinPoints", "MaxPoints", "Color", "Priority",
        "ContactTimeframeHours", "DisplayOrder", "IsActive", "CreatedAt", "LastModified",
    ],
    "cobra.CrmTierActions": [
        "Id", "TierId", "ActionType", "Config", "DisplayOrder", "IsActive", "CreatedAt", "LastModified",
    ],
    # Priority excluded -- masked code (FK -> CrmPriority.Id), same policy as CrmLead's.
    "cobra.CrmTasks": [
        "Id", "Title", "Description", "AssignedTo", "DueDate", "DueTime", "EstimatedDuration",
        "LinkedTo", "CreatedDate", "CreatedBy", "ModifiedDate", "ModifiedBy", "IsActive",
        "TaskType", "OutlookEventId",
    ],
    "cobra.CrmResubmissions": [
        "Id", "CreatedBy", "AssignedTo", "ReminderDate", "ReminderTime", "Title", "Notes",
        "ReferenceType", "ReferenceId", "Status", "CompletedAt", "CompletedBy", "CreatedAt",
        "ModifiedAt", "ModifiedBy", "IsDeleted", "DeletedAt", "DeletedBy", "IsPriority",
    ],
    "cobra.CrmScheduledActions": [
        "Id", "LeadId", "RuleId", "ScheduledTime", "Executed", "ExecutedAt", "CreateUser", "CreateDate",
    ],
    "cobra.CrmAutomationRules": [
        "Id", "Name", "IsActive", "CreateUser", "CreateDate", "ModifyDate", "ModifyUser",
        "RuleType", "IsGlobal", "OwnedByUser",
    ],
    # FieldId/OperatorId excluded -- masked codes (FK -> CrmAutomationConditionFields/Operators).
    "cobra.CrmAutomationConditions": [
        "Id", "RuleId", "Value1", "Value2", "LogicalOperator", "OrderIndex", "CreateUser",
        "CreateDate", "ModifyDate", "ModifyUser",
    ],
    # ActionTypeId excluded -- masked code (FK -> CrmAutomationActionTypes.Id).
    "cobra.CrmAutomationActions": [
        "Id", "RuleId", "OrderIndex", "CreateUser", "CreateDate", "ModifyDate", "ModifyUser",
    ],
    # --- NEWCAR tree (#39) -- AngStatus/PosArtId/SperrArt/Status/EinkPosTyp-style code
    # columns excluded throughout, same "no verified dictionary" policy as elsewhere in
    # this file; SollHaben/SperrKz are kept since their two-value meaning is verified.
    "cobra.CdnAuftragK": [
        "CID", "ID", "AuftragsId", "KundenId", "FzgStammId", "KundenBeraterId", "AuftragsDatum",
        "Marke", "Typ", "ModellBez", "FahrgestellNr", "AmtlKennz", "KmStand", "GwVertragsArt",
    ],
    "cobra.CdnAuftragsPos": [
        "CID", "ID", "AUFTRAGK_ID", "AUFTRAGKSPLITT_ID", "PosNr", "SachNr", "Anzahl",
        "VKPreis", "EKPreis", "RabProz", "RabBetrag", "PosBetrag", "CreateDate",
    ],
    "cobra.CdnAuftragKSplitt": [
        "CID", "ID", "AUFTRAGK_ID", "KundenId", "RechNr", "RechDatum", "BetragNetto",
        "BetragBrutto", "CreateDate",
    ],
    "cobra.CdnAuftragsSerAus": [
        "CID", "ID", "AUFTRAGK_ID", "AuftragsId", "SerAusId", "Bezeichnung", "CreateDate",
    ],
    "cobra.CdnAuftragSperre": ["CID", "AUFTRAGK_ID", "SperrKz", "Benutzer", "Zeit"],
    "cobra.CdnAuftragsSteuer": [
        "CID", "ID", "AUFTRAGKSPLITT_ID", "SteuerId", "Prozent", "Basis", "Betrag", "CreateDate",
    ],
    "cobra.CdnFzgVerkauf": [
        "CID", "ID", "FzgStammId", "FgstNr", "VKRECH_ID", "Verkaeufer1Id", "Verkaeufer2Id",
        "KaeuferId", "RechDatum", "AuslieferDat", "KomplettPreis", "PrsGesamt", "PrsGesamtBrutto",
        "NachlGesamtProz", "NachlGesamtBetrag", "Lagerplatz", "CreateDate",
    ],
    "cobra.CdnVkRech": [
        "CID", "VkRechId", "AuftragKId", "AuftragKSplittId", "FzgVerkaufId", "RechNr", "RechDat",
        "BetragNetto", "BetragSteuerFrei", "BetragMwst", "CreateDate",
    ],
    "cobra.CdnVkRechP": [
        "CID", "ID", "VKRECH_ID", "FZGVERKAUF_ID", "VKPreis", "EKPreis2", "RabBetrag",
        "EinstWert", "CreateDate",
    ],
    "cobra.CdnVkPreis": [
        "CID", "FzgVerkaufId", "PreisArt", "PrsDatum", "KomplettPreis", "PrsGesamt",
        "PrsGesamtBrutto", "NachlFahrzeug", "NachlGesamt", "CreateDate",
    ],
    "cobra.CdnFzgReservierung": [
        "CID", "ID", "FzgVerkaufId", "KundenId", "VerkaeuferId", "ReserviergDat", "CreateDate",
    ],
    "cobra.CdnInzahlg": ["CID", "ID", "FzgVerkaufid", "Kilometer", "Tacho", "AnkPreis"],
    "cobra.CdnPraeZusatz": [
        "CID", "ID", "FzgVerkaufId", "ZinsFreiTage", "ZinsFreiBeginn", "BHdlZinsFreiTage",
        "BHdlZinsFreiBeginn",
    ],
    "cobra.CdnLagerplatzHist": ["CID", "ID", "FZGVERKAUF_ID", "Lagerplatz", "Datum", "Uhrzeit"],
    "cobra.CdnFzgUmbuchung": [
        "CID", "ID", "FzgVerkaufId", "WagenNr_Alt", "WagenNr", "BuchungsDatum",
    ],
    "cobra.CdnVerkaeufer": [
        "CID", "ID", "SuchBegriff", "VerkaeuferNr", "Team", "ProvisionsArt", "VerkaeuferArt",
    ],
    "cobra.CdnBuchKopf": [
        "CID", "ID", "AUFTRAGK_ID", "AUFTRAGKSPLITT_ID", "BelegNr", "BuchDatum", "Betrag",
        "SollHaben", "CreateDate",
    ],
    "cobra.CdnBuchKtoSt": [
        "CID", "BUCHKOPF_ID", "AUFTRAGKSPLITT_ID", "AUFTRAGSPOS_ID", "KtoNr", "SollHaben",
        "Betrag", "CreateDate",
    ],
    "cobra.CdnBuchPos": [
        "CID", "ID", "BUCHKOPF_ID", "AUFTRAGKSPLITT_ID", "AUFTRAGSPOS_ID", "CreateDate",
    ],
    "cobra.CdnEinkKopf": [
        "CID", "EinkKopfId", "FzgVerkaufId", "KundenId", "Lieferant", "KreditorId", "RechngNr",
        "RechngDatum", "ReSuNetto", "ReSuMwst", "ReSuBrutto", "Verbuchung", "CreateDate",
    ],
    "cobra.CdnEinkPos": [
        "CID", "EinkPosId", "EinkKopfId", "EinkPosTyp", "EkPreis", "EkPreisGeplant", "CreateDate",
    ],
    "cobra.CdnEkBuchKopf": [
        "CID", "ID", "FZGVERKAUF_ID", "EINKKOPF_ID", "BelegNr", "BuchDatum", "Betrag",
        "SollHaben", "CreateDate",
    ],
    "cobra.CdnEkBuchKtoSt": [
        "CID", "ID", "EKBUCHKOPF_ID", "EINKKOPF_ID", "EINKPOS_ID", "KtoNr", "SollHaben",
        "Betrag", "CreateDate",
    ],
    # --- FINANCE tree (#40) -- Status/BewegungsArt/ProtArten/Typ/ZahlArtId-style code
    # columns excluded, same "no verified dictionary" policy as elsewhere in this file;
    # SollHaben/Storno are kept since their meaning is verified.
    "cobra.CdaBuchKopf": [
        "CID", "ID", "AUFTRAGK_ID", "BuchDatum", "FaelligDatum", "SollHaben", "Betrag", "CreateDate",
    ],
    "cobra.CdaBuchKtoSt": [
        "CID", "BUCHKOPF_ID", "AUFTRAGKSPLITT_ID", "AUFTRAGSPOS_ID", "KtoNr", "SollHaben",
        "Betrag", "CreateDate",
    ],
    "cobra.CdaBuchPos": ["CID", "ID", "BUCHKOPF_ID", "AUFTRAGKSPLITT_ID", "AUFTRAGSPOS_ID", "CreateDate"],
    "cobra.SKR51SachKto": ["CID", "KontoNummer", "Bezeichnung", "KostenArt", "KostenStelle", "CreateDate"],
    "cobra.CdcBewegungen": [
        "CID", "BewegungId", "KassenId", "Bediener", "KundenId", "Betrag", "ZahlBetrag",
        "RechDatum", "CreateDate", "Storno",
    ],
    "cobra.CdcVerbuchung": ["CID", "BewegungId", "KassenId", "Betrag", "CreateDate"],
    "cobra.CdcBewZahlArt": ["CID", "BewegungId", "ZahlArtId", "Betrag", "CreateDate"],
    "cobra.CdcBewBestand": ["CID", "ID", "Storno", "KassenId", "BewegungId", "ZahlArtId", "Bestand", "CreateDate"],
    "cobra.CdcVerknuepfung": ["CID", "BewegungId", "ZuAuftragsNr", "ZuRechNr", "Betrag", "CreateDate"],
    "cobra.CdcBewegungAusl": ["CID", "BewegungId", "CreateDate"],
    "cobra.CdcKasse": ["CID", "KassenId", "Bezeichnung", "CreateDate"],
    "cobra.CdcKassenProt": ["CID", "KassenId", "Bediener", "CreateDate"],
    "cobra.CdcTagesStartEndeK": ["CID", "ID", "KassenId", "StartEndeNr", "Bediener", "CreateDate"],
    "cobra.CdcTagesStartEndeP": [
        "CID", "ID", "TAGESSTARTENDEK_ID", "ZahlArtId", "BetrStart", "BetrAct", "BetrEnd",
        "UmsatzTag", "CreateDate",
    ],
    "cobra.CdcAuftragK": [
        "CID", "ID", "KundenId", "KundenName", "BelegDatum", "BetragNetto", "BetragBrutto",
        "Bediener", "Storno", "CreateDate",
    ],
    "cobra.CdcAuftragsPos": [
        "CID", "ID", "AUFTRAGK_ID", "PosNr", "SachNr", "Anzahl", "VKPreisNetto", "VKPreisBrutto",
        "EKPreis", "PosBetragNetto", "PosBetragBrutto", "CreateDate",
    ],
    "cobra.CdcAuftragsSteuer": ["CID", "ID", "AUFTRAGK_ID", "Prozent", "Basis", "Betrag", "CreateDate"],
    "cobra.CdcBuchKopf": ["CID", "ID", "AUFTRAGK_ID", "KassenId", "BelegDatum", "Betrag", "CreateDate"],
    "cobra.CdcBuchKtoSt": ["CID", "ID", "BUCHKOPF_ID", "AUFTRAGK_ID", "Betrag", "CreateDate"],
}

# Same soft-delete rule as each card's "MANDATORY FILTER" comment, structured for
# the deterministic ranking template to apply automatically.
_MANDATORY_FILTERS: dict[str, str] = {
    "cobra.CrmLead": "IsDeleted = 0",
    "cobra.CrmScoringConfigs": "IsDeleted = 0",
    "cobra.CrmResubmissions": "IsDeleted = 0",
}


def get_columns(table: str) -> list[str]:
    """Return the curated, safe-to-reference column whitelist for `table` (empty if unknown)."""
    return list(_COLUMNS.get(table, []))


def get_mandatory_filter(table: str) -> str | None:
    """Return the mandatory WHERE condition for `table`, if it has one (e.g. a soft-delete flag)."""
    return _MANDATORY_FILTERS.get(table)


_JOIN_SNIPPETS: dict[frozenset[str], str] = {
    frozenset({"cobra.CrmLead", "cobra.BaAddress"}): """\
-- JOIN LEAD x CUSTOMER (cross-domain, deterministic JOIN -- do not infer another path):
cobra.CrmLead l
LEFT JOIN cobra.BaAddress ba ON ba.AddressId = l.KundenId

-- NOTE (verified 2026-07-06): in the current sample data, l.KundenId does not
-- resolve to a real BaAddress.AddressId for any existing CrmLead row, so the
-- ba.* columns will currently be NULL for every lead (LEFT JOIN still returns
-- all leads -- this is not an empty result set). If the customer-side columns
-- are all NULL, explain it as "no linked customer record yet", not as a SQL error.""",
}


def get_schema_context(tables: list[str]) -> str:
    """Assemble compressed schema cards for `tables`, plus the LEAD×CUSTOMER JOIN
    snippet when the requested set spans both domains."""
    sections = [_CARDS[t] for t in tables if t in _CARDS]

    requested = frozenset(tables)
    for join_tables, snippet in _JOIN_SNIPPETS.items():
        if join_tables <= requested:
            sections.append(snippet)

    return "\n\n".join(sections)
