# CLM for SharePoint

[![CI](https://github.com/truonglybach/CLM-for-SharePoint/actions/workflows/ci.yml/badge.svg)](https://github.com/truonglybach/CLM-for-SharePoint/actions/workflows/ci.yml)

Contract Lifecycle Management (CLM) pipeline built on SharePoint and Microsoft Graph,
with AI-assisted metadata, clause, and amendment extraction via Azure OpenAI
Structured Outputs.

## Repository layout

```
src/clm/   the clm package (installable; see pyproject.toml)
tests/     pytest suite
docs/      reference documentation (SharePoint list/column reference)
```

## Modules

| File | Purpose |
| --- | --- |
| `src/clm/config.py` | Pydantic v2 settings loaded from environment / `.env` |
| `src/clm/auth.py` | App-only Microsoft Graph token acquisition (cert preferred, secret fallback) |
| `src/clm/ai_provider.py` | Backend selector: `USE_DUMMY_AI=true` → `ai_dummy`, otherwise `ai_extract` |
| `src/clm/ai_dummy.py` | Offline placeholder AI backend (no network calls) |
| `src/clm/ai_schemas.py` | Pydantic models for LLM structured outputs (attributes only, no identity fields) |
| `src/clm/azure_client.py` | Azure OpenAI Structured Outputs wrapper with 429/5xx retry |
| `src/clm/schema.py` | Storage models (contracts, amendments, clause/term maps, extraction runs) |
| `src/clm/sharepoint_io.py` | SharePoint / Microsoft Graph file and list I/O |
| `src/clm/ai_extract.py` | Real Azure OpenAI extraction backend |
| `src/clm/text_extract.py` | Document text extraction |
| `src/clm/process_contract.py` | Contract ingestion orchestrator (idempotent per contract) |
| `src/clm/process_amendment.py` | Amendment ingestion orchestrator |
| `src/clm/provision_lists.py` | Idempotent SharePoint list provisioning |
| `docs/LISTS_REFERENCE.md` | Column reference for the SharePoint lists |

## Provenance note

This repository was reconstructed from a combined codebase document. Eight
files whose source was truncated in transfer (`schema.py`, `sharepoint_io.py`,
`ai_extract.py`, `text_extract.py`, `process_contract.py`,
`process_amendment.py`, `provision_lists.py`, `tests/test_pipeline.py`) were
later supplied as best-effort reconstructions based on visible source snippets,
tests, and module docstrings — treat them as review-ready code, not a verified
byte-for-byte recovery of the originals.

## Setup

```bash
pip install -e ".[azure,dev]"        # add [ocr] for PDF/DOCX/image text extraction
```

Configuration is read from the environment or a `.env` file — see
`src/clm/config.py` for the full list (`TENANT_ID`, `CLIENT_ID`, `SITE_ID`,
`DRIVE_ID`, cert or client-secret credentials, and the Azure OpenAI settings).
Set `USE_DUMMY_AI=true` to run without any Azure OpenAI calls.

Console entry points are installed with the package:

```bash
clm-provision-lists
clm-process-contract --filename contract.pdf
clm-process-amendment --contract-id <uuid> --amendment-number 1 --filename amend.pdf
```

## Tests and linting

```bash
pytest
ruff check .
```

CI (GitHub Actions) runs both on every push to `main` and on every pull
request, against Python 3.11 and 3.12. `tests/conftest.py` makes `src/`
importable even without installing the package, injects dummy credentials, and
forces `USE_DUMMY_AI=true` so no network calls are made.
