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
| `code/sharepoint_upload_session_patch.py` | Proposed patch for `sharepoint_io.py`: simple vs. resumable upload routing |
| `docs/LISTS_REFERENCE.md` | Column reference for the three SharePoint index lists |

## Incomplete files

This repository was reconstructed from a combined codebase document. The source
for the following files was truncated in transfer, so they are currently stubs
that should be replaced with a fresh export from the original repository:

`code/text_extract.py`, `code/process_contract.py`, `code/provision_lists.py`,
`code/sharepoint_io.py`, `code/process_amendment.py`, `code/ai_extract.py`,
`code/schema.py`, `tests/test_pipeline.py`

Note that `code/schema.py` (the storage models) is imported by several modules
and tests, so the test suite will not pass until it is restored.

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
