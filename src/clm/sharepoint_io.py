"""SharePoint/Graph I/O for the CLM pipeline."""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from .auth import get_access_token
from .config import settings

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_DRIVE = f"{GRAPH_BASE}/sites/{settings.site_id}/drives/{settings.drive_id}"
_SITE = f"{GRAPH_BASE}/sites/{settings.site_id}"
CONTRACTS_ROOT = "Contracts"
SUBFOLDERS = ["01_Original", "02_Amendments", "03_SupportingDocs", "04_AI_Outputs", "04_AI_Outputs/Metadata", "04_AI_Outputs/ClauseExtraction", "04_AI_Outputs/Summaries", "04_AI_Outputs/Visualizations"]
_MAX_RETRIES = 5
SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024
CHUNK_SIZE = 5 * 1024 * 1024

def _auth_header(content_type: Optional[str] = "application/json") -> Dict[str, str]:
    h = {"Authorization": f"Bearer {get_access_token()}"}
    if content_type:
        h["Content-Type"] = content_type
    return h

def _request(method: str, url: str, **kwargs: Any) -> requests.Response:
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.request(method, url, timeout=60, **kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            if attempt == _MAX_RETRIES - 1:
                raise
            time.sleep(min(2 ** attempt, 30)); continue
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            if attempt == _MAX_RETRIES - 1:
                resp.raise_for_status()
            retry_after = resp.headers.get("Retry-After")
            time.sleep(float(retry_after) if retry_after else min(2 ** attempt, 30)); continue
        return resp
    if last_exc: raise last_exc
    raise RuntimeError("Graph request failed without returning a response.")

def _clean(path: str) -> str: return path.strip("/")
def contract_root(contract_id: str) -> str: return f"/{CONTRACTS_ROOT}/{contract_id}"
def _item_url(path: str) -> str:
    encoded = "/".join(quote(part) for part in _clean(path).split("/"))
    return f"{_DRIVE}/root:/{encoded}"
def folder_exists(path: str) -> bool: return _request("GET", _item_url(path), headers=_auth_header()).status_code == 200

def ensure_folder(path: str) -> Dict[str, Any]:
    clean = _clean(path)
    if not clean: return {}
    r = _request("GET", _item_url(clean), headers=_auth_header())
    if r.status_code == 200: return r.json()
    if r.status_code not in (404, 400): r.raise_for_status()
    parent, _, name = clean.rpartition("/")
    if parent:
        ensure_folder(parent); children_url = f"{_item_url(parent)}:/children"
    else:
        children_url = f"{_DRIVE}/root/children"
    body = {"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "replace"}
    created = _request("POST", children_url, headers=_auth_header(), json=body); created.raise_for_status(); return created.json()

def ensure_contract_folder_structure(contract_id: str) -> str:
    ensure_folder(CONTRACTS_ROOT); root = contract_root(contract_id); ensure_folder(root)
    for sf in SUBFOLDERS: ensure_folder(f"{root}/{sf}")
    return root

def download_file(sp_path: str) -> bytes:
    r = _request("GET", f"{_item_url(sp_path)}:/content", headers=_auth_header(None)); r.raise_for_status(); return r.content

def upload_file(sp_path: str, content: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
    return _simple_upload(sp_path, content, content_type) if len(content) < SIMPLE_UPLOAD_LIMIT else _resumable_upload(sp_path, content, content_type)

def _simple_upload(sp_path: str, content: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
    headers = _auth_header(None); headers["Content-Type"] = content_type
    r = _request("PUT", f"{_item_url(sp_path)}:/content", headers=headers, data=content); r.raise_for_status(); return r.json()

def _resumable_upload(sp_path: str, content: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
    r = _request("POST", f"{_item_url(sp_path)}:/createUploadSession", headers=_auth_header(), json={"item": {"@microsoft.graph.conflictBehavior": "replace"}}); r.raise_for_status()
    upload_url = r.json()["uploadUrl"]; total = len(content); offset = 0; final_response = None
    while offset < total:
        chunk = content[offset: offset + CHUNK_SIZE]; start = offset; end = offset + len(chunk) - 1
        headers = {"Content-Length": str(len(chunk)), "Content-Range": f"bytes {start}-{end}/{total}", "Content-Type": content_type}
        final_response = _request("PUT", upload_url, headers=headers, data=chunk); final_response.raise_for_status(); offset += len(chunk)
    if final_response is None: raise RuntimeError("No content was uploaded.")
    return final_response.json()

def upload_json(sp_path: str, data: Dict[str, Any]) -> Dict[str, Any]: return upload_file(sp_path, json.dumps(data, indent=2, default=str).encode("utf-8"), "application/json")
def upload_markdown(sp_path: str, text: str) -> Dict[str, Any]: return upload_file(sp_path, text.encode("utf-8"), "text/markdown")
def _list_items_url(list_name: str) -> str: return f"{_SITE}/lists/{quote(list_name)}/items"
def list_items(list_name: str) -> List[Dict[str, Any]]:
    url: Optional[str] = f"{_list_items_url(list_name)}?$expand=fields"
    items: List[Dict[str, Any]] = []
    while url:
        r = _request("GET", url, headers=_auth_header()); r.raise_for_status(); payload = r.json()
        items.extend(x.get("fields", {}) for x in payload.get("value", []))
        url = payload.get("@odata.nextLink")
    return items
def query_list_items(list_name: str, field: str, value: Any) -> List[Dict[str, Any]]:
    "All items whose fields/<field> equals value; each item carries its Graph id and expanded fields."
    escaped = str(value).replace("'", "''")
    url: Optional[str] = f"{_list_items_url(list_name)}?$expand=fields&$filter=fields/{field} eq '{escaped}'"
    headers = _auth_header(); headers["Prefer"] = "HonorNonIndexedQueriesWarningMayFailRandomly"
    items: List[Dict[str, Any]] = []
    while url:
        r = _request("GET", url, headers=headers); r.raise_for_status(); payload = r.json()
        items.extend(payload.get("value", [])); url = payload.get("@odata.nextLink")
    return items
def delete_list_item(list_name: str, item_id: str) -> None:
    r = _request("DELETE", f"{_list_items_url(list_name)}/{item_id}", headers=_auth_header(None)); r.raise_for_status()
def upsert_list_item(list_name: str, key_field: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    matches = query_list_items(list_name, key_field, fields[key_field])
    if matches:
        item_id = matches[0]["id"]
        r = _request("PATCH", f"{_list_items_url(list_name)}/{item_id}/fields", headers=_auth_header(), json=fields); r.raise_for_status(); return r.json() if r.content else {}
    r = _request("POST", _list_items_url(list_name), headers=_auth_header(), json={"fields": fields}); r.raise_for_status(); return r.json()
