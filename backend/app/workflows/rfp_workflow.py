"""
RFP Builder Workflow using Microsoft Agent Framework.
Orchestrates the sequential flow of RFP analysis, generation, review, and finalization.
"""

import logging
from typing import Optional, AsyncIterator
from dataclasses import dataclass

from app.core.config import get_config
from app.core.llm_client import create_llm_client
from app.models.schemas import RFPResponse, RFPAnalysis, ReviewFeedback
from .state import WorkflowInput, FinalResult
from .executors import (
    RFPAnalyzerExecutor,
    SectionGeneratorExecutor,
    ReviewerExecutor,
    FinalizerExecutor,
)


logger = logging.getLogger(__name__)


@dataclass
class WorkflowEvent:
    """Event emitted during workflow execution."""
    event_type: str  # 'started', 'step_complete', 'error', 'finished'
    step_name: Optional[str] = None
    message: Optional[str] = None
    data: Optional[dict] = None


class RFPBuilderWorkflow:
    """
    Main workflow for RFP generation.
    
    This workflow follows a sequential pattern:
    1. Analyze RFP -> Extract requirements
    2. Generate Sections -> Create proposal content
    3. Review -> Check quality and compliance
    4. Finalize -> Incorporate feedback and polish
    """
    
    def __init__(self):
        self.config = get_config()
        self.client = create_llm_client()
        
        # Initialize executors with shared client
        self.analyzer = RFPAnalyzerExecutor(self.client)
        self.generator = SectionGeneratorExecutor(self.client)
        self.reviewer = ReviewerExecutor(self.client)
        self.finalizer = FinalizerExecutor(self.client)
    
    async def run(self, input_data: WorkflowInput) -> FinalResult:
        """
        Run the complete RFP workflow.
        
        Args:
            input_data: Workflow input with RFP and context.
            
        Returns:
            FinalResult with generated proposal.
        """
        logger.info("Starting RFP Builder workflow")
        
        # Step 1: Analyze RFP
        analysis_result = await self.analyzer.execute(input_data)
        logger.info(f"Analysis complete: {len(analysis_result.analysis.requirements)} requirements")
        
        # Step 2: Generate sections
        generation_result = await self.generator.execute(
            input_data, 
            analysis_result.analysis
        )
        logger.info(f"Generation complete: {len(generation_result.response.sections)} sections")
        
        # Step 3: Review
        review_result = await self.reviewer.execute(
            analysis_result.analysis,
            generation_result.response
        )
        logger.info(f"Review complete: Score {review_result.feedback.overall_score}/10")
        
        # Step 4: Finalize (only if review suggests changes)
        if review_result.feedback.required_changes:
            final_result = await self.finalizer.execute(
                generation_result.response,
                review_result.feedback
            )
            final_response = final_result.response
        else:
            final_response = generation_result.response
        
        return FinalResult(
            response=final_response,
            analysis=analysis_result.analysis,
            review=review_result.feedback
        )
    
    async def run_stream(self, input_data: WorkflowInput) -> AsyncIterator[WorkflowEvent]:
        """
        Run the workflow with streaming events.
        
        Args:
            input_data: Workflow input with RFP and context.
            
        Yields:
            WorkflowEvent objects for each step.
        """
        yield WorkflowEvent(
            event_type="started",
            message="RFP Builder workflow started"
        )
        
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
            
            # Step 2: Generate
            yield WorkflowEvent(
                event_type="step_started",
                step_name="generate",
                message="Generating proposal sections..."
            )
            
            generation_result = await self.generator.execute(
                input_data,
                analysis_result.analysis
            )
            
            yield WorkflowEvent(
                event_type="step_complete",
                step_name="generate",
                message=f"Generated {len(generation_result.response.sections)} sections",
                data={"sections_count": len(generation_result.response.sections)}
            )
            
            # Step 3: Review
            yield WorkflowEvent(
                event_type="step_started",
                step_name="review",
                message="Reviewing proposal quality..."
            )
            
            review_result = await self.reviewer.execute(
                analysis_result.analysis,
                generation_result.response
            )
            
            yield WorkflowEvent(
                event_type="step_complete",
                step_name="review",
                message=f"Review score: {review_result.feedback.overall_score}/10",
                data={
                    "score": review_result.feedback.overall_score,
                    "compliance": review_result.feedback.compliance_status
                }
            )
            
            # Step 4: Finalize if needed
            if review_result.feedback.required_changes:
                yield WorkflowEvent(
                    event_type="step_started",
                    step_name="finalize",
                    message="Finalizing proposal with feedback..."
                )
                
                final_result = await self.finalizer.execute(
                    generation_result.response,
                    review_result.feedback
                )
                final_response = final_result.response
                
                yield WorkflowEvent(
                    event_type="step_complete",
                    step_name="finalize",
                    message="Proposal finalized"
                )
            else:
                final_response = generation_result.response
            
            # Complete
            yield WorkflowEvent(
                event_type="finished",
                message="RFP generation complete",
                data={
                    "total_sections": len(final_response.sections),
                    "review_score": review_result.feedback.overall_score
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
