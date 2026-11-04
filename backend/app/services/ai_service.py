import collections
import hashlib
import json
import logging
import random
import re
import threading
import time
from typing import Optional, List, Dict, Any, Tuple, Generator
import httpx
from sqlalchemy.orm import Session
from app.config import settings
from app.models import PDFDocument, PDFPage
from app.services.pdf_service import search_relevant_pages, search_relevant_chunks

logger = logging.getLogger(__name__)


# ==============================================================================
# Exceptions
# ==============================================================================

class AIServiceError(Exception):
    """Base exception for Gemini AI service errors."""
    def __init__(
        self,
        message: str = "The AI service encountered an error.",
        status_code: int = 503,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.original_error = original_error


class AIServiceUnavailableError(AIServiceError):
    """Raised when Gemini AI is temporarily unavailable (e.g. 503 high demand, 504 timeout)."""
    def __init__(
        self,
        message: str = "The AI service is temporarily unavailable due to high demand. Please try again later.",
        status_code: int = 503,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, status_code=status_code, original_error=original_error)


class AIServiceRateLimitError(AIServiceError):
    """Raised when Gemini AI rate limit (RPM) or daily quota (RPD) is reached."""
    def __init__(
        self,
        message: str = "The AI service rate limit has been reached. Please try again in a few moments.",
        status_code: int = 429,
        is_daily_exhaustion: bool = False,
        retry_after_seconds: Optional[int] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, status_code=status_code, original_error=original_error)
        self.is_daily_exhaustion = is_daily_exhaustion
        self.retry_after_seconds = retry_after_seconds


class AIServiceConfigurationError(AIServiceError):
    """Raised when Gemini AI is misconfigured (missing API key, unsupported model 404, auth 401/403)."""
    def __init__(
        self,
        message: str = "The AI service configuration is invalid. Please check your settings.",
        status_code: int = 502,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, status_code=status_code, original_error=original_error)


# ==============================================================================
# Helper Functions: Error Parsing & Sanitization
# ==============================================================================

def sanitize_gemini_error(msg: str) -> str:
    """Removes API keys and sensitive tokens from error and log messages."""
    if not msg:
        return ""
    if getattr(settings, "GEMINI_API_KEY", None) and settings.GEMINI_API_KEY in msg:
        msg = msg.replace(settings.GEMINI_API_KEY, "[REDACTED_API_KEY]")
    msg = re.sub(r"(key=)[A-Za-z0-9_\-\.]{10,}", r"\1[REDACTED]", msg)
    msg = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", r"\1[REDACTED]", msg)
    return msg


def extract_retry_delay_seconds(exc: Exception) -> Optional[float]:
    """
    Extracts suggested retryDelay in seconds from Gemini API error message,
    HTTP headers (Retry-After), or metadata/details if present.
    """
    # 1. Check HTTP response headers if present (e.g. from httpx or google client error)
    response = getattr(exc, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None)
        if headers:
            retry_after = headers.get("retry-after") or headers.get("Retry-After")
            if retry_after:
                try:
                    return float(retry_after)
                except (ValueError, TypeError):
                    pass

    # 2. Check exception attributes or protobuf details
    details = getattr(exc, "details", None)
    if details:
        try:
            details_str = str(details)
            m = re.search(r"retryDelay[\'\":\s]+(\d+(?:\.\d+)?)s?", details_str, re.IGNORECASE)
            if m:
                return float(m.group(1))
        except Exception:
            pass

    # 3. Check error string patterns
    exc_str = str(exc)
    patterns = [
        r"retryDelay[\'\":\s]+(\d+(?:\.\d+)?)s?",
        r"retry[\s_-]?after[\'\":\s]+(\d+(?:\.\d+)?)s?",
        r"retry\s+in\s+(\d+(?:\.\d+)?)\s*s?",
        r"wait\s+(\d+(?:\.\d+)?)\s*s(?:econds)?",
        r"reset\s+in\s+(\d+(?:\.\d+)?)\s*s?",
    ]
    for pattern in patterns:
        match = re.search(pattern, exc_str, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, TypeError):
                pass
    return None


def is_daily_quota_exhaustion(exc: Exception, delay_seconds: Optional[float] = None) -> bool:
    """
    Distinguishes daily quota exhaustion (RPD) from a transient burst rate limit (RPM).
    Daily quota errors typically report retryDelay in hours/thousands of seconds
    or contain phrases like 'free_tier_requests', 'per day', 'requests per day', 'daily'.
    """
    if delay_seconds is not None and delay_seconds > 60.0:
        return True
    exc_upper = str(exc).upper()
    indicators = (
        "PER DAY",
        "REQUESTS PER DAY",
        "DAILY",
        "FREE_TIER_REQUESTS",
        "GENERATE_CONTENT_FREE_TIER_REQUESTS",
        "DAY LIMIT",
    )
    return any(ind in exc_upper for ind in indicators)


def is_transient_gemini_error(exc: Exception) -> Tuple[bool, int, str]:
    """
    Determines whether a Gemini API error is transient and retryable (e.g. transient 429 RPM, 500, 502, 503, 504).
    Daily quota exhaustion (RPD) is marked as NOT transient to avoid futile retry loops.
    Returns (is_transient, status_code, reason).
    """
    delay = extract_retry_delay_seconds(exc)
    is_daily = is_daily_quota_exhaustion(exc, delay)

    # Fast path for daily quota limits
    if is_daily:
        return False, 429, "DAILY_QUOTA_EXHAUSTED"

    # 1. Check if the exception has an integer HTTP code (e.g. google.genai.errors.APIError)
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        if code == 429:
            return True, 429, "RPM_RATE_LIMIT"
        if code in (500, 502, 503, 504):
            return True, code, f"HTTP_{code}"
        if code in (400, 401, 403, 404):
            return False, code, f"HTTP_{code}"

    # 2. Check for network / timeout exceptions
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return True, 504, "NETWORK_TIMEOUT"
    if isinstance(exc, (httpx.NetworkError, ConnectionError)):
        return True, 503, "NETWORK_CONNECTION_ERROR"

    # 3. Check status attribute if present
    status_attr = str(getattr(exc, "status", "")).upper()
    if status_attr in ("UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL", "DEADLINE_EXCEEDED"):
        if status_attr == "RESOURCE_EXHAUSTED":
            return True, 429, "RPM_RATE_LIMIT"
        code_map = {
            "UNAVAILABLE": 503,
            "INTERNAL": 500,
            "DEADLINE_EXCEEDED": 504,
        }
        return True, code_map.get(status_attr, 503), status_attr

    # 4. Check string contents
    exc_str = str(exc).upper()
    if (
        "429" in exc_str
        or "RESOURCE_EXHAUSTED" in exc_str
        or "RESOURCE EXHAUSTED" in exc_str
        or "TOO MANY REQUESTS" in exc_str
        or "QUOTA" in exc_str
        or "RATE LIMIT" in exc_str
        or "RATELIMIT" in exc_str
    ):
        return True, 429, "RPM_RATE_LIMIT"

    if "TIMEOUT" in exc_str or "TIMED OUT" in exc_str or "DEADLINE" in exc_str:
        return True, 504, "REQUEST_TIMEOUT"
    if "503" in exc_str or "UNAVAILABLE" in exc_str or "HIGH DEMAND" in exc_str:
        return True, 503, "503_UNAVAILABLE"
    if "500" in exc_str or "INTERNAL SERVER ERROR" in exc_str or "INTERNAL" in exc_str:
        return True, 500, "500_INTERNAL"
    if "502" in exc_str or "BAD GATEWAY" in exc_str:
        return True, 502, "502_BAD_GATEWAY"
    if "504" in exc_str or "GATEWAY TIMEOUT" in exc_str:
        return True, 504, "504_GATEWAY_TIMEOUT"
    if "404" in exc_str or "NOT_FOUND" in exc_str:
        return False, 404, "404_NOT_FOUND"
    if "401" in exc_str or "UNAUTHENTICATED" in exc_str or "INVALID API KEY" in exc_str:
        return False, 401, "401_UNAUTHENTICATED"
    if "403" in exc_str or "PERMISSION_DENIED" in exc_str:
        return False, 403, "403_FORBIDDEN"
    if "400" in exc_str or "INVALID_ARGUMENT" in exc_str:
        return False, 400, "400_BAD_REQUEST"

    return False, 500, "UNKNOWN_ERROR"


# ==============================================================================
# In-Memory Intelligent Cache with User & Document Isolation
# ==============================================================================

class AIResponseCache:
    """
    Thread-safe, TTL-based LRU response cache for AI outputs.
    Ensures strict user data isolation by including user_id in composite cache keys.
    Supports granular invalidation by PDF ID or User ID.
    """
    def __init__(self, ttl_seconds: int = 86400, max_items: int = 2000):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def _make_key(self, user_id: int, pdf_id: Optional[int], operation: str, query: str, model: str) -> str:
        norm_q = query.strip().lower()
        q_hash = hashlib.sha256(norm_q.encode("utf-8")).hexdigest()[:24]
        return f"{user_id}:{pdf_id or 0}:{operation}:{q_hash}:{model}"

    def get(self, user_id: int, pdf_id: Optional[int], operation: str, query: str, model: str) -> Optional[Any]:
        if not getattr(settings, "AI_CACHE_ENABLED", True):
            return None
        key = self._make_key(user_id, pdf_id, operation, query, model)
        now = time.time()
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                self.misses += 1
                return None
            if now > entry["expires_at"]:
                del self._cache[key]
                self.misses += 1
                return None
            self.hits += 1
            return entry["value"]

    def set(self, user_id: int, pdf_id: Optional[int], operation: str, query: str, model: str, value: Any):
        if not getattr(settings, "AI_CACHE_ENABLED", True):
            return
        key = self._make_key(user_id, pdf_id, operation, query, model)
        now = time.time()
        with self._lock:
            if len(self._cache) >= self.max_items:
                # Evict expired or oldest items
                expired = [k for k, v in self._cache.items() if now > v["expires_at"]]
                if expired:
                    for k in expired:
                        del self._cache[k]
                else:
                    oldest_k = min(self._cache.keys(), key=lambda k: self._cache[k]["expires_at"])
                    del self._cache[oldest_k]

            self._cache[key] = {
                "value": value,
                "expires_at": now + self.ttl,
                "pdf_id": pdf_id,
                "user_id": user_id,
            }

    def invalidate_pdf(self, pdf_id: int) -> int:
        """Invalidates all cached entries for a given PDF document."""
        with self._lock:
            keys_to_del = [k for k, v in self._cache.items() if v.get("pdf_id") == pdf_id]
            for k in keys_to_del:
                del self._cache[k]
            return len(keys_to_del)

    def invalidate_user(self, user_id: int) -> int:
        """Invalidates all cached entries for a given user."""
        with self._lock:
            keys_to_del = [k for k, v in self._cache.items() if v.get("user_id") == user_id]
            for k in keys_to_del:
                del self._cache[k]
            return len(keys_to_del)

    def clear(self):
        """Clears all cached entries."""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0


# Global cache instance
ai_cache = AIResponseCache(
    ttl_seconds=getattr(settings, "AI_CACHE_TTL_SECONDS", 86400)
)

# Concurrency limiter to prevent burst parallel spikes
_concurrency_semaphore = threading.Semaphore(
    getattr(settings, "GEMINI_MAX_CONCURRENT_REQUESTS", 2)
)


class GeminiRateLimiter:
    """
    Thread-safe sliding-window rate limiter and request throttler.
    Ensures outgoing requests to Gemini never exceed GEMINI_MAX_RPM
    and enforces a minimum spacing between consecutive dispatches.
    """
    def __init__(self, max_rpm: Optional[int] = None, min_interval: Optional[float] = None):
        self._max_rpm = max_rpm
        self._min_interval = min_interval
        self._timestamps: collections.deque = collections.deque()
        self._last_dispatch_time = 0.0
        self._lock = threading.Lock()

    @property
    def max_rpm(self) -> int:
        if self._max_rpm is not None:
            return self._max_rpm
        return getattr(settings, "GEMINI_MAX_RPM", 8)

    @property
    def min_interval(self) -> float:
        if self._min_interval is not None:
            return self._min_interval
        return getattr(settings, "GEMINI_MIN_REQUEST_INTERVAL_SECONDS", 1.0)

    def acquire(self, operation: str = "ai_request", timeout: float = 20.0):
        """
        Blocks until a request slot is available within rate limits, or raises
        AIServiceRateLimitError if waiting would exceed timeout.
        """
        start_wait = time.time()
        while True:
            now = time.time()
            with self._lock:
                cutoff = now - 60.0
                while self._timestamps and self._timestamps[0] < cutoff:
                    self._timestamps.popleft()

                time_since_last = now - self._last_dispatch_time
                spacing_wait = max(0.0, self.min_interval - time_since_last)

                if len(self._timestamps) < self.max_rpm and spacing_wait <= 0.0:
                    self._timestamps.append(now)
                    self._last_dispatch_time = now
                    return

                if len(self._timestamps) >= self.max_rpm:
                    rpm_wait = max(0.0, 60.0 - (now - self._timestamps[0]) + 0.1)
                else:
                    rpm_wait = 0.0

                wait_time = max(spacing_wait, rpm_wait)

            if (now - start_wait) + wait_time > timeout:
                logger.warning(
                    f"[RateLimiter] Throttling timeout exceeded ({timeout:.1f}s) for '{operation}'. RPM window full ({len(self._timestamps)}/{self.max_rpm})."
                )
                raise AIServiceRateLimitError(
                    message="The AI service rate limit has been reached. Please try again in a few moments.",
                    status_code=429,
                    is_daily_exhaustion=False,
                )

            logger.info(
                f"[RateLimiter] Throttling '{operation}': waiting {wait_time:.2f}s to respect {self.max_rpm} RPM limit."
            )
            time.sleep(min(wait_time, 2.0))

    def reset(self):
        """Resets rate limiter state (used in unit tests)."""
        with self._lock:
            self._timestamps.clear()
            self._last_dispatch_time = 0.0


# Global rate limiter instance
gemini_rate_limiter = GeminiRateLimiter()


# ==============================================================================
# Structured Telemetry Logger
# ==============================================================================

def log_ai_telemetry(
    operation: str,
    model: str,
    latency_ms: float,
    status_code: int,
    cached: bool = False,
    extra: Optional[str] = None,
):
    """
    Structured usage telemetry logger for AI operations.
    Guarantees no sensitive user data, API keys, or tokens are logged.
    """
    extra_str = f" {extra}" if extra else ""
    logger.info(
        f"[AI Telemetry] operation={operation} model={model} latency_ms={latency_ms:.1f} "
        f"status={status_code} cached={cached}{extra_str}"
    )


# ==============================================================================
# AIService Implementation
# ==============================================================================

class AIService:
    """
    AI Teacher service powered by Google Gemini API.
    Handles grounded Q&A with PDF context, learning path generation,
    topic explanations, and quiz question authoring with intelligent caching,
    strict rate-limit/quota handling, and graceful model fallback.
    """

    @classmethod
    def get_client(cls):
        """Initializes and returns the Gemini Client with a finite HTTP timeout if API key is configured."""
        if not settings.GEMINI_API_KEY:
            return None
        try:
            from google import genai
            from google.genai import types
            timeout_ms = int(getattr(settings, "GEMINI_TIMEOUT_SECONDS", 12.0) * 1000)
            http_options = types.HttpOptions(timeout=timeout_ms)
            return genai.Client(api_key=settings.GEMINI_API_KEY, http_options=http_options)
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini Client: {sanitize_gemini_error(str(e))}")
            return None

    @classmethod
    def _raise_mapped_error(cls, status_code: int, reason: str, original_error: Optional[Exception] = None):
        """Maps HTTP/API status codes to clean, safe, user-facing AIService errors."""
        if status_code == 429:
            if reason == "DAILY_QUOTA_EXHAUSTED":
                raise AIServiceRateLimitError(
                    message="The daily AI quota has been reached for today. Please try again tomorrow or upgrade your plan.",
                    status_code=429,
                    is_daily_exhaustion=True,
                    original_error=original_error,
                )
            else:
                raise AIServiceRateLimitError(
                    message="The AI service rate limit has been exceeded. Please try again in a few moments.",
                    status_code=429,
                    is_daily_exhaustion=False,
                    original_error=original_error,
                )
        elif status_code == 504 or "TIMEOUT" in reason.upper():
            raise AIServiceUnavailableError(
                message="The AI service request timed out while generating content. Please try again later.",
                status_code=504,
                original_error=original_error,
            )
        elif status_code == 503:
            raise AIServiceUnavailableError(
                message="The AI service is temporarily unavailable due to high demand. Please try again later.",
                status_code=503,
                original_error=original_error,
            )
        elif status_code == 404:
            raise AIServiceConfigurationError(
                message=f"The configured AI model is not available or supported. Please check GEMINI_MODEL in .env.",
                status_code=502,
                original_error=original_error,
            )
        elif status_code in (401, 403):
            raise AIServiceConfigurationError(
                message="Authentication with the AI service failed. Please check your GEMINI_API_KEY in .env.",
                status_code=502,
                original_error=original_error,
            )
        else:
            raise AIServiceUnavailableError(
                message="The AI service is currently unavailable. Please try again later.",
                status_code=503 if status_code >= 500 else 502,
                original_error=original_error,
            )

    @classmethod
    def _invoke_generate_single_model(
        cls,
        client: Any,
        model_name: str,
        full_prompt: str,
        timeout_ms: int,
        max_retries: int,
        initial_delay: float,
        max_delay: float,
        backoff_factor: float,
        operation_name: str = "generate_text",
    ) -> Tuple[Optional[str], Optional[Exception], int, str]:
        """
        Attempts to generate content with a specific model, applying bounded retries
        only for transient errors (never for daily quota exhaustion).
        Returns (text, last_error, status_code, reason).
        """
        last_error: Optional[Exception] = None
        last_status_code = 503
        last_reason = "UNAVAILABLE"

        for attempt in range(max_retries + 1):
            logger.info(
                f"[AI Request Start] purpose='{operation_name}' model='{model_name}' attempt={attempt + 1}/{max_retries + 1}"
            )
            try:
                try:
                    from google.genai import types
                    config = types.GenerateContentConfig(
                        http_options=types.HttpOptions(timeout=timeout_ms)
                    )
                    response = client.models.generate_content(
                        model=model_name,
                        contents=full_prompt,
                        config=config,
                    )
                except (TypeError, AttributeError):
                    response = client.models.generate_content(
                        model=model_name,
                        contents=full_prompt,
                    )
                logger.info(
                    f"[AI Request Success] purpose='{operation_name}' model='{model_name}' attempt={attempt + 1} status=200"
                )
                return response.text or "", None, 200, "OK"
            except Exception as exc:
                last_error = exc
                is_transient, status_code, reason = is_transient_gemini_error(exc)
                last_status_code = status_code
                last_reason = reason
                safe_err = sanitize_gemini_error(str(exc))

                # Immediately stop retries if daily quota is exhausted or error is non-transient
                if reason == "DAILY_QUOTA_EXHAUSTED":
                    logger.warning(
                        f"[AI Quota Exceeded] Daily AI quota exhausted on model '{model_name}': {safe_err}. Halting retries immediately."
                    )
                    return None, last_error, last_status_code, last_reason

                if not is_transient:
                    logger.error(
                        f"[AI Request Fatal Error] Non-transient Gemini API error ({reason}, code={status_code}) on model '{model_name}': {safe_err}"
                    )
                    return None, last_error, last_status_code, last_reason

                logger.warning(
                    f"[AI Request Transient Error] purpose='{operation_name}' model='{model_name}' error_category='{reason}' "
                    f"status_code={status_code} attempt={attempt + 1}/{max_retries + 1} error='{safe_err}'"
                )

                if attempt < max_retries:
                    suggested_delay = extract_retry_delay_seconds(exc)
                    if status_code == 429 and suggested_delay is not None and suggested_delay > 10.0:
                        logger.warning(
                            f"[AI Rate Limit] Suggested delay ({suggested_delay}s) exceeds threshold. Halting retries on '{model_name}'."
                        )
                        return None, last_error, last_status_code, last_reason

                    if suggested_delay is not None and 0.1 <= suggested_delay <= max_delay:
                        delay = suggested_delay
                    else:
                        base_delay = min(max_delay, initial_delay * (backoff_factor ** attempt))
                        jitter = random.uniform(0.0, base_delay * 0.5)
                        delay = (base_delay * 0.5) + jitter

                    logger.info(
                        f"[AI Request Retry] Retrying attempt {attempt + 2}/{max_retries + 1} on model '{model_name}' in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"[AI Request Exhausted] Gemini API retries exhausted ({max_retries} retries) on model '{model_name}'. "
                        f"Final error ({reason}, code={status_code}): {safe_err}"
                    )

        return None, last_error, last_status_code, last_reason

    @classmethod
    def generate_text(
        cls,
        prompt: str,
        system_instruction: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        operation_name: str = "generate_text",
        **kwargs,
    ) -> str:
        """
        Sends a generation request to the Gemini API with rate throttling, concurrency control,
        bounded retry for transient errors, and automatic model fallback.
        """
        if not settings.GEMINI_API_KEY:
            raise AIServiceConfigurationError(
                message="Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env.",
                status_code=503,
            )

        client = cls.get_client()
        if not client:
            raise AIServiceConfigurationError(
                message="Failed to initialize Gemini AI client. Please check your configuration.",
                status_code=503,
            )

        full_prompt = prompt
        if system_instruction:
            full_prompt = f"System Instructions:\n{system_instruction}\n\nUser Request:\n{prompt}"

        effective_timeout = timeout_seconds if timeout_seconds is not None else getattr(settings, "GEMINI_TIMEOUT_SECONDS", 12.0)
        timeout_ms = int(max(0.1, effective_timeout) * 1000)

        max_retries = max(0, getattr(settings, "GEMINI_MAX_RETRIES", 1))
        initial_delay = max(0.001, getattr(settings, "GEMINI_INITIAL_RETRY_DELAY", 1.0))
        max_delay = max(initial_delay, getattr(settings, "GEMINI_MAX_RETRY_DELAY", 4.0))
        backoff_factor = 2.0

        primary_model = getattr(settings, "GEMINI_MODEL", "gemini-flash-lite-latest")
        fallback_model = getattr(settings, "GEMINI_FALLBACK_MODEL", None)

        start_time = time.perf_counter()

        # Enforce sliding-window rate throttling before making the API call
        gemini_rate_limiter.acquire(operation=operation_name)

        with _concurrency_semaphore:
            # 1. Attempt primary model
            result_text, last_error, status_code, reason = cls._invoke_generate_single_model(
                client=client,
                model_name=primary_model,
                full_prompt=full_prompt,
                timeout_ms=timeout_ms,
                max_retries=max_retries,
                initial_delay=initial_delay,
                max_delay=max_delay,
                backoff_factor=backoff_factor,
                operation_name=operation_name,
            )

            if result_text is not None:
                latency_ms = (time.perf_counter() - start_time) * 1000
                log_ai_telemetry(operation=operation_name, model=primary_model, latency_ms=latency_ms, status_code=200)
                return result_text

            # 2. Attempt fallback model only for model-specific errors (500, 502, 503, 504, 404).
            # Never fallback on 429 rate limit or quota exhaustion (project-level limit).
            if fallback_model and fallback_model != primary_model and status_code in (404, 500, 502, 503, 504):
                logger.info(
                    f"[AI Fallback] Primary model '{primary_model}' failed ({reason}, code={status_code}). "
                    f"Attempting fallback to '{fallback_model}'..."
                )
                fb_text, fb_error, fb_code, fb_reason = cls._invoke_generate_single_model(
                    client=client,
                    model_name=fallback_model,
                    full_prompt=full_prompt,
                    timeout_ms=timeout_ms,
                    max_retries=0,
                    initial_delay=initial_delay,
                    max_delay=max_delay,
                    backoff_factor=backoff_factor,
                    operation_name=f"{operation_name}_fallback",
                )
                if fb_text is not None:
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    log_ai_telemetry(
                        operation=operation_name,
                        model=fallback_model,
                        latency_ms=latency_ms,
                        status_code=200,
                        extra=f"(fallback from {primary_model})",
                    )
                    return fb_text

                last_error = fb_error or last_error
                status_code = fb_code
                reason = fb_reason

        latency_ms = (time.perf_counter() - start_time) * 1000
        log_ai_telemetry(operation=operation_name, model=primary_model, latency_ms=latency_ms, status_code=status_code)
        cls._raise_mapped_error(status_code, reason, last_error)

    @classmethod
    def generate_text_stream(
        cls,
        prompt: str,
        system_instruction: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        operation_name: str = "generate_text_stream",
    ) -> Generator[str, None, None]:
        """
        Sends a streaming generation request to the Gemini API with native streaming,
        rate throttling, concurrency control, and model fallback.
        """
        if not settings.GEMINI_API_KEY:
            raise AIServiceConfigurationError(
                message="Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env.",
                status_code=503,
            )

        client = cls.get_client()
        if not client:
            raise AIServiceConfigurationError(
                message="Failed to initialize Gemini AI client. Please check your configuration.",
                status_code=503,
            )

        full_prompt = prompt
        if system_instruction:
            full_prompt = f"System Instructions:\n{system_instruction}\n\nUser Request:\n{prompt}"

        effective_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else getattr(settings, "GEMINI_TIMEOUT_SECONDS", 12.0)
        )
        timeout_ms = int(max(0.1, effective_timeout) * 1000)

        primary_model = getattr(settings, "GEMINI_MODEL", "gemini-flash-lite-latest")
        fallback_model = getattr(settings, "GEMINI_FALLBACK_MODEL", None)

        start_time = time.perf_counter()
        response_stream = None
        active_model = primary_model

        # Enforce rate throttling before opening stream
        gemini_rate_limiter.acquire(operation=operation_name)

        with _concurrency_semaphore:
            logger.info(
                f"[AI Request Start] purpose='{operation_name}' model='{primary_model}' stream=True"
            )
            # 1. Attempt primary stream
            try:
                from google.genai import types
                config = types.GenerateContentConfig(
                    http_options=types.HttpOptions(timeout=timeout_ms)
                )
                response_stream = client.models.generate_content_stream(
                    model=primary_model,
                    contents=full_prompt,
                    config=config,
                )
            except Exception as exc:
                is_transient, status_code, reason = is_transient_gemini_error(exc)
                safe_err = sanitize_gemini_error(str(exc))
                logger.warning(f"[AI Request Stream Error] purpose='{operation_name}' model='{primary_model}' error_category='{reason}' code={status_code}: {safe_err}")

                # Try fallback model only for model-specific errors (not on 429)
                if fallback_model and fallback_model != primary_model and status_code in (404, 500, 502, 503, 504):
                    logger.info(f"[AI Fallback Stream] Attempting fallback stream with model '{fallback_model}'...")
                    try:
                        from google.genai import types
                        config = types.GenerateContentConfig(
                            http_options=types.HttpOptions(timeout=timeout_ms)
                        )
                        response_stream = client.models.generate_content_stream(
                            model=fallback_model,
                            contents=full_prompt,
                            config=config,
                        )
                        active_model = fallback_model
                    except Exception as fb_exc:
                        fb_transient, fb_status, fb_reason = is_transient_gemini_error(fb_exc)
                        cls._raise_mapped_error(fb_status, fb_reason, fb_exc)
                else:
                    cls._raise_mapped_error(status_code, reason, exc)

            if response_stream is None:
                cls._raise_mapped_error(503, "UNAVAILABLE", None)

            # 2. Yield chunks from active stream
            try:
                for chunk in response_stream:
                    if chunk.text:
                        yield chunk.text
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.info(
                    f"[AI Request Success] purpose='{operation_name}' model='{active_model}' stream=True latency_ms={latency_ms:.1f} status=200"
                )
                log_ai_telemetry(operation=operation_name, model=active_model, latency_ms=latency_ms, status_code=200)
            except Exception as exc:
                latency_ms = (time.perf_counter() - start_time) * 1000
                is_transient, status_code, reason = is_transient_gemini_error(exc)
                logger.error(
                    f"[AI Request Stream Error] purpose='{operation_name}' model='{active_model}' error_category='{reason}' code={status_code}"
                )
                log_ai_telemetry(operation=operation_name, model=active_model, latency_ms=latency_ms, status_code=status_code)
                cls._raise_mapped_error(status_code, reason, exc)

    @classmethod
    def _build_ai_teacher_prompt(
        cls,
        question: str,
        pdf: Optional[PDFDocument],
        db: Session,
        history: Optional[List[Dict[str, str]]] = None,
        user_name: Optional[str] = None,
    ) -> Tuple[str, str, List[int], bool]:
        """
        Builds the grounded RAG context, strict document-only instructions,
        personalized student name context, and full prompt for AI Teacher.
        Returns (full_prompt, system_instruction, source_pages, has_relevant_content).
        """
        source_pages: List[int] = []
        context_str = ""
        has_relevant_content = True

        # Retrieve relevant PDF chunks using semantic thresholded search
        if pdf:
            relevant_chunks, max_score = search_relevant_chunks(
                pdf_id=pdf.id,
                query=question,
                db=db,
            )

            if relevant_chunks:
                source_pages = sorted(list(set(c["page_number"] for c in relevant_chunks)))
                context_blocks = []
                for chunk in relevant_chunks:
                    page_number = chunk["page_number"]
                    context_blocks.append(
                        f"--- [Page {page_number}] ---\n"
                        f"{chunk['text']}\n"
                    )
                context_str = "\n".join(context_blocks)
            else:
                has_relevant_content = False
                context_str = (
                    "NO_RELEVANT_CONTENT_FOUND_IN_UPLOADED_PDF. "
                    "The uploaded document does not contain information to answer this question."
                )

        clean_name = user_name.strip() if user_name and user_name.strip() else None
        name_instruction = ""
        if clean_name:
            name_instruction = (
                f"STUDENT PROFILE:\n"
                f"- The student's registered name is '{clean_name}'.\n"
                f"- Address the student naturally by their name where appropriate (e.g., in greetings or encouragement, such as 'Sure {clean_name}, let's look at this concept').\n"
                f"- Do NOT repeat the student's name unnaturally in every single sentence.\n"
                f"- Personalization must NEVER override document grounding, factual accuracy, or safety guidelines.\n\n"
            )

        if pdf:
            system_instruction = (
                f"You are MindVault AI, an academic assistant analyzing the user's uploaded document: '{pdf.title}'.\n\n"
                f"{name_instruction}"
                "CRITICAL GROUNDING RULES:\n"
                "1. Answer the student's question STRICTLY and EXCLUSIVELY based on the DOCUMENT CONTEXT provided below.\n"
                "2. Cite facts from the document using exact bracketed page citations like [Page 1] or [Page 2].\n"
                "3. NEVER use general knowledge, external assumptions, or outside training data to answer or embellish.\n"
                "4. If the provided DOCUMENT CONTEXT does not contain enough information to fully answer the question, state EXACTLY:\n"
                "'I could not find this information in your uploaded document.'\n"
                "Do NOT attempt to guess, hypothesize, or provide a general educational explanation.\n"
                "5. Maintain clean markdown formatting with headings and bullet points where helpful."
            )
        else:
            system_instruction = (
                "You are MindVault AI, an inspiring, empathetic, and expert Personal AI Teacher. "
                "Your mission is to help students understand concepts with maximum clarity, intelligence, and structure.\n\n"
                f"{name_instruction}"
                "ADAPTIVE PROGRESSIVE ANSWER STRUCTURE:\n"
                "- Simple questions: Give a clear, direct, and complete answer in 1-2 short paragraphs.\n"
                "- Step-by-step or process questions: Use clean numbered steps (1., 2., 3.) with bold action phrases.\n"
                "- Technical or complex concepts: Start with a clear 1-2 sentence core definition. "
                "Follow with '### How It Works' or '### Key Concepts' using concise bullet points. "
                "Conclude with '### Why It Matters' or a real-world takeaway.\n"
                "- Coding questions: Provide a brief explanation followed by clean, formatted code blocks with syntax highlighting and helpful comments.\n"
                "- Readability rules: Break text into short, digestible paragraphs (2-3 sentences max). Use bold text for key terms. Avoid monolithic walls of text."
            )

        prompt_parts = []
        if context_str:
            prompt_parts.append(
                f"DOCUMENT CONTEXT (PDF: '{pdf.title}'):\n"
                f"{context_str}\n"
            )

        if history:
            prompt_parts.append("CONVERSATION HISTORY:")
            for msg in history[-4:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_parts.append(f"{role.title()}: {content}")
            prompt_parts.append("")

        prompt_parts.append(f"STUDENT QUESTION: {question}")
        full_prompt = "\n".join(prompt_parts)

        return full_prompt, system_instruction, source_pages, has_relevant_content

    @classmethod
    def ask_ai_teacher(
        cls,
        question: str,
        pdf: Optional[PDFDocument],
        db: Session,
        history: Optional[List[Dict[str, str]]] = None,
        user_name: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Non-streaming personal AI teacher response strictly grounded in document context
        with intelligent response caching.
        """
        model_name = getattr(settings, "GEMINI_MODEL", "gemini-flash-lite-latest")
        effective_user_id = user_id or (pdf.owner_id if pdf else 0)

        # Check response cache when no conversation history is passed
        if not history:
            cached = ai_cache.get(
                user_id=effective_user_id,
                pdf_id=pdf.id if pdf else None,
                operation="ask_ai",
                query=question,
                model=model_name,
            )
            if cached is not None:
                log_ai_telemetry(
                    operation="ask_ai",
                    model=model_name,
                    latency_ms=0.5,
                    status_code=200,
                    cached=True,
                )
                return cached

        full_prompt, system_instruction, source_pages, has_relevant_content = (
            cls._build_ai_teacher_prompt(
                question=question,
                pdf=pdf,
                db=db,
                history=history,
                user_name=user_name,
            )
        )

        # Fast exit if PDF is attached but query contains zero relevant content
        if pdf and not has_relevant_content:
            logger.info(
                "RAG Grounding Guard | pdf_id=%s, question='%s' -> No relevant content found",
                pdf.id,
                question[:50],
            )
            negative_result = {
                "answer": "I could not find this information in your uploaded document.",
                "source_pages": [],
                "used_pdf": True,
                "pdf_id": pdf.id,
            }
            if not history:
                ai_cache.set(
                    user_id=effective_user_id,
                    pdf_id=pdf.id,
                    operation="ask_ai",
                    query=question,
                    model=model_name,
                    value=negative_result,
                )
            return negative_result

        # Generate AI answer
        raw_answer = cls.generate_text(
            full_prompt,
            system_instruction=system_instruction,
        )

        # Keep only valid page citations
        cited_pages = []
        for match in re.findall(
            r"\[Page\s*(\d+)\]",
            raw_answer,
            re.IGNORECASE,
        ):
            page_num = int(match)
            if page_num in source_pages and page_num not in cited_pages:
                cited_pages.append(page_num)

        # If answer states information was not found, citations must be empty
        if "could not find" in raw_answer.lower() and "document" in raw_answer.lower():
            cited_pages = []

        result = {
            "answer": raw_answer,
            "source_pages": sorted(cited_pages) if pdf else [],
            "used_pdf": bool(pdf),
            "pdf_id": pdf.id if pdf else None,
        }

        # Cache result if stateless question
        if not history:
            ai_cache.set(
                user_id=effective_user_id,
                pdf_id=pdf.id if pdf else None,
                operation="ask_ai",
                query=question,
                model=model_name,
                value=result,
            )

        return result

    @classmethod
    def ask_ai_teacher_stream(
        cls,
        question: str,
        pdf: Optional[PDFDocument],
        db: Session,
        history: Optional[List[Dict[str, str]]] = None,
        user_name: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streaming personal AI teacher generator yielding initial metadata,
        real-time tokens, and final citation verification with cache hit support.
        """
        model_name = getattr(settings, "GEMINI_MODEL", "gemini-flash-lite-latest")
        effective_user_id = user_id or (pdf.owner_id if pdf else 0)

        # Check response cache when no conversation history is passed
        if not history:
            cached = ai_cache.get(
                user_id=effective_user_id,
                pdf_id=pdf.id if pdf else None,
                operation="ask_ai",
                query=question,
                model=model_name,
            )
            if cached is not None:
                log_ai_telemetry(
                    operation="ask_ai_stream",
                    model=model_name,
                    latency_ms=1.0,
                    status_code=200,
                    cached=True,
                )
                yield {
                    "type": "metadata",
                    "used_pdf": cached.get("used_pdf", False),
                    "pdf_id": cached.get("pdf_id"),
                    "source_pages": cached.get("source_pages", []),
                }
                yield {
                    "type": "token",
                    "text": cached["answer"],
                }
                yield {
                    "type": "done",
                    "source_pages": cached.get("source_pages", []),
                    "used_pdf": cached.get("used_pdf", False),
                    "pdf_id": cached.get("pdf_id"),
                    "full_answer": cached["answer"],
                }
                return

        full_prompt, system_instruction, source_pages, has_relevant_content = (
            cls._build_ai_teacher_prompt(
                question=question,
                pdf=pdf,
                db=db,
                history=history,
                user_name=user_name,
            )
        )

        # Fast exit if PDF is attached but query contains zero relevant content
        if pdf and not has_relevant_content:
            logger.info(
                "RAG Stream Grounding Guard | pdf_id=%s, question='%s' -> No relevant content found",
                pdf.id,
                question[:50],
            )
            yield {
                "type": "metadata",
                "used_pdf": True,
                "pdf_id": pdf.id,
                "source_pages": [],
            }
            yield {
                "type": "token",
                "text": "I could not find this information in your uploaded document.",
            }
            yield {
                "type": "done",
                "source_pages": [],
                "used_pdf": True,
                "pdf_id": pdf.id,
                "full_answer": "I could not find this information in your uploaded document.",
            }
            return

        # 1. Immediately yield metadata so client can prepare UI
        yield {
            "type": "metadata",
            "used_pdf": bool(pdf),
            "pdf_id": pdf.id if pdf else None,
            "source_pages": source_pages,
        }

        # 2. Stream incremental text tokens with zero artificial delay
        full_answer = ""
        for chunk in cls.generate_text_stream(
            full_prompt,
            system_instruction=system_instruction,
        ):
            full_answer += chunk
            yield {
                "type": "token",
                "text": chunk,
            }

        # 3. Compute final valid citations
        cited_pages = []
        for match in re.findall(
            r"\[Page\s*(\d+)\]",
            full_answer,
            re.IGNORECASE,
        ):
            page_num = int(match)
            if page_num in source_pages and page_num not in cited_pages:
                cited_pages.append(page_num)

        if "could not find" in full_answer.lower() and "document" in full_answer.lower():
            cited_pages = []

        result_dict = {
            "answer": full_answer,
            "source_pages": sorted(cited_pages) if pdf else [],
            "used_pdf": bool(pdf),
            "pdf_id": pdf.id if pdf else None,
        }

        # Cache completed stream result
        if not history:
            ai_cache.set(
                user_id=effective_user_id,
                pdf_id=pdf.id if pdf else None,
                operation="ask_ai",
                query=question,
                model=model_name,
                value=result_dict,
            )

        # 4. Yield completion event
        yield {
            "type": "done",
            "source_pages": sorted(cited_pages) if pdf else [],
            "used_pdf": bool(pdf),
            "pdf_id": pdf.id if pdf else None,
            "full_answer": full_answer,
        }

    @classmethod
    def generate_learning_path(cls, pdf: PDFDocument, db: Session) -> Dict[str, Any]:
        """
        Analyzes the PDF document content and generates a structured learning roadmap.
        """
        model_name = getattr(settings, "GEMINI_MODEL", "gemini-flash-lite-latest")
        cached = ai_cache.get(
            user_id=pdf.owner_id,
            pdf_id=pdf.id,
            operation="learning_path",
            query=f"lp:{pdf.id}",
            model=model_name,
        )
        if cached is not None:
            return cached

        # Collect sample text from first 8 pages
        pages = db.query(PDFPage).filter(PDFPage.pdf_id == pdf.id).order_by(PDFPage.page_number).limit(8).all()
        extracted_content = "\n\n".join([f"Page {p.page_number}: {p.text_content[:800]}" for p in pages])

        prompt = f"""
You are an expert curriculum designer. Analyze this textbook/document excerpt and create a structured Learning Path for a student.

DOCUMENT TITLE: {pdf.title}
DOCUMENT EXCERPT:
{extracted_content}

Return ONLY a valid JSON object with the following exact structure (no other markdown or text outside JSON):
{{
  "title": "{pdf.title} - Complete Learning Roadmap",
  "overview": "Comprehensive roadmap designed to take you from fundamentals to mastery.",
  "estimated_hours": 5.0,
  "topics": [
    {{
      "title": "Topic Name",
      "description": "Brief description of the concept and why it matters.",
      "difficulty": "beginner",
      "estimated_minutes": 45,
      "key_points": ["Key concept 1", "Key concept 2"]
    }}
  ]
}}
Provide between 3 and 7 coherent topics covering the material sequentially.
"""
        response_text = cls.generate_text(prompt)

        # Parse JSON
        parsed_data = cls._extract_json(response_text)
        if (
            parsed_data
            and isinstance(parsed_data, dict)
            and "topics" in parsed_data
            and isinstance(parsed_data["topics"], list)
            and len(parsed_data["topics"]) > 0
        ):
            ai_cache.set(
                user_id=pdf.owner_id,
                pdf_id=pdf.id,
                operation="learning_path",
                query=f"lp:{pdf.id}",
                model=model_name,
                value=parsed_data,
            )
            return parsed_data

        logger.error(
            f"Failed to extract valid learning path JSON from Gemini response for PDF '{pdf.title}'"
        )
        raise AIServiceError(
            message="Unable to generate a structured learning path from the document content. Please try again.",
            status_code=502,
        )

    @classmethod
    def explain_topic(cls, pdf: PDFDocument, topic: str, depth: str, db: Session, user_id: Optional[int] = None) -> str:
        """
        Explains a specific topic from the PDF at the chosen depth (beginner, intermediate, advanced)
        with intelligent caching.
        """
        effective_user_id = user_id or pdf.owner_id
        model_name = getattr(settings, "GEMINI_MODEL", "gemini-flash-lite-latest")

        cached = ai_cache.get(
            user_id=effective_user_id,
            pdf_id=pdf.id,
            operation="explain_topic",
            query=f"{topic}:{depth}",
            model=model_name,
        )
        if cached is not None:
            return cached

        relevant_pages = search_relevant_pages(pdf.id, topic, db, max_pages=3)
        context = "\n".join([f"[Page {p['page_number']}]: {p['text']}" for p in relevant_pages])

        prompt = f"""
You are an expert tutor. Explain the following topic from the student's study material '{pdf.title}'.

TOPIC: {topic}
TARGET DEPTH: {depth} (beginner = intuitive analogies & simple terms; intermediate = standard academic rigor; advanced = in-depth nuances & edge cases)

SOURCE CONTEXT:
{context}

Provide a well-structured explanation including:
1. Quick Summary / Intuition
2. Core Breakdown (with bullet points)
3. Real-world Example or Analogy
4. Source references (cite [Page X] when referencing context)
"""
        explanation = cls.generate_text(prompt)

        ai_cache.set(
            user_id=effective_user_id,
            pdf_id=pdf.id,
            operation="explain_topic",
            query=f"{topic}:{depth}",
            model=model_name,
            value=explanation,
        )
        return explanation

    @classmethod
    def _extract_json(cls, text: str) -> Optional[Dict[str, Any]]:
        """Extracts and parses JSON from response text even if wrapped in markdown codeblocks."""
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(text[first_brace : last_brace + 1])
            except json.JSONDecodeError:
                pass

        return None

    # Cache Management Helpers
    @classmethod
    def invalidate_pdf_cache(cls, pdf_id: int) -> int:
        return ai_cache.invalidate_pdf(pdf_id)

    @classmethod
    def invalidate_user_cache(cls, user_id: int) -> int:
        return ai_cache.invalidate_user(user_id)

    @classmethod
    def clear_cache(cls):
        ai_cache.clear()
