"""
Configuration endpoints for frontend.
"""

from fastapi import APIRouter

from app.core.config import get_config
from app.models.schemas import ConfigResponse, WorkflowStepConfig, PromptDefinition, PromptsResponse
from app.prompts import system_prompts, user_prompts


router = APIRouter(prefix="/api/config", tags=["Config"])


def _build_workflow_steps(enable_planner: bool, enable_critiquer: bool) -> list[WorkflowStepConfig]:
    """
    Build the list of workflow steps based on configuration.
    
    Steps are dynamically included/excluded based on planner and critiquer settings.
    """
    steps = [
        WorkflowStepConfig(
            id="upload",
            name="Upload Documents",
            description="Preparing your files",
            enabled=True,
        ),
        WorkflowStepConfig(
            id="analyze",
            name="Analyze RFP",
            description="Extracting requirements",
            enabled=True,
        ),
        WorkflowStepConfig(
            id="plan",
            name="Plan Proposal",
            description="Creating proposal structure",
            enabled=enable_planner,
        ),
        WorkflowStepConfig(
            id="generate",
            name="Generate Sections",
            description="Creating proposal content",
            enabled=True,
        ),
        WorkflowStepConfig(
            id="execute_code",
            name="Execute Code",
            description="Generating diagrams, charts & tables",
            enabled=True,
        ),
        WorkflowStepConfig(
            id="critique",
            name="Quality Review",
            description="Checking compliance",
            enabled=enable_critiquer,
        ),
        WorkflowStepConfig(
            id="revise",
            name="Revise",
            description="Improving based on feedback",
            enabled=enable_critiquer,
        ),
        WorkflowStepConfig(
            id="complete",
            name="Complete",
            description="Document ready for download",
            enabled=True,
        ),
    ]
    return steps


@router.get("", response_model=ConfigResponse)
async def get_frontend_config():
    """
    Get frontend configuration.
    
    Returns public configuration needed by the frontend,
    including auth settings, workflow settings, and dynamic step list.
    """
    config = get_config()
    
    enable_planner = config.workflow.enable_planner
    enable_critiquer = config.workflow.enable_critiquer
    
    response = ConfigResponse(
        auth_enabled=config.features.enable_auth,
        images_enabled=config.features.enable_images,
        enable_planner=enable_planner,
        enable_critiquer=enable_critiquer,
        workflow_steps=_build_workflow_steps(enable_planner, enable_critiquer),
    )
    
    # Only expose MSAL config if auth is enabled
    if config.features.enable_auth and config.msal.is_configured:
        response.msal_client_id = config.msal.client_id
        response.msal_tenant_id = config.msal.tenant_id
        response.msal_redirect_uri = config.msal.redirect_uri
        response.msal_scopes = config.msal.scopes
    
    return response


def _collect_prompt_definitions(module) -> list[PromptDefinition]:
    """Collect exported prompt constants from a module."""
    prompts: list[PromptDefinition] = []
    for name in sorted(dir(module)):
        if not name.endswith("_PROMPT"):
            continue
        value = getattr(module, name)
        if isinstance(value, str):
            prompts.append(PromptDefinition(name=name, content=value))
    return prompts


@router.get("/prompts", response_model=PromptsResponse)
async def get_prompts():
    """Return read-only system/base prompt catalog for frontend viewing."""
    return PromptsResponse(
        system_prompts=_collect_prompt_definitions(system_prompts),
        base_prompts=_collect_prompt_definitions(user_prompts),
    )
