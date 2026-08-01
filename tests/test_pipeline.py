"""End-to-end pipeline tests with SharePoint and text extraction stubbed."""
from __future__ import annotations

import itertools
import json

import pytest

from clm import ai_provider
from clm import process_amendment as pa
from clm import process_contract as pc
from clm import sharepoint_io as sp


@pytest.fixture
def store(monkeypatch):
    """In-memory stand-in for SharePoint: files keyed by path, list rows under LIST:<name>."""
    data = {}
    item_ids = itertools.count()
    def upsert(ln, key, fields):
        rows = data.setdefault("LIST:" + ln, [])
        for r in rows:
            if r.get(key) == fields[key]: r.update(fields); return {}
        rows.append({**fields, "_item_id": str(next(item_ids))}); return {}
    def query(ln, field, value):
        return [{"id": r["_item_id"], "fields": r} for r in data.get("LIST:" + ln, []) if str(r.get(field)) == str(value)]
    def delete(ln, item_id):
        data["LIST:" + ln] = [r for r in data.get("LIST:" + ln, []) if r["_item_id"] != item_id]
    monkeypatch.setattr(sp, "ensure_contract_folder_structure", lambda cid: f"/Contracts/{cid}")
    monkeypatch.setattr(sp, "contract_root", lambda cid: f"/Contracts/{cid}")
    monkeypatch.setattr(sp, "download_file", lambda p: data.get(p, b"dummy"))
    monkeypatch.setattr(sp, "upload_json", lambda p, d: data.__setitem__(p, json.dumps(d, default=str).encode()) or {})
    monkeypatch.setattr(sp, "upload_markdown", lambda p, t: data.__setitem__(p, t.encode()) or {})
    monkeypatch.setattr(sp, "upsert_list_item", upsert)
    monkeypatch.setattr(sp, "query_list_items", query)
    monkeypatch.setattr(sp, "delete_list_item", delete)
    monkeypatch.setattr(sp, "ensure_folder", lambda p: {})
    monkeypatch.setattr(sp, "list_items", lambda ln: [])
    monkeypatch.setattr(pc, "extract_text", lambda fn, raw, **k: "CONTRACT TEXT")
    monkeypatch.setattr(pa, "extract_text", lambda fn, raw, **k: "CONTRACT TEXT")
    return data

def test_toggle_selects_dummy_backend(store):
    assert ai_provider.MODEL_VERSION == "dummy-v0"

def test_process_contract_writes_index_and_json(store):
    cid = pc.process_contract("contract.pdf"); rows = store["LIST:Contract Index"]
    assert len(rows) == 1; assert rows[0]["ContractID"] == cid; assert rows[0]["CurrentValue"] == 100000.0; assert rows[0]["ReviewStatus"] == "Pending"
    assert any("contract_" in k for k in store); assert any("ai_run_" in k for k in store)

def test_process_amendment_rolls_value(store):
    cid = pc.process_contract("contract.pdf"); pa.process_amendment(cid, 1, "amend.pdf")
    assert store["LIST:Contract Index"][-1]["CurrentValue"] == 125000.0
    assert len(store["LIST:Amendment Index"]) == 1; assert store["LIST:Amendment Index"][0]["ValueChange"] == 25000.0

def test_reprocessing_same_contract_is_idempotent(store):
    cid = pc.process_contract("contract.pdf"); pc.process_contract("contract.pdf", cid)
    assert len(store["LIST:Contract Index"]) == 1
    assert len(store["LIST:Clause Map Index"]) == 1  # deterministic MapID upserts in place

def test_stale_mappings_deleted_on_reprocess(store, monkeypatch):
    cid = pc.process_contract("contract.pdf")
    monkeypatch.setattr(ai_provider, "map_subject_terms", lambda text, clauses, candidate_terms=None: {
        "mappings": [{"ClauseID": "SOW", "TermID": "NEW_TERM", "RelevanceScore": 0.9, "ExtractionConfidence": 0.9, "Notes": ""}], "confidence": 0.9})
    pc.process_contract("contract.pdf", cid)
    rows = store["LIST:Clause Map Index"]
    assert len(rows) == 1; assert rows[0]["TermID"] == "NEW_TERM"

def test_candidate_terms_loaded_and_forwarded_to_mapper(store, monkeypatch):
    monkeypatch.setattr(sp, "list_items", lambda ln: ([{"TermID": "PROGRAM_EXIT", "TermName": "Program Exit", "Domain": "HHS", "Definition": "", "Synonyms": "exit; discharge"}] if ln == "Subject Matter Terms" else []))
    captured = {}; orig = ai_provider.map_subject_terms
    monkeypatch.setattr(ai_provider, "map_subject_terms", lambda text, clauses, candidate_terms=None: captured.__setitem__("terms", candidate_terms) or orig(text, clauses, candidate_terms))
    pc.process_contract("contract.pdf")
    assert captured["terms"] == [{"TermID": "PROGRAM_EXIT", "TermName": "Program Exit", "Domain": "HHS", "Definition": "", "Synonyms": ["exit", "discharge"]}]

def test_metadata_diff_records_pre_amendment_values(store):
    cid = pc.process_contract("contract.pdf"); pa.process_amendment(cid, 1, "amend.pdf")
    diff = json.loads(next(v for k, v in store.items() if "metadata_diff_" in k))
    assert diff["ExpirationDate"] == {"old": "2026-01-01", "new": "2027-01-01"}; assert diff["CurrentValue"] == {"old": 100000.0, "new": 125000.0}

def test_amendment_archives_pre_amendment_contract(store):
    cid = pc.process_contract("contract.pdf"); pa.process_amendment(cid, 1, "amend.pdf")
    archived = json.loads(next(v for k, v in store.items() if "/History/contract_" in k))
    assert archived["ExpirationDate"] == "2026-01-01"; assert archived["CurrentValue"] == 100000.0  # state before the amendment
    current = json.loads(store[f"/Contracts/{cid}/04_AI_Outputs/Metadata/contract_{cid}.json"])
    assert current["ExpirationDate"] == "2027-01-01"; assert current["CurrentValue"] == 125000.0

def test_failed_run_writes_record_and_no_index_row(store, monkeypatch):
    monkeypatch.setattr(ai_provider, "extract_metadata", lambda text: {"attributes": {"Title": ""}, "confidence": 0.9})
    with pytest.raises(Exception): pc.process_contract("contract.pdf")
    assert "LIST:Contract Index" not in store; assert any("ai_run_" in k for k in store)

def test_failure_record_write_error_does_not_mask_original(store, monkeypatch):
    # SharePoint being down must not turn a validation failure into a confusing upload error.
    monkeypatch.setattr(ai_provider, "extract_metadata", lambda text: {"attributes": {"Title": ""}, "confidence": 0.9})
    monkeypatch.setattr(sp, "upload_json", lambda p, d: (_ for _ in ()).throw(RuntimeError("SharePoint unavailable")))
    with pytest.raises(Exception) as excinfo: pc.process_contract("contract.pdf")
    assert "SharePoint unavailable" not in str(excinfo.value)
