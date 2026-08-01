"""End-to-end pipeline tests with SharePoint and text extraction stubbed."""
from __future__ import annotations
import json, sys, types
import pytest
@pytest.fixture
def store(monkeypatch):
    data = {}; sp = types.ModuleType("sharepoint_io")
    sp.ensure_contract_folder_structure = lambda cid: f"/Contracts/{cid}"; sp.contract_root = lambda cid: f"/Contracts/{cid}"; sp.download_file = lambda p: data.get(p, b"dummy"); sp.upload_json = lambda p, d: data.__setitem__(p, json.dumps(d, default=str).encode()) or {}; sp.upload_markdown = lambda p, t: data.__setitem__(p, t.encode()) or {}; sp.upsert_list_item = lambda ln, key, fields: data.setdefault("LIST:" + ln, []).append(fields) or {}; sp.ensure_folder = lambda p: {}
    monkeypatch.setitem(sys.modules, "sharepoint_io", sp); te = types.ModuleType("text_extract"); te.extract_text = lambda fn, raw, **k: "CONTRACT TEXT"; monkeypatch.setitem(sys.modules, "text_extract", te)
    for m in ("ai_provider", "process_contract", "process_amendment"): sys.modules.pop(m, None)
    return data
def test_toggle_selects_dummy_backend(store):
    import ai_provider; assert ai_provider.MODEL_VERSION == "dummy-v0"
def test_process_contract_writes_index_and_json(store):
    import process_contract as pc; cid = pc.process_contract("contract.pdf"); rows = store["LIST:Contract Index"]; assert len(rows) == 1; assert rows[0]["ContractID"] == cid; assert rows[0]["CurrentValue"] == 100000.0; assert rows[0]["ReviewStatus"] == "Pending"; assert any("contract_" in k for k in store); assert any("ai_run_" in k for k in store)
def test_process_amendment_rolls_value(store):
    import process_contract as pc; import process_amendment as pa; cid = pc.process_contract("contract.pdf"); pa.process_amendment(cid, 1, "amend.pdf"); assert store["LIST:Contract Index"][-1]["CurrentValue"] == 125000.0; assert len(store["LIST:Amendment Index"]) == 1; assert store["LIST:Amendment Index"][0]["ValueChange"] == 25000.0
def test_candidate_terms_loaded_and_forwarded_to_mapper(store, monkeypatch):
    sys.modules["sharepoint_io"].list_items = lambda ln: ([{"TermID": "PROGRAM_EXIT", "TermName": "Program Exit", "Domain": "HHS", "Definition": "", "Synonyms": "exit; discharge"}] if ln == "Subject Matter Terms" else [])
    import ai_provider; captured = {}; orig = ai_provider.map_subject_terms
    monkeypatch.setattr(ai_provider, "map_subject_terms", lambda text, clauses, candidate_terms=None: captured.__setitem__("terms", candidate_terms) or orig(text, clauses, candidate_terms))
    import process_contract as pc; pc.process_contract("contract.pdf")
    assert captured["terms"] == [{"TermID": "PROGRAM_EXIT", "TermName": "Program Exit", "Domain": "HHS", "Definition": "", "Synonyms": ["exit", "discharge"]}]
def test_metadata_diff_records_pre_amendment_values(store):
    import process_contract as pc; import process_amendment as pa; cid = pc.process_contract("contract.pdf"); pa.process_amendment(cid, 1, "amend.pdf")
    diff = json.loads(next(v for k, v in store.items() if "metadata_diff_" in k))
    assert diff["ExpirationDate"] == {"old": "2026-01-01", "new": "2027-01-01"}; assert diff["CurrentValue"] == {"old": 100000.0, "new": 125000.0}
def test_failed_run_writes_record_and_no_index_row(store, monkeypatch):
    import ai_provider; monkeypatch.setattr(ai_provider, "extract_metadata", lambda text: {"attributes": {"Title": ""}, "confidence": 0.9}); import process_contract as pc
    with pytest.raises(Exception): pc.process_contract("contract.pdf")
    assert "LIST:Contract Index" not in store; assert any("ai_run_" in k for k in store)
