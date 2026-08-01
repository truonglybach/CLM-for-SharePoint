# CLM for SharePoint

Contract Lifecycle Management (CLM) pipeline built on SharePoint and Microsoft Graph,
with AI-assisted metadata, clause, and amendment extraction via Azure OpenAI
Structured Outputs.

## Repository layout

```
code/    application source (importable modules; tests add this to sys.path)
tests/   pytest suite
docs/    reference documentation (SharePoint list/column reference)
```

## Modules

| File | Purpose |
| --- | --- |
| `code/config.py` | Pydantic v2 settings loaded from environment / `.env` |
| `code/auth.py` | App-only Microsoft Graph token acquisition (cert preferred, secret fallback) |
| `code/ai_provider.py` | Backend selector: `USE_DUMMY_AI=true` → `ai_dummy`, otherwise `ai_extract` |
| `code/ai_dummy.py` | Offline placeholder AI backend (no network calls) |
| `code/ai_schemas.py` | Pydantic models for LLM structured outputs (attributes only, no identity fields) |
| `code/azure_client.py` | Thin wrapper around Azure OpenAI Structured Outputs |
| `code/schema.py` | Storage models (contracts, amendments, clause/term maps, extraction runs) |
| `code/sharepoint_io.py` | SharePoint / Microsoft Graph file and list I/O |
| `code/ai_extract.py` | Real Azure OpenAI extraction backend |
| `code/text_extract.py` | Document text extraction |
| `code/process_contract.py` | Contract ingestion orchestrator |
| `code/process_amendment.py` | Amendment ingestion orchestrator |
| `code/provision_lists.py` | Idempotent SharePoint list provisioning |
| `docs/LISTS_REFERENCE.md` | Column reference for the three SharePoint index lists |

## Provenance note

This repository was reconstructed from a combined codebase document. Eight
files whose source was truncated in transfer (`code/schema.py`,
`code/sharepoint_io.py`, `code/ai_extract.py`, `code/text_extract.py`,
`code/process_contract.py`, `code/process_amendment.py`,
`code/provision_lists.py`, `tests/test_pipeline.py`) were later supplied as
best-effort reconstructions based on visible source snippets, tests, and module
docstrings — treat them as review-ready code, not a verified byte-for-byte
recovery of the originals.

## Setup

```bash
pip install -r requirements.txt
```

Configuration is read from the environment or a `.env` file — see
`code/config.py` for the full list (`TENANT_ID`, `CLIENT_ID`, `SITE_ID`,
`DRIVE_ID`, cert or client-secret credentials, and the Azure OpenAI settings).
Set `USE_DUMMY_AI=true` to run without any Azure OpenAI calls.

## Tests

```bash
pytest tests/
```

`tests/conftest.py` puts `code/` on `sys.path`, injects dummy credentials, and
forces `USE_DUMMY_AI=true` so no network calls are made.
