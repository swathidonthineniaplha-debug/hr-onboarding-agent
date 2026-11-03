# HR Onboarding Agent

<!-- Replace <org>, <project> and <definitionId> with your Azure DevOps values (Pipelines > ... > Status badge). -->
[![Build Status](https://dev.azure.com/<org>/<project>/_apis/build/status/<definitionId>?branchName=main)](https://dev.azure.com/<org>/<project>/_build/latest?definitionId=<definitionId>&branchName=main)

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
  service.py             Pipeline + storage: incoming -> routed blob (+ SQL row)
  routing/               Container / folder rules
  storage/               Blob store (Azure/Azurite + in-memory) and SQL repository
  reporting/             Excel report
sql/create_employee_data.sql   EmployeeData table for the Azure portal
upload_samples.py        Upload sample_documents/ to "incoming"
run_local.py             Run the full flow locally
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
| `STORAGE_CONNECTION_STRING` | `UseDevelopmentStorage=true` (Azurite) | Blob Storage connection |
| `SQL_CONNECTION_STRING` | SQLite `output/hr_onboarding.db` | SQLAlchemy URL, or the Azure SQL ODBC string from the portal |
| `OUTPUT_DIR` | `output` | Local runs only: Excel report and SQLite file |
| `BLOB_TRIGGER_SOURCE` | `EventGrid` | Set to `LogsAndContainerScan` locally (Azurite has no Event Grid) |

## Running locally

With Azurite running (VS Code: `Azurite: Start Blob Service`):

```powershell
python upload_samples.py   # sample_documents/ -> "incoming" container
python run_local.py        # route blobs, upsert EmployeeData, write the Excel report
```

Without Azurite, `python run_local.py --offline` runs the same flow with in-memory blobs.

## Storage

| Category | Destination | SQL row |
|---|---|---|
| Passport | `passports/<PersonKey>/<FileName>` | No |
| DrivingLicence | `driving-licences/<PersonKey>/<FileName>` | No |
| EmployeeDocument | `employee-documents/<PersonKey>/<FileName>` | Yes, in `EmployeeData` |
| Other, low confidence (< 0.8) or name not found | stays in `incoming`, blob metadata `status=NeedsReview` | No |

- **Order of steps:** copy to the destination, then upsert the SQL row, and only then delete from `incoming`. A failure at any step leaves the original in place, and a retry is safe.
- **Two tables:** `EmployeeData` has a unique key on `(PersonKey, FileName)`, matching the blob path. `ClassificationResults` holds the latest classification of every document, one row per blob location. For a manual Azure SQL setup, see [sql/create_employee_data.sql](sql/create_employee_data.sql).
- **Excel report:** sheets Classification, EmployeeData and PreviousEmployment, built from both tables. Saved to `output/onboarding_results.xlsx` by `run_local.py`, or `reports/onboarding_results_<timestamp>.xlsx` by `/api/report`.
- **Local to Azure:** you only change the connection strings, no code.

## Azure Function

| Function | Trigger | Does |
|---|---|---|
| `process_incoming_blob` | Blob created in `incoming` | Classifies and routes that one file. Skips files already marked `NeedsReview` until they are re-uploaded. |
| `process_all` | `POST /api/process-all` | Processes everything in `incoming` and returns a JSON summary per file |
| `report` | `POST /api/report` | Builds the report from the database, saves it to `reports` and returns the blob name and row counts (no link) |

HTTP functions use `AuthLevel.FUNCTION` (a function key in Azure; not checked by `func start`). The blob trigger uses Event Grid by default, which Flex Consumption requires. Locally, `BLOB_TRIGGER_SOURCE=LogsAndContainerScan` switches it to polling, because Azurite has no Event Grid. In Azure, `SQL_CONNECTION_STRING` is required: the SQLite fallback is for local runs only.

### Running the Function locally

Needs [Azure Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and Azurite with **all** services (VS Code: `Azurite: Start`), because the Functions host uses blobs, queues and tables.

```powershell
Copy-Item local.settings.example.json local.settings.json   # once
.venv\Scripts\Activate.ps1
func start
python upload_samples.py                                     # in a second terminal: the blob trigger picks these up
Invoke-RestMethod -Method Post http://localhost:7071/api/process-all
Invoke-RestMethod -Method Post http://localhost:7071/api/report
```

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
- [x] Blob routing
- [x] SQL persistence (SQLite locally, Azure SQL via connection string)
- [x] Excel report
- [x] Azure Function triggers (blob, process-all, report)
- [ ] Deployment
