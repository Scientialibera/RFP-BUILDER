"""
Executors for the RFP Builder workflow.
Each executor handles a specific stage of the RFP generation process.
"""

import json
import logging
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import get_config
from app.core.llm_client import create_llm_client, get_model_name
from app.prompts.system_prompts import (
    RFP_ANALYZER_SYSTEM_PROMPT,
    RFP_SECTION_GENERATOR_SYSTEM_PROMPT,
    RFP_REVIEWER_SYSTEM_PROMPT,
    RFP_FINALIZER_SYSTEM_PROMPT,
)
from app.prompts.user_prompts import (
    ANALYZE_RFP_USER_PROMPT,
    GENERATE_SECTIONS_USER_PROMPT,
    REVIEW_PROPOSAL_USER_PROMPT,
    FINALIZE_PROPOSAL_USER_PROMPT,
)
from app.functions.rfp_functions import (
    ANALYZE_RFP_FUNCTION,
    GENERATE_RFP_RESPONSE_FUNCTION,
    REVIEW_PROPOSAL_FUNCTION,
)
from app.models.schemas import (
    RFPAnalysis,
    RFPResponse,
    RFPSection,
    ReviewFeedback,
    ReviewChange,
    RFPRequirement,
    EvaluationCriterion,
    SubmissionRequirements,
)
from .state import (
    WorkflowInput,
    AnalysisResult,
    GenerationResult,
    ReviewResult,
    FinalResult,
)


logger = logging.getLogger(__name__)


