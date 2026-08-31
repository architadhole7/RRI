from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RevenueGuard"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    # Recovery Policy Defaults
    max_retries: int = 3
    cooldown_hours: int = 24
    contact_limit: int = 2
    human_approval_threshold_inr: float = 5000.0
    kill_switch_enabled: bool = False

    # Directories
    model_dir: str = "data/models"
    data_dir: str = "data"

    # Operator Identity (Configured Display - Auth deferred for MVP)
    operator_name: str = "Merchant Operations Admin"
    operator_role: str = "merchant_operator"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()