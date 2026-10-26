import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "AI Agent Workflow Automation")
    environment: str = os.getenv("ENVIRONMENT", "development")


settings = Settings()
