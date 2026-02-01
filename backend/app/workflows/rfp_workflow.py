"""
RFP Builder Workflow using Microsoft Agent Framework.
Orchestrates the sequential flow of RFP analysis, generation, and code execution.

Supports:
- Optional Planner: Creates a detailed plan before generation
- Optional Critiquer: Reviews generated code and requests revisions
- Error Recovery: Retries generation if code execution fails
"""

import logging
from pathlib import Path
from typing import Optional, AsyncIterator
from dataclasses import dataclass

from app.core.config import get_config
from app.core.llm_client import create_llm_client
from app.models.schemas import RFPResponse, RFPAnalysis, ProposalPlan, CritiqueResult
from .state import WorkflowInput, FinalResult
from .executors import (
    RFPAnalyzerExecutor,
    SectionGeneratorExecutor,
    CodeInterpreterExecutor,
    PlannerExecutor,
    CritiquerExecutor,
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
    
    This workflow follows a sequential pattern with optional enhancements:
    1. Analyze RFP -> Extract requirements
    2. (Optional) Plan Proposal -> Create detailed section plan
    3. Generate Document Code -> Create python-docx code with diagram/chart definitions
    4. (Optional) Critique -> Review code and request revisions
    5. Execute Code -> Run the document code (with error recovery loop)
    6. Return path to generated .docx file
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.config = get_config()
        self.client = create_llm_client()
        self.output_dir = output_dir or Path(self.config.app.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _create_run_directory(self) -> Path:
        """Create a timestamped run directory."""
        from datetime import datetime
        run_name = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        run_dir = self.output_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
    
    def _initialize_executors(self, run_dir: Path):
        """Initialize executors with the run directory for logging."""
        # Initialize executors with shared client
        self.analyzer = RFPAnalyzerExecutor(self.client, run_dir)
        self.generator = SectionGeneratorExecutor(self.client, run_dir)
        self.code_interpreter = CodeInterpreterExecutor(self.client, run_dir)
        self.planner = PlannerExecutor(self.client, run_dir)
        self.critiquer = CritiquerExecutor(self.client, run_dir)
    
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
        
        # Create a run directory for this execution
        run_dir = self._create_run_directory()
        logger.info(f"Run directory: {run_dir}")
        
        # Initialize executors for this run
        self._initialize_executors(run_dir)
        
        # Use run directory for outputs, or custom job directory
        output_dir = job_output_dir or run_dir
        
        critique_history: list[CritiqueResult] = []
        error_recovery_count = 0
        plan: Optional[ProposalPlan] = None
        
        # Step 1: Analyze RFP
        analysis_result = await self.analyzer.execute(input_data)
        logger.info(f"Analysis complete: {len(analysis_result.analysis.requirements)} requirements")
        
        # Step 2: Optional Planning
        if self.config.workflow.enable_planner:
            logger.info("Planner enabled - creating proposal plan")
            planning_result = await self.planner.execute(input_data, analysis_result.analysis)
            plan = planning_result.plan
            logger.info(f"Planning complete: {len(plan.sections)} sections")
        
        # Step 3: Generate document code (with optional plan)
        if plan:
            generation_result = await self.generator.execute_with_plan(
                input_data, 
                analysis_result.analysis,
                plan
            )
        else:
            generation_result = await self.generator.execute(
                input_data, 
                analysis_result.analysis
            )
        logger.info(f"Generation complete: {len(generation_result.response.document_code)} chars of document code")
        
        # Step 4: Optional Critique Loop
        critique_count = 0
        while self.config.workflow.enable_critiquer and critique_count < self.config.workflow.max_critiques:
            logger.info(f"Critique pass {critique_count + 1}/{self.config.workflow.max_critiques}")
            
            critique_result = await self.critiquer.execute(
                analysis_result.analysis,
                generation_result.response.document_code
            )
            critique_history.append(critique_result.critique)
            
            if not critique_result.critique.needs_revision:
                logger.info("Critique passed - no revisions needed")
                break
            
            logger.info("Critique requires revisions - regenerating")
            generation_result = await self.generator.execute_with_critique(
                input_data,
                analysis_result.analysis,
                generation_result.response.document_code,
                critique_result.critique
            )
            critique_count += 1
        
        # Step 5: Execute code with error recovery loop
        max_error_loops = self.config.workflow.max_error_loops
        current_response = generation_result.response
        docx_path = run_dir / "proposal.docx"
        code_stats = {}
        
        for error_loop in range(max_error_loops + 1):
            docx_path, code_stats = await self.code_interpreter.execute(
                current_response,
                output_dir
            )
            
            if code_stats['document_success']:
                logger.info(f"Code execution: success")
                break
            
            error_recovery_count = error_loop + 1
            if error_loop < max_error_loops:
                error_msg = code_stats.get('errors', ['Unknown error'])[0]
                logger.warning(f"Code execution failed (attempt {error_loop + 1}/{max_error_loops + 1}): {error_msg}")
                
                # Regenerate with error context
                generation_result = await self.generator.execute_with_error(
                    input_data,
                    analysis_result.analysis,
                    current_response.document_code,
                    error_msg
                )
                current_response = generation_result.response
            else:
                logger.error(f"Code execution failed after {max_error_loops + 1} attempts - giving up")
        
        return FinalResult(
            response=current_response,
            analysis=analysis_result.analysis,
            plan=plan,
            critique_history=critique_history,
            error_recovery_count=error_recovery_count,
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
        plan: Optional[ProposalPlan] = None
        critique_history: list[CritiqueResult] = []
        error_recovery_count = 0
        
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
            
            # Step 2: Optional Planning
            if self.config.workflow.enable_planner:
                yield WorkflowEvent(
                    event_type="step_started",
                    step_name="plan",
                    message="Creating proposal plan..."
                )
                
                planning_result = await self.planner.execute(input_data, analysis_result.analysis)
                plan = planning_result.plan
                
                yield WorkflowEvent(
                    event_type="step_complete",
                    step_name="plan",
                    message=f"Planned {len(plan.sections)} sections",
                    data={"sections_count": len(plan.sections)}
                )
            
            # Step 3: Generate document code
            yield WorkflowEvent(
                event_type="step_started",
                step_name="generate",
                message="Generating proposal document code..."
            )
            
            if plan:
                generation_result = await self.generator.execute_with_plan(
                    input_data,
                    analysis_result.analysis,
                    plan
                )
            else:
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
            
            # Step 4: Optional Critique Loop
            critique_count = 0
            while self.config.workflow.enable_critiquer and critique_count < self.config.workflow.max_critiques:
                yield WorkflowEvent(
                    event_type="step_started",
                    step_name="critique",
                    message=f"Reviewing document (pass {critique_count + 1})..."
                )
                
                critique_result = await self.critiquer.execute(
                    analysis_result.analysis,
                    generation_result.response.document_code
                )
                critique_history.append(critique_result.critique)
                
                if not critique_result.critique.needs_revision:
                    yield WorkflowEvent(
                        event_type="step_complete",
                        step_name="critique",
                        message="Critique passed - no revisions needed",
                        data={"needs_revision": False}
                    )
                    break
                
                yield WorkflowEvent(
                    event_type="step_complete",
                    step_name="critique",
                    message="Revisions needed - regenerating...",
                    data={"needs_revision": True, "weaknesses": critique_result.critique.weaknesses}
                )
                
                yield WorkflowEvent(
                    event_type="step_started",
                    step_name="generate",
                    message="Regenerating with critique feedback..."
                )
                
                generation_result = await self.generator.execute_with_critique(
                    input_data,
                    analysis_result.analysis,
                    generation_result.response.document_code,
                    critique_result.critique
                )
                
                yield WorkflowEvent(
                    event_type="step_complete",
                    step_name="generate",
                    message=f"Regenerated {len(generation_result.response.document_code)} chars",
                    data={"document_code_length": len(generation_result.response.document_code)}
                )
                
                critique_count += 1
            
            # Step 5: Execute Code with error recovery loop
            max_error_loops = self.config.workflow.max_error_loops
            current_response = generation_result.response
            
            for error_loop in range(max_error_loops + 1):
                yield WorkflowEvent(
                    event_type="step_started",
                    step_name="execute_code",
                    message=f"Executing code to create Word document{' (retry)' if error_loop > 0 else ''}..."
                )
                
                docx_path, code_stats = await self.code_interpreter.execute(
                    current_response,
                    output_dir
                )
                
                if code_stats['document_success']:
                    yield WorkflowEvent(
                        event_type="step_complete",
                        step_name="execute_code",
                        message="Document created successfully",
                        data=code_stats
                    )
                    break
                
                error_recovery_count = error_loop + 1
                error_msg = code_stats.get('errors', ['Unknown error'])[0]
                
                if error_loop < max_error_loops:
                    yield WorkflowEvent(
                        event_type="step_complete",
                        step_name="execute_code",
                        message=f"Execution failed - attempting recovery ({error_loop + 1}/{max_error_loops})",
                        data={"error": error_msg}
                    )
                    
                    yield WorkflowEvent(
                        event_type="step_started",
                        step_name="generate",
                        message="Regenerating to fix error..."
                    )
                    
                    generation_result = await self.generator.execute_with_error(
                        input_data,
                        analysis_result.analysis,
                        current_response.document_code,
                        error_msg
                    )
                    current_response = generation_result.response
                    
                    yield WorkflowEvent(
                        event_type="step_complete",
                        step_name="generate",
                        message="Error recovery code generated",
                        data={"document_code_length": len(current_response.document_code)}
                    )
                else:
                    yield WorkflowEvent(
                        event_type="step_complete",
                        step_name="execute_code",
                        message=f"Document creation failed after {max_error_loops + 1} attempts",
                        data=code_stats
                    )
            
            # Complete
            yield WorkflowEvent(
                event_type="finished",
                message="RFP generation complete",
                data={
                    "docx_path": str(docx_path),
                    "document_success": code_stats['document_success'],
                    "error_recovery_count": error_recovery_count,
                    "critique_count": len(critique_history),
                    "planner_used": plan is not None
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
