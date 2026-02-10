"""
Configuration management for RFP Builder.
Loads settings from config.toml with support for Azure OpenAI and direct OpenAI.
"""

from pathlib import Path
from typing import Optional
import os
import json
import base64
import tomli
from pydantic import BaseModel, Field


class AzureConfig(BaseModel):
    """Azure OpenAI configuration."""
    endpoint: str = ""
    model: str = "gpt-4o"
    deployment: str = ""
    api_version: str = "2024-02-15-preview"
    api_key: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", ""))
    
    @property
    def is_configured(self) -> bool:
        """Check if Azure is configured (has endpoint)."""
        return bool(self.endpoint.strip())
    
    @property
    def deployment_name(self) -> str:
        """Get deployment name, defaulting to model name."""
        return self.deployment.strip() or self.model


class OpenAIConfig(BaseModel):
    """Direct OpenAI configuration."""
    api_key: str = ""
    model: str = "gpt-4o"
    base_url: str = ""
    
    @property
    def is_configured(self) -> bool:
        """Check if OpenAI is configured (has API key)."""
        return bool(self.api_key.strip())


class AppConfig(BaseModel):
    """Application settings."""
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    max_file_size_mb: int = 50
    allowed_extensions: list[str] = Field(default_factory=lambda: ["pdf"])
    upload_dir: str = "./uploads"
    output_dir: str = "./outputs/runs"
    
    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024


class FeaturesConfig(BaseModel):
    """Feature toggles."""
    enable_images: bool = True
    enable_tables: bool = True
    image_dpi: int = 150
    max_images: int = 50
    min_table_rows: int = 2
    min_table_cols: int = 2
    image_ratio_examples: float = 0.5
    image_ratio_rfp: float = 0.25
    image_ratio_context: float = 0.25
    enable_auth: bool = False
    front_end_auth: bool = False
    front_end_required_role: str = ""
    admin_permission: str = ""
    toggle_requirements_chunking: bool = False
    max_tokens_reqs_chunking: int = 12000
    toggle_generation_chunking: bool = False
    max_tokens_generation_chunking: int = 12000
    generator_intro_pages: int = 3
    generation_page_overlap: int = 1
    max_sections_per_chunk: int = 3

    def normalized_image_ratios(self, include_examples: bool, include_rfp: bool, include_context: bool) -> dict[str, float]:
        ratios = {
            "examples": self.image_ratio_examples,
            "rfp": self.image_ratio_rfp,
            "context": self.image_ratio_context,
        }
        if not include_examples:
            ratios["examples"] = 0.0
        if not include_rfp:
            ratios["rfp"] = 0.0
        if not include_context:
            ratios["context"] = 0.0
        total = sum(ratios.values())
        if total <= 0:
            active = []
            if include_examples:
                active.append("examples")
            if include_rfp:
                active.append("rfp")
            if include_context:
                active.append("context")
            if not active:
                return {"examples": 0.0, "rfp": 0.0, "context": 0.0}
            equal = 1.0 / len(active)
            return {
                "examples": equal if "examples" in active else 0.0,
                "rfp": equal if "rfp" in active else 0.0,
                "context": equal if "context" in active else 0.0,
            }
        return {key: value / total for key, value in ratios.items()}


class MSALConfig(BaseModel):
    """Microsoft Authentication Library configuration."""
    client_id: str = ""
    tenant_id: str = ""
    redirect_uri: str = "http://localhost:3000"
    scopes: list[str] = Field(default_factory=lambda: ["User.Read"])
    
    @property
    def is_configured(self) -> bool:
        """Check if MSAL is fully configured."""
        return bool(self.client_id.strip() and self.tenant_id.strip())


class APIAuthConfig(BaseModel):
    """API authentication configuration."""
    enabled: bool = False
    header_name: str = "X-API-Key"
    token_type: str = "bearer"  # "bearer", "jwt", or "custom"
    # JWT secret for validating signed tokens (only for jwt type)
    jwt_secret: str = ""
    # List of required token fields and their expected values
    # Example: [{"field": "user_id", "value": "admin"}, {"field": "org", "value": "acme"}]
    required_fields: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of dicts with 'field' and 'value' keys. Token claims/fields must match to be valid."
    )
    
    @property
    def is_configured(self) -> bool:
        """Check if API auth is properly configured."""
        return self.enabled and len(self.required_fields) > 0


