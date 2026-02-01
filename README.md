# RFP Builder

Enterprise RFP (Request for Proposal) response generator powered by Microsoft Agent Framework workflows and AI.

## Features

- **AI-Powered Analysis**: Automatically extracts requirements from RFP documents
- **Optional Proposal Planning**: AI-driven planning before document generation (toggle `enable_planner`)
- **Optional Quality Critique**: Automatic code review with revision loops (toggle `enable_critiquer`)
- **Error Recovery**: Automatic error detection and code regeneration with max retry limit
- **Style Learning**: Uses example RFPs to match your organization's proposal style
- **Inline Visualizations**: Generates seaborn charts and mermaid diagrams directly in the document
- **Word Document Output**: Creates professional DOCX proposals with embedded images
- **Optional MSAL Auth**: Toggle Microsoft login in the frontend
- **Optional API Auth**: Token validation for API requests
- **Image Mode**: Send PDFs as images for better format understanding
- **Table-Aware Image Selection**: Prioritizes table-heavy pages for vision input
- **Image Budgeting**: Split a total image budget across example RFPs, the target RFP, and company context PDFs (per LLM call)
- **Requirements Chunking**: Token-aware RFP chunking for large requirements extraction
- **Generation Chunking**: Section-aware generation using the planner output + final synthesis

## Architecture

```
RFP-BUILDER/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Configuration, LLM client
│   │   ├── functions/      # Function calling definitions
│   │   ├── models/         # Pydantic schemas
│   │   ├── prompts/        # System and user prompts
│   │   ├── services/       # PDF, diagram services
│   │   └── workflows/      # Agent Framework workflows
│   └── pyproject.toml
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── context/       # Auth context
│   │   ├── services/      # API client
│   │   └── types/         # TypeScript types
│   └── package.json
├── config.toml            # Your configuration (git-ignored)
├── config.toml.example    # Example configuration
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Azure CLI (if using Azure OpenAI)
- Mermaid CLI (optional, for diagrams): `npm install -g @mermaid-js/mermaid-cli`
- Poppler (for PDF to image conversion): 
  - Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases
  - Mac: `brew install poppler`
  - Linux: `apt-get install poppler-utils`

### Configuration

1. Copy the example config:
```bash
cp config.toml.example config.toml
```

2. Edit `config.toml` with your settings:
```toml
[azure]
endpoint = "https://your-resource.openai.azure.com/"
model = "gpt-4o"

[features]
enable_images = true   # Convert PDFs to images for LLM
enable_tables = true   # Prioritize table pages when selecting images
enable_auth = false    # Toggle MSAL authentication
```

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e .

# Run the server
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run the dev server
npm run dev
```

The frontend will be available at http://localhost:3000

## API Endpoints

### Generate RFP Response

```
POST /api/rfp/generate
Content-Type: multipart/form-data

Parameters:
- rfp: PDF file (required) - The RFP to respond to
- example_rfps: PDF files (required) - Example RFP responses for style reference
- company_context: PDF files (optional) - Company capability documents
```

### Health Check

```
GET /health
```

### Configuration

```
GET /api/config
```

Returns frontend configuration including auth settings.

## Workflow Stages

The RFP Builder uses a sophisticated workflow with optional enhancements:

1. **Analyze**: Extract requirements, evaluation criteria, and submission guidelines
2. **Plan** (optional): Create a detailed proposal plan with section strategy, visualizations, and win strategy
3. **Generate**: Write complete Python code that creates the DOCX with inline seaborn charts and mermaid diagrams
4. **Critique** (optional): Review generated code and request revisions if needed (configurable loop count)
5. **Execute**: Run the document code with automatic error detection and recovery (configurable retry limit)
6. **Output**: Generate the final DOCX proposal with all visualizations

## Configuration Options

### Azure OpenAI (Recommended)

```toml
[azure]
endpoint = "https://your-resource.openai.azure.com/"
model = "gpt-4o"
api_version = "2024-02-15-preview"
```

Uses `DefaultAzureCredential` for authentication - ensure you're logged in via Azure CLI.

### Direct OpenAI

```toml
[openai]
api_key = "sk-..."
model = "gpt-4o"
```

### Authentication

```toml
[features]
enable_auth = true

[msal]
client_id = "your-app-registration-client-id"
tenant_id = "your-tenant-id"
redirect_uri = "http://localhost:3000"
scopes = ["User.Read"]
```

### Image & Table Settings

Image handling is driven by a total budget (`max_images`) and normalized ratios for the three PDF types:
1) example RFP responses  
2) the target RFP to answer  
3) internal company capabilities/context PDFs

