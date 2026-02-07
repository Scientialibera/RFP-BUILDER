"""
RFP Generation API endpoints.
"""

import logging
import json
import time
import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TypeVar

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ValidationError

from app.core.config import get_config, FeaturesConfig
from app.core.auth import verify_api_token
from app.core.llm_client import create_llm_client
from app.models.schemas import (
    GenerateRFPResponse,
    ExtractReqsResponse,
    PlanStepRequest,
    PlanStepResponse,
    GenerateRFPStepResponse,
    CritiqueStepRequest,
    CritiqueStepResponse,
    RFPAnalysis,
    ProposalPlan,
    RFPRequirement,
)
from app.services.pdf_service import PDFService
from app.workflows.rfp_workflow import create_rfp_workflow
from app.workflows.executors import (
    RFPAnalyzerExecutor,
    PlannerExecutor,
    SectionGeneratorExecutor,
    CritiquerExecutor,
    CodeInterpreterExecutor,
)
from app.workflows.run_dirs import create_unique_run_directory
from app.workflows.state import WorkflowInput, DocumentInfo


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rfp", tags=["RFP"])
ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass
class ProcessedDocuments:
    """Container for processed document data."""
    rfp_text: str
    rfp_images: list[dict] | None
    example_texts: list[str]
    example_images: list[list[dict]] | None
    context_text: str | None
    context_images: list[dict] | None
    # Document info for storage
    documents: list[DocumentInfo] = field(default_factory=list)


def _validate_pdf_files(files: list[UploadFile]) -> None:
    """Validate that all uploads are PDF files."""
    for file in files:
        if file.filename and not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"Only PDF files are allowed. Got: {file.filename}",
            )


def _safe_filename(filename: str) -> str:
    """Return a path-safe basename."""
    return Path(filename).name


def _validate_simple_path_part(value: str, field_name: str) -> str:
    """Reject path traversal by forcing a single path segment."""
    safe = Path(value).name
    if safe != value:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: {value}")
    return safe


def _create_step_run_directory() -> Path:
    """Create a run directory for step endpoints."""
    config = get_config()
    output_root = Path(config.app.output_dir)
    return create_unique_run_directory(output_root)


def _save_documents(run_dir: Path, documents: list[DocumentInfo]) -> None:
    """Persist uploaded source documents in the run directory."""
    if not documents:
        return

    docs_dir = run_dir / "documents"
    for doc_info in documents:
        if not doc_info.file_bytes:
            continue
        safe_name = _safe_filename(doc_info.filename)
        try:
            with open(docs_dir / safe_name, "wb") as f:
                f.write(doc_info.file_bytes)
        except Exception as exc:
            logger.warning(f"Failed to save source document {safe_name}: {exc}")

    manifest = {
        "documents": [
            {"filename": _safe_filename(d.filename), "type": d.file_type}
            for d in documents
        ]
    }
    try:
        with open(docs_dir / "documents_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as exc:
        logger.warning(f"Failed to save source documents manifest: {exc}")


def _save_code_snapshot(run_dir: Path, stage: str, code: str) -> None:
    """Save generated code snapshot."""
    snapshot_file = run_dir / "code_snapshots" / f"{stage}_document_code.py"
    try:
        with open(snapshot_file, "w", encoding="utf-8") as f:
            f.write(code)
    except Exception as exc:
        logger.warning(f"Failed to save code snapshot {snapshot_file.name}: {exc}")


def _chunk_sections(sections: list, max_sections: int) -> list[list]:
    """Chunk sections list by max size."""
    if max_sections <= 0:
        return [sections]
    return [sections[i:i + max_sections] for i in range(0, len(sections), max_sections)]


def _parse_json_model(value: Optional[str], model_cls: type[ModelT], field_name: str) -> Optional[ModelT]:
    """Parse JSON from form field and validate against a pydantic model."""
    if value is None or not value.strip():
        return None
    try:
        parsed = json.loads(value)
        return model_cls.model_validate(parsed)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON for {field_name}: {exc}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid schema for {field_name}: {exc}") from exc


def _parse_previous_requirements(value: Optional[str]) -> Optional[list[RFPRequirement]]:
    """Parse previous requirements JSON payload."""
    if value is None or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON for previous_requirements: {exc}") from exc
    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail="previous_requirements must be a JSON array.")
    try:
        return [RFPRequirement.model_validate(item) for item in parsed]
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid requirement schema: {exc}") from exc


