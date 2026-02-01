"""
RFP Builder Workflow using Microsoft Agent Framework.
Orchestrates the sequential flow of RFP analysis, generation, and code execution.
"""

import logging
from pathlib import Path
from typing import Optional, AsyncIterator
from dataclasses import dataclass

from app.core.config import get_config
from app.core.llm_client import create_llm_client
from app.models.schemas import RFPResponse, RFPAnalysis
from .state import WorkflowInput, FinalResult
from .executors import (
    RFPAnalyzerExecutor,
    SectionGeneratorExecutor,
    CodeInterpreterExecutor,
)


logger = logging.getLogger(__name__)


@dataclass
class WorkflowEvent:
    """Event emitted during workflow execution."""
    event_type: str  # 'started', 'step_started', 'step_complete', 'error', 'finished'
    step_name: Optional[str] = None
    message: Optional[str] = None
    data: Optional[dict] = None


class RFPBuilderWorkflow:
    """
    Main workflow for RFP generation.
    
    This workflow follows a simple sequential pattern:
    1. Analyze RFP -> Extract requirements
    2. Generate Document Code -> Create python-docx code with diagram/chart definitions
    3. Execute Code -> Run Mermaid/Python code, then execute document code
    4. Return path to generated .docx file
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.config = get_config()
        self.client = create_llm_client()
        self.output_dir = output_dir or Path(self.config.app.output_dir)
        
        # Initialize executors with shared client
        self.analyzer = RFPAnalyzerExecutor(self.client)
        self.generator = SectionGeneratorExecutor(self.client)
        self.code_interpreter = CodeInterpreterExecutor(self.client, self.output_dir)
    
    async def run(self, input_data: WorkflowInput, job_output_dir: Optional[Path] = None) -> FinalResult:
        """
        Run the complete RFP workflow.
        
        Args:
            input_data: Workflow input with RFP and context.
            job_output_dir: Optional job-specific output directory for images.
            
        Returns:
            FinalResult with generated proposal and docx path.
        """
        logger.info("Starting RFP Builder workflow")
        
        output_dir = job_output_dir or self.output_dir
        
        # Step 1: Analyze RFP
        analysis_result = await self.analyzer.execute(input_data)
        logger.info(f"Analysis complete: {len(analysis_result.analysis.requirements)} requirements")
        
        # Step 2: Generate document code
        generation_result = await self.generator.execute(
            input_data, 
            analysis_result.analysis
        )
        logger.info(f"Generation complete: {len(generation_result.response.document_code)} chars of document code")
        
        # Step 3: Execute code to create the Word document
        docx_path, code_stats = await self.code_interpreter.execute(
            generation_result.response,
            output_dir
        )
        logger.info(f"Code execution: {'success' if code_stats['document_success'] else 'failed'}")
        
        return FinalResult(
            response=generation_result.response,
            analysis=analysis_result.analysis,
            docx_path=str(docx_path),
            execution_stats=code_stats
        )
    
    async def run_stream(
        self, 
        input_data: WorkflowInput,
        job_output_dir: Path | None = None
    ) -> AsyncIterator[WorkflowEvent]:
        """
        Run the workflow with streaming events.
        
        Args:
            input_data: Workflow input with RFP and context.
            job_output_dir: Directory for output files (charts, diagrams, docx).
            
        Yields:
            WorkflowEvent objects for each step.
        """
        yield WorkflowEvent(
            event_type="started",
            message="RFP Builder workflow started"
        )
        
        # Determine output directory
        output_dir = job_output_dir or self.output_dir
        
        try:
            # Step 1: Analyze
            yield WorkflowEvent(
                event_type="step_started",
                step_name="analyze",
                message="Analyzing RFP requirements..."
            )
            
            analysis_result = await self.analyzer.execute(input_data)
            
            yield WorkflowEvent(
                event_type="step_complete",
                step_name="analyze",
                message=f"Found {len(analysis_result.analysis.requirements)} requirements",
                data={"requirements_count": len(analysis_result.analysis.requirements)}
            )
            
            # Step 2: Generate document code
            yield WorkflowEvent(
                event_type="step_started",
                step_name="generate",
                message="Generating proposal document code..."
            )
            
            generation_result = await self.generator.execute(
                input_data,
                analysis_result.analysis
            )
            
            yield WorkflowEvent(
                event_type="step_complete",
                step_name="generate",
                message=f"Generated {len(generation_result.response.document_code)} chars of document code",
                data={"document_code_length": len(generation_result.response.document_code)}
            )
            
            # Step 3: Execute Code to create document
            yield WorkflowEvent(
                event_type="step_started",
                step_name="execute_code",
                message="Executing code to create Word document..."
            )
            
            docx_path, code_stats = await self.code_interpreter.execute(
                generation_result.response,
                output_dir
            )
            
            yield WorkflowEvent(
                event_type="step_complete",
                step_name="execute_code",
                message=f"Document {'created successfully' if code_stats['document_success'] else 'creation failed'}",
                data=code_stats
            )
            
            # Complete
            yield WorkflowEvent(
                event_type="finished",
                message="RFP generation complete",
                data={
                    "docx_path": str(docx_path),
                    "document_success": code_stats['document_success']
                }
            )
            
        except Exception as e:
            logger.exception("Workflow error")
            yield WorkflowEvent(
                event_type="error",
                message=str(e)
            )
            raise


def create_rfp_workflow() -> RFPBuilderWorkflow:
    """Factory function to create an RFP workflow instance."""
    return RFPBuilderWorkflow()