If ratios do not sum to 1, they are normalized. Budgets are then split across documents of the same type.

Note: the max image cap is applied per LLM call. When generation chunking is enabled, a hard cap is enforced
per chunk (images are trimmed to `max_images` before each chunk call).

```toml
[features]
enable_images = true
enable_tables = true
image_dpi = 150
max_images = 50
min_table_rows = 2
min_table_cols = 2
image_ratio_examples = 0.5
image_ratio_rfp = 0.25
image_ratio_context = 0.25
```

### Requirements Chunking (Requirements Extraction Only)

When enabled, the requirements analysis step splits the RFP into token-aware chunks and
processes them sequentially. Each chunk includes the relevant pages and the previous chunk
output to avoid duplicate requirements.

```toml
[features]
toggle_requirements_chunking = false
max_tokens_reqs_chunking = 12000
```

### Generation Chunking (Planner Required)

Generation chunking uses the planner output to generate sections in parts, then synthesizes a final
document code file. Each chunk includes:
- The first N RFP pages (intro/exposition)
- The pages cited by the planned sections, with overlap
- The requirements linked to those sections

Critique is applied per chunk (if enabled). Final synthesis is not critiqued.

```toml
[features]
toggle_generation_chunking = false
max_tokens_generation_chunking = 12000
generator_intro_pages = 3
generation_page_overlap = 1
max_sections_per_chunk = 3
```

### API Overrides (Generator)

You can override generator formatting and chunking settings per request (multipart form fields):
- `generator_formatting_injection`
- `generator_intro_pages`
- `generation_page_overlap`
- `toggle_generation_chunking`
- `max_tokens_generation_chunking`
- `max_sections_per_chunk`

### API Token Authentication

```toml
[api_auth]
# Enable API token authentication (default: false)
enabled = false
# Header name for API token (default: X-API-Key)
header_name = "X-API-Key"
# Token type: "bearer", "jwt", or "custom"
token_type = "bearer"
# JWT secret for validating signed tokens (only for jwt type)
jwt_secret = ""
# Required token fields and expected values
# Token must be JSON (plain or base64-encoded) containing these fields
required_fields = [
  { field = "user_id", value = "admin123" },
  { field = "org", value = "acme-corp" }
]
```

When enabled, tokens are validated against the required fields. Tokens can be plain JSON or base64-encoded JSON:

**Plain JSON token example:**
```bash
TOKEN='{"user_id":"admin123","org":"acme-corp","timestamp":"2026-02-01T12:00:00Z"}'
curl -X POST http://localhost:8000/api/rfp/generate \
  -H "X-API-Key: $TOKEN" \
  -F "rfp=@rfp.pdf" \
  -F "example_rfps=@example1.pdf"
```

**Base64-encoded JSON token:**
```bash
TOKEN=$(echo '{"user_id":"admin123","org":"acme-corp"}' | base64)
curl -X POST http://localhost:8000/api/rfp/generate \
  -H "X-API-Key: $TOKEN" \
  -F "rfp=@rfp.pdf" \
  -F "example_rfps=@example1.pdf"
```

Token validation:
- All required fields in the token must match the configured values exactly
- Missing fields cause validation to fail
- Extra fields in the token are ignored
- Empty `required_fields` list means any token is accepted (if auth is enabled)

### Page Markers (Requirements vs Generation)

The PDF text extraction uses explicit page markers:
- Requirements analysis expects `PAGE TO CITE: <n>`
- Generation prompts receive `PAGE NUMBER: <n>` markers (same numbers) for consistency

### Workflow Features

```toml
[workflow]
llm_timeout = 120           # seconds
max_retries = 3             # API call retries
verbose = false
log_all_steps = true        # Log all LLM interactions

# Planner: Creates proposal structure before generation
enable_planner = false

# Critiquer: Reviews code and requests revisions
enable_critiquer = false
max_critiques = 1           # Max critique loops

# Error Recovery: Retries generation on execution errors
max_error_loops = 2         # Max error recovery attempts
```

## Function Calling Schema

The RFP Builder uses structured function calling for AI agents:

### 1. analyze_rfp
Extracts requirements and evaluation criteria from RFP documents.

### 2. plan_proposal (optional)
Creates a detailed proposal structure:
- Section titles and summaries
- Requirement mapping
- RFP page references
- Suggested visualizations (diagrams, charts, tables)
- Win strategy

### 3. generate_rfp_response
Generates complete Python code that:
- Creates the DOCX document structure
- Generates seaborn charts inline
- Creates mermaid diagrams inline
- Builds tables and formatted text

