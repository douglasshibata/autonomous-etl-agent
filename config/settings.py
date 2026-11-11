from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    app_name: str = "Autonomous ETL Agent Platform"
    app_version: str = "2.0.0"
    environment: str = Field(default="production", alias="ENVIRONMENT")

    # Sandboxing & Resource Quotas
    sandbox_memory_limit_mb: int = Field(default=2048, alias="SANDBOX_MEMORY_LIMIT_MB")
    subprocess_timeout_seconds: int = Field(default=30, alias="SUBPROCESS_TIMEOUT_SECONDS")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")

    # Storage & Workspace Isolation
    sessions_root_dir: Path = Field(default=Path("/tmp/sessions"), alias="SESSIONS_ROOT_DIR")
    base_data_dir: Path = Field(default=Path("data"), alias="BASE_DATA_DIR")
    scripts_dir: Path = Field(default=Path("scripts"), alias="SCRIPTS_DIR")

    # LLM Settings
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    agent_model: str = Field(default="gpt-4o", alias="AGENT_MODEL")
    temperature: float = Field(default=0.0, alias="AGENT_TEMPERATURE")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()
