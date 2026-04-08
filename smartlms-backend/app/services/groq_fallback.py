"""
Groq fallback helpers.

Centralized model failover for chat and transcription calls when a model
is rate-limited or temporarily unavailable.
"""

import asyncio
import re
import time
from typing import Any, Iterable, List, Optional, Sequence, Tuple


_RATE_LIMIT_MARKERS = (
    "429",
    "rate limit",
    "rate_limit",
    "too many requests",
    "resource exhausted",
)

_RETRIABLE_MODEL_MARKERS = (
    "overloaded",
    "temporarily unavailable",
    "model is loading",
    "unavailable",
    "context length",
    "does not exist",
    "not found",
)


def _error_text(error: Exception) -> str:
    parts = [str(error)]
    status_code = getattr(error, "status_code", None)
    if status_code is not None:
        parts.append(str(status_code))

    body = getattr(error, "body", None)
    if body is not None:
        parts.append(str(body))

    return " | ".join(parts).lower()


class AllModelsRateLimitedError(RuntimeError):
    """Raised when every candidate model is exhausted by rate limits."""

    def __init__(self, *, models_tried: Sequence[str], retry_after_seconds: int, last_error: Optional[Exception] = None):
        message = (
            "All AI models are temporarily rate-limited. "
            f"Please retry in about {max(1, int(retry_after_seconds))} seconds."
        )
        super().__init__(message)
        self.models_tried = list(models_tried)
        self.retry_after_seconds = max(1, int(retry_after_seconds))
        self.last_error = last_error


class AllModelsUnavailableError(RuntimeError):
    """Raised when all model candidates fail for non-rate-limit reasons."""

    def __init__(self, *, models_tried: Sequence[str], last_error: Optional[Exception] = None):
        message = "All AI models failed for this request. Please retry shortly."
        super().__init__(message)
        self.models_tried = list(models_tried)
        self.last_error = last_error


def _retry_after_seconds(error: Exception) -> int:
    response = getattr(error, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None) or {}
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after:
            try:
                return max(1, int(float(str(retry_after).strip())))
            except Exception:
                pass

    text = _error_text(error)
    match = re.search(r"retry\s*after\s*(\d+)", text)
    if match:
        return max(1, int(match.group(1)))

    return 30


def _backoff_seconds(*, attempt: int, base_seconds: float, max_seconds: float, floor_seconds: float = 0.0) -> float:
    exponential = base_seconds * (2 ** max(0, attempt))
    return max(floor_seconds, min(max_seconds, exponential))


def is_rate_limited_error(error: Exception) -> bool:
    text = _error_text(error)
    return any(marker in text for marker in _RATE_LIMIT_MARKERS)


def should_failover_to_next_model(error: Exception) -> bool:
    text = _error_text(error)
    if is_rate_limited_error(error):
        return True
    return any(marker in text for marker in _RETRIABLE_MODEL_MARKERS)


def _model_candidates(primary_model: str, fallback_models: Optional[Sequence[str]]) -> List[str]:
    ordered = [primary_model]
    if fallback_models:
        ordered.extend([m for m in fallback_models if m])

    # Deduplicate while preserving order.
    return list(dict.fromkeys(ordered))


async def chat_completion_with_fallback(
    client: Any,
    *,
    primary_model: str,
    fallback_models: Optional[Sequence[str]],
    messages: Sequence[dict],
    temperature: float = 0.7,
    max_tokens: int = 1024,
    stream: bool = False,
    retries_per_model: int = 1,
    retry_base_seconds: float = 1.2,
    retry_max_seconds: float = 12.0,
) -> Tuple[Any, str]:
    """Attempt a chat completion across a model chain.

    Returns: (response, used_model)
    Raises: last exception if all candidates fail.
    """
    last_error: Optional[Exception] = None
    models_tried = _model_candidates(primary_model, fallback_models)
    rate_limited_models = set()
    max_retry_after = 0

    for model_name in models_tried:
        for attempt in range(max(0, retries_per_model) + 1):
            try:
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                )
                return response, model_name
            except Exception as error:  # pragma: no cover - external provider behavior
                last_error = error

                if is_rate_limited_error(error):
                    rate_limited_models.add(model_name)
                    retry_after = _retry_after_seconds(error)
                    max_retry_after = max(max_retry_after, retry_after)
                    if attempt < max(0, retries_per_model):
                        delay = _backoff_seconds(
                            attempt=attempt,
                            base_seconds=retry_base_seconds,
                            max_seconds=retry_max_seconds,
                            floor_seconds=retry_after,
                        )
                        await asyncio.sleep(delay)
                        continue
                    break

                if should_failover_to_next_model(error):
                    if attempt < max(0, retries_per_model):
                        delay = _backoff_seconds(
                            attempt=attempt,
                            base_seconds=retry_base_seconds,
                            max_seconds=retry_max_seconds,
                        )
                        await asyncio.sleep(delay)
                        continue
                    break

                raise

    if last_error is not None:
        if models_tried and len(rate_limited_models) == len(models_tried):
            raise AllModelsRateLimitedError(
                models_tried=models_tried,
                retry_after_seconds=max_retry_after or 30,
                last_error=last_error,
            )
        raise AllModelsUnavailableError(models_tried=models_tried, last_error=last_error)

    raise RuntimeError("No model candidates available for chat completion")


def transcription_with_fallback(
    client: Any,
    *,
    file_tuple: Tuple[str, bytes],
    primary_model: str,
    fallback_models: Optional[Sequence[str]],
    response_format: str = "text",
    retries_per_model: int = 1,
    retry_base_seconds: float = 1.2,
    retry_max_seconds: float = 12.0,
) -> Tuple[Any, str]:
    """Attempt an audio transcription across a model chain.

    Returns: (response, used_model)
    Raises: last exception if all candidates fail.
    """
    last_error: Optional[Exception] = None
    models_tried = _model_candidates(primary_model, fallback_models)
    rate_limited_models = set()
    max_retry_after = 0

    for model_name in models_tried:
        for attempt in range(max(0, retries_per_model) + 1):
            try:
                response = client.audio.transcriptions.create(
                    file=file_tuple,
                    model=model_name,
                    response_format=response_format,
                )
                return response, model_name
            except Exception as error:  # pragma: no cover - external provider behavior
                last_error = error

                if is_rate_limited_error(error):
                    rate_limited_models.add(model_name)
                    retry_after = _retry_after_seconds(error)
                    max_retry_after = max(max_retry_after, retry_after)
                    if attempt < max(0, retries_per_model):
                        delay = _backoff_seconds(
                            attempt=attempt,
                            base_seconds=retry_base_seconds,
                            max_seconds=retry_max_seconds,
                            floor_seconds=retry_after,
                        )
                        time.sleep(delay)
                        continue
                    break

                if should_failover_to_next_model(error):
                    if attempt < max(0, retries_per_model):
                        delay = _backoff_seconds(
                            attempt=attempt,
                            base_seconds=retry_base_seconds,
                            max_seconds=retry_max_seconds,
                        )
                        time.sleep(delay)
                        continue
                    break

                raise

    if last_error is not None:
        if models_tried and len(rate_limited_models) == len(models_tried):
            raise AllModelsRateLimitedError(
                models_tried=models_tried,
                retry_after_seconds=max_retry_after or 30,
                last_error=last_error,
            )
        raise AllModelsUnavailableError(models_tried=models_tried, last_error=last_error)

    raise RuntimeError("No model candidates available for transcription")
