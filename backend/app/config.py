import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_TIMEZONE: str = "Africa/Douala"
    
    DATABASE_URL: str
    
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    MIN_REST_HOURS: int = 12
    MAX_WEEKLY_HOURS: int = 48
    MAX_UPLOAD_MB: int = 25
    
    LLM_PROVIDER: str = "ollama"  # "ollama", "gemini", or "openai"
    GEMINI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    RAG_MIN_CONFIDENCE: float = 0.75
    
    TESSERACT_CMD_PATH: str = ""
    
    # Microsoft SSO Configuration
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_TENANT_ID: str = "common"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
