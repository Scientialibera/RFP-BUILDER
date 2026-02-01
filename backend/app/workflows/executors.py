"""
Executors for the RFP Builder workflow.
Each executor handles a specific stage of the RFP generation process.
"""

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import get_config
from app.core.llm_client import create_llm_client, get_model_name
from app.core.llm_logger import create_llm_logger
from app.prompts.system_prompts import (
    RFP_ANALYZER_SYSTEM_PROMPT,
    RFP_SECTION_GENERATOR_SYSTEM_PROMPT,
    PROPOSAL_PLANNER_SYSTEM_PROMPT,
    PROPOSAL_CRITIQUER_SYSTEM_PROMPT,
)
from app.prompts.user_prompts import (
    ANALYZE_RFP_USER_PROMPT,
    GENERATE_SECTIONS_USER_PROMPT,
    PLAN_PROPOSAL_USER_PROMPT,
    GENERATE_WITH_PLAN_USER_PROMPT,
    GENERATE_WITH_ERROR_USER_PROMPT,
    GENERATE_WITH_CRITIQUE_USER_PROMPT,
    CRITIQUE_DOCUMENT_USER_PROMPT,
)
from app.functions.rfp_functions import (
    ANALYZE_RFP_FUNCTION,
    GENERATE_RFP_RESPONSE_FUNCTION,
    PLAN_PROPOSAL_FUNCTION,
    CRITIQUE_RESPONSE_FUNCTION,
)
from app.models.schemas import (
    RFPAnalysis,
    RFPResponse,
    RFPRequirement,
    EvaluationCriterion,
    SubmissionRequirements,
    ProposalPlan,
    PlannedSection,
    CritiqueResult,
)
from .state import (
    WorkflowInput,
    AnalysisResult,
    GenerationResult,
    PlanningResult,
    CritiqueResultData,
    FinalResult,
)


logger = logging.getLogger(__name__)


class BaseExecutor:
    """Base class for workflow executors."""
    
    def __init__(self, client: Optional[AsyncOpenAI] = None, run_dir: Optional[Path] = None):
        self.config = get_config()
        self.client = client or create_llm_client()
        self.model = get_model_name()
        
        # Initialize LLM logger if enabled
        self.llm_logger = None
        if self.config.workflow.log_all_steps and run_dir:
            self.llm_logger = create_llm_logger(run_dir)
    
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
            "temperature": 0.7
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
        """Analyze the RFP document and extract structured requirements."""
        logger.info("Starting RFP analysis")
        
        additional_context = ""
        if input_data.company_context_text:
            additional_context = f"Company Context:\n{input_data.company_context_text}"
        
        user_prompt = ANALYZE_RFP_USER_PROMPT.format(
            rfp_content=input_data.rfp_text,
            additional_context=additional_context
        )
        
        messages = self._build_messages_with_images(
            RFP_ANALYZER_SYSTEM_PROMPT,
            user_prompt,
            input_data.rfp_images
        )
        
        response = await self._call_llm(
            messages,
            functions=[ANALYZE_RFP_FUNCTION],
            function_call={"name": "analyze_rfp"}
        )
        
        message = response.choices[0].message
        raw_response = str(message)
        
        if message.tool_calls:
            func_args = json.loads(message.tool_calls[0].function.arguments)
            
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
            
            if self.llm_logger:
                self.llm_logger.log_step(
                    step_name="analyze",
                    function_name="analyze_rfp",
                    function_args=func_args,
                    raw_response=raw_response,
                    parsed_result=json.loads(json.dumps(analysis, default=str))
                )
        else:
            analysis = RFPAnalysis(
                summary=message.content or "Analysis not available",
                requirements=[]
            )
        
        logger.info(f"Analysis complete: {len(analysis.requirements)} requirements found")
        return AnalysisResult(analysis=analysis, raw_response=raw_response)