async def _extract_context_from_files(
    company_context: Optional[list[UploadFile]],
    pdf_service: PDFService,
) -> tuple[Optional[str], list[DocumentInfo]]:
    """Extract text from optional context PDFs for planning."""
    if not company_context:
        return None, []

    _validate_pdf_files(company_context)

    context_parts: list[str] = []
    documents: list[DocumentInfo] = []
    for idx, ctx in enumerate(company_context):
        ctx_bytes = await ctx.read()
        context_parts.append(pdf_service.extract_text_from_bytes(ctx_bytes))
        documents.append(
            DocumentInfo(
                filename=ctx.filename or f"context_{idx + 1}.pdf",
                file_type="context",
                file_bytes=ctx_bytes,
            )
        )

    context_text = "\n\n---\n\n".join(context_parts) if context_parts else None
    return context_text, documents


def _resolve_docx_download_path(run_id: str, filename: str) -> Path:
    """Resolve and validate docx download path."""
    safe_run_id = _validate_simple_path_part(run_id, "run_id")
    safe_filename = _validate_simple_path_part(filename, "filename")

    if not safe_filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only DOCX downloads allowed")

    config = get_config()
    output_root = Path(config.app.output_dir).resolve()
    file_path = (output_root / safe_run_id / "word_document" / safe_filename).resolve()

    if not file_path.is_relative_to(output_root):
        raise HTTPException(status_code=400, detail="Invalid download path")

    return file_path


async def _process_documents(
    rfp: UploadFile,
    example_rfps: list[UploadFile],
    company_context: list[UploadFile] | None,
    features: FeaturesConfig,
    pdf_service: PDFService,
    store_documents: bool = True,
) -> ProcessedDocuments:
    """
    Process uploaded PDF documents and extract text/images.
    
    Shared logic between streaming and non-streaming endpoints.
    
    Args:
        store_documents: If True, include file bytes in DocumentInfo for storage.
    """
    image_budgets = _allocate_image_budgets(
        features,
        len(example_rfps),
        1,
        len(company_context or []),
    )
    
    # Collect document info for storage
    documents: list[DocumentInfo] = []
    
    # Read RFP
    logger.info(f"Processing RFP: {rfp.filename}")
    rfp_bytes = await rfp.read()
    rfp_text = pdf_service.extract_text_from_bytes(rfp_bytes)
    
    if store_documents:
        documents.append(DocumentInfo(
            filename=rfp.filename or "rfp.pdf",
            file_type="rfp",
            file_bytes=rfp_bytes
        ))
    
    rfp_images = None
    if features.enable_images and image_budgets["rfp"] > 0:
        rfp_images = pdf_service.pdf_to_base64_images(
            rfp_bytes,
            max_pages=image_budgets["rfp"],
            min_table_rows=features.min_table_rows,
            min_table_cols=features.min_table_cols,
        )
    
    # Read example RFPs
    example_texts = []
    example_images = []
    for idx, ex in enumerate(example_rfps):
        logger.info(f"Processing example: {ex.filename}")
        ex_bytes = await ex.read()
        example_texts.append(pdf_service.extract_text_from_bytes(ex_bytes))
        
        if store_documents:
            documents.append(DocumentInfo(
                filename=ex.filename or f"example_{idx+1}.pdf",
                file_type="example",
                file_bytes=ex_bytes
            ))
        
        if features.enable_images and image_budgets["examples_per_doc"] > 0:
            example_images.append(
                pdf_service.pdf_to_base64_images(
                    ex_bytes,
                    max_pages=image_budgets["examples_per_doc"],
                    min_table_rows=features.min_table_rows,
                    min_table_cols=features.min_table_cols,
                )
            )
    
    # Read company context
    context_text = None
    context_images = None
    if company_context:
        context_parts = []
        context_imgs = []
        for idx, ctx in enumerate(company_context):
            logger.info(f"Processing context: {ctx.filename}")
            ctx_bytes = await ctx.read()
            context_parts.append(pdf_service.extract_text_from_bytes(ctx_bytes))
            
            if store_documents:
                documents.append(DocumentInfo(
                    filename=ctx.filename or f"context_{idx+1}.pdf",
                    file_type="context",
                    file_bytes=ctx_bytes
                ))
            
            if features.enable_images and image_budgets["context_per_doc"] > 0:
                context_imgs.extend(
                    pdf_service.pdf_to_base64_images(
                        ctx_bytes,
                        max_pages=image_budgets["context_per_doc"],
                        min_table_rows=features.min_table_rows,
                        min_table_cols=features.min_table_cols,
                    )
                )
        
        context_text = "\n\n---\n\n".join(context_parts)
        context_images = context_imgs if context_imgs else None
    
    return ProcessedDocuments(
        rfp_text=rfp_text,
        rfp_images=rfp_images,
        example_texts=example_texts,
        example_images=example_images if example_images else None,
        context_text=context_text,
        context_images=context_images,
        documents=documents,
    )


