"""Phase-1 amendment orchestrator."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from . import ai_provider as ai
from . import sharepoint_io as sp
from .ai_provider import MODEL_VERSION
from .schema import AIExtractionRun, Amendment, Contract, ExtractionType
from .text_extract import extract_text

log = logging.getLogger(__name__)
CONFIDENCE_THRESHOLD = 0.85
CONTRACT_INDEX_LIST = "Contract Index"
AMENDMENT_INDEX_LIST = "Amendment Index"
_DERIVED_CONTRACT_KEYS = ("CurrentValue",)
def _load_contract(contract_id: str) -> Contract:
    root = sp.contract_root(contract_id); raw = sp.download_file(f"{root}/04_AI_Outputs/Metadata/contract_{contract_id}.json"); data = json.loads(raw)
    for k in _DERIVED_CONTRACT_KEYS: data.pop(k, None)
    return Contract.model_validate(data)
def _load_clause_set(contract_id: str) -> Dict[str, Any]:
    root = sp.contract_root(contract_id); path = f"{root}/04_AI_Outputs/ClauseExtraction/clauses_{contract_id}.json"
    try: return json.loads(sp.download_file(path))
    except Exception as exc: log.warning("Could not load original clause set for %s from %s: %s", contract_id, path, exc); return {"clauses": []}
def process_amendment(contract_id: str, amendment_number: int, filename: str) -> str:
    amendment_id = uuid.uuid4(); run_id = uuid.uuid4(); root = sp.contract_root(contract_id); amd_folder = f"{root}/02_Amendments/Amendment_{amendment_number:02d}"; sp.ensure_folder(amd_folder); out = f"{root}/04_AI_Outputs"; confidences: Dict[str, float] = {}
    try:
        contract = _load_contract(contract_id); original_clauses = _load_clause_set(contract_id); raw = sp.download_file(f"{amd_folder}/{filename}"); text = extract_text(filename, raw)
        metadata = ai.extract_amendment_metadata(text); modified = ai.detect_modified_clauses(text, original_clauses); confidences = {"Amendment": float(metadata.get("confidence", 0.0)), "Diff": float(modified.get("confidence", 0.0))}
        amendment = Amendment(AmendmentID=amendment_id, ContractID=contract.contract_id, AmendmentNumber=amendment_number, AmendmentDocumentURL=f"{amd_folder}/{filename}", ParentFolderURL=amd_folder, **metadata["attributes"])
        contract_changes = metadata.get("contract_changes", {})
        # Snapshot values before mutation so the diff records true pre-amendment state.
        before_value = contract.current_value; old_values = _snapshot_old_values(contract, contract_changes); contract.amendments.append(amendment)
        for alias, new_val in contract_changes.items(): _apply_contract_change(contract, alias, new_val)
        diff = _build_metadata_diff(contract, contract_changes, before_value, old_values)
        sp.upload_json(f"{out}/Metadata/amendment_{amendment_id}.json", amendment.model_dump(by_alias=True)); sp.upload_json(f"{out}/Metadata/contract_{contract_id}.json", contract.model_dump(by_alias=True)); sp.upload_json(f"{out}/Metadata/metadata_diff_{amendment_id}.json", diff); sp.upload_json(f"{out}/ClauseExtraction/modified_clauses_{amendment_id}.json", modified)
        sp.upsert_list_item(AMENDMENT_INDEX_LIST, "AmendmentID", amendment.index_row()); c_row = contract.index_row(); c_row["PriorityReview"] = any(v < CONFIDENCE_THRESHOLD for v in confidences.values()); sp.upsert_list_item(CONTRACT_INDEX_LIST, "ContractID", c_row)
        _write_run(out, run_id, contract_id, [ExtractionType.AMENDMENT, ExtractionType.DIFF], confidences, True); return str(amendment_id)
    except Exception as exc: log.exception("Amendment processing failed for contract %s amendment %s", contract_id, amendment_number); _write_run(out, run_id, contract_id, [ExtractionType.AMENDMENT, ExtractionType.DIFF], confidences, False, str(exc)); raise
_ALIAS_TO_ATTR = {"ExpirationDate": "expiration_date", "Status": "status", "EffectiveDate": "effective_date", "AutoRenewal": "auto_renewal"}
def _apply_contract_change(contract: Contract, field_alias: str, new_val: Any) -> None:
    attr = _ALIAS_TO_ATTR.get(field_alias)
    if attr: setattr(contract, attr, new_val)
def _snapshot_old_values(contract: Contract, contract_changes: Dict[str, Any]) -> Dict[str, Any]:
    return {alias: getattr(contract, _ALIAS_TO_ATTR[alias]) if alias in _ALIAS_TO_ATTR else None for alias in contract_changes}
def _build_metadata_diff(contract: Contract, contract_changes: Dict[str, Any], before_value: float, old_values: Dict[str, Any]) -> Dict[str, Any]:
    diff = {"CurrentValue": {"old": before_value, "new": contract.current_value}}
    for alias, new_val in contract_changes.items():
        old_val = old_values.get(alias); old_str = old_val.isoformat() if hasattr(old_val, "isoformat") else old_val; diff[alias] = {"old": old_str, "new": new_val}
    return diff
def _write_run(out_base: str, run_id: uuid.UUID, contract_id: str, types: list, confidences: dict, succeeded: bool, error: Optional[str] = None) -> None:
    run = AIExtractionRun(RunID=run_id, ContractID=contract_id, Timestamp=datetime.now(timezone.utc), ModelVersion=MODEL_VERSION, ExtractionTypes=types, ConfidenceScores=confidences, Succeeded=succeeded); payload = run.model_dump(by_alias=True)
    if error: payload["Error"] = error
    sp.upload_json(f"{out_base}/Metadata/ai_run_{run_id}.json", payload)
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"); ap = argparse.ArgumentParser(description="Process one amendment through the CLM pipeline."); ap.add_argument("--contract-id", required=True); ap.add_argument("--amendment-number", required=True, type=int); ap.add_argument("--filename", required=True); args = ap.parse_args()
    try: process_amendment(args.contract_id, args.amendment_number, args.filename)
    except Exception: sys.exit(1)
if __name__ == "__main__": main()
