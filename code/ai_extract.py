"""Real Azure OpenAI extraction, drop-in for ai_dummy.py."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import azure_client as aoai
import ai_schemas as S

_RULES = "You extract structured facts from contract text. Return only supported attributes, never identifiers. Provide verbatim evidence spans. Use null rather than guessing."
_MAP_RULES = "Map each clause to one supplied candidate term. If no candidate fits or context is ambiguous, set term_id null and ambiguous true."
_JUDGE_RULES = "Compare clauses and classify relationship as identical, stricter, looser, superset, subset, related, or conflicting."

def _normalize_field(field: str) -> str:
    return field.replace("_", "").replace(" ", "").lower()

def _coverage_confidence(evidenced: set[str], key_fields: set[str]) -> float:
    if not key_fields:
        return 1.0
    evidenced_n = {_normalize_field(f) for f in evidenced}
    key_n = {_normalize_field(f) for f in key_fields}
    return round(len(key_n & evidenced_n) / len(key_n), 3)

def _evidenced_fields(evidence: list[S.FieldEvidence]) -> set[str]:
    return {e.field for e in evidence if e.quote and e.quote.strip()}

def extract_metadata(text: str) -> Dict[str, Any]:
    m = aoai.extract(S.MetadataExtraction, _RULES, f"Contract text:\n{text}")
    evidenced = _evidenced_fields(m.evidence)
    conf = _coverage_confidence(evidenced, {"Title", "Counterparty", "ContractType", "TotalValue"})
    return {"attributes": {"Title": m.title, "Counterparty": m.counterparty, "ContractType": m.contract_type, "EffectiveDate": m.effective_date, "ExpirationDate": m.expiration_date, "AutoRenewal": m.auto_renewal, "TotalValue": m.total_value, "FundingSource": m.funding_source, "Status": m.status}, "evidence": [e.model_dump() for e in m.evidence], "confidence": conf}

def extract_clauses(text: str) -> Dict[str, Any]:
    c = aoai.extract(S.ClauseExtraction, _RULES, f"Identify standard clauses.\n\nContract text:\n{text}")
    return {"clauses": [ci.model_dump() for ci in c.clauses], "confidence": 1.0 if c.clauses else 0.0}

def map_subject_terms(text: str, clauses: Dict[str, Any], candidate_terms: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    candidates = candidate_terms or []
    cand_lines = "\n".join(f"- {t['TermID']}: {t.get('TermName','')} ({t.get('Domain','')}) - {t.get('Definition','')}; synonyms={', '.join(t.get('Synonyms', []))}" for t in candidates) or "(none supplied; you must abstain for every clause)"
    user = f"Candidate terms:\n{cand_lines}\n\nClauses:\n{clauses.get('clauses')}\n\nContext:\n{text}"
    res = aoai.map_terms(S.TaxonomyExtraction, _MAP_RULES, user)
    resolved, abstained = [], []
    for mp in res.mappings:
        if mp.term_id and not mp.ambiguous:
            resolved.append({"ClauseID": mp.clause_id, "TermID": mp.term_id, "RelevanceScore": mp.relevance, "ExtractionConfidence": mp.relevance, "Notes": f"{mp.sense_label}: {mp.discriminator}"})
        else:
            abstained.append({"ClauseID": mp.clause_id, "Reason": "ambiguous" if mp.ambiguous else "no candidate fit", "EvidenceSpan": mp.evidence_span})
    conf = round(min((r["RelevanceScore"] for r in resolved), default=0.0), 3)
    return {"mappings": resolved, "abstained": abstained, "confidence": conf}

def extract_amendment_metadata(text: str) -> Dict[str, Any]:
    a = aoai.extract(S.AmendmentExtraction, _RULES, f"Amendment text:\n{text}")
    evidenced = _evidenced_fields(a.evidence)
    conf = _coverage_confidence(evidenced, {"AmendmentType", "ValueChange"})
    return {"attributes": {"AmendmentType": a.amendment_type, "EffectiveDate": a.effective_date, "ExpirationDate": a.expiration_date, "ValueChange": a.value_change, "SummaryOfChanges": a.summary_of_changes}, "contract_changes": {fc.field: fc.new_value for fc in a.contract_changes}, "evidence": [e.model_dump() for e in a.evidence], "confidence": conf}

def detect_modified_clauses(text: str, original_clauses: Dict[str, Any]) -> Dict[str, Any]:
    user = f"Original clauses:\n{original_clauses.get('clauses')}\n\nAmendment text:\n{text}"
    res = aoai.judge(S.ModifiedClausesExtraction, _RULES, user)
    return {"modified": [{"ClauseID": mc.clause_id, "ChangeType": mc.change_type, "Note": mc.note, "EvidenceSpan": mc.evidence_span} for mc in res.modified], "confidence": 1.0 if res.modified else 0.0}

def judge_clause_pair(clause_a: str, clause_b: str) -> Dict[str, Any]:
    j = aoai.judge(S.ClauseDiffJudgment, _JUDGE_RULES, f"Clause A:\n{clause_a}\n\nClause B:\n{clause_b}")
    return j.model_dump()
