import os
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Environnement et localisation
    APP_ENV: str = "development"
    APP_TIMEZONE: str = "Africa/Douala"
    
    # Base de données PostgreSQL & Pool
    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    HNSW_EF_SEARCH: int = 64
    
    # Sécurité JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # Règles métier RH / Upload
    MIN_REST_HOURS: int = 12
    MAX_WEEKLY_HOURS: int = 48
    MAX_UPLOAD_MB: int = 25
    
    # Chemins et modèles locaux (100% hors-ligne)
    MODELS_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"
    EMBEDDING_DIM: int = 384
    EMBEDDING_QUERY_PREFIX: str = "query: "
    EMBEDDING_PASSAGE_PREFIX: str = "passage: "
    
    # LLM Local (Ollama)
    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_TIMEOUT_SECONDS: int = 120
    OLLAMA_NUM_PREDICT: int = 400
    OLLAMA_NUM_CTX: int = 6144
    RAG_LLM_TOP_K: int = 4
    
    # Reranker optionnel (désactivé par défaut sur CPU modeste)
    RERANKER_ENABLED: bool = False
    RERANKER_MODEL: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    
    # RAG Seuil et Chunking
    RAG_MIN_CONFIDENCE: float = 0.20
    CHUNK_SIZE_WORDS: int = 150
    CHUNK_OVERLAP_WORDS: int = 30
    DOCX_WORDS_PER_VIRTUAL_PAGE: int = 450
    EVIDENCE_MIN_SCORE: float = 0.30
    
    # Concurrence, files et limitation de débit
    MAX_CONCURRENT_GENERATIONS: int = 4
    QUEUE_TIMEOUT_SECONDS: int = 60
    RATE_LIMIT_PER_MINUTE: int = 10
    QUERY_EMBEDDING_CACHE_SIZE: int = 1024
    QUERY_CACHE_TTL_SECONDS: int = 3600
    UVICORN_WORKERS: int = 2
    
    # Outils OCR locaux
    TESSERACT_CMD_PATH: str = ""
    
    # URLs réseau configurables (évite tout localhost en dur)
    CORS_ORIGINS: str = "http://localhost:3000"
    FRONTEND_URL: str = "http://localhost:3000"
    API_PUBLIC_URL: str = "http://localhost:8000"
    
    # Authentification Microsoft SSO (Azure AD / Entra ID)
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_TENANT_ID: str = "common"

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        return [origin.strip() for origin in str(self.CORS_ORIGINS).split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
