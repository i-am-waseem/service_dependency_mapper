from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "Service Dependency Mapper"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    gemini_max_tokens: int = 4096
    gemini_max_retries: int = 3

    graph_persistence_path: Optional[str] = None

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    spof_in_degree_threshold: int = 2  # services with more dependents than this are SPOFs

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
