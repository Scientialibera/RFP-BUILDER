"""
Microsoft Agent Framework Workflows for RFP Builder.

Simplified 3-step workflow:
1. Analyze: Extract requirements from RFP
2. Generate: Create proposal with markdown content and placeholders for diagrams/charts
3. Execute Code: Render Mermaid diagrams and Python charts
"""

from .rfp_workflow import RFPBuilderWorkflow, create_rfp_workflow
from .executors import (
    RFPAnalyzerExecutor,
    SectionGeneratorExecutor,
    CodeInterpreterExecutor,
)

__all__ = [
    "RFPBuilderWorkflow",
    "create_rfp_workflow",
    "RFPAnalyzerExecutor",
    "SectionGeneratorExecutor",
    "CodeInterpreterExecutor",
]
