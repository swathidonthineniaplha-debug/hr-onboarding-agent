# HR Onboarding Agent

An Azure Function that uses an LLM to classify uploaded onboarding documents and route them:

- **Passports and driving licences**: filed in Blob Storage, one folder per person
- **Employee documents**: fields extracted into one Azure SQL table (`EmployeeData`)
- **Report**: an Excel summary of every processed document

> All data in this repository is fictional.

## Architecture

_TBD: diagram and design decisions (trigger, LLM abstraction, routing, idempotency, security)._

```
Blob upload ─► Azure Function ─► LLM classify ─┬─► identity doc ─► Blob: <person>/...
                                               └─► employee doc ─► LLM extract ─► Azure SQL
                                                                      └─► Excel report
```

## Project structure

```
function_app.py          Azure Functions entry point
src/hr_onboarding/       Core logic (no Azure Functions dependency)
  config.py              Settings from environment variables
  pipeline.py            read -> classify -> person key -> extract -> validate
  documents.py           .txt / .pdf to text
  prompts.py             System prompts for each LLM task
  person_key.py          Full name -> blob-safe key ("alex-example")
  llm/                   Provider interface + mock / Azure OpenAI / Anthropic,
                         plus the shared JSON-validate-retry helper
  classification/        Passport / DrivingLicence / EmployeeDocument / Other
  extraction/            Employee field extraction + validation rules
  routing/               Blob folder routing for identity documents
  storage/               Blob and SQL adapters
  reporting/             Excel report
sql/schema.sql           EmployeeData table
sample_documents/        Fictional test documents (see its README)
scripts/                 Helper scripts (e.g. regenerate sample PDFs)
tests/                   pytest suite
```

## Setup

Requires **Python 3.13**, the version this project targets on the Azure Functions Flex Consumption plan.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
Copy-Item local.settings.example.json local.settings.json
pytest
```

## Configuration

All settings come from environment variables. See [.env.example](.env.example) for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `mock` | `mock`, `azure_openai` or `anthropic` |
| `AZURE_OPENAI_ENDPOINT` / `_API_KEY` / `_DEPLOYMENT` / `_API_VERSION` | _(none)_ / _(none)_ / _(none)_ / `2024-10-21` | Azure OpenAI / Microsoft Foundry connection |
| `AZURE_OPENAI_TEMPERATURE` | _(not sent)_ | Optional; leave unset for reasoning models |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | _(none)_ / `claude-opus-5-5` | Anthropic connection |
| `STORAGE_CONNECTION_STRING` | Azurite | Blob Storage connection |
| `BLOB_INPUT_CONTAINER` | `onboarding-uploads` | Upload container watched by the function |
| `BLOB_IDENTITY_CONTAINER` | `identity-documents` | Per-person passport/licence folders |
| `SQL_CONNECTION_STRING` | _(none)_ | Azure SQL connection |
| `OUTPUT_DIR` | `output` | Excel report location |

## Running locally

Run the core pipeline over the sample documents (no Azure needed):

```powershell
python run_local.py
```

_TBD: Azurite + `func start` for the full Azure Function._

## Mock vs real LLM

`LLM_PROVIDER=mock` (the default, and what the tests use) swaps the LLM for keyword and regex rules. It needs no API key, costs nothing and gives the same result every time.

- **Structured forms work well with rules.** Labelled fields such as `Date of birth: 12 April 1990` or `Company: Example Widgets Ltd` are easy to match. The mock extracts Alex's new-starter form completely.
- **Prose needs the LLM.** Jordan's HR letter describes previous jobs in full sentences ("Jordan's career began at Mock Retail Group, where they worked as..."). The mock picks out the name, the date of birth written in words and "aged 41", but returns an **empty employment history**. A real model reads the sentences and returns both jobs.

Both modes share the same prompts, Pydantic validation, retry and business rules. Only the provider changes, so switching to `azure_openai` or `anthropic` is a configuration change, not a code change.

## Deployment

_TBD: Flex Consumption, managed identity, Key Vault._

## Roadmap

- [x] Project scaffold and configuration
- [x] LLM provider abstraction
- [x] Classification, person key, extraction and validation
- [ ] Blob routing
- [ ] Azure SQL persistence
- [ ] Excel report
- [ ] Azure Function trigger and deployment
