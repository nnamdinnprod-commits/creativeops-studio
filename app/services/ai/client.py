"""Provider abstraction — the only file in the codebase that imports an LLM SDK.
Every other AI function goes through complete_json(). See docs/AI_WORKFLOWS.md.
"""

import json
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _call_openai(prompt: str, temperature: float) -> str | None:
    try:
        import openai
    except ImportError:
        logger.error("AI_PROVIDER=openai but the openai package is not installed.")
        return None
    try:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.ai_model or "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content
    except Exception:
        logger.exception("OpenAI call failed")
        return None


def _call_anthropic(prompt: str, temperature: float) -> str | None:
    try:
        import anthropic
    except ImportError:
        logger.error("AI_PROVIDER=anthropic but the anthropic package is not installed.")
        return None
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.ai_model or "claude-sonnet-4-5",
            max_tokens=2048,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception:
        logger.exception("Anthropic call failed")
        return None


def _raw_completion(prompt: str, temperature: float) -> str | None:
    if settings.ai_provider == "openai":
        return _call_openai(prompt, temperature)
    if settings.ai_provider == "anthropic":
        return _call_anthropic(prompt, temperature)
    logger.error("complete_json called with AI_PROVIDER=%s (expected openai/anthropic)", settings.ai_provider)
    return None


def _parse(raw: str | None, schema: type[T]) -> T | None:
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        return schema.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("AI response failed schema validation: %s", exc)
        return None


def complete_json(prompt: str, schema: type[T], *, temperature: float = 0.2) -> T | None:
    """Send a prompt to the configured live provider, parse the response as JSON,
    and validate it against `schema`. Returns None on any failure — network error,
    malformed JSON, or a schema mismatch. Retries once on a validation failure,
    then gives up. Never called when AI_PROVIDER is 'mock'; callers branch to
    mock.py before reaching here."""
    raw = _raw_completion(prompt, temperature)
    result = _parse(raw, schema)
    if result is not None:
        return result

    raw_retry = _raw_completion(prompt, temperature)
    return _parse(raw_retry, schema)