class BaseExecutor:
    """Base class for workflow executors."""
    
    def __init__(self, client: Optional[AsyncOpenAI] = None):
        self.config = get_config()
        self.client = client or create_llm_client()
        self.model = get_model_name()
    
    def _build_messages_with_images(
        self,
        system_prompt: str,
        user_text: str,
        images: Optional[list[dict]] = None
    ) -> list[dict]:
        """Build message list with optional image content."""
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        if images and self.config.features.enable_images:
            # Multimodal message with images
            content = [
                {"type": "text", "text": user_text}
            ]
            content.extend(images)
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user_text})
        
        return messages
    
    async def _call_llm(
        self,
        messages: list[dict],
        functions: Optional[list[dict]] = None,
        function_call: Optional[dict] = None,
    ) -> dict:
        """Make an LLM call with optional function calling."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 16000,
        }
        
        if functions:
            kwargs["tools"] = [
                {"type": "function", "function": f} for f in functions
            ]
            if function_call:
                kwargs["tool_choice"] = {
                    "type": "function",
                    "function": {"name": function_call["name"]}
                }
        
        response = await self.client.chat.completions.create(**kwargs)
        return response


class RFPAnalyzerExecutor(BaseExecutor):
    """Executor that analyzes the RFP and extracts requirements."""
    
    async def execute(self, input_data: WorkflowInput) -> AnalysisResult:
        """
        Analyze the RFP document and extract structured requirements.
        
        Args:
            input_data: Workflow input containing RFP text and optional images.
            
        Returns:
            AnalysisResult with structured RFP analysis.
        """
        logger.info("Starting RFP analysis")
        
        # Build user prompt
        additional_context = ""
        if input_data.company_context_text:
            additional_context = f"Company Context:\n{input_data.company_context_text}"
        
        user_prompt = ANALYZE_RFP_USER_PROMPT.format(
            rfp_content=input_data.rfp_text,
            additional_context=additional_context
        )
        
        # Build messages with images if available
        messages = self._build_messages_with_images(
            RFP_ANALYZER_SYSTEM_PROMPT,
            user_prompt,
            input_data.rfp_images
        )
        
        # Call LLM with function calling
        response = await self._call_llm(
            messages,
            functions=[ANALYZE_RFP_FUNCTION],
            function_call={"name": "analyze_rfp"}
        )
        
        # Parse response
        message = response.choices[0].message
        raw_response = str(message)
        
        if message.tool_calls:
            func_args = json.loads(message.tool_calls[0].function.arguments)
            
            # Build analysis object
            requirements = [
                RFPRequirement(**req) for req in func_args.get("requirements", [])
            ]
            
            eval_criteria = None
            if func_args.get("evaluation_criteria"):
                eval_criteria = [
                    EvaluationCriterion(**ec) 
                    for ec in func_args["evaluation_criteria"]
                ]
            
            sub_reqs = None
            if func_args.get("submission_requirements"):
                sub_reqs = SubmissionRequirements(**func_args["submission_requirements"])
            
            analysis = RFPAnalysis(
                summary=func_args.get("summary", ""),
                requirements=requirements,
                evaluation_criteria=eval_criteria,
                submission_requirements=sub_reqs,
                key_differentiators=func_args.get("key_differentiators"),
            )
        else:
            # Fallback if no function call
            analysis = RFPAnalysis(
                summary=message.content or "Analysis not available",
                requirements=[]
            )
        
        logger.info(f"Analysis complete: {len(analysis.requirements)} requirements found")
        return AnalysisResult(analysis=analysis, raw_response=raw_response)


class SectionGeneratorExecutor(BaseExecutor):
    """Executor that generates proposal sections."""
    
    async def execute(
        self, 
        input_data: WorkflowInput,
        analysis: RFPAnalysis
    ) -> GenerationResult:
        """
        Generate proposal sections based on RFP analysis.
        
        Args:
            input_data: Original workflow input with examples.
            analysis: Analyzed RFP requirements.
            
        Returns:
            GenerationResult with generated sections.
        """
        logger.info("Starting section generation")
        
        # Combine example RFP texts
        example_text = "\n\n---\n\n".join(input_data.example_rfps_text)
        
        # Build requirements list
        req_list = "\n".join([
            f"- [{req.id}] {req.description} (Category: {req.category}, Mandatory: {req.is_mandatory})"
            for req in analysis.requirements
        ])
        
        # Build user prompt
        user_prompt = GENERATE_SECTIONS_USER_PROMPT.format(
            rfp_analysis=analysis.summary,
            example_rfps=example_text,
            company_context=input_data.company_context_text or "No company context provided.",
            requirements=req_list
        )
        
        # Combine all images for multimodal
        all_images = []
        if input_data.example_rfps_images:
            for img_list in input_data.example_rfps_images:
                all_images.extend(img_list)
        if input_data.company_context_images:
            all_images.extend(input_data.company_context_images)
        
        messages = self._build_messages_with_images(
            RFP_SECTION_GENERATOR_SYSTEM_PROMPT,
            user_prompt,
            all_images if all_images else None
        )
        
        # Call LLM with function calling
        response = await self._call_llm(
            messages,
            functions=[GENERATE_RFP_RESPONSE_FUNCTION],
            function_call={"name": "generate_rfp_response"}
        )
        
        # Parse response
        message = response.choices[0].message
        raw_response = str(message)
        
        if message.tool_calls:
            func_args = json.loads(message.tool_calls[0].function.arguments)
            
            sections = [
                RFPSection(**sec) for sec in func_args.get("sections", [])
            ]
            
            rfp_response = RFPResponse(sections=sections)
        else:
            # Fallback
            rfp_response = RFPResponse(sections=[
                RFPSection(
                    section_title="Generated Response",
                    section_content=message.content or "Generation failed",
                    section_type="body"
                )
            ])
        
        logger.info(f"Generation complete: {len(rfp_response.sections)} sections")
        return GenerationResult(response=rfp_response, raw_response=raw_response)


class ReviewerExecutor(BaseExecutor):
    """Executor that reviews the generated proposal."""
    
    async def execute(
        self,
        analysis: RFPAnalysis,
        draft: RFPResponse
    ) -> ReviewResult:
        """
        Review the proposal draft against requirements.
        
        Args:
            analysis: Original RFP analysis.
            draft: Generated proposal draft.
            
        Returns:
            ReviewResult with feedback.
        """
        logger.info("Starting proposal review")
        
        # Format draft for review
        draft_text = "\n\n".join([
            f"## {sec.section_title}\n{sec.section_content}"
            for sec in draft.sections
        ])
        
        # Format evaluation criteria
        eval_text = "Not specified"
        if analysis.evaluation_criteria:
            eval_text = "\n".join([
                f"- {ec.criterion}: {ec.description or ''} (Weight: {ec.weight or 'N/A'})"
                for ec in analysis.evaluation_criteria
            ])
        
        user_prompt = REVIEW_PROPOSAL_USER_PROMPT.format(
            rfp_analysis=analysis.summary,
            proposal_draft=draft_text,
            evaluation_criteria=eval_text
        )
        
        messages = [
            {"role": "system", "content": RFP_REVIEWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._call_llm(
            messages,
            functions=[REVIEW_PROPOSAL_FUNCTION],
            function_call={"name": "review_proposal"}
        )
        
        message = response.choices[0].message
        raw_response = str(message)
        
        if message.tool_calls:
            func_args = json.loads(message.tool_calls[0].function.arguments)
            
            changes = [
                ReviewChange(**ch) for ch in func_args.get("required_changes", [])
            ]
            
            feedback = ReviewFeedback(
                overall_score=func_args.get("overall_score", 5),
                compliance_status=func_args.get("compliance_status", "partially_compliant"),
                strengths=func_args.get("strengths"),
                weaknesses=func_args.get("weaknesses"),
                required_changes=changes,
                missing_requirements=func_args.get("missing_requirements"),
            )
        else:
            feedback = ReviewFeedback(
                overall_score=5,
                compliance_status="partially_compliant",
                required_changes=[]
            )
        
        logger.info(f"Review complete: Score {feedback.overall_score}/10")
        return ReviewResult(feedback=feedback, raw_response=raw_response)


class FinalizerExecutor(BaseExecutor):
    """Executor that finalizes the proposal."""
    
    async def execute(
        self,
        draft: RFPResponse,
        review: ReviewFeedback,
        style_guidelines: str = ""
    ) -> FinalResult:
        """
        Finalize the proposal incorporating review feedback.
        
        Args:
            draft: Original proposal draft.
            review: Review feedback.
            style_guidelines: Style guidelines from examples.
            
        Returns:
            FinalResult with finalized proposal.
        """
        logger.info("Starting proposal finalization")
        
        # Format draft
        draft_text = "\n\n".join([
            f"## {sec.section_title} [{sec.section_type}]\n{sec.section_content}"
            for sec in draft.sections
        ])
        
        # Format feedback
        feedback_text = f"""
