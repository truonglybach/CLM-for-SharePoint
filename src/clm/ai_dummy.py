"""
ai_dummy.py (v2)
Placeholder AI so the SharePoint + schema wiring can be tested before the real
Azure OpenAI calls exist. The AI returns ATTRIBUTES ONLY, never identity fields.
"""
from __future__ import annotations

from typing import Any, Dict


def extract_metadata(text: str) -> Dict[str, Any]:
    return {
        "attributes": {
            "Title": "Sample Vendor Agreement",
            "Counterparty": "Sample Vendor Inc.",
            "ContractType": "Vendor",
            "EffectiveDate": "2025-01-01",
            "ExpirationDate": "2026-01-01",
            "AutoRenewal": False,
            "TotalValue": 100000,
            "FundingSource": "State",
            "Status": "Active",
        },
        "confidence": 0.91,
    }

def extract_clauses(text: str) -> Dict[str, Any]:
    return {
        "clauses": [
            {"clause_id": "TERM", "clause_name": "Termination", "text_span": "...dummy termination text..."},
            {"clause_id": "SOW", "clause_name": "Scope of Work", "text_span": "...dummy scope text..."},
        ],
        "confidence": 0.84,
    }

def map_subject_terms(text: str, clauses: Dict[str, Any], candidate_terms: Any = None) -> Dict[str, Any]:
    return {
        "mappings": [
            {"ClauseID": "TERM", "TermID": "PROGRAM_EXIT", "RelevanceScore": 0.9,
             "ExtractionConfidence": 0.85, "Notes": "Dummy mapping."}
        ],
        "confidence": 0.85,
    }

def extract_amendment_metadata(text: str) -> Dict[str, Any]:
    return {
        "attributes": {
            "AmendmentType": "Extension",
            "EffectiveDate": "2026-01-01",
            "ExpirationDate": "2027-01-01",
            "ValueChange": 25000,
            "SummaryOfChanges": "Extends the term by one year and adds $25,000 in funding.",
        },
        "contract_changes": {"ExpirationDate": "2027-01-01", "Status": "Active"},
        "confidence": 0.88,
    }

def detect_modified_clauses(text: str, original_clauses: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "modified": [
            {"ClauseID": "TERM", "ChangeType": "Modified",
             "Note": "Termination notice period changed from 30 to 60 days."},
        ],
        "confidence": 0.82,
    }
