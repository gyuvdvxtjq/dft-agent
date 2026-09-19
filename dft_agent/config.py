"""Configuration: reads .env at project root. Nothing here prints secrets."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    # LLM (Discovery token-plan, OpenAI-compatible)
    LLM_BASE_URL: str = os.getenv("DFT_LLM_BASE_URL", "https://discovery-api.intern-ai.org.cn/v1")
    LLM_API_KEY: str = os.getenv("DFT_LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("DFT_LLM_MODEL", "glm-5.3")

    # Execution backend
    RUNNER: str = os.getenv("DFT_RUNNER", "platform")  # "platform" | "local"
    PLATFORM_BASE: str = "https://discovery.intern-ai.org.cn"
    PLATFORM_TIMEOUT_S: int = 3600

    # Safety
    MAX_ATTEMPTS: int = int(os.getenv("DFT_MAX_ATTEMPTS", "2"))

    @classmethod
    def llm_ready(cls) -> bool:
        return bool(cls.LLM_API_KEY)


settings = Settings()
