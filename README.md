# RFP Builder

Enterprise RFP response generator with FastAPI + React, built around a staged AI workflow.

## What It Does

- Extracts structured requirements from a source RFP
- Optionally creates a proposal plan before generation
- Generates executable `python-docx` code
- Executes code to produce a DOCX and retries on execution errors
- Optionally critiques generated code and supports revision loops
- Stores full run artifacts and supports post-run regeneration from edited code

## Current Frontend Tabs

- **Standard Flow**: One orchestrated call
- **Custom Flow**: Step-by-step calls (extract -> optional plan -> generate -> optional critique)
- **Config**: Read-only viewer for all system and base prompts via API

## Repository Layout

```text
RFP-BUILDER/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── functions/
│   │   ├── models/
│   │   ├── prompts/
│   │   ├── services/
│   │   └── workflows/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── context/
│   │   ├── services/
│   │   └── types/
│   └── package.json
├── requirements.txt
├── config.toml.example
└── README.md
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- Poppler (required when `enable_images = true`)
  - Windows: <https://github.com/oschwartz10612/poppler-windows/releases>
  - macOS: `brew install poppler`
  - Linux: `apt-get install poppler-utils`
- Mermaid CLI `mmdc` (required for Mermaid rendering)
  - `npm install -g @mermaid-js/mermaid-cli`

## Quick Start

### 1) Configure

```bash
cp config.toml.example config.toml
```

Update `config.toml` for Azure/OpenAI settings and feature flags.

### 2) Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate     # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r ..\requirements.txt
# optional: pip install -e .

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API base: `http://127.0.0.1:8000`

### 3) Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite dev server: typically `http://127.0.0.1:5173`

## API Surface

### Health

- `GET /health`

### Frontend Config + Prompts

- `GET /api/config`
- `GET /api/config/prompts` (read-only prompt catalog for Config tab)

### Orchestrated Flow

- `POST /api/rfp/orchestrate` (snake_case)
- `POST /api/rfp/orchestrate/stream` (SSE)
- Legacy aliases kept:
  - `POST /api/rfp/generate`
  - `POST /api/rfp/generate/stream`

### Step Endpoints (Custom Flow)

- `POST /api/rfp/extract-reqs`
  - Inputs: `source_rfp`, optional `company_context[]`, optional `comment`, optional `previous_requirements`
- `POST /api/rfp/plan`
  - JSON body: `analysis`, optional `company_context_text`, optional `comment`, optional `previous_plan`
- `POST /api/rfp/plan-with-context`
  - Multipart: `analysis_json`, optional `company_context_text`, optional `company_context[]`, optional `comment`, optional `previous_plan_json`
- `POST /api/rfp/generate-rfp`
  - Inputs: `source_rfp`, `example_rfps[]`, optional `company_context[]`, `analysis_json`, optional `plan_json`,
    optional `comment`, optional `previous_document_code`
  - Returns: `document_code` + `docx_base64` + `docx_download_url`
- `POST /api/rfp/critique`
  - JSON body: `analysis`, `document_code`, optional `comment`
- `GET /api/rfp/download/{run_id}/{filename}`

### Runs Management

