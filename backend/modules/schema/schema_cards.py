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
"""

_CARDS: dict[str, str] = {
    "cobra.CrmLead": """\
-- cobra.CrmLead: Sales Lead master table, core table of the LEAD domain
-- MANDATORY FILTER: WHERE IsDeleted = 0 (soft-delete flag)
-- WARNING: Status / Priority / Source / LeadType hold masked opaque codes
--   (e.g. "A1B2C3D4", "83946BC5855049BCAD298A3FCD0686C6"), not readable
--   strings like "Converted". Do not use them in WHERE/GROUP BY for a
--   human-facing answer; they exist as columns but their values aren't
--   interpretable.
CrmLead(
  Id PK,
  FirstName, LastName, Email, PhoneNumber,
  Score INT,                   -- lead score, NULL for most rows
  Brand, Model,                -- vehicle brand/model of interest, plain text, safe to filter
  AssignedToEmployee,          -- salesperson responsible
  FirstResponseTime DATETIME2, LastActivityDate DATETIME2, CreatedAt DATETIME2,
  KundenId,                    -- FK -> BaAddress.AddressId (see JOIN note below: most leads currently unlinked)
  FzgStammId,                  -- FK -> CdvFzgStamm.CID (Fzg=Fahrzeug/vehicle; outside LEAD/CUSTOMER scope)
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
}

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
