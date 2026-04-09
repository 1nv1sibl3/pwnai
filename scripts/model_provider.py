#!/usr/bin/env python3
"""Helpers for provider-agnostic chat model initialization."""

from __future__ import annotations

import os
from typing import Any


class ModelProviderError(RuntimeError):
    pass


_RATE_LIMITER_BY_RPM: dict[int, Any] = {}


def _resolveModelName() -> str:
    for name in ("LLM_MODEL", "MODEL"):
        model = os.getenv(name, "").strip()
        if model:
            return model
    raise ModelProviderError("missing model name: set LLM_MODEL (or MODEL for backward compatibility)")


def _resolveApiKey() -> str:
    # Prefer provider-neutral env names first.
    for name in ("LLM_API_KEY", "API_KEY", "NIM_API_KEY", "OPENAI_API_KEY", "OPENAI_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise ModelProviderError(
        "missing API key: set LLM_API_KEY (or API_KEY / NIM_API_KEY / OPENAI_API_KEY / OPENAI_KEY)"
    )


def _resolveBaseUrl() -> str | None:
    # Prefer provider-neutral env names first.
    for name in ("LLM_BASE_URL", "API_BASE_URL", "NIM_BASE_URL", "OPENAI_BASE_URL", "OPENAI_API_BASE"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def _resolveRateLimitRpm() -> int:
    raw = os.getenv("LLM_RATE_LIMIT_RPM", os.getenv("API_RATE_LIMIT_RPM", "40")).strip()
    try:
        rpm = int(raw)
    except ValueError as exc:
        raise ModelProviderError("LLM_RATE_LIMIT_RPM/API_RATE_LIMIT_RPM must be an integer") from exc
    if rpm <= 0:
        raise ModelProviderError("LLM_RATE_LIMIT_RPM/API_RATE_LIMIT_RPM must be > 0")
    return rpm


def _getRateLimiter(rpm: int):
    if rpm in _RATE_LIMITER_BY_RPM:
        return _RATE_LIMITER_BY_RPM[rpm]
    try:
        from langchain_core.rate_limiters import InMemoryRateLimiter
    except ModuleNotFoundError as exc:
        raise ModelProviderError("missing dependency: langchain_core.rate_limiters") from exc

    limiter = InMemoryRateLimiter(
        requests_per_second=rpm / 60,
        check_every_n_seconds=0.05,
        max_bucket_size=max(1, rpm // 4),
    )
    _RATE_LIMITER_BY_RPM[rpm] = limiter
    return limiter


def createChatModel(*, temperature: float = 0):
    """Create a chat model for OpenAI-compatible endpoints (e.g. NVIDIA NIM)."""
    try:
        from langchain_openai import ChatOpenAI
    except ModuleNotFoundError as exc:
        raise ModelProviderError("missing dependency: langchain_openai") from exc

    model = _resolveModelName()
    api_key = _resolveApiKey()
    base_url = _resolveBaseUrl()
    rpm = _resolveRateLimitRpm()
    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "temperature": temperature,
        "rate_limiter": _getRateLimiter(rpm),
        "max_retries": 5,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)
