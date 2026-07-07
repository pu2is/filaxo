"""Thema -> core table set, MVP 1 Wave 1 (D5): a flat dict standing in for the scope
tree that #30 will build. `DOMAIN_DOC_REF` feeds the `sources` field on a chat result
so the UI can cite which ER doc backs the tables a query touched."""

DOMAIN_TABLES: dict[str, list[str]] = {
    "LEAD": ["cobra.CrmLead", "cobra.CrmLeadActivity", "cobra.CrmLeadScores"],
    "CUSTOMER": ["cobra.BaAddress", "cobra.BaAddInfo"],
}

DOMAIN_DOC_REF: dict[str, str] = {
    "LEAD": "docs/01-lead-sales-erDiagram.md",
    "CUSTOMER": "docs/01-customer-address-erDiagram.md",
}