- `GET /api/runs?limit=50&offset=0`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/code?stage=99_final`
- `POST /api/runs/{run_id}/regenerate`
- `GET /api/runs/{run_id}/revisions/{revision_id}/{filename}`
- `GET /api/runs/{run_id}/documents/{filename}`

## Workflow Notes

Primary workflow:

1. Extract requirements
2. Optional planning
3. Generate document code
4. Execute code to DOCX (with error recovery)
5. Optional critique/revision loop

Custom Flow supports iterative regeneration using:

- previously generated requirements
- previous plan
- previous generated code
- comments for additional guidance

## Prompt and Comment Behavior

- User comments are injected as additional **user prompt sections** for each stage.
- Planner enforces numeric `rfp_pages` values (integers, not titles).
- Generator prompt includes multiple visualization templates (bar, burndown, schedule/gantt, milestone timeline).

## Mermaid Rendering Notes

- Runtime helper: `render_mermaid(code, output_filename, width=1600, height=1000, scale=1.5)`
- Helper clamps dimensions/scale to safer ranges to reduce clipped or oversized diagrams.
- In generated docs, diagrams should be inserted with bounded width (for example `Inches(5.8)`).

## Configuration Highlights

Common flags in `config.toml`:

- `[workflow]`:
  - `enable_planner`
  - `enable_critiquer`
  - `max_critiques`
  - `max_error_loops`
- `[features]`:
  - `enable_images`
  - `enable_tables`
  - `toggle_requirements_chunking`
  - `toggle_generation_chunking`
  - `generator_intro_pages`
  - `generation_page_overlap`
  - `max_sections_per_chunk`

Generator overrides can also be sent per request in multipart form fields.

## Run Output Structure

Each run creates `outputs/runs/run_YYYYMMDD_HHMMSS/` with standard subfolders:

- `word_document/`
- `image_assets/`
- `diagrams/`
- `documents/`
- `revisions/`
- `llm_interactions/`
- `execution_logs/`
- `metadata/`
- `code_snapshots/`

## Development

### Backend checks

```bash
cd backend
python -m compileall app
pytest
```

### Frontend checks

```bash
cd frontend
npm run build
npm run lint
```

## Azure Deployment

Deployment scripts live in `deploy/`:

- `deploy/deploy_backend.ps1`
- `deploy/deploy_frontend.ps1`

### Prerequisites

- `az login` completed
- Access to target subscription/resource group
- Docker installed and running
- Existing Azure resources (or matching names updated in scripts):
  - Web Apps
  - ACR
  - Azure OpenAI account
  - Storage account for run artifacts

### Backend deploy

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/deploy_backend.ps1 -Environment dev
```

Useful flags:

- `-SkipDockerBuild`
- `-SkipPush`
- `-SkipConfig`
- `-SkipRoleAssignments`
- `-ConfigPath C:\path\to\config.toml`

What backend deploy now does automatically:

- Builds/pushes backend image to ACR
- Updates Web App container image
- Clears stale Web App startup override (`appCommandLine`) so Docker `CMD` is used
- Pushes `config.toml` values to App Settings (including complex list/dict values)
- Restarts Web App
- Applies managed identity roles only when missing (no redundant re-apply):
  - `Cognitive Services OpenAI User`
  - `Storage Blob Data Contributor`
  - `AcrPull`

### Frontend deploy

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/deploy_frontend.ps1 -Environment dev
```

What frontend deploy now does automatically:

- Builds/pushes frontend image to ACR
- Builds with `VITE_API_BASE_URL` pointing to backend `/api` base
- Updates Web App container image
- Clears stale Web App startup override (`appCommandLine`) so nginx container starts correctly
- Sets runtime app settings and restarts Web App

### Config behavior in Azure

- Local/dev: if `config.toml` exists, backend loads it.
- Azure: backend can run without `config.toml`, reading App Settings as environment variables.
- Environment variables override TOML when both exist.

### Post-deploy smoke checks

```powershell
Invoke-WebRequest -UseBasicParsing https://<backend-app>.azurewebsites.net/health
Invoke-WebRequest -UseBasicParsing https://<backend-app>.azurewebsites.net/api/config
Invoke-WebRequest -UseBasicParsing https://<frontend-app>.azurewebsites.net
```

## Troubleshooting

### Vite proxy `ECONNREFUSED` for `/api/*`

Backend is not reachable on `127.0.0.1:8000`. Start/restart backend:

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Mermaid generation failures

Install Mermaid CLI and ensure `mmdc` is on PATH:

```bash
npm install -g @mermaid-js/mermaid-cli
```

### Azure frontend shows `Application Error` with `pm2: not found`

Cause: stale App Service startup command overriding Docker image startup.

Fix:

```powershell
$cfgId = az webapp config show -g <rg> -n <frontend-app> --query id -o tsv
az resource update --ids $cfgId --set properties.appCommandLine="" -o none
az webapp restart -g <rg> -n <frontend-app>
```

### Azure frontend shows `Failed to load application configuration`

Check:

- Frontend app is running (not `503`)
- Backend `/api/config` returns `200`
- Frontend build arg/app setting points to backend with `/api` suffix
  - Example: `https://<backend-app>.azurewebsites.net/api`

### Image extraction failures

Install Poppler and verify binaries are available on PATH.

## License

MIT
