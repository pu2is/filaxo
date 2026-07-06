"""Loader for the DB-verified question -> T-SQL base set (question_bank.yaml).

Data-reality caveats found while verifying this set against FilaksOne
(localhost,14330) on 2026-07-06 -- relevant to schema cards, JOIN registries,
or generate_sql prompts built against LEAD/CUSTOMER later:

- CrmLead.Status / Priority / Source / LeadType hold masked opaque codes
  (e.g. "A1B2C3D4"), not the readable strings ("Converted", ...) the domain
  docs' example queries assume. No entry here filters/groups by them.
- BaAddInfo.InfoTypeId is NULL for every row -- phone vs. email etc. can't be
  distinguished by type.
- The documented CrmLead.KundenId -> BaAddress.AddressId FK (and
  CrmLeadContactHistory.CustomerId -> BaAddress.AddressId) does not resolve to
  any matching row in this sample data -- checked directly, zero-padded, and
  cast-to-int. A live JOIN on this path currently returns zero rows, so the
  cross-domain entry combines independent counts from both tables instead of
  joining them.
"""

from pathlib import Path

import yaml

_BANK_PATH = Path(__file__).parent / "question_bank.yaml"

with _BANK_PATH.open("r", encoding="utf-8") as _f:
    _ENTRIES: list[dict] = yaml.safe_load(_f) or []


def get_few_shots(domains: list[str]) -> list[str]:
    """Return formatted question->SQL few-shot blocks for the given domain scope.

    An entry is included when every domain it requires is in `domains`, so a
    single-domain entry shows whenever its domain is selected, and a
    cross-domain entry only shows once all of its domains are selected.
    """
    requested = set(domains)
    matches = [e for e in _ENTRIES if set(e["domain"]).issubset(requested)]
    return [
        f"-- Frage: {entry['question']}\n{entry['reference_sql'].strip()}"
        for entry in matches
    ]
