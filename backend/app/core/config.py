"""Application settings (environment driven, no hard-coded production secrets)."""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        protected_namespaces=(),
        env_file=(str(PROJECT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        extra="ignore",
    )

    app_name: str = "TrafficVision AI"
    environment: str = "development"  # development | production | test
    debug: bool = False

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'trafficvision.db').as_posix()}"
    secret_key: str = ""
    access_token_expire_minutes: int = 720
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    data_dir: Path = BACKEND_DIR / "data"
    sample_dir: Path = PROJECT_DIR / "sample_data"
    model_dir: Path = BACKEND_DIR / "models"
    yolo_model: str = "yolo11n.pt"
    device: str = "auto"  # auto | cpu | cuda:0 | mps

    max_upload_mb: int = 500
    max_concurrent_video_jobs: int = 1

    seed_demo_data: bool = True
    demo_admin_email: str = "admin@trafficvision.demo"
    demo_admin_password: str = "Admin@12345"
    demo_operator_email: str = "operator@trafficvision.demo"
    demo_operator_password: str = "Operator@12345"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def evidence_dir(self) -> Path:
        return self.data_dir / "evidence"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.upload_dir, self.processed_dir, self.evidence_dir,
                  self.model_dir, self.sample_dir):
            d.mkdir(parents=True, exist_ok=True)

    def resolve_secret(self) -> str:
        """Return the JWT secret. In production it MUST come from the environment."""
        if self.secret_key:
            return self.secret_key
        if self.environment == "production":
            raise RuntimeError("SECRET_KEY must be set when ENVIRONMENT=production")
        # Development: generate once and persist locally (never committed, see .gitignore).
        self.data_dir.mkdir(parents=True, exist_ok=True)
        f = self.data_dir / ".dev_secret"
        if not f.exists():
            f.write_text(secrets.token_urlsafe(48))
        return f.read_text().strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