class SectionGeneratorExecutor(BaseExecutor):
    """Executor that generates the proposal document code."""
    
    async def execute(
        self, 
        input_data: WorkflowInput,
        analysis: RFPAnalysis
    ) -> GenerationResult:
        """Generate Python code for the proposal document."""
        logger.info("Starting document generation")
        
        example_text = "\n\n---\n\n".join(input_data.example_rfps_text)
        
        req_list = "\n".join([
            f"- [{req.id}] {req.description} (Category: {req.category}, Mandatory: {req.is_mandatory})"
            for req in analysis.requirements
        ])
        
        user_prompt = GENERATE_SECTIONS_USER_PROMPT.format(
            rfp_analysis=analysis.summary,
            example_rfps=example_text,
            company_context=input_data.company_context_text or "No company context provided.",
            requirements=req_list
        )
        
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
        
        response = await self._call_llm(
            messages,
            functions=[GENERATE_RFP_RESPONSE_FUNCTION],
            function_call={"name": "generate_rfp_response"}
        )
        
        message = response.choices[0].message
        raw_response = str(message)
        
        if message.tool_calls:
            func_args = json.loads(message.tool_calls[0].function.arguments)
            
            rfp_response = RFPResponse(
                document_code=func_args.get("document_code", "")
            )
            
            if self.llm_logger:
                self.llm_logger.log_step(
                    step_name="generate",
                    function_name="generate_rfp_response",
                    function_args=func_args,
                    raw_response=raw_response,
                    parsed_result={"document_code_length": len(rfp_response.document_code)}
                )
        else:
            rfp_response = RFPResponse(
                document_code="doc.add_heading('Generation Failed', level=0)\ndoc.add_paragraph('Unable to generate proposal.')"
            )
        
        logger.info(f"Generation complete: {len(rfp_response.document_code)} chars of document code")
        return GenerationResult(response=rfp_response, raw_response=raw_response)
    
    async def execute_with_plan(
        self, 
        input_data: WorkflowInput,
        analysis: RFPAnalysis,
        plan: ProposalPlan
    ) -> GenerationResult:
        """Generate Python code for the proposal document using the proposal plan."""
        logger.info("Starting document generation with plan")
        
        example_text = "\n\n---\n\n".join(input_data.example_rfps_text)
        
        req_list = "\n".join([
            f"- [{req.id}] {req.description} (Category: {req.category}, Mandatory: {req.is_mandatory})"
            for req in analysis.requirements
        ])
        
        # Format the plan for the prompt
        plan_text = f"Overview: {plan.overview}\n\nWin Strategy: {plan.win_strategy}\n\nKey Themes:\n"
        for theme in plan.key_themes:
            plan_text += f"- {theme}\n"
        plan_text += "\nPlanned Sections:\n"
        for section in plan.sections:
            plan_text += f"\n### {section.title}\n"
            plan_text += f"Summary: {section.summary}\n"
            if section.related_requirements:
                plan_text += f"Requirements: {', '.join(section.related_requirements)}\n"
            if section.suggested_diagrams:
                plan_text += f"Diagrams: {', '.join(section.suggested_diagrams)}\n"
            if section.suggested_charts:
                plan_text += f"Charts: {', '.join(section.suggested_charts)}\n"
            if section.suggested_tables:
                plan_text += f"Tables: {', '.join(section.suggested_tables)}\n"
        
        user_prompt = GENERATE_WITH_PLAN_USER_PROMPT.format(
            rfp_analysis=analysis.summary,
            proposal_plan=plan_text,
            example_rfps=example_text,
            company_context=input_data.company_context_text or "No company context provided.",
            requirements=req_list
        )
        
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
        
        response = await self._call_llm(
            messages,
            functions=[GENERATE_RFP_RESPONSE_FUNCTION],
            function_call={"name": "generate_rfp_response"}
        )
        
        message = response.choices[0].message
        raw_response = str(message)
        
        if message.tool_calls:
            func_args = json.loads(message.tool_calls[0].function.arguments)
            rfp_response = RFPResponse(document_code=func_args.get("document_code", ""))
        else:
            rfp_response = RFPResponse(
                document_code="doc.add_heading('Generation Failed', level=0)\ndoc.add_paragraph('Unable to generate proposal.')"
            )
        
        logger.info(f"Generation with plan complete: {len(rfp_response.document_code)} chars")
        return GenerationResult(response=rfp_response, raw_response=raw_response)
    
    async def execute_with_error(
        self, 
        input_data: WorkflowInput,
        analysis: RFPAnalysis,
        previous_code: str,
        error_message: str
    ) -> GenerationResult:
        """Regenerate document code after fixing an execution error."""
        logger.info(f"Regenerating document code after error: {error_message[:100]}...")
        
        req_list = "\n".join([
            f"- [{req.id}] {req.description}"
            for req in analysis.requirements
        ])
        
        user_prompt = GENERATE_WITH_ERROR_USER_PROMPT.format(
            error_message=error_message,
            previous_code=previous_code[:5000],  # Limit code size
            rfp_analysis=analysis.summary,
            requirements=req_list
        )
        
        messages = self._build_messages_with_images(
            RFP_SECTION_GENERATOR_SYSTEM_PROMPT,
            user_prompt,
            None  # No images needed for error recovery
        )
        
        response = await self._call_llm(
            messages,
            functions=[GENERATE_RFP_RESPONSE_FUNCTION],
            function_call={"name": "generate_rfp_response"}
        )
        
        message = response.choices[0].message
        raw_response = str(message)
        
        if message.tool_calls:
            func_args = json.loads(message.tool_calls[0].function.arguments)
            rfp_response = RFPResponse(document_code=func_args.get("document_code", ""))
        else:
            rfp_response = RFPResponse(
                document_code="doc.add_heading('Error Recovery Failed', level=0)"
            )
        
        logger.info(f"Error recovery generation complete: {len(rfp_response.document_code)} chars")
        return GenerationResult(response=rfp_response, raw_response=raw_response)
    
    async def execute_with_critique(
        self, 
        input_data: WorkflowInput,
        analysis: RFPAnalysis,
        previous_code: str,
        critique: CritiqueResult
    ) -> GenerationResult:
        """Regenerate document code after critique."""
        logger.info("Regenerating document code based on critique")
        
        req_list = "\n".join([
            f"- [{req.id}] {req.description}"
            for req in analysis.requirements
        ])
        
        critique_text = f"Needs Revision: {critique.needs_revision}\n"
        critique_text += f"\nCritique: {critique.critique}\n"
        if critique.weaknesses:
            critique_text += "\nWeaknesses:\n" + "\n".join(f"- {w}" for w in critique.weaknesses)
        if critique.priority_fixes:
            critique_text += "\n\nPriority Fixes:\n" + "\n".join(f"- {f}" for f in critique.priority_fixes)
        
        user_prompt = GENERATE_WITH_CRITIQUE_USER_PROMPT.format(
            critique=critique_text,
            previous_code=previous_code[:5000],
            rfp_analysis=analysis.summary,
            requirements=req_list
        )
        
        messages = self._build_messages_with_images(
            RFP_SECTION_GENERATOR_SYSTEM_PROMPT,
            user_prompt,
            None
        )
        
        response = await self._call_llm(
            messages,
            functions=[GENERATE_RFP_RESPONSE_FUNCTION],
            function_call={"name": "generate_rfp_response"}
        )
        
        message = response.choices[0].message
        raw_response = str(message)
        
        if message.tool_calls:
            func_args = json.loads(message.tool_calls[0].function.arguments)
            rfp_response = RFPResponse(document_code=func_args.get("document_code", ""))
        else:
            rfp_response = RFPResponse(
                document_code="doc.add_heading('Critique Recovery Failed', level=0)"
            )
        
        logger.info(f"Critique-based generation complete: {len(rfp_response.document_code)} chars")
        return GenerationResult(response=rfp_response, raw_response=raw_response)


