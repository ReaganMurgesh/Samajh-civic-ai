"""Application configuration utilities for the Samajh platform."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv


load_dotenv()


def _parse_csv(value: str) -> List[str]:
    """Parse a comma-separated environment variable into a clean list."""
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass
class Config:
    """Typed application configuration loaded from environment variables."""

    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    app_host: str = field(default_factory=lambda: os.getenv("APP_HOST", "127.0.0.1"))
    app_port: int = field(default_factory=lambda: int(os.getenv("APP_PORT", "8000")))
    default_language: str = field(
        default_factory=lambda: os.getenv("DEFAULT_LANGUAGE", "english")
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )

    chroma_persist_dir: str = field(
        default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", "./chromadb")
    )
    postgresql_url: str = field(
        default_factory=lambda: os.getenv(
            "POSTGRESQL_URL", "postgresql://user:password@localhost:5432/samajh"
        )
    )
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )

    langfuse_public_key: str = field(
        default_factory=lambda: os.getenv("LANGFUSE_PUBLIC_KEY", "")
    )
    langfuse_secret_key: str = field(
        default_factory=lambda: os.getenv("LANGFUSE_SECRET_KEY", "")
    )
    langfuse_host: str = field(
        default_factory=lambda: os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    )

    firebase_project_id: str = field(
        default_factory=lambda: os.getenv("FIREBASE_PROJECT_ID", "")
    )
    firebase_client_email: str = field(
        default_factory=lambda: os.getenv("FIREBASE_CLIENT_EMAIL", "")
    )
    firebase_private_key: str = field(
        default_factory=lambda: os.getenv("FIREBASE_PRIVATE_KEY", "")
    )

    supported_languages: List[str] = field(
        default_factory=lambda: _parse_csv(
            os.getenv(
                "SUPPORTED_LANGUAGES",
                "english,hindi,tamil,telugu,kannada,bengali,marathi",
            )
        )
    )
    supported_domains: List[str] = field(
        default_factory=lambda: _parse_csv(
            os.getenv(
                "SUPPORTED_DOMAINS",
                "law,health,finance,news,schemes,environment,career,rights,general",
            )
        )
    )

    def validate(self) -> None:
        """Validate required settings depending on the current environment."""
        missing_keys: List[str] = []

        if not self.groq_api_key:
            missing_keys.append("GROQ_API_KEY")

        if self.app_env.lower() == "production":
            if not self.anthropic_api_key:
                missing_keys.append("ANTHROPIC_API_KEY")
            if not self.langfuse_public_key:
                missing_keys.append("LANGFUSE_PUBLIC_KEY")
            if not self.langfuse_secret_key:
                missing_keys.append("LANGFUSE_SECRET_KEY")

        if missing_keys:
            joined = ", ".join(missing_keys)
            raise ValueError(f"Missing required environment variables: {joined}")


config = Config()