def _build_workflow_input(
    docs: ProcessedDocuments,
    *,
    enable_planner: Optional[bool] = None,
    enable_critiquer: Optional[bool] = None,
    generator_formatting_injection: Optional[str] = None,
    generator_intro_pages: Optional[int] = None,
    generation_page_overlap: Optional[int] = None,
    toggle_generation_chunking: Optional[bool] = None,
    max_tokens_generation_chunking: Optional[int] = None,
    max_sections_per_chunk: Optional[int] = None,
    extract_reqs_comment: Optional[str] = None,
    previous_requirements: Optional[list[RFPRequirement]] = None,
    plan_comment: Optional[str] = None,
    previous_plan: Optional[ProposalPlan] = None,
    generate_rfp_comment: Optional[str] = None,
    previous_document_code: Optional[str] = None,
    critique_comment: Optional[str] = None,
) -> WorkflowInput:
    """Build a WorkflowInput object from processed document content."""
    return WorkflowInput(
        rfp_text=docs.rfp_text,
        rfp_images=docs.rfp_images,
        example_rfps_text=docs.example_texts,
        example_rfps_images=docs.example_images,
        company_context_text=docs.context_text,
        company_context_images=docs.context_images,
        enable_planner=enable_planner,
        enable_critiquer=enable_critiquer,
        generator_formatting_injection=generator_formatting_injection,
        generator_intro_pages=generator_intro_pages,
        generation_page_overlap=generation_page_overlap,
        toggle_generation_chunking=toggle_generation_chunking,
        max_tokens_generation_chunking=max_tokens_generation_chunking,
        max_sections_per_chunk=max_sections_per_chunk,
        extract_reqs_comment=extract_reqs_comment,
        previous_requirements=previous_requirements,
        plan_comment=plan_comment,
        previous_plan=previous_plan,
        generate_rfp_comment=generate_rfp_comment,
        previous_document_code=previous_document_code,
        critique_comment=critique_comment,
        documents=docs.documents,
    )


