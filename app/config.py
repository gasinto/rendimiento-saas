"""
Application configuration via pydantic-settings.
All secrets and env-dependent values come from environment variables.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # PostgreSQL connection
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rendimiento"

    # JWT
    jwt_secret: str = "change-me-in-production-min-32-chars!!"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Admin seed
    admin_email: str = "admin@nsp.com"
    admin_password: str = "admin123"

    # CORS
    cors_origin: str = "*"

    # Logging
    log_level: str = "INFO"

    # App
    app_name: str = "rendimiento-saas"
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Railway injects DATABASE_URL as postgresql:// without +asyncpg suffix
        # but SQLAlchemy async needs postgresql+asyncpg://
        if self.database_url.startswith("postgresql://") and "+asyncpg" not in self.database_url:
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif self.database_url.startswith("postgres://") and "+asyncpg" not in self.database_url:
            self.database_url = self.database_url.replace("postgres://", "postgresql+asyncpg://", 1)


settings = Settings()
