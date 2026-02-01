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
from app.services.diagram_service import DiagramService
from app.services.pdf_generator import PDFGeneratorService
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
    4. Generates a structured proposal response
    5. Returns the response with a downloadable PDF
    
    Args:
        rfp: The RFP document to respond to (required)
        example_rfps: One or more example RFP responses (required)
        company_context: Company capability documents (optional)
        
    Returns:
        GenerateRFPResponse with sections and PDF download URL
    """
    start_time = time.time()
    config = get_config()
    pdf_service = PDFService()
    diagram_service = DiagramService()
    
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
        if config.features.enable_images:
            rfp_images = pdf_service.pdf_to_base64_images(rfp_bytes, max_pages=10)
        
        # Read example RFPs
        example_texts = []
        example_images = []
        for ex in example_rfps:
            logger.info(f"Processing example: {ex.filename}")
            ex_bytes = await ex.read()
            example_texts.append(pdf_service.extract_text_from_bytes(ex_bytes))
            
            if config.features.enable_images:
                example_images.append(
                    pdf_service.pdf_to_base64_images(ex_bytes, max_pages=5)
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
                
                if config.features.enable_images:
                    context_imgs.extend(
                        pdf_service.pdf_to_base64_images(ctx_bytes, max_pages=3)
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
        
        # Run workflow
        logger.info("Starting RFP workflow")
        workflow = create_rfp_workflow()
        result = await workflow.run(workflow_input)
        
        # Process diagrams in response
        processed_sections = []
        for section in result.response.sections:
            content = section.section_content
            
            # Check for mermaid blocks
            if '```mermaid' in content and diagram_service.is_available():
                content, png_paths = diagram_service.process_content_diagrams(
                    content,
                    output_dir,
                    base_name=f"diagram_{section.section_title.replace(' ', '_')}"
                )
                # Update section with processed content
                section.section_content = content
            
            processed_sections.append(section)
        
        result.response.sections = processed_sections
        
        # Generate PDF
        pdf_generator = PDFGeneratorService()
        pdf_path = output_dir / "rfp_response.pdf"
        pdf_generator.generate_pdf(
            result.response.sections,
            output_path=pdf_path,
            title="RFP Response",
            image_dir=output_dir
        )
        
        processing_time = time.time() - start_time
        
        return GenerateRFPResponse(
            success=True,
            message="RFP response generated successfully",
            rfp_response=result.response,
            analysis=result.analysis,
            pdf_download_url=f"/api/rfp/download/{job_id}/rfp_response.pdf",
            processing_time_seconds=round(processing_time, 2)
        )
        
    except Exception as e:
        logger.exception("RFP generation failed")
        raise HTTPException(
            status_code=500,
            detail=f"RFP generation failed: {str(e)}"
        )


@router.get("/download/{job_id}/{filename}")
async def download_pdf(job_id: str, filename: str):
    """Download a generated PDF file."""
    config = get_config()
    output_dir = Path(config.app.output_dir) / job_id
    file_path = output_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    if not filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF downloads allowed")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/pdf"
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
        try:
            # Process files (same as above)
            yield f"data: {json.dumps({'event': 'processing', 'message': 'Reading documents...'})}\n\n"
            
            rfp_bytes = await rfp.read()
            rfp_text = pdf_service.extract_text_from_bytes(rfp_bytes)
            rfp_images = None
            if config.features.enable_images:
                rfp_images = pdf_service.pdf_to_base64_images(rfp_bytes, max_pages=10)
            
            example_texts = []
            example_images = []
            for ex in example_rfps:
                ex_bytes = await ex.read()
                example_texts.append(pdf_service.extract_text_from_bytes(ex_bytes))
                if config.features.enable_images:
                    example_images.append(pdf_service.pdf_to_base64_images(ex_bytes, max_pages=5))
            
            context_text = None
            if company_context:
                parts = []
                for ctx in company_context:
                    ctx_bytes = await ctx.read()
                    parts.append(pdf_service.extract_text_from_bytes(ctx_bytes))
                context_text = "\n\n---\n\n".join(parts)
            
            workflow_input = WorkflowInput(
                rfp_text=rfp_text,
                rfp_images=rfp_images,
                example_rfps_text=example_texts,
                example_rfps_images=example_images if example_images else None,
                company_context_text=context_text,
            )
            
            # Run workflow with streaming
            workflow = create_rfp_workflow()
            async for event in workflow.run_stream(workflow_input):
                yield f"data: {json.dumps({'event': event.event_type, 'step': event.step_name, 'message': event.message, 'data': event.data})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
