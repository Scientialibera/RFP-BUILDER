"""
RFP Generation API endpoints.
"""

import time
import uuid
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import get_config
from app.models.schemas import GenerateRFPResponse
from app.services.pdf_service import PDFService
from app.workflows.rfp_workflow import create_rfp_workflow
from app.workflows.state import WorkflowInput


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rfp", tags=["RFP"])


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
    
    # Create temp directories
    job_id = str(uuid.uuid4())
    upload_dir = Path(config.app.upload_dir) / job_id
    output_dir = Path(config.app.output_dir) / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Validate file types
        all_files = [rfp] + example_rfps + (company_context or [])
        for file in all_files:
            if file.filename and not file.filename.lower().endswith('.pdf'):
                raise HTTPException(
                    status_code=400,
                    detail=f"Only PDF files are allowed. Got: {file.filename}"
                )
        
        # Read RFP
        logger.info(f"Processing RFP: {rfp.filename}")
        rfp_bytes = await rfp.read()
        rfp_text = pdf_service.extract_text_from_bytes(rfp_bytes)
        
        rfp_images = None
        image_budgets = _allocate_image_budgets(
            config.features,
            len(example_rfps),
            1,
            len(company_context or []),
        )
        if config.features.enable_images and image_budgets["rfp"] > 0:
            rfp_images = pdf_service.pdf_to_base64_images(
                rfp_bytes,
                max_pages=image_budgets["rfp"],
                min_table_rows=config.features.min_table_rows,
                min_table_cols=config.features.min_table_cols,
            )
        
        # Read example RFPs
        example_texts = []
        example_images = []
        for ex in example_rfps:
            logger.info(f"Processing example: {ex.filename}")
            ex_bytes = await ex.read()
            example_texts.append(pdf_service.extract_text_from_bytes(ex_bytes))
            
            if config.features.enable_images and image_budgets["examples_per_doc"] > 0:
                example_images.append(
                    pdf_service.pdf_to_base64_images(
                        ex_bytes,
                        max_pages=image_budgets["examples_per_doc"],
                        min_table_rows=config.features.min_table_rows,
                        min_table_cols=config.features.min_table_cols,
                    )
                )
        
        # Read company context
        context_text = None
        context_images = None
        if company_context:
            context_parts = []
            context_imgs = []
            for ctx in company_context:
                logger.info(f"Processing context: {ctx.filename}")
                ctx_bytes = await ctx.read()
                context_parts.append(pdf_service.extract_text_from_bytes(ctx_bytes))
                
                if config.features.enable_images and image_budgets["context_per_doc"] > 0:
                    context_imgs.extend(
                        pdf_service.pdf_to_base64_images(
                            ctx_bytes,
                            max_pages=image_budgets["context_per_doc"],
                            min_table_rows=config.features.min_table_rows,
                            min_table_cols=config.features.min_table_cols,
                        )
                    )
            
            context_text = "\n\n---\n\n".join(context_parts)
            context_images = context_imgs if context_imgs else None
        
        # Build workflow input
        workflow_input = WorkflowInput(
            rfp_text=rfp_text,
            rfp_images=rfp_images,
            example_rfps_text=example_texts,
            example_rfps_images=example_images if example_images else None,
            company_context_text=context_text,
            company_context_images=context_images,
        )
        
        # Run workflow - returns FinalResult with docx_path
        logger.info("Starting RFP workflow")
        workflow = create_rfp_workflow()
        result = await workflow.run(workflow_input, job_output_dir=output_dir)
        
        processing_time = time.time() - start_time
        
        # Get the filename from the docx_path
        docx_filename = Path(result.docx_path).name if result.docx_path else "proposal.docx"
        
        return GenerateRFPResponse(
            success=True,
            message="RFP response generated successfully",
            rfp_response=result.response,
            analysis=result.analysis,
            docx_download_url=f"/api/rfp/download/{job_id}/{docx_filename}",
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


@router.get("/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    """Download a generated file (DOCX)."""
    config = get_config()
    output_dir = Path(config.app.output_dir) / job_id
    file_path = output_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine media type based on extension
    if filename.endswith('.pdf'):
        media_type = "application/pdf"
    elif filename.endswith('.docx'):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX downloads allowed")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type
    )


@router.post("/generate/stream")
async def generate_rfp_stream(
    rfp: UploadFile = File(...),
    example_rfps: list[UploadFile] = File(...),
    company_context: Optional[list[UploadFile]] = File(None),
):
    """
    Generate an RFP response with streaming progress events.
    
    Returns Server-Sent Events (SSE) with workflow progress.
    """
    import json
    
    config = get_config()
    pdf_service = PDFService()
    
    async def event_generator():
        job_id = str(uuid.uuid4())
        output_dir = Path(config.app.output_dir) / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Process files
            yield f"data: {json.dumps({'event': 'processing', 'message': 'Reading documents...'})}\n\n"
            
            rfp_bytes = await rfp.read()
            rfp_text = pdf_service.extract_text_from_bytes(rfp_bytes)
            rfp_images = None
            image_budgets = _allocate_image_budgets(
                config.features,
                len(example_rfps),
                1,
                len(company_context or []),
            )
            if config.features.enable_images and image_budgets["rfp"] > 0:
                rfp_images = pdf_service.pdf_to_base64_images(
                    rfp_bytes,
                    max_pages=image_budgets["rfp"],
                    min_table_rows=config.features.min_table_rows,
                    min_table_cols=config.features.min_table_cols,
                )
            
            example_texts = []
            example_images = []
            for ex in example_rfps:
                ex_bytes = await ex.read()
                example_texts.append(pdf_service.extract_text_from_bytes(ex_bytes))
                if config.features.enable_images and image_budgets["examples_per_doc"] > 0:
                    example_images.append(
                        pdf_service.pdf_to_base64_images(
                            ex_bytes,
                            max_pages=image_budgets["examples_per_doc"],
                            min_table_rows=config.features.min_table_rows,
                            min_table_cols=config.features.min_table_cols,
                        )
                    )
            
            context_text = None
            context_images = None
            if company_context:
                parts = []
                context_imgs = []
                for ctx in company_context:
                    ctx_bytes = await ctx.read()
                    parts.append(pdf_service.extract_text_from_bytes(ctx_bytes))
                    if config.features.enable_images and image_budgets["context_per_doc"] > 0:
                        context_imgs.extend(
                            pdf_service.pdf_to_base64_images(
                                ctx_bytes,
                                max_pages=image_budgets["context_per_doc"],
                                min_table_rows=config.features.min_table_rows,
                                min_table_cols=config.features.min_table_cols,
                            )
                        )
                context_text = "\n\n---\n\n".join(parts)
                context_images = context_imgs if context_imgs else None
            
            workflow_input = WorkflowInput(
                rfp_text=rfp_text,
                rfp_images=rfp_images,
                example_rfps_text=example_texts,
                example_rfps_images=example_images if example_images else None,
                company_context_text=context_text,
                company_context_images=context_images,
            )
            
            # Run workflow with streaming
            workflow = create_rfp_workflow()
            async for event in workflow.run_stream(workflow_input, job_output_dir=output_dir):
                yield f"data: {json.dumps({'event': event.event_type, 'step': event.step_name, 'message': event.message, 'data': event.data})}\n\n"
            
            # Send final download URL
            yield f"data: {json.dumps({'event': 'complete', 'download_url': f'/api/rfp/download/{job_id}/proposal.docx'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