async def _run_orchestrated_generation(
    rfp: UploadFile,
    example_rfps: list[UploadFile],
    company_context: Optional[list[UploadFile]],
    enable_planner: Optional[bool],
    enable_critiquer: Optional[bool],
    generator_formatting_injection: Optional[str],
    generator_intro_pages: Optional[int],
    generation_page_overlap: Optional[int],
    toggle_generation_chunking: Optional[bool],
    max_tokens_generation_chunking: Optional[int],
    max_sections_per_chunk: Optional[int],
) -> GenerateRFPResponse:
    """Shared orchestrated flow implementation."""
    start_time = time.time()
    config = get_config()
    pdf_service = PDFService()

    all_files = [rfp] + example_rfps + (company_context or [])
    _validate_pdf_files(all_files)

    docs = await _process_documents(
        rfp,
        example_rfps,
        company_context,
        config.features,
        pdf_service,
    )

    workflow_input = _build_workflow_input(
        docs,
        enable_planner=enable_planner,
        enable_critiquer=enable_critiquer,
        generator_formatting_injection=generator_formatting_injection,
        generator_intro_pages=generator_intro_pages,
        generation_page_overlap=generation_page_overlap,
        toggle_generation_chunking=toggle_generation_chunking,
        max_tokens_generation_chunking=max_tokens_generation_chunking,
        max_sections_per_chunk=max_sections_per_chunk,
    )

    logger.info("Starting orchestrated RFP workflow")
    workflow = create_rfp_workflow()
    result = await workflow.run(workflow_input)

    processing_time = time.time() - start_time
    docx_path = Path(result.docx_path) if result.docx_path else None
    if docx_path:
        run_id = docx_path.parent.parent.name
        docx_filename = docx_path.name
    else:
        run_id = "unknown"
        docx_filename = "proposal.docx"

    return GenerateRFPResponse(
        success=True,
        message="RFP response generated successfully",
        rfp_response=result.response,
        analysis=result.analysis,
        docx_download_url=f"/api/rfp/download/{run_id}/{docx_filename}",
        processing_time_seconds=round(processing_time, 2),
    )


