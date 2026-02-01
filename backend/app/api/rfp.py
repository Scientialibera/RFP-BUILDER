"""
RFP Generation API endpoints.
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Depends, Form
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import get_config, FeaturesConfig
from app.core.auth import verify_api_token
from app.models.schemas import GenerateRFPResponse
from app.services.pdf_service import PDFService
from app.workflows.rfp_workflow import create_rfp_workflow
from app.workflows.state import WorkflowInput, DocumentInfo


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rfp", tags=["RFP"])


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


@router.post("/generate", response_model=GenerateRFPResponse)
async def generate_rfp(
    background_tasks: BackgroundTasks,
    rfp: UploadFile = File(..., description="The RFP document to respond to (PDF)"),
    example_rfps: list[UploadFile] = File(
        ..., 
        description="Example RFP responses for style reference (PDF)"
    ),
    company_context: Optional[list[UploadFile]] = File(
        None, 
        description="Company context documents (PDF)"
    ),
    enable_planner: Optional[bool] = Form(
        None, description="Enable proposal planning before generation (overrides config)"
    ),
    enable_critiquer: Optional[bool] = Form(
        None, description="Enable code critique and revision loop (overrides config)"
    ),
    generator_formatting_injection: Optional[str] = Form(
        None, description="Override formatting injection prompt for generator"
    ),
    generator_intro_pages: Optional[int] = Form(
        None, description="Number of intro RFP pages to always include in generator context"
    ),
    generation_page_overlap: Optional[int] = Form(
        None, description="Page overlap added around cited pages during generation chunking"
    ),
    toggle_generation_chunking: Optional[bool] = Form(
        None, description="Enable generation chunking (requires planner)"
    ),
    max_tokens_generation_chunking: Optional[int] = Form(
        None, description="Max tokens for generation chunk context"
    ),
    max_sections_per_chunk: Optional[int] = Form(
        None, description="Max sections per generation chunk"
    ),
    _: Optional[str] = Depends(verify_api_token),
):
    """
    Generate an RFP response based on the provided RFP and example responses.
    
    This endpoint:
    1. Analyzes the RFP to extract requirements
    2. Uses example RFPs as style/format references
    3. Incorporates company context if provided
    4. Generates python-docx code to create the proposal
    5. Executes the code to create the Word document
    
    Args:
        rfp: The RFP document to respond to (required)
        example_rfps: One or more example RFP responses (required)
        company_context: Company capability documents (optional)
        
    Returns:
        GenerateRFPResponse with document download URL
    """
    start_time = time.time()
    config = get_config()
    pdf_service = PDFService()
    
    # Create upload directory for temp files
    job_id = str(uuid.uuid4())
    upload_dir = Path(config.app.upload_dir) / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Validate file types
        all_files = [rfp] + example_rfps + (company_context or [])
        for file in all_files:
            if file.filename and not file.filename.lower().endswith('.pdf'):
                raise HTTPException(
                    status_code=400,
                    detail=f"Only PDF files are allowed. Got: {file.filename}"
                )
        
        # Process documents using shared function
        docs = await _process_documents(
            rfp, example_rfps, company_context,
            config.features, pdf_service
        )
        
        # Build workflow input
        workflow_input = WorkflowInput(
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
            documents=docs.documents,
        )
        
        # Run workflow - returns FinalResult with docx_path
        logger.info("Starting RFP workflow")
        workflow = create_rfp_workflow()
        result = await workflow.run(workflow_input)
        
        processing_time = time.time() - start_time
        
        # Extract run_id and filename from docx_path (e.g., outputs/runs/run_20260201_123456/word_document/proposal.docx)
        docx_path = Path(result.docx_path) if result.docx_path else None
        if docx_path:
            # Get run directory name (e.g., "run_20260201_123456")
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
            processing_time_seconds=round(processing_time, 2)
        )
        
    except Exception as e:
        logger.exception("RFP generation failed")
        raise HTTPException(
            status_code=500,
            detail=f"RFP generation failed: {str(e)}"
        )


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


@router.get("/download/{run_id}/{filename}")
async def download_file(run_id: str, filename: str):
    """Download a generated DOCX file from a run directory."""
    config = get_config()
    # Files are in outputs/runs/{run_id}/word_document/
    file_path = Path(config.app.output_dir) / run_id / "word_document" / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    if not filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="Only DOCX downloads allowed")
    
    return FileResponse(
        path=file_path,
        filename=filename,
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
    import json
    
    config = get_config()
    pdf_service = PDFService()
    
    async def event_generator():
        try:
            # Process files using shared function
            yield f"data: {json.dumps({'event': 'processing', 'message': 'Reading documents...'})}\n\n"
            
            docs = await _process_documents(
                rfp, example_rfps, company_context,
                config.features, pdf_service
            )
            
            workflow_input = WorkflowInput(
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
                documents=docs.documents,
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
