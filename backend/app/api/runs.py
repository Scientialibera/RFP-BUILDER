"""
Runs management API endpoints.

Provides endpoints to:
- List past runs
- Get run details (metadata, documents, code)
- Regenerate documents from modified code
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import get_config
from app.workflows.executors import CodeInterpreterExecutor
from app.core.llm_client import create_llm_client


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs", tags=["Runs"])


# ============================================================================
# Response Models
# ============================================================================

class DocumentSummary(BaseModel):
    """Summary of a document in a run."""
    filename: str
    file_type: str  # 'rfp', 'example', 'context'


class RevisionInfo(BaseModel):
    """Information about a revision."""
    revision_id: str  # e.g., "rev_001"
    created_at: str
    docx_filename: str


class RunSummary(BaseModel):
    """Summary of a run for list view."""
    run_id: str
    created_at: str
    has_docx: bool
    has_plan: bool
    critique_count: int
    revision_count: int


class RunDetails(BaseModel):
    """Detailed information about a run."""
    run_id: str
    created_at: str
    has_docx: bool
    has_plan: bool
    critique_count: int
    documents: list[DocumentSummary]
    revisions: list[RevisionInfo]
    docx_download_url: Optional[str] = None
    code_available: bool = False


class RunCodeResponse(BaseModel):
    """Response containing the generation code."""
    run_id: str
    code: str
    stage: str  # e.g., "99_final"


class RegenerateRequest(BaseModel):
    """Request to regenerate a document with modified code."""
    code: str


class RegenerateResponse(BaseModel):
    """Response after regenerating a document."""
    success: bool
    message: str
    revision_id: str
    docx_download_url: str


class RunsListResponse(BaseModel):
    """Response for listing runs."""
    runs: list[RunSummary]
    total: int


# ============================================================================
# Helper Functions
# ============================================================================

def _get_runs_dir() -> Path:
    """Get the runs output directory."""
    config = get_config()
    return Path(config.app.output_dir)


def _safe_path_part(value: str, field_name: str) -> str:
    """Validate a path segment to prevent traversal."""
    safe = Path(value).name
    if safe != value:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: {value}")
    return safe


def _resolve_run_dir(run_id: str) -> Path:
    """Resolve run directory safely under the runs root."""
    runs_dir = _get_runs_dir().resolve()
    safe_run_id = _safe_path_part(run_id, "run_id")
    run_dir = (runs_dir / safe_run_id).resolve()
    if not run_dir.is_relative_to(runs_dir):
        raise HTTPException(status_code=400, detail="Invalid run path")
    return run_dir


def _parse_run_timestamp(run_id: str) -> Optional[datetime]:
    """Parse timestamp from run_id (e.g., 'run_20260201_123456')."""
    try:
        if run_id.startswith("run_"):
            ts_str = run_id[4:]  # Remove "run_" prefix
            return datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
    except ValueError:
        pass
    return None


def _get_run_info(run_dir: Path) -> Optional[RunSummary]:
    """Extract summary info from a run directory."""
    run_id = run_dir.name
    
    # Check if it's a valid run directory
    if not run_id.startswith("run_"):
        return None
    
    # Parse timestamp
    ts = _parse_run_timestamp(run_id)
    created_at = ts.isoformat() if ts else ""
    
    # Check for docx
    docx_path = run_dir / "word_document" / "proposal.docx"
    has_docx = docx_path.exists()
    
    # Check for plan
    plan_path = run_dir / "metadata" / "plan.json"
    has_plan = plan_path.exists()
    
    # Count critiques
    critiques_path = run_dir / "metadata" / "critiques.json"
    critique_count = 0
    if critiques_path.exists():
        try:
            with open(critiques_path, "r", encoding="utf-8") as f:
                critiques = json.load(f)
                critique_count = len(critiques) if isinstance(critiques, list) else 0
        except Exception:
            pass
    
    # Count revisions
    revisions_dir = run_dir / "revisions"
    revision_count = 0
    if revisions_dir.exists():
        revision_count = len([d for d in revisions_dir.iterdir() if d.is_dir() and d.name.startswith("rev_")])
    
    return RunSummary(
        run_id=run_id,
        created_at=created_at,
        has_docx=has_docx,
        has_plan=has_plan,
        critique_count=critique_count,
        revision_count=revision_count
    )


def _get_documents_list(run_dir: Path) -> list[DocumentSummary]:
    """Get list of documents in a run."""
    docs_manifest = run_dir / "documents" / "documents_manifest.json"
    if docs_manifest.exists():
        try:
            with open(docs_manifest, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [
                    DocumentSummary(filename=d["filename"], file_type=d["type"])
                    for d in data.get("documents", [])
                ]
        except Exception:
            pass
    
    # Fallback: scan documents directory
    docs_dir = run_dir / "documents"
    if docs_dir.exists():
        return [
            DocumentSummary(filename=f.name, file_type="unknown")
            for f in docs_dir.iterdir()
            if f.is_file() and f.suffix.lower() == ".pdf"
        ]
    
    return []


def _get_revisions_list(run_dir: Path) -> list[RevisionInfo]:
    """Get list of revisions in a run."""
    revisions_dir = run_dir / "revisions"
    revisions = []
    
    if revisions_dir.exists():
        for rev_dir in sorted(revisions_dir.iterdir()):
            if rev_dir.is_dir() and rev_dir.name.startswith("rev_"):
                # Check for docx
                docx_files = list(rev_dir.glob("*.docx"))
                docx_filename = docx_files[0].name if docx_files else "proposal.docx"
                
                # Get creation time
                try:
                    created_at = datetime.fromtimestamp(rev_dir.stat().st_ctime).isoformat()
                except Exception:
                    created_at = ""
                
                revisions.append(RevisionInfo(
                    revision_id=rev_dir.name,
                    created_at=created_at,
                    docx_filename=docx_filename
                ))
    
    return revisions


def _get_next_revision_id(run_dir: Path) -> str:
    """Get the next revision ID (e.g., 'rev_001', 'rev_002', etc.)."""
    revisions_dir = run_dir / "revisions"
    if not revisions_dir.exists():
        return "rev_001"
    
    existing = [d.name for d in revisions_dir.iterdir() if d.is_dir() and d.name.startswith("rev_")]
    if not existing:
        return "rev_001"
    
    # Extract numbers and find max
    max_num = 0
    for rev in existing:
        try:
            num = int(rev.split("_")[1])
            max_num = max(max_num, num)
        except (IndexError, ValueError):
            pass
    
    return f"rev_{max_num + 1:03d}"


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=RunsListResponse)
async def list_runs(
    limit: int = 50,
    offset: int = 0,
):
    """
    List all past runs.
    
    Returns runs sorted by creation time (newest first).
    """
    runs_dir = _get_runs_dir()
    
    if not runs_dir.exists():
        return RunsListResponse(runs=[], total=0)
    
    # Get all run directories
    all_runs = []
    for item in runs_dir.iterdir():
        if item.is_dir():
            run_info = _get_run_info(item)
            if run_info:
                all_runs.append(run_info)
    
    # Sort by created_at (newest first)
    all_runs.sort(key=lambda r: r.created_at, reverse=True)
    
    # Apply pagination
    total = len(all_runs)
    runs = all_runs[offset:offset + limit]
    
    return RunsListResponse(runs=runs, total=total)


@router.get("/{run_id}", response_model=RunDetails)
async def get_run_details(run_id: str):
    """
    Get detailed information about a specific run.
    """
    run_dir = _resolve_run_dir(run_id)
    
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    
    summary = _get_run_info(run_dir)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Invalid run directory: {run_id}")
    
    # Get documents
    documents = _get_documents_list(run_dir)
    
    # Get revisions
    revisions = _get_revisions_list(run_dir)
    
    # Check if code is available
    code_path = run_dir / "code_snapshots" / "99_final_document_code.py"
    code_available = code_path.exists()
    
    # Build download URL if docx exists
    docx_download_url = None
    if summary.has_docx:
        docx_download_url = f"/api/rfp/download/{run_id}/proposal.docx"
    
    return RunDetails(
        run_id=summary.run_id,
        created_at=summary.created_at,
        has_docx=summary.has_docx,
        has_plan=summary.has_plan,
        critique_count=summary.critique_count,
        documents=documents,
        revisions=revisions,
        docx_download_url=docx_download_url,
        code_available=code_available
    )


@router.get("/{run_id}/code", response_model=RunCodeResponse)
async def get_run_code(run_id: str, stage: str = "99_final"):
    """
    Get the generation code for a run.
    
    Args:
        run_id: The run ID
        stage: The code stage (default: "99_final" for final code)
    """
    run_dir = _resolve_run_dir(run_id)
    
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    
    safe_stage = _safe_path_part(stage, "stage")
    code_path = run_dir / "code_snapshots" / f"{safe_stage}_document_code.py"
    
    if not code_path.exists():
        # Try to find any code file
        code_dir = run_dir / "code_snapshots"
        if code_dir.exists():
            code_files = list(code_dir.glob("*.py"))
            if code_files:
                # Return the last one (highest numbered)
                code_files.sort()
                code_path = code_files[-1]
                safe_stage = code_path.stem.replace("_document_code", "")
            else:
                raise HTTPException(status_code=404, detail="No code files found in this run")
        else:
            raise HTTPException(status_code=404, detail="Code snapshots directory not found")
    
    try:
        with open(code_path, "r", encoding="utf-8") as f:
            code = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read code: {str(e)}")
    
    return RunCodeResponse(
        run_id=run_id,
        code=code,
        stage=safe_stage
    )


@router.post("/{run_id}/regenerate", response_model=RegenerateResponse)
async def regenerate_document(
    run_id: str,
    request: RegenerateRequest = Body(...),
):
    """
    Regenerate a document using modified code.
    
    Creates a new revision under the run directory.
    """
    run_dir = _resolve_run_dir(run_id)
    
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    
    # Create revision directory
    revision_id = _get_next_revision_id(run_dir)
    revision_dir = run_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the modified code
    code_path = revision_dir / "document_code.py"
    try:
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(request.code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save code: {str(e)}")
    
    # Create a mock RFPResponse with the code
    from app.models.schemas import RFPResponse
    mock_response = RFPResponse(document_code=request.code)
    
    # Execute the code
    client = create_llm_client()
    code_interpreter = CodeInterpreterExecutor(client, run_dir)
    
    try:
        docx_path, code_stats = await code_interpreter.execute(
            mock_response,
            image_dir=revision_dir / "images",
            docx_dir=revision_dir
        )
        
        if not code_stats.get('document_success', False):
            errors = code_stats.get('errors', ['Unknown error'])
            raise HTTPException(
                status_code=400,
                detail=f"Code execution failed: {errors[0] if errors else 'Unknown error'}"
            )
        
        # Get the actual docx filename
        docx_files = list(revision_dir.glob("*.docx"))
        docx_filename = docx_files[0].name if docx_files else "proposal.docx"
        
        return RegenerateResponse(
            success=True,
            message=f"Document regenerated successfully as {revision_id}",
            revision_id=revision_id,
            docx_download_url=f"/api/runs/{run_dir.name}/revisions/{revision_id}/{docx_filename}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Regeneration failed")
        raise HTTPException(status_code=500, detail=f"Regeneration failed: {str(e)}")


@router.get("/{run_id}/revisions/{revision_id}/{filename}")
async def download_revision(run_id: str, revision_id: str, filename: str):
    """Download a document from a specific revision."""
    run_dir = _resolve_run_dir(run_id)
    safe_revision_id = _safe_path_part(revision_id, "revision_id")
    safe_filename = _safe_path_part(filename, "filename")
    file_path = (run_dir / "revisions" / safe_revision_id / safe_filename).resolve()
    if not file_path.is_relative_to(run_dir):
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    if not safe_filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="Only DOCX downloads allowed")
    
    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@router.get("/{run_id}/documents/{filename}")
async def download_source_document(run_id: str, filename: str):
    """Download a source document (RFP, example, context) from a run."""
    run_dir = _resolve_run_dir(run_id)
    safe_filename = _safe_path_part(filename, "filename")
    file_path = (run_dir / "documents" / safe_filename).resolve()
    if not file_path.is_relative_to(run_dir):
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    
    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="application/pdf"
    )
