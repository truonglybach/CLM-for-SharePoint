"""Phase-1 contract orchestrator."""
from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import ai_provider as ai
from . import sharepoint_io as sp
from .ai_provider import MODEL_VERSION
from .schema import AIExtractionRun, ClauseTermMap, Contract, ExtractionType
from .text_extract import extract_text

log = logging.getLogger(__name__)
CONFIDENCE_THRESHOLD = 0.85
CONTRACT_INDEX_LIST = "Contract Index"
CLAUSE_MAP_LIST = "Clause Map Index"
SUBJECT_TERMS_LIST = "Subject Matter Terms"
_MAP_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "clm-for-sharepoint/clause-term-map")
def _map_id(contract_id: str, clause_id: str, term_id: str) -> uuid.UUID:
    """Deterministic MapID so reprocessing a contract upserts the same rows instead of appending duplicates."""
    return uuid.uuid5(_MAP_NAMESPACE, f"{contract_id}|{clause_id}|{term_id}")
def _delete_stale_mappings(contract_id: str, keep_map_ids: set) -> None:
    """Remove Clause Map Index rows from earlier runs that this run no longer produced."""
    try:
        for item in sp.query_list_items(CLAUSE_MAP_LIST, "ContractID", contract_id):
            if item.get("fields", {}).get("MapID") not in keep_map_ids:
                sp.delete_list_item(CLAUSE_MAP_LIST, item["id"])
    except Exception as exc:
        log.warning("Stale-mapping cleanup failed for %s (rows from prior runs may linger): %s", contract_id, exc)
def _load_candidate_terms() -> List[Dict[str, Any]]:
    """Load the taxonomy the mapper grounds against; without it the real backend abstains on every clause."""
    try:
        items = sp.list_items(SUBJECT_TERMS_LIST)
    except Exception as exc:
        log.warning("Could not load candidate terms from %s: %s", SUBJECT_TERMS_LIST, exc); return []
    terms: List[Dict[str, Any]] = []
    for fields in items:
        if not fields.get("TermID"): continue
        syn = fields.get("Synonyms") or []
        if isinstance(syn, str): syn = [s.strip() for s in syn.split(";") if s.strip()]
        terms.append({"TermID": fields["TermID"], "TermName": fields.get("TermName", ""), "Domain": fields.get("Domain", ""), "Definition": fields.get("Definition", ""), "Synonyms": syn})
    return terms
def process_contract(filename: str, contract_id: Optional[str] = None) -> str:
    contract_id = contract_id or str(uuid.uuid4()); run_id = uuid.uuid4(); root = sp.ensure_contract_folder_structure(contract_id); out = f"{root}/04_AI_Outputs"; confidences: Dict[str, float] = {}
    try:
        raw = sp.download_file(f"{root}/01_Original/{filename}"); text = extract_text(filename, raw)
        metadata = ai.extract_metadata(text); clauses = ai.extract_clauses(text); mappings = ai.map_subject_terms(text, clauses, _load_candidate_terms())
        confidences = {"Metadata": float(metadata.get("confidence", 0.0)), "Clauses": float(clauses.get("confidence", 0.0)), "Taxonomy": float(mappings.get("confidence", 0.0))}
        priority_review = any(v < CONFIDENCE_THRESHOLD for v in confidences.values())
        contract = Contract(ContractID=contract_id, PrimaryDocumentURL=f"{root}/01_Original/{filename}", ParentFolderURL=root, **metadata["attributes"])
        sp.upload_json(f"{out}/Metadata/contract_{contract_id}.json", contract.model_dump(by_alias=True))
        sp.upload_json(f"{out}/Metadata/metadata_evidence_{run_id}.json", {"ContractID": contract_id, "RunID": str(run_id), "Evidence": metadata.get("evidence", [])})
        sp.upload_json(f"{out}/ClauseExtraction/clauses_{contract_id}.json", clauses); sp.upload_json(f"{out}/ClauseExtraction/taxonomy_mappings_{contract_id}.json", mappings)
        row = contract.index_row(); row["PriorityReview"] = priority_review; sp.upsert_list_item(CONTRACT_INDEX_LIST, "ContractID", row)
        current_map_ids = set()
        for m in mappings.get("mappings", []):
            cm = ClauseTermMap(MapID=_map_id(contract_id, m["ClauseID"], m["TermID"]), ContractID=contract.contract_id, ClauseID=m["ClauseID"], TermID=m["TermID"], RelevanceScore=m["RelevanceScore"], ExtractionConfidence=m["ExtractionConfidence"], Notes=m.get("Notes", ""))
            current_map_ids.add(str(cm.map_id)); sp.upsert_list_item(CLAUSE_MAP_LIST, "MapID", cm.index_row(priority_review=cm.extraction_confidence < CONFIDENCE_THRESHOLD))
        _delete_stale_mappings(contract_id, current_map_ids)
        _write_run(out, run_id, contract_id, [ExtractionType.METADATA, ExtractionType.CLAUSES, ExtractionType.TAXONOMY], confidences, True); return contract_id
    except Exception as exc:
        log.exception("Contract processing failed for %s", contract_id)
        _write_run(out, run_id, contract_id, [ExtractionType.METADATA, ExtractionType.CLAUSES, ExtractionType.TAXONOMY], confidences, False, str(exc)); raise
def _write_run(out_base: str, run_id: uuid.UUID, contract_id: str, types: List[ExtractionType], confidences: Dict[str, float], succeeded: bool, error: Optional[str] = None) -> None:
    run = AIExtractionRun(RunID=run_id, ContractID=contract_id, Timestamp=datetime.now(timezone.utc), ModelVersion=MODEL_VERSION, ExtractionTypes=types, ConfidenceScores=confidences, Succeeded=succeeded)
    payload = run.model_dump(by_alias=True)
    if error: payload["Error"] = error
    sp.upload_json(f"{out_base}/Metadata/ai_run_{run_id}.json", payload)
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"); ap = argparse.ArgumentParser(description="Process one contract through the CLM pipeline."); ap.add_argument("--filename", required=True); ap.add_argument("--contract-id", default=None); args = ap.parse_args()
    try: process_contract(args.filename, args.contract_id)
    except Exception: sys.exit(1)
if __name__ == "__main__": main()