The code has access to:
- `python-docx` - Document creation
- `seaborn` & `matplotlib` - Chart generation
- `render_mermaid()` helper - Diagram rendering
- `pandas` & `numpy` - Data manipulation

### 4. critique_response (optional)
Reviews generated code for:
- Completeness (all requirements addressed)
- Technical correctness (will code execute?)
- Professional quality (formatting, structure)
- Visualization quality (appropriate charts/diagrams)

## Output Structure

Each RFP generation creates a timestamped run directory with **enterprise-grade organization**:

```
outputs/
└── runs/
    └── run_20260201_152345/
        ├── word_document/                 # Final deliverable
        │   └── proposal.docx              # Generated DOCX with embedded charts & diagrams
        │
        ├── image_assets/                  # Generated visualizations
        │   ├── chart_001.png              # Seaborn/matplotlib charts
        │   ├── chart_002.png
        │   └── ...
        │
        ├── diagrams/                      # Mermaid diagram artifacts
        │   ├── architecture.svg
        │   ├── timeline.svg
        │   └── ...
        │
        ├── llm_interactions/              # Complete LLM interaction logs
        │   ├── analyze_analyze_rfp.json   # RFP analysis
        │   ├── analyze_analyze_rfp.md
        │   ├── plan_plan_proposal.json    # Planning (if enabled)
        │   ├── plan_plan_proposal.md
        │   ├── generate_generate_rfp_response.json
        │   ├── generate_generate_rfp_response.md
        │   ├── critique_critique_response.json (if enabled)
        │   ├── critique_critique_response.md
        │   └── ...
        │
        ├── execution_logs/                # Code execution details
        │   └── execution.json             # Generation stats, errors, timings
        │
        ├── metadata/                      # Structured data artifacts
        │   ├── analysis.json              # Extracted requirements & evaluation criteria
        │   ├── plan.json                  # Section plan with strategies (if enabled)
        │   ├── critiques.json             # Critique feedback history (if enabled)
        │   └── manifest.json              # Run summary and directory index
        │
        └── code_snapshots/                # Generated code evolution
            ├── 01_initial_document_code.py
            ├── 02_critique_revision_1.py
            ├── 02_critique_revision_2.py
            ├── 03_error_recovery_1.py
            └── 99_final_document_code.py
```

### Key Directories

**word_document/**  
The final deliverable - a polished DOCX proposal with all visualizations embedded.

**image_assets/**  
Generated charts and graphs (seaborn/matplotlib PNGs) referenced in the document code. Allows separation of generation and embedding workflows.

**diagrams/**  
Mermaid diagram SVG outputs (architecture, timelines, workflows, etc.).

**llm_interactions/**  
Complete transparency into every LLM API call:
- Raw function arguments sent to the LLM
- Full LLM response text before parsing
- Parsed/validated results as JSON
- Formatted markdown version for human review

**execution_logs/**  
Python code execution details including success/failure status, error messages, execution time, and recovery attempt history.

**metadata/**  
Structured data for further analysis or auditing:
- `analysis.json`: Extracted RFP requirements, evaluation criteria, deliverables
- `plan.json`: AI-generated proposal structure and strategy (if planning enabled)
- `critiques.json`: All feedback iterations from the critique loop (if critique enabled)
- `manifest.json`: Run summary with timestamps and feature toggles used

**code_snapshots/**  
Timestamped snapshots of the python-docx code at each generation stage:
- `01_initial_*`: First generation pass
- `02_critique_revision_*`: Post-critique revisions (numbered sequentially)
- `03_error_recovery_*`: Error recovery regenerations (numbered sequentially)
- `99_final_*`: Final version used for document generation

### Manifest File

The `metadata/manifest.json` provides a high-level overview of the run:

```json
{
  "timestamp": "2026-02-01T15:23:45.123456",
  "run_dir": "outputs/runs/run_20260201_152345",
  "has_plan": true,
  "critique_count": 2,
  "subdirectories": {
    "word_document": "Final .docx proposal file",
    "image_assets": "Generated charts and visualizations",
    "diagrams": "Generated Mermaid diagrams",
    "llm_interactions": "LLM request/response logs",
    "execution_logs": "Code execution logs and errors",
    "metadata": "Analysis, plan, and critique JSON files",
    "code_snapshots": "Generated document code snapshots"
  }
}
```

## Development

### Running Tests

```bash
cd backend
pytest
```

### Code Formatting

```bash
# Backend
cd backend
black .
ruff check .

# Frontend
cd frontend
npm run lint
```

## License

MIT
