"""Deterministic schema supply for LEAD + CUSTOMER (mvp-request D2 — replaces vector RAG for MVP1).

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