Overall Score: {review.overall_score}/10
Compliance: {review.compliance_status}

Strengths:
{chr(10).join(['- ' + s for s in (review.strengths or [])])}

Weaknesses:
{chr(10).join(['- ' + w for w in (review.weaknesses or [])])}

Required Changes:
{chr(10).join([f'- [{c.section}] {c.issue}: {c.suggestion}' for c in review.required_changes])}
"""
        
        user_prompt = FINALIZE_PROPOSAL_USER_PROMPT.format(
            proposal_draft=draft_text,
            review_feedback=feedback_text,
            style_guidelines=style_guidelines or "Match the professional tone of the examples."
        )
        
        messages = [
            {"role": "system", "content": RFP_FINALIZER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._call_llm(
            messages,
            functions=[GENERATE_RFP_RESPONSE_FUNCTION],
            function_call={"name": "generate_rfp_response"}
        )
        
        message = response.choices[0].message
        
        if message.tool_calls:
            func_args = json.loads(message.tool_calls[0].function.arguments)
            
            sections = [
                RFPSection(**sec) for sec in func_args.get("sections", [])
            ]
            
            final_response = RFPResponse(sections=sections)
        else:
            # Use draft as final if parsing fails
            final_response = draft
        
        logger.info(f"Finalization complete: {len(final_response.sections)} sections")
        
        return FinalResult(
            response=final_response,
            analysis=RFPAnalysis(summary="", requirements=[]),  # Placeholder
            review=review
        )