class PlannerExecutor(BaseExecutor):
    """Executor that creates a detailed proposal plan before generation."""
    
    async def execute(
        self, 
        input_data: WorkflowInput,
        analysis: RFPAnalysis
    ) -> PlanningResult:
        """Create a detailed proposal plan."""
        logger.info("Starting proposal planning")
        
        req_list = "\n".join([
            f"- [{req.id}] {req.description} (Category: {req.category}, Mandatory: {req.is_mandatory}, Priority: {req.priority or 'medium'})"
            for req in analysis.requirements
        ])
        
        user_prompt = PLAN_PROPOSAL_USER_PROMPT.format(
            rfp_analysis=analysis.summary,
            requirements=req_list,
            company_context=input_data.company_context_text or "No company context provided."
        )
        
        messages = self._build_messages_with_images(
            PROPOSAL_PLANNER_SYSTEM_PROMPT,
            user_prompt,
            None  # No images needed for planning
        )
        
        response = await self._call_llm(
            messages,
            functions=[PLAN_PROPOSAL_FUNCTION],
            function_call={"name": "plan_proposal"}
        )
        
        message = response.choices[0].message
        raw_response = str(message)
        
        if message.tool_calls:
            func_args = json.loads(message.tool_calls[0].function.arguments)
            
            sections = [
                PlannedSection(
                    title=s.get("title", "Untitled Section"),
                    summary=s.get("summary", ""),
                    related_requirements=s.get("related_requirements", []),
                    rfp_pages=s.get("rfp_pages", []),
                    suggested_diagrams=s.get("suggested_diagrams", []),
                    suggested_charts=s.get("suggested_charts", []),
                    suggested_tables=s.get("suggested_tables", [])
                )
                for s in func_args.get("sections", [])
            ]
            
            plan = ProposalPlan(
                overview=func_args.get("overview", ""),
                sections=sections,
                key_themes=func_args.get("key_themes", []),
                win_strategy=func_args.get("win_strategy", "")
            )
            
            if self.llm_logger:
                self.llm_logger.log_step(
                    step_name="plan",
                    function_name="plan_proposal",
                    function_args=func_args,
                    raw_response=raw_response,
                    parsed_result={"sections_count": len(plan.sections)}
                )
        else:
            plan = ProposalPlan(
                overview="Planning not available",
                sections=[]
            )
        
        logger.info(f"Planning complete: {len(plan.sections)} sections planned")
        return PlanningResult(plan=plan, raw_response=raw_response)


