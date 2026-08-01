"""Creates SharePoint Lists that form the CLM query layer."""
from __future__ import annotations
from typing import Any, Dict, List
import requests
from auth import get_access_token
from config import settings
GRAPH = "https://graph.microsoft.com/v1.0"
SITE = f"{GRAPH}/sites/{settings.site_id}"
REVIEW_CHOICES = ["Pending", "Reviewed", "Approved"]
def text(name: str) -> Dict[str, Any]: return {"name": name, "text": {}}
def number(name: str, decimals: int = 2) -> Dict[str, Any]: return {"name": name, "number": {"decimalPlaces": str(decimals)}}
def boolean(name: str) -> Dict[str, Any]: return {"name": name, "boolean": {}}
def datetime_col(name: str) -> Dict[str, Any]: return {"name": name, "dateTime": {"format": "dateOnly"}}
def choice(name: str, choices: List[str]) -> Dict[str, Any]: return {"name": name, "choice": {"choices": choices, "displayAs": "dropDownMenu"}}
LISTS = {
    "Contract Index": [text("ContractID"), text("Title"), text("Counterparty"), choice("ContractType", ["Grant", "Vendor", "Subrecipient", "MOU", "Lease", "Other"]), choice("Status", ["Draft", "Active", "Expired", "Terminated"]), datetime_col("EffectiveDate"), datetime_col("ExpirationDate"), number("CurrentValue"), choice("FundingSource", ["Federal", "State", "Local", "Private"]), choice("ReviewStatus", REVIEW_CHOICES), boolean("PriorityReview")],
    "Amendment Index": [text("AmendmentID"), text("ContractID"), number("AmendmentNumber", 0), choice("AmendmentType", ["Extension", "Budget Revision", "Scope Change", "Legal Correction", "Other"]), datetime_col("EffectiveDate"), number("ValueChange"), choice("ReviewStatus", REVIEW_CHOICES)],
    "Clause Map Index": [text("MapID"), text("ContractID"), text("ClauseID"), text("TermID"), number("RelevanceScore"), number("ExtractionConfidence"), choice("ReviewStatus", REVIEW_CHOICES), boolean("PriorityReview")],
    "Subject Matter Terms": [text("TermID"), text("Domain"), text("TermName"), text("Definition"), text("Synonyms"), text("RegulatorySource")],
}
def _headers() -> Dict[str, str]: return {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
def _existing_lists() -> Dict[str, str]:
    r = requests.get(f"{SITE}/lists?$select=id,displayName", headers=_headers(), timeout=60); r.raise_for_status(); return {x["displayName"]: x["id"] for x in r.json().get("value", [])}
def _existing_columns(list_id: str) -> set[str]:
    r = requests.get(f"{SITE}/lists/{list_id}/columns?$select=name", headers=_headers(), timeout=60); r.raise_for_status(); return {c["name"] for c in r.json().get("value", [])}
def _add_column(list_id: str, col_def: Dict[str, Any]) -> None:
    r = requests.post(f"{SITE}/lists/{list_id}/columns", headers=_headers(), json=col_def, timeout=60); r.raise_for_status(); print(f"  + column added: {col_def['name']}")
def ensure_list(display_name: str, columns: List[Dict[str, Any]]) -> None:
    existing = _existing_lists()
    if display_name in existing:
        list_id = existing[display_name]; print(f"= list exists: {display_name}")
    else:
        r = requests.post(f"{SITE}/lists", headers=_headers(), json={"displayName": display_name, "list": {"template": "genericList"}}, timeout=60); r.raise_for_status(); list_id = r.json()["id"]; print(f"+ created list: {display_name}")
    existing_cols = _existing_columns(list_id)
    for col in columns:
        if col["name"] in existing_cols: print(f"  = column exists: {col['name']}"); continue
        _add_column(list_id, col)
def main() -> None:
    for name, cols in LISTS.items(): ensure_list(name, cols)
    print("Done. Lists are ready for the orchestrator to upsert into.")
if __name__ == "__main__": main()
