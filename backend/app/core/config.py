from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CCM_", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    bind_host: str = "127.0.0.1"
    data_dir: Path = Path("/data")
    storage_root: Path = Path("/data/files")
    framework_pack_root: Path = Path("/app/framework-packs")
    demo_files_root: Path = Path("/app/demo-files")
    load_demo: bool = False
    database_url: str = "sqlite:////data/compliance-control.db"
    auth_mode: Literal["disabled", "local"] = "disabled"
    allow_insecure_no_auth: bool = False
    bootstrap_admin_email: str | None = None
    bootstrap_admin_display_name: str = "Workspace administrator"
    bootstrap_admin_password: SecretStr | None = None
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )
    max_upload_bytes: int = 50 * 1024 * 1024
    allowed_upload_extensions: list[str] = Field(
        default_factory=lambda: [
            ".pdf",
            ".docx",
            ".xlsx",
            ".csv",
            ".txt",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".zip",
            ".json",
        ]
    )
    inference_enabled: bool = False
    inference_allowed_base_urls: list[str] = Field(default_factory=list)
    inference_max_concurrent_runs: int = Field(default=2, ge=1, le=8)
    inference_max_context_chars: int = Field(default=60_000, ge=1_000, le=600_000)
    inference_max_output_chars: int = Field(default=12_000, ge=1_000, le=120_000)
    inference_max_iterations: int = Field(default=4, ge=1, le=8)
    inference_max_tool_calls: int = Field(default=8, ge=0, le=32)
    inference_timeout_seconds: int = Field(default=90, ge=5, le=300)
    inference_agent_root: Path = Path("/app/agents")
    inference_skill_root: Path = Path("/app/skills")

    @model_validator(mode="after")
    def reject_remote_no_auth(self) -> Self:
        if (
            self.auth_mode == "disabled"
            and self.bind_host not in {"127.0.0.1", "localhost"}
            and not self.allow_insecure_no_auth
        ):
            raise ValueError("disabled authentication may only bind to loopback")
        if self.app_env == "production":
            bootstrap_password = (
                self.bootstrap_admin_password.get_secret_value()
                if self.bootstrap_admin_password is not None
                else ""
            )
            if "CHANGE_ME" in self.database_url or "CHANGE_ME" in bootstrap_password:
                raise ValueError("production configuration cannot use CHANGE_ME example secrets")
        return self
