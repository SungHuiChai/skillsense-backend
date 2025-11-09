"""
Configuration management for SkillSense API
Loads settings from environment variables
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database
    DATABASE_URL: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # File Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10485760  # 10MB
    ALLOWED_EXTENSIONS: str = "pdf,docx,txt"

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "SkillSense API"
    VERSION: str = "1.0.0"

    # CORS
    BACKEND_CORS_ORIGINS: str = '["http://localhost:3000", "http://localhost:5173"]'

    # Admin
    ADMIN_EMAIL: str = "admin@skillsense.com"
    ADMIN_PASSWORD: str = "Admin@123"

    # Supabase (Optional)
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # Application
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Phase 2: Data Collection API Keys
    GITHUB_TOKEN: str = ""
    TAVILY_API_KEY: str = ""
    COLLECTION_TIMEOUT: int = 60
    MAX_COLLECTION_RETRIES: int = 3
    ENABLE_PARALLEL_COLLECTION: bool = True

    # Phase 2: Throttling Configuration
    GITHUB_CRAWL_COOLDOWN_SECONDS: int = 3600  # 1 hour between GitHub crawls per user
    ENABLE_CRAWL_THROTTLING: bool = True

    # OpenAI Configuration
    OPENAI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow"
    )

    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from JSON string"""
        try:
            return json.loads(self.BACKEND_CORS_ORIGINS)
        except:
            return ["http://localhost:3000", "http://localhost:5173"]

    @property
    def allowed_extensions_list(self) -> List[str]:
        """Get allowed file extensions as a list"""
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(',')]


# Global settings instance
settings = Settings()
