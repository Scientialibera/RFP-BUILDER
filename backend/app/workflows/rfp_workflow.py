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
from .run_dirs import create_unique_run_directory


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
        """Create a timestamped run directory with enterprise-grade subdirectory structure."""
        run_dir = create_unique_run_directory(self.output_dir)
        logger.info(f"Created run directory structure: {run_dir}")
        return run_dir
    
    def _initialize_executors(self, run_dir: Path):
        """Initialize executors with the run directory for logging."""
        # Initialize executors with shared client
        self.analyzer = RFPAnalyzerExecutor(self.client, run_dir)
        self.generator = SectionGeneratorExecutor(self.client, run_dir)
        self.code_interpreter = CodeInterpreterExecutor(self.client, run_dir)
        self.planner = PlannerExecutor(self.client, run_dir)
        self.critiquer = CritiquerExecutor(self.client, run_dir)

    def _is_planner_enabled(self, input_data: WorkflowInput) -> bool:
        """Check if planner is enabled (input override takes precedence over config)."""
        if input_data.enable_planner is not None:
            return input_data.enable_planner
        return self.config.workflow.enable_planner
    
    def _is_critiquer_enabled(self, input_data: WorkflowInput) -> bool:
        """Check if critiquer is enabled (input override takes precedence over config)."""
        if input_data.enable_critiquer is not None:
            return input_data.enable_critiquer
        return self.config.workflow.enable_critiquer

    def _should_chunk_generation(self, input_data: WorkflowInput, plan: Optional[ProposalPlan]) -> bool:
        if not plan:
            return False
        if input_data.toggle_generation_chunking is not None:
            return input_data.toggle_generation_chunking
        return self.config.features.toggle_generation_chunking

    def _chunk_sections(self, sections: list, max_sections: int) -> list[list]:
        if max_sections <= 0:
            return [sections]
        return [sections[i:i + max_sections] for i in range(0, len(sections), max_sections)]
    
    def _save_metadata(
        self, 
        run_dir: Path, 
        analysis: RFPAnalysis,
        plan: Optional[ProposalPlan],
        critique_history: list[CritiqueResult]
    ) -> None:
        """Save metadata artifacts (analysis, plan, critiques) to metadata folder."""
        import json
        from datetime import datetime
        
        metadata_dir = run_dir / "metadata"
        
        # Save analysis
        analysis_file = metadata_dir / "analysis.json"
        try:
            with open(analysis_file, "w") as f:
                json.dump(analysis.model_dump(), f, indent=2, default=str)
            logger.info(f"Saved analysis to {analysis_file}")
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")
        
        # Save plan if available
        if plan:
            plan_file = metadata_dir / "plan.json"
            try:
                with open(plan_file, "w") as f:
                    json.dump(plan.model_dump(), f, indent=2, default=str)
                logger.info(f"Saved plan to {plan_file}")
            except Exception as e:
                logger.error(f"Failed to save plan: {e}")
        
        # Save critique history
        if critique_history:
            critiques_file = metadata_dir / "critiques.json"
            try:
                critiques_data = [c.model_dump() for c in critique_history]
                with open(critiques_file, "w") as f:
                    json.dump(critiques_data, f, indent=2, default=str)
                logger.info(f"Saved {len(critique_history)} critiques to {critiques_file}")
            except Exception as e:
                logger.error(f"Failed to save critiques: {e}")
        
        # Save run manifest
        manifest_file = metadata_dir / "manifest.json"
        try:
            manifest = {
                "timestamp": datetime.now().isoformat(),
                "run_dir": str(run_dir),
                "has_plan": plan is not None,
                "critique_count": len(critique_history),
                "subdirectories": {
                    "word_document": "Final .docx proposal file",
                    "image_assets": "Generated charts and visualizations",
                    "diagrams": "Generated Mermaid diagrams",
                    "llm_interactions": "LLM request/response logs",
                    "execution_logs": "Code execution logs and errors",
                    "metadata": "Analysis, plan, and critique JSON files",
                    "code_snapshots": "Generated document code snapshots",
                    "documents": "Uploaded source documents (RFP, examples, context)",
                    "revisions": "User-initiated code revisions"
                }
            }
            with open(manifest_file, "w") as f:
                json.dump(manifest, f, indent=2)
            logger.info(f"Saved run manifest to {manifest_file}")
        except Exception as e:
            logger.error(f"Failed to save manifest: {e}")
    
    def _save_code_snapshot(self, run_dir: Path, stage: str, code: str) -> None:
        """Save a snapshot of generated code at a specific stage."""
        snapshots_dir = run_dir / "code_snapshots"
        snapshot_file = snapshots_dir / f"{stage}_document_code.py"
        try:
            with open(snapshot_file, "w", encoding="utf-8") as f:
                f.write(code)
            logger.debug(f"Saved code snapshot to {snapshot_file}")
        except Exception as e:
            logger.error(f"Failed to save code snapshot: {e}")
    
    def _save_documents(self, run_dir: Path, input_data: 'WorkflowInput') -> None:
        """Save uploaded documents to the run's documents folder."""
        if not input_data.documents:
            return
        
        docs_dir = run_dir / "documents"
        for doc_info in input_data.documents:
            if doc_info.file_bytes:
                doc_path = docs_dir / doc_info.filename
                try:
                    with open(doc_path, "wb") as f:
                        f.write(doc_info.file_bytes)
                    logger.info(f"Saved document: {doc_info.filename} ({doc_info.file_type})")
                except Exception as e:
                    logger.error(f"Failed to save document {doc_info.filename}: {e}")
        
        # Also save document manifest
        doc_manifest = {
            "documents": [
                {"filename": d.filename, "type": d.file_type}
                for d in input_data.documents
            ]
        }
        manifest_path = docs_dir / "documents_manifest.json"
        try:
            import json
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(doc_manifest, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save documents manifest: {e}")
    
    async def run(self, input_data: WorkflowInput) -> FinalResult:
        """
        Run the complete RFP workflow.
        
        Args:
            input_data: Workflow input with RFP and context.
            
        Returns:
            FinalResult with generated proposal and docx path.
        """
        logger.info("Starting RFP Builder workflow")
        
        # Create a run directory for this execution
        run_dir = self._create_run_directory()
        run_id = run_dir.name  # e.g., "run_20260201_123456"
        logger.info(f"Run directory: {run_dir}")
        
        # Save uploaded documents to run directory
        self._save_documents(run_dir, input_data)
        
        # Initialize executors for this run
        self._initialize_executors(run_dir)
        
        critique_history: list[CritiqueResult] = []
        error_recovery_count = 0
        plan: Optional[ProposalPlan] = None
        
        # Step 1: Analyze RFP
        analysis_result = await self.analyzer.execute(input_data)
        logger.info(f"Analysis complete: {len(analysis_result.analysis.requirements)} requirements")
        
        # Step 2: Optional Planning
        if self._is_planner_enabled(input_data):
            logger.info("Planner enabled - creating proposal plan")
            planning_result = await self.planner.execute(input_data, analysis_result.analysis)
            plan = planning_result.plan
            logger.info(f"Planning complete: {len(plan.sections)} sections")
        
        # Step 3: Generate document code (with optional plan)
        use_generation_chunking = self._should_chunk_generation(input_data, plan)
        if plan and use_generation_chunking:
            max_sections = input_data.max_sections_per_chunk if input_data.max_sections_per_chunk is not None else self.config.features.max_sections_per_chunk
            section_chunks = self._chunk_sections(plan.sections, max_sections)
            chunk_codes: list[str] = []
            logger.info(f"Generation chunking enabled: {len(section_chunks)} chunks")

            for idx, chunk in enumerate(section_chunks, start=1):
                generation_result = await self.generator.execute_chunk_with_plan(
                    input_data,
                    analysis_result.analysis,
                    chunk,
                    part_number=idx,
                    total_parts=len(section_chunks),
                )

                # Critique per chunk (if enabled)
                if self._is_critiquer_enabled(input_data):
                    critique_count = 0
                    chunk_req_ids = {req_id for section in chunk for req_id in (section.related_requirements or [])}
                    chunk_requirements = [
                        req for req in analysis_result.analysis.requirements if req.id in chunk_req_ids
                    ]
                    chunk_analysis = RFPAnalysis(
                        summary=analysis_result.analysis.summary,
                        requirements=chunk_requirements
                    )

                    while critique_count < self.config.workflow.max_critiques:
                        critique_result = await self.critiquer.execute(
                            chunk_analysis,
                            generation_result.response.document_code,
                            comment=input_data.critique_comment,
                        )
                        critique_history.append(critique_result.critique)

                        if not critique_result.critique.needs_revision:
                            break

                        generation_result = await self.generator.execute_chunk_with_plan(
                            input_data,
                            analysis_result.analysis,
                            chunk,
                            part_number=idx,
                            total_parts=len(section_chunks),
                            critique_text=critique_result.critique.critique,
                            previous_code=generation_result.response.document_code
                        )
                        critique_count += 1

                chunk_codes.append(generation_result.response.document_code)
                self._save_code_snapshot(run_dir, f"01_chunk_{idx}", generation_result.response.document_code)

            generation_result = await self.generator.synthesize_from_chunks(input_data, chunk_codes)
            logger.info(f"Synthesis complete: {len(generation_result.response.document_code)} chars of document code")
            self._save_code_snapshot(run_dir, "02_synthesized", generation_result.response.document_code)
        elif plan:
            generation_result = await self.generator.execute_with_plan(
                input_data,
                analysis_result.analysis,
                plan
            )
            logger.info(f"Generation complete: {len(generation_result.response.document_code)} chars of document code")
            self._save_code_snapshot(run_dir, "01_initial", generation_result.response.document_code)
        else:
            generation_result = await self.generator.execute(
                input_data,
                analysis_result.analysis
            )
            logger.info(f"Generation complete: {len(generation_result.response.document_code)} chars of document code")
            self._save_code_snapshot(run_dir, "01_initial", generation_result.response.document_code)
        
        # Step 4: Optional Critique Loop (skip if generation chunking was used)
        critique_count = 0
        while self._is_critiquer_enabled(input_data) and not use_generation_chunking and critique_count < self.config.workflow.max_critiques:
            logger.info(f"Critique pass {critique_count + 1}/{self.config.workflow.max_critiques}")
            
            critique_result = await self.critiquer.execute(
                analysis_result.analysis,
                generation_result.response.document_code,
                comment=input_data.critique_comment,
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
            # Save revised code snapshot after each critique
            self._save_code_snapshot(run_dir, f"02_critique_revision_{critique_count + 1}", generation_result.response.document_code)
            critique_count += 1
        
        # Step 5: Execute code with error recovery loop
        max_error_loops = self.config.workflow.max_error_loops
        current_response = generation_result.response
        
        # Use separate directories for images and docx
        docx_dir = run_dir / "word_document"
        image_dir = run_dir / "image_assets"
        docx_path = docx_dir / "proposal.docx"
        code_stats = {}
        
        for error_loop in range(max_error_loops + 1):
            docx_path, code_stats = await self.code_interpreter.execute(
                current_response,
                image_dir=image_dir,
                docx_dir=docx_dir
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
                # Save error recovery code snapshot
                self._save_code_snapshot(run_dir, f"03_error_recovery_{error_loop + 1}", current_response.document_code)
            else:
                logger.error(f"Code execution failed after {max_error_loops + 1} attempts - giving up")
        
        # Save metadata artifacts to metadata folder
        self._save_metadata(run_dir, analysis_result.analysis, plan, critique_history)
        
        # Save final code snapshot
        self._save_code_snapshot(run_dir, "99_final", current_response.document_code)
        
        return FinalResult(
            response=current_response,
            analysis=analysis_result.analysis,
            plan=plan,
            critique_history=critique_history,
            error_recovery_count=error_recovery_count,
            docx_path=str(docx_path),
            execution_stats=code_stats,
            run_id=run_id
        )
    
    async def run_stream(
        self, 
        input_data: WorkflowInput,
    ) -> AsyncIterator[WorkflowEvent]:
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
        
        # Create a run directory for this execution (consistent with run())
        run_dir = self._create_run_directory()
        run_id = run_dir.name  # e.g., "run_20260201_123456"
        logger.info(f"Run directory: {run_dir}")
        
        # Save uploaded documents to run directory
        self._save_documents(run_dir, input_data)
        
        # Initialize executors for this run
        self._initialize_executors(run_dir)
        
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
            if self._is_planner_enabled(input_data):
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
            use_generation_chunking = self._should_chunk_generation(input_data, plan)

            if plan and use_generation_chunking:
                max_sections = input_data.max_sections_per_chunk if input_data.max_sections_per_chunk is not None else self.config.features.max_sections_per_chunk
                section_chunks = self._chunk_sections(plan.sections, max_sections)
                chunk_codes: list[str] = []

                for idx, chunk in enumerate(section_chunks, start=1):
                    yield WorkflowEvent(
                        event_type="step_started",
                        step_name="generate_chunk",
                        message=f"Generating chunk {idx}/{len(section_chunks)}..."
                    )

                    generation_result = await self.generator.execute_chunk_with_plan(
                        input_data,
                        analysis_result.analysis,
                        chunk,
                        part_number=idx,
                        total_parts=len(section_chunks),
                    )

                    if self._is_critiquer_enabled(input_data):
                        critique_count = 0
                        chunk_req_ids = {req_id for section in chunk for req_id in (section.related_requirements or [])}
                        chunk_requirements = [
                            req for req in analysis_result.analysis.requirements if req.id in chunk_req_ids
                        ]
                        chunk_analysis = RFPAnalysis(
                            summary=analysis_result.analysis.summary,
                            requirements=chunk_requirements
                        )

                        while critique_count < self.config.workflow.max_critiques:
                            critique_result = await self.critiquer.execute(
                                chunk_analysis,
                                generation_result.response.document_code,
                                comment=input_data.critique_comment,
                            )
                            critique_history.append(critique_result.critique)

                            if not critique_result.critique.needs_revision:
                                break

                            generation_result = await self.generator.execute_chunk_with_plan(
                                input_data,
                                analysis_result.analysis,
                                chunk,
                                part_number=idx,
                                total_parts=len(section_chunks),
                                critique_text=critique_result.critique.critique,
                                previous_code=generation_result.response.document_code
                            )
                            critique_count += 1

                    chunk_codes.append(generation_result.response.document_code)
                    self._save_code_snapshot(run_dir, f"01_chunk_{idx}", generation_result.response.document_code)

                    yield WorkflowEvent(
                        event_type="step_complete",
                        step_name="generate_chunk",
                        message=f"Generated chunk {idx}/{len(section_chunks)}",
                        data={"document_code_length": len(generation_result.response.document_code)}
                    )

                generation_result = await self.generator.synthesize_from_chunks(input_data, chunk_codes)
                self._save_code_snapshot(run_dir, "02_synthesized", generation_result.response.document_code)

                yield WorkflowEvent(
                    event_type="step_complete",
                    step_name="generate",
                    message=f"Synthesized {len(generation_result.response.document_code)} chars of document code",
                    data={"document_code_length": len(generation_result.response.document_code)}
                )
            elif plan:
                generation_result = await self.generator.execute_with_plan(
                    input_data,
                    analysis_result.analysis,
                    plan
                )
                yield WorkflowEvent(
                    event_type="step_complete",
                    step_name="generate",
                    message=f"Generated {len(generation_result.response.document_code)} chars of document code",
                    data={"document_code_length": len(generation_result.response.document_code)}
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
            
            # Step 4: Optional Critique Loop (skip if generation chunking was used)
            critique_count = 0
            while self._is_critiquer_enabled(input_data) and not use_generation_chunking and critique_count < self.config.workflow.max_critiques:
                yield WorkflowEvent(
                    event_type="step_started",
                    step_name="critique",
                    message=f"Reviewing document (pass {critique_count + 1})..."
                )
                
                critique_result = await self.critiquer.execute(
                    analysis_result.analysis,
                    generation_result.response.document_code,
                    comment=input_data.critique_comment,
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
            
            # Use separate directories for images and docx (consistent with run())
            docx_dir = run_dir / "word_document"
            image_dir = run_dir / "image_assets"
            docx_path = docx_dir / "proposal.docx"
            code_stats = {}
            
            for error_loop in range(max_error_loops + 1):
                yield WorkflowEvent(
                    event_type="step_started",
                    step_name="execute_code",
                    message=f"Executing code to create Word document{' (retry)' if error_loop > 0 else ''}..."
                )
                
                docx_path, code_stats = await self.code_interpreter.execute(
                    current_response,
                    image_dir=image_dir,
                    docx_dir=docx_dir
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
            
            # Save metadata artifacts (consistent with run())
            self._save_metadata(run_dir, analysis_result.analysis, plan, critique_history)
            self._save_code_snapshot(run_dir, "99_final", current_response.document_code)
            
            # Complete
            yield WorkflowEvent(
                event_type="finished",
                message="RFP generation complete",
                data={
                    "docx_path": str(docx_path),
                    "run_dir": str(run_dir),
                    "run_id": run_id,
                    "document_success": code_stats.get('document_success', False),
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
