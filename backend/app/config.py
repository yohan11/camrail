import os
import logging
from typing import List, Union
from pydantic import model_validator
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
    
    # Sécurité JWT & Authentification
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_HOURS: int = 8
    
    # Protection force brute
    LOGIN_MAX_FAILURES: int = 5
    LOCKOUT_MINUTES: int = 15
    LOGIN_MAX_PER_IP: int = 20
    TRUSTED_PROXIES: str = ""
    ENABLE_HSTS: bool = False
    
    # Intégrité du Journal d'Audit (Chaîne HMAC-SHA256)
    AUDIT_HMAC_KEY: str = ""
    
    # Règles métier RH / Upload
    MIN_REST_HOURS: int = 12
    MAX_WEEKLY_HOURS: int = 48
    MAX_UPLOAD_MB: int = 25
    MAX_UNCOMPRESSED_MB: int = 200
    MAX_PDF_PAGES: int = 2000
    MAX_ZIP_RATIO: int = 100
    
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

    @property
    def trusted_proxies_list(self) -> List[str]:
        if not self.TRUSTED_PROXIES:
            return []
        return [ip.strip() for ip in str(self.TRUSTED_PROXIES).split(",") if ip.strip()]

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        secret = getattr(self, "JWT_SECRET", "") or ""
        is_weak = False
        weak_reason = ""

        known_weak = {
            "changeme",
            "secret",
            "secretkey",
            "jwtsecret",
            "password",
            "admin",
            "remplacez_cette_cle_par_une_chaine_aleatoire_securisee_en_production",
            "12345678901234567890123456789012",
            "abcdefghijklmnopqrstuvwxyz123456",
        }

        weak_keywords = ["changeme", "remplacez_cette_cle"]

        if not secret:
            is_weak = True
            weak_reason = "JWT_SECRET est absent ou vide."
        elif len(secret) < 32:
            is_weak = True
            weak_reason = f"JWT_SECRET trop court ({len(secret)} caractères, minimum 32 requis)."
        elif secret.lower() in known_weak or any(k in secret.lower() for k in weak_keywords):
            is_weak = True
            weak_reason = "JWT_SECRET utilise une valeur par défaut ou connue comme faible."
        elif len(set(secret)) <= 4:
            is_weak = True
            weak_reason = "JWT_SECRET contient trop de caractères répétés."

        if self.APP_ENV == "production":
            if is_weak:
                raise ValueError(f"Démarrage refusé en production : {weak_reason}")
        else:
            if is_weak:
                logger = logging.getLogger("railmind")
                logger.warning(
                    f"ATTENTION SÉCURITÉ (développement) : {weak_reason} "
                    "Générez une clé robuste avec : python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )

        # Validation de AUDIT_HMAC_KEY (clé HMAC dédiée et distincte pour la chaîne d'audit)
        audit_key = getattr(self, "AUDIT_HMAC_KEY", "") or ""
        audit_weak = False
        audit_reason = ""

        if not audit_key:
            audit_weak = True
            audit_reason = "AUDIT_HMAC_KEY est absent ou vide."
        elif len(audit_key) < 32:
            audit_weak = True
            audit_reason = f"AUDIT_HMAC_KEY trop courte ({len(audit_key)} caractères, minimum 32 requis)."
        elif audit_key == secret:
            audit_weak = True
            audit_reason = "AUDIT_HMAC_KEY doit impérativement être distincte de JWT_SECRET."
        elif audit_key.lower() in known_weak or any(k in audit_key.lower() for k in weak_keywords):
            audit_weak = True
            audit_reason = "AUDIT_HMAC_KEY utilise une valeur par défaut ou connue comme faible."
        elif len(set(audit_key)) <= 4:
            audit_weak = True
            audit_reason = "AUDIT_HMAC_KEY contient trop de caractères répétés."

        if self.APP_ENV == "production":
            if audit_weak:
                raise ValueError(f"Démarrage refusé en production : {audit_reason}")
        else:
            if audit_weak:
                logger = logging.getLogger("railmind")
                logger.warning(
                    f"ATTENTION SÉCURITÉ (développement) : {audit_reason} "
                    "Générez une clé HMAC robuste avec : python -c \"import secrets; print(secrets.token_hex(32))\""
                )
                if not audit_key:
                    self.AUDIT_HMAC_KEY = "dev_audit_hmac_key_railmind_camrail_32chars_min!"

        return self

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
