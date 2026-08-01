"""Unit tests for the real backend's post-processing, with the Azure calls stubbed."""
from __future__ import annotations

from clm import ai_extract
from clm import ai_schemas as S
from clm import azure_client as aoai


def test_no_modified_clauses_is_confident_not_zero(monkeypatch):
    # A clean amendment must not be scored 0.0 (which forced priority review).
    monkeypatch.setattr(aoai, "judge", lambda model, system, user: S.ModifiedClausesExtraction(modified=[]))
    res = ai_extract.detect_modified_clauses("text", {"clauses": []})
    assert res["modified"] == []
    assert res["confidence"] == 1.0

def test_ambiguous_mappings_are_abstained_not_resolved(monkeypatch):
    mapping = S.TermMapping(clause_id="TERM", term_id=None, sense_label="", discriminator="",
                            evidence_span="", relevance=0.4, ambiguous=True)
    monkeypatch.setattr(aoai, "map_terms", lambda model, system, user: S.TaxonomyExtraction(mappings=[mapping]))
    res = ai_extract.map_subject_terms("text", {"clauses": []}, [])
    assert res["mappings"] == []
    assert res["abstained"][0]["ClauseID"] == "TERM"
