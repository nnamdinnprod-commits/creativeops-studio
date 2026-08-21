from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    ai_provider: str = "mock"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ai_model: str = ""

    database_url: str = "sqlite:///./creativeops.db"

    capacity_tight_threshold: int = 85
    brief_readiness_threshold: int = 70

    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
