"""
Configuration endpoints for frontend.
"""

from fastapi import APIRouter, HTTPException

from app.core.config import get_config
from app.models.schemas import (
    ConfigResponse,
    WorkflowStepConfig,
    PromptDefinition,
    PromptsResponse,
    PromptUpdateRequest,
)
from app.prompts import system_prompts, user_prompts


router = APIRouter(prefix="/api/config", tags=["Config"])
_PROMPT_MODULES = {
    "system": system_prompts,
    "base": user_prompts,
}


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
        front_end_auth=config.features.front_end_auth,
        front_end_required_role=config.features.front_end_required_role.strip() or None,
        images_enabled=config.features.enable_images,
        enable_planner=enable_planner,
        enable_critiquer=enable_critiquer,
        workflow_steps=_build_workflow_steps(enable_planner, enable_critiquer),
    )
    
    # Expose MSAL config when auth-dependent frontend features are enabled.
    if (config.features.enable_auth or config.features.front_end_auth) and config.msal.is_configured:
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


def _parse_user_roles(raw_roles: str | None) -> set[str]:
    if not raw_roles:
        return set()
    return {role.strip() for role in raw_roles.split(",") if role.strip()}


def _authorize_prompt_access(admin_permission: str | None, user_roles: set[str] | None = None) -> None:
    config = get_config()
    if not config.features.front_end_auth:
        return

    expected_permission = config.features.admin_permission.strip()
    required_role = config.features.front_end_required_role.strip()
    roles = user_roles or set()

    if expected_permission and admin_permission and admin_permission.strip() == expected_permission:
        return

    if required_role and required_role in roles:
        return

    if not expected_permission and not required_role:
        raise HTTPException(
            status_code=500,
            detail="front_end_auth is enabled but no authorization rule is configured.",
        )

    raise HTTPException(
        status_code=403,
        detail="Prompt access denied. Missing valid admin_permission or required role.",
    )


@router.get("/prompts", response_model=PromptsResponse)
async def get_prompts(
    admin_permission: str | None = None,
    user_roles: str | None = None,
):
    """Return system/base prompt catalog for frontend viewing."""
    _authorize_prompt_access(admin_permission, _parse_user_roles(user_roles))
    return PromptsResponse(
        system_prompts=_collect_prompt_definitions(system_prompts),
        base_prompts=_collect_prompt_definitions(user_prompts),
    )


@router.put("/prompts", response_model=PromptDefinition)
async def update_prompt(payload: PromptUpdateRequest):
    """Update a single prompt in memory for this backend process."""
    _authorize_prompt_access(payload.admin_permission, set(payload.user_roles or []))

    module = _PROMPT_MODULES.get(payload.prompt_group)
    if module is None:
        raise HTTPException(status_code=400, detail="Invalid prompt_group.")

    prompt_name = payload.prompt_name.strip()
    if not prompt_name.endswith("_PROMPT"):
        raise HTTPException(status_code=400, detail="prompt_name must end with _PROMPT.")
    if not prompt_name:
        raise HTTPException(status_code=400, detail="prompt_name is required.")

    existing = getattr(module, prompt_name, None)
    if not isinstance(existing, str):
        raise HTTPException(status_code=404, detail="Prompt not found.")

    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="content cannot be empty.")

    setattr(module, prompt_name, payload.content)

    if payload.prompt_group == "system" and prompt_name == "DOCX_FORMATTING_INJECTION_PROMPT":
        system_prompts.RFP_SECTION_GENERATOR_SYSTEM_PROMPT = system_prompts.build_rfp_section_generator_system_prompt(
            payload.content
        )

    return PromptDefinition(name=prompt_name, content=payload.content)
