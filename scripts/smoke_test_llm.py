"""
Ticket 4 smoke test: can a 7B model turn a German question about cobra.CrmLead
into usable T-SQL, and how long does that take on this machine?

Deliberately dependency-free (stdlib only) and deliberately not an
LLMProvider abstraction or a real pipeline -- see issue #4 scope. Just:
schema card + one few-shot example + a handful of German questions -> Ollama.

Usage:
    python scripts/smoke_test_llm.py
"""

import json
import time
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:7b"

# Column list + types pulled live from the restored sample DB
# (INFORMATION_SCHEMA.COLUMNS on cobra.CrmLead). Notes call out the
# German-derived / abbreviated names and the columns that are masked in
# this sample dataset, so the model isn't nudged into inventing values
# for codes it can't actually decode.
SCHEMA_CARD = """\
Table: cobra.CrmLead  (one row = one sales lead)
Columns:
  Id                    nvarchar    primary key
  FirstName, LastName   nvarchar
  Email, PhoneNumber    nvarchar
  Status, Priority,     nvarchar    NOTE: in this sample dataset these are masked
    Source, LeadType                opaque codes (e.g. 'A1B2C3D4'), not readable
                                     business values -- do not assume literal
                                     strings like 'New' or 'Qualified' exist.
  Score                 int         lead score
  Campaign, Channel     nvarchar
  ConversionProbability decimal
  InterestType,         nvarchar
    VehicleType
  Brand, Model          nvarchar    vehicle brand/model the lead is interested in
  Budget,               decimal
    EstimatedValue
  FinancingRequest,     bit         1/0 flags
    LeasingRequest,
    TradeInRequest,
    TestDriveRequest
  AssignedToEmployee,   nvarchar
    AssignedToLocation
  AssignedAt, FirstResponseTime,
    LastActivityDate, NextActivityDate   datetime2
  KundenId              nvarchar    FK -> cobra.BaAddress.AddressId (Kunde = customer)
  FzgStammId            nvarchar    FK -> cobra.CdvFzgStamm.CID (Fahrzeug = vehicle)
  FgstNr                varchar     Fahrgestellnummer (vehicle chassis/VIN number)
  BrancheId             nvarchar    Branche = industry/business sector (B2B leads)
  CreatedAt, UpdatedAt  datetime2
  IsDeleted             bit         soft-delete flag; filter IsDeleted = 0 unless asked otherwise
"""

FEW_SHOT_QUESTION = "Wie viele Leads interessieren sich fuer einen Audi?"
FEW_SHOT_SQL = (
    "SELECT COUNT(*) FROM cobra.CrmLead WHERE Brand = 'Audi' AND IsDeleted = 0;"
)

QUESTIONS = [
    "Wie viele Leads gibt es insgesamt?",
    "Welche Marken interessieren die Leads?",
    "Zeige alle Leads mit einem Budget ueber 30000.",
    "Wie viele Leads wuenschen eine Finanzierung?",
    "Welcher Lead hat den hoechsten Score?",
]


def build_prompt(question: str) -> str:
    return f"""You are a T-SQL assistant for a SQL Server database (schema `cobra`).
Given the table schema and one example, write ONE T-SQL query that answers
the question. Output ONLY the SQL, no explanation, no markdown fences.

{SCHEMA_CARD}

Example:
Q: {FEW_SHOT_QUESTION}
SQL: {FEW_SHOT_SQL}

Q: {question}
SQL:"""


def call_ollama(prompt: str) -> tuple[str, float]:
    payload = json.dumps(
        {"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0}}
    ).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    elapsed = time.perf_counter() - start
    return body.get("response", "").strip(), elapsed


def main() -> None:
    print(f"Model: {MODEL}  |  Endpoint: {OLLAMA_URL}")
    print(f"Sample data note: cobra.CrmLead has only 7 rows in this dataset, and\n"
          f"Status/Priority/Source/LeadType are masked codes, not readable text.\n")

    results = []
    for i, question in enumerate(QUESTIONS, start=1):
        prompt = build_prompt(question)
        sql, elapsed = call_ollama(prompt)
        results.append((question, sql, elapsed))
        print(f"[{i}/{len(QUESTIONS)}] Q: {question}")
        print(f"SQL: {sql}")
        print(f"Latency: {elapsed:.2f}s\n")

    print("=" * 60)
    print("Summary")
    print("=" * 60)
    for question, _, elapsed in results:
        print(f"{elapsed:6.2f}s  {question}")
    avg = sum(r[2] for r in results) / len(results)
    print(f"\nAverage latency: {avg:.2f}s over {len(results)} questions")


if __name__ == "__main__":
    main()