@router.post("/generate", response_model=GenerateRFPResponse)
async def generate_rfp(
    rfp: UploadFile = File(..., description="The RFP document to respond to (PDF)"),
    example_rfps: list[UploadFile] = File(
        ...,
        description="Example RFP responses for style reference (PDF)",
    ),
    company_context: Optional[list[UploadFile]] = File(
        None,
        description="Company context documents (PDF)",
    ),
    enable_planner: Optional[bool] = Form(None),
    enable_critiquer: Optional[bool] = Form(None),
    generator_formatting_injection: Optional[str] = Form(None),
    generator_intro_pages: Optional[int] = Form(None),
    generation_page_overlap: Optional[int] = Form(None),
    toggle_generation_chunking: Optional[bool] = Form(None),
    max_tokens_generation_chunking: Optional[int] = Form(None),
    max_sections_per_chunk: Optional[int] = Form(None),
    _: Optional[str] = Depends(verify_api_token),
):
    """Legacy orchestrated endpoint kept for compatibility."""
    try:
        return await _run_orchestrated_generation(
            rfp=rfp,
            example_rfps=example_rfps,
            company_context=company_context,
            enable_planner=enable_planner,
            enable_critiquer=enable_critiquer,
            generator_formatting_injection=generator_formatting_injection,
            generator_intro_pages=generator_intro_pages,
            generation_page_overlap=generation_page_overlap,
            toggle_generation_chunking=toggle_generation_chunking,
            max_tokens_generation_chunking=max_tokens_generation_chunking,
            max_sections_per_chunk=max_sections_per_chunk,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("RFP generation failed")
        raise HTTPException(status_code=500, detail=f"RFP generation failed: {exc}") from exc


@router.post("/orchestrate", response_model=GenerateRFPResponse)
async def orchestrate_rfp(
    source_rfp: UploadFile = File(..., description="The RFP document to respond to (PDF)"),
    example_rfps: list[UploadFile] = File(
        ...,
        description="Example RFP responses for style reference (PDF)",
    ),
    company_context: Optional[list[UploadFile]] = File(
        None,
        description="Company context documents (PDF)",
    ),
    enable_planner: Optional[bool] = Form(None),
    enable_critiquer: Optional[bool] = Form(None),
    generator_formatting_injection: Optional[str] = Form(None),
    generator_intro_pages: Optional[int] = Form(None),
    generation_page_overlap: Optional[int] = Form(None),
    toggle_generation_chunking: Optional[bool] = Form(None),
    max_tokens_generation_chunking: Optional[int] = Form(None),
    max_sections_per_chunk: Optional[int] = Form(None),
    _: Optional[str] = Depends(verify_api_token),
):
    """New orchestrated endpoint using snake_case parameter names."""
    try:
        return await _run_orchestrated_generation(
            rfp=source_rfp,
            example_rfps=example_rfps,
            company_context=company_context,
            enable_planner=enable_planner,
            enable_critiquer=enable_critiquer,
            generator_formatting_injection=generator_formatting_injection,
            generator_intro_pages=generator_intro_pages,
            generation_page_overlap=generation_page_overlap,
            toggle_generation_chunking=toggle_generation_chunking,
            max_tokens_generation_chunking=max_tokens_generation_chunking,
            max_sections_per_chunk=max_sections_per_chunk,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("RFP orchestration failed")
        raise HTTPException(status_code=500, detail=f"RFP orchestration failed: {exc}") from exc


def _allocate_image_budgets(features, example_count: int, rfp_count: int, context_count: int) -> dict[str, int]:
    total = max(0, int(features.max_images))
    ratios = features.normalized_image_ratios(
        include_examples=example_count > 0,
        include_rfp=rfp_count > 0,
        include_context=context_count > 0,
    )
    targets = {
        "examples": ratios["examples"] * total,
        "rfp": ratios["rfp"] * total,
        "context": ratios["context"] * total,
    }
    floors = {key: int(value) for key, value in targets.items()}
    remainder = total - sum(floors.values())
    if remainder > 0:
        order = sorted(
            targets.items(),
            key=lambda item: (item[1] - floors[item[0]]),
            reverse=True,
        )
        for key, _ in order:
            if remainder <= 0:
                break
            floors[key] += 1
            remainder -= 1
    examples_per_doc = floors["examples"] // example_count if example_count else 0
    context_per_doc = floors["context"] // context_count if context_count else 0
    return {
        "examples": floors["examples"],
        "rfp": floors["rfp"],
        "context": floors["context"],
        "examples_per_doc": examples_per_doc,
        "context_per_doc": context_per_doc,
    }


@router.post("/extract-reqs", response_model=ExtractReqsResponse)
async def extract_reqs(
    source_rfp: UploadFile = File(..., description="RFP PDF to extract requirements from"),
    company_context: Optional[list[UploadFile]] = File(None, description="Optional company context PDFs"),
    comment: Optional[str] = Form(None, description="Optional guidance for regeneration"),
    previous_requirements: Optional[str] = Form(
        None,
        description="Optional JSON array of previously generated requirements",
    ),
    _: Optional[str] = Depends(verify_api_token),
):
    """Extract requirements from an RFP with optional regeneration context."""
    config = get_config()
    pdf_service = PDFService()
    _validate_pdf_files([source_rfp] + (company_context or []))

    previous_reqs = _parse_previous_requirements(previous_requirements)
    docs = await _process_documents(
        source_rfp,
        [],
        company_context,
        config.features,
        pdf_service,
    )

    run_dir = _create_step_run_directory()
    _save_documents(run_dir, docs.documents)

    client = create_llm_client()
    analyzer = RFPAnalyzerExecutor(client, run_dir)
    input_data = _build_workflow_input(
        docs,
        extract_reqs_comment=comment,
        previous_requirements=previous_reqs,
    )

    try:
        analysis_result = await analyzer.execute(input_data)
        return ExtractReqsResponse(
            success=True,
            message="Requirements extracted successfully",
            analysis=analysis_result.analysis,
        )
    except Exception as exc:
        logger.exception("Requirement extraction failed")
        raise HTTPException(status_code=500, detail=f"Requirement extraction failed: {exc}") from exc


@router.post("/plan", response_model=PlanStepResponse)
async def plan_rfp(
    request: PlanStepRequest,
    _: Optional[str] = Depends(verify_api_token),
):
    """Generate a proposal plan from extracted requirements."""
    run_dir = _create_step_run_directory()
    client = create_llm_client()
    planner = PlannerExecutor(client, run_dir)

    input_data = WorkflowInput(
        rfp_text="",
        company_context_text=request.company_context_text,
        plan_comment=request.comment,
        previous_plan=request.previous_plan,
    )

    try:
        planning_result = await planner.execute(input_data, request.analysis)
        return PlanStepResponse(
            success=True,
            message="Plan generated successfully",
            plan=planning_result.plan,
        )
    except Exception as exc:
        logger.exception("Plan generation failed")
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {exc}") from exc


@router.post("/plan-with-context", response_model=PlanStepResponse)
async def plan_rfp_with_context(
    analysis_json: str = Form(..., description="JSON for RFPAnalysis"),
    company_context_text: Optional[str] = Form(None, description="Optional free-text planning context"),
    company_context: Optional[list[UploadFile]] = File(None, description="Optional context PDFs"),
    comment: Optional[str] = Form(None, description="Optional guidance for planning/regeneration"),
    previous_plan_json: Optional[str] = Form(None, description="Optional JSON for ProposalPlan"),
    _: Optional[str] = Depends(verify_api_token),
):
    """Generate a proposal plan using analysis + optional context PDFs + optional context text."""
    try:
        analysis = RFPAnalysis.model_validate_json(analysis_json)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid analysis_json schema: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid analysis_json: {exc}") from exc

    previous_plan = _parse_json_model(previous_plan_json, ProposalPlan, "previous_plan_json")

    pdf_service = PDFService()
    context_pdf_text, context_docs = await _extract_context_from_files(company_context, pdf_service)

    context_parts = []
    if company_context_text and company_context_text.strip():
        context_parts.append(company_context_text.strip())
    if context_pdf_text and context_pdf_text.strip():
        context_parts.append(context_pdf_text.strip())
    combined_context = "\n\n---\n\n".join(context_parts) if context_parts else None

    run_dir = _create_step_run_directory()
    _save_documents(run_dir, context_docs)

    client = create_llm_client()
    planner = PlannerExecutor(client, run_dir)
    input_data = WorkflowInput(
        rfp_text="",
        company_context_text=combined_context,
        plan_comment=comment,
        previous_plan=previous_plan,
        documents=context_docs,
    )

    try:
        planning_result = await planner.execute(input_data, analysis)
        return PlanStepResponse(
            success=True,
            message="Plan generated successfully",
            plan=planning_result.plan,
        )
    except Exception as exc:
        logger.exception("Plan generation (with context) failed")
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {exc}") from exc


@router.post("/generate-rfp", response_model=GenerateRFPStepResponse)
async def generate_rfp_step(
    source_rfp: UploadFile = File(..., description="RFP PDF to generate against"),
    example_rfps: list[UploadFile] = File(..., description="Style reference PDFs"),
    company_context: Optional[list[UploadFile]] = File(None, description="Optional company context PDFs"),
    analysis_json: str = Form(..., description="JSON for RFPAnalysis"),
    plan_json: Optional[str] = Form(None, description="Optional JSON for ProposalPlan"),
    comment: Optional[str] = Form(None, description="Optional guidance for regeneration"),
    previous_document_code: Optional[str] = Form(
        None,
        description="Optional previous generated code for iterative regeneration",
    ),
    generator_formatting_injection: Optional[str] = Form(None),
    generator_intro_pages: Optional[int] = Form(None),
    generation_page_overlap: Optional[int] = Form(None),
    toggle_generation_chunking: Optional[bool] = Form(None),
    max_tokens_generation_chunking: Optional[int] = Form(None),
    max_sections_per_chunk: Optional[int] = Form(None),
    _: Optional[str] = Depends(verify_api_token),
):
    """
    Generate and execute proposal code.

    Returns both executable code and a base64 DOCX payload.
    """
    config = get_config()
    pdf_service = PDFService()
    _validate_pdf_files([source_rfp] + example_rfps + (company_context or []))

    try:
        analysis = RFPAnalysis.model_validate_json(analysis_json)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid analysis_json schema: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid analysis_json: {exc}") from exc

    plan = _parse_json_model(plan_json, ProposalPlan, "plan_json")
    docs = await _process_documents(
        source_rfp,
        example_rfps,
        company_context,
        config.features,
        pdf_service,
    )

    run_dir = _create_step_run_directory()
    _save_documents(run_dir, docs.documents)

    client = create_llm_client()
    generator = SectionGeneratorExecutor(client, run_dir)
    code_interpreter = CodeInterpreterExecutor(client, run_dir)

    input_data = _build_workflow_input(
        docs,
        generator_formatting_injection=generator_formatting_injection,
        generator_intro_pages=generator_intro_pages,
        generation_page_overlap=generation_page_overlap,
        toggle_generation_chunking=toggle_generation_chunking,
        max_tokens_generation_chunking=max_tokens_generation_chunking,
        max_sections_per_chunk=max_sections_per_chunk,
        generate_rfp_comment=comment,
        previous_document_code=previous_document_code,
    )

    try:
        if plan:
            chunking_enabled = (
                toggle_generation_chunking
                if toggle_generation_chunking is not None
                else config.features.toggle_generation_chunking
            )

            if chunking_enabled and plan.sections:
                max_sections = (
                    max_sections_per_chunk
                    if max_sections_per_chunk is not None
                    else config.features.max_sections_per_chunk
                )
                section_chunks = _chunk_sections(plan.sections, max_sections)
                chunk_codes: list[str] = []
                for idx, chunk in enumerate(section_chunks, start=1):
                    chunk_result = await generator.execute_chunk_with_plan(
                        input_data,
                        analysis,
                        chunk,
                        part_number=idx,
                        total_parts=len(section_chunks),
                    )
                    _save_code_snapshot(run_dir, f"01_chunk_{idx}", chunk_result.response.document_code)
                    chunk_codes.append(chunk_result.response.document_code)
                generation_result = await generator.synthesize_from_chunks(input_data, chunk_codes)
                _save_code_snapshot(run_dir, "02_synthesized", generation_result.response.document_code)
            else:
                generation_result = await generator.execute_with_plan(input_data, analysis, plan)
                _save_code_snapshot(run_dir, "01_initial", generation_result.response.document_code)
        else:
            generation_result = await generator.execute(input_data, analysis)
            _save_code_snapshot(run_dir, "01_initial", generation_result.response.document_code)

        max_error_loops = config.workflow.max_error_loops
        current_response = generation_result.response
        docx_dir = run_dir / "word_document"
        image_dir = run_dir / "image_assets"
        docx_path = docx_dir / "proposal.docx"
        code_stats: dict = {}

        for error_loop in range(max_error_loops + 1):
            docx_path, code_stats = await code_interpreter.execute(
                current_response,
                image_dir=image_dir,
                docx_dir=docx_dir,
            )

            if code_stats.get("document_success"):
                break

            if error_loop < max_error_loops:
                error_msg = code_stats.get("errors", ["Unknown error"])[0]
                generation_result = await generator.execute_with_error(
                    input_data,
                    analysis,
                    current_response.document_code,
                    error_msg,
                )
                current_response = generation_result.response
                _save_code_snapshot(run_dir, f"03_error_recovery_{error_loop + 1}", current_response.document_code)

        _save_code_snapshot(run_dir, "99_final", current_response.document_code)

        docx_bytes = docx_path.read_bytes() if docx_path.exists() else b""
        docx_base64 = base64.b64encode(docx_bytes).decode("ascii")
        execution_success = bool(code_stats.get("document_success", False))

        return GenerateRFPStepResponse(
            success=execution_success,
            message="RFP generated and executed successfully" if execution_success else "RFP code generated, but execution failed",
            document_code=current_response.document_code,
            docx_base64=docx_base64,
            docx_filename="proposal.docx",
            execution_stats=code_stats,
            run_id=run_dir.name,
            docx_download_url=f"/api/rfp/download/{run_dir.name}/proposal.docx",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Generate RFP step failed")
        raise HTTPException(status_code=500, detail=f"Generate RFP step failed: {exc}") from exc


@router.post("/critique", response_model=CritiqueStepResponse)
async def critique_rfp(
    request: CritiqueStepRequest,
    _: Optional[str] = Depends(verify_api_token),
):
    """Critique generated code with optional user guidance."""
    run_dir = _create_step_run_directory()
    client = create_llm_client()
    critiquer = CritiquerExecutor(client, run_dir)
    try:
        critique_result = await critiquer.execute(
            request.analysis,
            request.document_code,
            comment=request.comment,
        )
        return CritiqueStepResponse(
            success=True,
            message="Critique completed successfully",
            critique=critique_result.critique,
        )
    except Exception as exc:
        logger.exception("Critique step failed")
        raise HTTPException(status_code=500, detail=f"Critique step failed: {exc}") from exc


@router.get("/download/{run_id}/{filename}")
async def download_file(run_id: str, filename: str):
    """Download a generated DOCX file from a run directory."""
    file_path = _resolve_docx_download_path(run_id, filename)
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@router.post("/generate/stream")
async def generate_rfp_stream(
    rfp: UploadFile = File(...),
    example_rfps: list[UploadFile] = File(...),
    company_context: Optional[list[UploadFile]] = File(None),
    enable_planner: Optional[bool] = Form(None),
    enable_critiquer: Optional[bool] = Form(None),
    generator_formatting_injection: Optional[str] = Form(None),
    generator_intro_pages: Optional[int] = Form(None),
    generation_page_overlap: Optional[int] = Form(None),
    toggle_generation_chunking: Optional[bool] = Form(None),
    max_tokens_generation_chunking: Optional[int] = Form(None),
    max_sections_per_chunk: Optional[int] = Form(None),
):
    """
    Generate an RFP response with streaming progress events.
    
    Returns Server-Sent Events (SSE) with workflow progress.
    """
    config = get_config()
    pdf_service = PDFService()
    _validate_pdf_files([rfp] + example_rfps + (company_context or []))
    
    async def event_generator():
        try:
            # Process files using shared function
            yield f"data: {json.dumps({'event': 'processing', 'message': 'Reading documents...'})}\n\n"
            
            docs = await _process_documents(
                rfp, example_rfps, company_context,
                config.features, pdf_service
            )
            
            workflow_input = _build_workflow_input(
                docs,
                enable_planner=enable_planner,
                enable_critiquer=enable_critiquer,
                generator_formatting_injection=generator_formatting_injection,
                generator_intro_pages=generator_intro_pages,
                generation_page_overlap=generation_page_overlap,
                toggle_generation_chunking=toggle_generation_chunking,
                max_tokens_generation_chunking=max_tokens_generation_chunking,
                max_sections_per_chunk=max_sections_per_chunk,
            )
            
            # Run workflow with streaming
            workflow = create_rfp_workflow()
            run_id = None
            async for event in workflow.run_stream(workflow_input):
                yield f"data: {json.dumps({'event': event.event_type, 'step': event.step_name, 'message': event.message, 'data': event.data})}\n\n"
                # Capture run_id from the finished event
                if event.event_type == "finished" and event.data:
                    run_id = event.data.get("run_id") or event.data.get("run_dir", "").split("/")[-1] or event.data.get("run_dir", "").split("\\")[-1]
            
            # Send final download URL using run_id from workflow
            if run_id:
                yield f"data: {json.dumps({'event': 'complete', 'download_url': f'/api/rfp/download/{run_id}/proposal.docx', 'run_id': run_id})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.post("/orchestrate/stream")
async def orchestrate_rfp_stream(
    source_rfp: UploadFile = File(...),
    example_rfps: list[UploadFile] = File(...),
    company_context: Optional[list[UploadFile]] = File(None),
    enable_planner: Optional[bool] = Form(None),
    enable_critiquer: Optional[bool] = Form(None),
    generator_formatting_injection: Optional[str] = Form(None),
    generator_intro_pages: Optional[int] = Form(None),
    generation_page_overlap: Optional[int] = Form(None),
    toggle_generation_chunking: Optional[bool] = Form(None),
    max_tokens_generation_chunking: Optional[int] = Form(None),
    max_sections_per_chunk: Optional[int] = Form(None),
):
    """Snake_case alias for orchestrated streaming generation."""
    return await generate_rfp_stream(
        rfp=source_rfp,
        example_rfps=example_rfps,
        company_context=company_context,
        enable_planner=enable_planner,
        enable_critiquer=enable_critiquer,
        generator_formatting_injection=generator_formatting_injection,
        generator_intro_pages=generator_intro_pages,
        generation_page_overlap=generation_page_overlap,
        toggle_generation_chunking=toggle_generation_chunking,
        max_tokens_generation_chunking=max_tokens_generation_chunking,
        max_sections_per_chunk=max_sections_per_chunk,
    )