class WorkflowConfig(BaseModel):
    """Agent Framework workflow settings."""
    llm_timeout: int = 120
    max_retries: int = 3
    verbose: bool = False
    log_all_steps: bool = True
    
    # Planner settings
    enable_planner: bool = False
    
    # Critiquer settings
    enable_critiquer: bool = False
    max_critiques: int = 1
    
    # Error recovery settings
    max_error_loops: int = 2


class StorageConfig(BaseModel):
    """Azure Blob storage settings."""
    use_blob_storage: bool = False
    use_local_storage: bool = True
    blob_account_name: str = ""
    blob_container_name: str = "rfps"
    blob_runs_prefix: str = "runs"


class Config(BaseModel):
    """Root configuration object."""
    azure: AzureConfig = Field(default_factory=AzureConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    msal: MSALConfig = Field(default_factory=MSALConfig)
    api_auth: APIAuthConfig = Field(default_factory=APIAuthConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    
    @property
    def use_azure(self) -> bool:
        """Determine if we should use Azure OpenAI."""
        return self.azure.is_configured


def find_config_file() -> Path:
    """Find the config.toml file, searching up from cwd."""
    # Check common locations
    candidates = [
        Path("config.toml"),
        Path("../config.toml"),
        Path(__file__).parent.parent.parent.parent / "config.toml",
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    
    raise FileNotFoundError(
        "config.toml not found. Please copy config.toml.example to config.toml "
        "and configure your settings."
    )


def _parse_env_value(raw: str):
    text = raw.strip()
    normalized = text.strip("'\"")
    if normalized.startswith("__JSON_B64__"):
        payload = normalized[len("__JSON_B64__"):].strip()
        if payload:
            try:
                decoded = base64.b64decode(payload).decode("utf-8")
                return json.loads(decoded)
            except Exception:
                return normalized
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    if text.startswith("[") or text.startswith("{"):
        try:
            return json.loads(text)
        except Exception:
            pass
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _assign_nested(target: dict, path: list[str], value):
    current = target
    for key in path[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[path[-1]] = value


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_env_overrides() -> dict:
    """
    Load config overrides from environment variables.

    Supported generic patterns:
    - SECTION__FIELD=value
    - RFP_SECTION__FIELD=value
    - APPSETTING_SECTION__FIELD=value

    Also maps common Azure/OpenAI env vars.
    """
    overrides: dict = {}

    allowed_sections = {
        "azure",
        "openai",
        "app",
        "features",
        "msal",
        "api_auth",
        "workflow",
        "storage",
    }

    for key, raw in os.environ.items():
        candidate = key
        if candidate.startswith("APPSETTING_"):
            candidate = candidate[len("APPSETTING_"):]
        if candidate.startswith("RFP_"):
            candidate = candidate[len("RFP_"):]
        if "__" not in candidate:
            continue
        parts = [p.strip().lower() for p in candidate.split("__") if p.strip()]
        if len(parts) < 2:
            continue
        if parts[0] not in allowed_sections:
            continue
        _assign_nested(overrides, parts, _parse_env_value(raw))

    # Common convenience mappings (single vars used in Azure App Settings).
    common = {
        "AZURE_OPENAI_ENDPOINT": ["azure", "endpoint"],
        "AZURE_OPENAI_API_VERSION": ["azure", "api_version"],
        "AZURE_OPENAI_DEPLOYMENT": ["azure", "deployment"],
        "AZURE_OPENAI_MODEL": ["azure", "model"],
        "AZURE_OPENAI_API_KEY": ["azure", "api_key"],
        "OPENAI_API_KEY": ["openai", "api_key"],
        "OPENAI_MODEL": ["openai", "model"],
        "OPENAI_BASE_URL": ["openai", "base_url"],
        "PORT": ["app", "port"],
        "WEBSITES_PORT": ["app", "port"],
    }
    for env_name, path in common.items():
        raw = os.getenv(env_name)
        if raw is None or raw == "":
            continue
        _assign_nested(overrides, path, _parse_env_value(raw))

    return overrides


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from TOML file."""
    file_data: dict = {}
    if config_path is None:
        try:
            config_path = find_config_file()
        except FileNotFoundError:
            config_path = None

    if config_path is not None and config_path.exists():
        with open(config_path, "rb") as f:
            file_data = tomli.load(f)

    env_overrides = _load_env_overrides()
    data = _deep_merge(file_data, env_overrides)
    return Config(**data)


# Global config instance (lazy loaded)
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> Config:
    """Reload configuration from disk."""
    global _config
    _config = load_config()
    return _config
