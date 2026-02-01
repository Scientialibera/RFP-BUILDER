"""
Configuration management for RFP Builder.
Loads settings from config.toml with support for Azure OpenAI and direct OpenAI.
"""

from pathlib import Path
from typing import Optional
import tomli
from pydantic import BaseModel, Field


class AzureConfig(BaseModel):
    """Azure OpenAI configuration."""
    endpoint: str = ""
    model: str = "gpt-4o"
    deployment: str = ""
    api_version: str = "2024-02-15-preview"
    
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
    output_dir: str = "./output"
    
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


class PDFOutputConfig(BaseModel):
    """PDF generation settings."""
    page_size: str = "letter"
    margin_top: int = 72
    margin_bottom: int = 72
    margin_left: int = 72
    margin_right: int = 72
    font_family: str = "Helvetica"
    font_size_body: int = 11
    font_size_h1: int = 24
    font_size_h2: int = 18
    font_size_h3: int = 14


class WorkflowConfig(BaseModel):
    """Agent Framework workflow settings."""
    llm_timeout: int = 120
    max_retries: int = 3
    verbose: bool = False
    log_all_steps: bool = True
    log_dir: str = "./logs"


class Config(BaseModel):
    """Root configuration object."""
    azure: AzureConfig = Field(default_factory=AzureConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    msal: MSALConfig = Field(default_factory=MSALConfig)
    pdf_output: PDFOutputConfig = Field(default_factory=PDFOutputConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    
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


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from TOML file."""
    if config_path is None:
        config_path = find_config_file()
    
    with open(config_path, "rb") as f:
        data = tomli.load(f)
    
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