class CritiquerExecutor(BaseExecutor):
    """Executor that reviews generated document code and provides critique."""
    
    async def execute(
        self, 
        analysis: RFPAnalysis,
        document_code: str
    ) -> CritiqueResultData:
        """Review document code and provide critique."""
        logger.info("Starting document critique")
        
        req_list = "\n".join([
            f"- [{req.id}] {req.description} (Mandatory: {req.is_mandatory})"
            for req in analysis.requirements
        ])
        
        user_prompt = CRITIQUE_DOCUMENT_USER_PROMPT.format(
            requirements=req_list,
            document_code=document_code[:10000]  # Limit for context window
        )
        
        messages = [
            {"role": "system", "content": PROPOSAL_CRITIQUER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._call_llm(
            messages,
            functions=[CRITIQUE_RESPONSE_FUNCTION],
            function_call={"name": "critique_response"}
        )
        
        message = response.choices[0].message
        raw_response = str(message)
        
        if message.tool_calls:
            func_args = json.loads(message.tool_calls[0].function.arguments)
            
            critique = CritiqueResult(
                needs_revision=func_args.get("needs_revision", False),
                critique=func_args.get("critique", ""),
                strengths=func_args.get("strengths", []),
                weaknesses=func_args.get("weaknesses", []),
                priority_fixes=func_args.get("priority_fixes", [])
            )
            
            if self.llm_logger:
                self.llm_logger.log_step(
                    step_name="critique",
                    function_name="critique_response",
                    function_args=func_args,
                    raw_response=raw_response,
                    parsed_result={"needs_revision": critique.needs_revision}
                )
        else:
            critique = CritiqueResult(
                needs_revision=False,
                critique="Unable to perform critique"
            )
        
        logger.info(f"Critique complete: needs_revision={critique.needs_revision}")
        return CritiqueResultData(critique=critique, raw_response=raw_response)


class CodeInterpreterExecutor(BaseExecutor):
    """Executor that runs document code to generate the final Word document."""
    
    def __init__(self, client: Optional[AsyncOpenAI] = None, run_dir: Optional[Path] = None, output_dir: Optional[Path] = None):
        super().__init__(client, run_dir)
        self.output_dir = output_dir or Path("./output")
    
    def _find_mmdc(self) -> Optional[str]:
        """Find the mermaid CLI executable."""
        import shutil
        
        # Try to find mmdc in PATH
        mmdc = shutil.which('mmdc')
        if mmdc:
            return mmdc
        
        # Try common npm global install locations
        possible_paths = [
            Path.home() / 'AppData' / 'Roaming' / 'npm' / 'mmdc.cmd',  # Windows
            Path.home() / 'AppData' / 'Roaming' / 'npm' / 'mmdc',
            Path('/usr/local/bin/mmdc'),  # macOS/Linux
            Path('/usr/bin/mmdc'),
        ]
        
        for p in possible_paths:
            if p.exists():
                return str(p)
        
        return None
    
    async def execute(
        self,
        response: RFPResponse,
        output_dir: Optional[Path] = None
    ) -> tuple[Path, dict]:
        """
        Execute the document_code to create the Word document.
        
        The code has full access to:
        - python-docx for document creation
        - seaborn/matplotlib for charts
        - subprocess for mermaid CLI
        """
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        import seaborn as sns
        import numpy as np
        import pandas as pd
        from docx import Document
        from docx.shared import Inches, Pt, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        
        out_dir = output_dir or self.output_dir
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Starting code interpreter execution")
        
        stats = {
            "document_success": False,
            "errors": []
        }
        
        docx_path = out_dir / "proposal.docx"
        
        # Find mmdc path
        mmdc_path = self._find_mmdc()
        
        try:
            # Create the document
            doc = Document()
            
            # Helper function for mermaid that uses the correct path
            def render_mermaid(mermaid_code: str, output_filename: str) -> Path:
                """Render mermaid diagram and return the image path."""
                if not mmdc_path:
                    raise RuntimeError("Mermaid CLI (mmdc) not found. Install with: npm install -g @mermaid-js/mermaid-cli")
                
                mmd_file = out_dir / f"{output_filename}.mmd"
                mmd_file.write_text(mermaid_code, encoding='utf-8')
                png_path = out_dir / f"{output_filename}.png"
                
                result = subprocess.run(
                    [mmdc_path, '-i', str(mmd_file), '-o', str(png_path), '-b', 'white'],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise RuntimeError(f"Mermaid failed: {result.stderr}")
                return png_path
            
            # Create execution environment with everything the LLM needs
            exec_globals = {
                # Builtins
                "__builtins__": __builtins__,
                # Document
                "doc": doc,
                "output_dir": out_dir,
                # python-docx
                "Inches": Inches,
                "Pt": Pt,
                "Cm": Cm,
                "WD_ALIGN_PARAGRAPH": WD_ALIGN_PARAGRAPH,
                "WD_TABLE_ALIGNMENT": WD_TABLE_ALIGNMENT,
                # Data science
                "plt": plt,
                "sns": sns,
                "np": np,
                "pd": pd,
                # System
                "subprocess": subprocess,
                "tempfile": tempfile,
                "os": os,
                "Path": Path,
                # Mermaid helper
                "render_mermaid": render_mermaid,
                "mmdc_path": mmdc_path,
            }
            
            # Execute the document code
            exec(response.document_code, exec_globals)
            
            # Close any open matplotlib figures
            plt.close('all')
            
            # Save the document
            doc.save(docx_path)
            stats["document_success"] = True
            logger.info(f"Document saved to {docx_path}")
            
        except Exception as e:
            error_msg = f"Document generation failed: {str(e)}"
            stats["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)
            
            # Create a fallback document with error info
            doc = Document()
            doc.add_heading("Document Generation Error", level=0)
            doc.add_paragraph(f"Error: {str(e)}")
            doc.add_heading("Generated Code", level=1)
            doc.add_paragraph(response.document_code[:5000])  # First 5000 chars
            doc.save(docx_path)
        
        logger.info(f"Code interpreter complete: {'success' if stats['document_success'] else 'failed'}")
        
        return docx_path, stats
