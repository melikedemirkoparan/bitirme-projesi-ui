"""LLM backend router.

Single dispatch point for both the definition pipeline and the assistant.
The protocol is always Ollama-native (`/api/chat`, JSON in / JSON out).
The only thing that differs between "local" and "remote" is the base URL:

  - remote URL configured -> hit the remote Ollama via that URL
  - otherwise             -> hit the local Ollama at settings.ollama_base_url

`llm_client` does the actual HTTP work; this module only chooses the URL.
The model name is the same in both cases (settings.ollama_model). Pull the
model into your remote Ollama before pointing the URL at it.

Three entry points:
  - `call_llm`        — raw text out, single-message (legacy)
  - `generate_raw`    — raw text out, system+user split (pipeline, no JSON mode)
  - `generate_json`   — parsed dict out, JSON mode (assistant)
"""

from __future__ import annotations

from app.generation import llm_client, remote_llm_client
from app.generation.llm_client import (
    LLMConnectionError,
    LLMParseError,
    LLMResponseError,
)


# Pipeline prompts already contain their own SYSTEM/PROCEDURE blocks,
# so when we forward them to Ollama (which expects a separate system
# message field) we pass a neutral system prompt and put the whole
# pipeline prompt into the user message.
_PASSTHROUGH_SYSTEM = (
    "You are a patent drafting assistant. Follow the instructions in "
    "the user message exactly. Output only what the instructions request."
)


def active_backend() -> str:
    """Return "remote" or "local" — for status endpoints/logs."""
    return "remote" if remote_llm_client.is_configured() else "local"


def _effective_base_url() -> str | None:
    """Return the remote URL if configured, else None (= local default)."""
    return remote_llm_client.get_remote_llm_url() or None


def call_llm(prompt: str, max_new_tokens: int = 256, temperature: float = 0.2) -> str:
    """Call the active Ollama backend and return raw text. "" on failure.

    `max_new_tokens` is accepted for backward compatibility with the
    legacy `rag_engine._call_llm` signature; Ollama controls response
    length internally and there is no per-call cap in the current
    /api/chat schema.
    """
    try:
        return llm_client.generate(
            user_prompt=prompt,
            system_prompt=_PASSTHROUGH_SYSTEM,
            temperature=temperature,
            base_url=_effective_base_url(),
        )
    except (LLMConnectionError, LLMResponseError) as exc:
        print(f"[LLM] call_llm failed ({active_backend()}): {exc}")
        return ""


def generate_raw(
    user_prompt: str,
    system_prompt: str,
    temperature: float = 0.35,
) -> str:
    """Call the active backend WITHOUT JSON mode and return raw text.

    Unlike `generate_json`, this does NOT set `response_format=json_object`
    or Ollama's `format=json`. Reasoning models (e.g. DeepSeek-R1) that emit
    <think>…</think> blocks need raw mode so their chain-of-thought is
    preserved and the JSON that follows can be parsed by the caller.

    Returns "" on any connection / response error.
    """
    try:
        return llm_client.generate(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            base_url=_effective_base_url(),
        )
    except (LLMConnectionError, LLMResponseError) as exc:
        print(f"[LLM] generate_raw failed ({active_backend()}): {exc}")
        return ""


def generate_json(
    user_prompt: str,
    system_prompt: str,
    temperature: float = 0.15,
    max_new_tokens: int = 800,
) -> dict:
    """Return a parsed JSON dict from the active Ollama backend.

    Uses Ollama's native `format=json` mode. On a parse failure the
    underlying `llm_client.generate_json` retries once with a correction
    prompt; if that also fails it raises `LLMParseError`.

    Raises:
        LLMConnectionError: backend unreachable / empty response
        LLMResponseError:   non-200 / empty content
        LLMParseError:      invalid JSON after one retry
    """
    return llm_client.generate_json(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        base_url=_effective_base_url(),
    )
