import time
import threading
from typing import Dict, List
from contextlib import contextmanager
from fastapi import HTTPException, status
from app.config import settings

class ConcurrencyLimiter:
    """
    Limite le nombre de générations LLM simultanées pour protéger les ressources CPU / GPU.
    Met les requêtes excédentaires en file d'attente avec un délai d'attente maximal configurable.
    Renvoie une erreur 503 explicite en cas d'expiration du délai d'attente.
    """
    def __init__(self, max_concurrent: int = 4, timeout: float = 60.0):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.semaphore = threading.Semaphore(max_concurrent)

    @contextmanager
    def slot(self):
        timeout = getattr(settings, "QUEUE_TIMEOUT_SECONDS", self.timeout)
        acquired = self.semaphore.acquire(timeout=float(timeout))
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le serveur est très sollicité, réessayez dans un instant"
            )
        try:
            yield
        finally:
            self.semaphore.release()

class UserRateLimiter:
    """
    Limitation de débit par utilisateur via une fenêtre glissante en mémoire (60 secondes).
    Protège les endpoints d'interrogation documentaire contre le spam et les abus.
    Renvoie un code HTTP 429 si la limite est dépassée.
    """
    def __init__(self, max_per_minute: int = 10, window_seconds: float = 60.0):
        self.max_per_minute = max_per_minute
        self.window_seconds = window_seconds
        self._user_timestamps: Dict[int, List[float]] = {}
        self._lock = threading.Lock()

    def check(self, user_id: int):
        limit = getattr(settings, "RATE_LIMIT_PER_MINUTE", self.max_per_minute)
        now = time.time()
        with self._lock:
            timestamps = self._user_timestamps.setdefault(user_id, [])
            # Filtrer les horodatages en dehors de la fenêtre glissante
            valid_timestamps = [t for t in timestamps if now - t < self.window_seconds]
            if len(valid_timestamps) >= limit:
                self._user_timestamps[user_id] = valid_timestamps
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Trop de requêtes, veuillez patienter une minute."
                )
            valid_timestamps.append(now)
            self._user_timestamps[user_id] = valid_timestamps

    def reset(self):
        """Réinitialise les compteurs (utile pour les tests unitaires)."""
        with self._lock:
            self._user_timestamps.clear()

# Instances globales uniques
concurrency_limiter = ConcurrencyLimiter(
    max_concurrent=getattr(settings, "MAX_CONCURRENT_GENERATIONS", 4),
    timeout=getattr(settings, "QUEUE_TIMEOUT_SECONDS", 60.0)
)
user_rate_limiter = UserRateLimiter(
    max_per_minute=getattr(settings, "RATE_LIMIT_PER_MINUTE", 10),
    window_seconds=60.0
)
