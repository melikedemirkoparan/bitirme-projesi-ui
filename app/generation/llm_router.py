"""LLM backend router.

Single dispatch point for both the definition pipeline and the
assistant. Picks between the remote LLM (`remote_llm_client`,
ngrok/Colab) and the local Ollama instance (`llm_client`) at call time:

  - remote URL configured -> remote backend
  - otherwise              -> local Ollama

Two entry points:
  - `call_llm`        — raw text out (used by the definition pipeline)
  - `generate_json`   — parsed dict out (used by the assistant)

Callers never import either backend directly so backends can be
swapped at runtime without a restart.
"""

from __future__ import annotations

from app.generation import llm_client, remote_llm_client
from app.generation.llm_client import (
    LLMConnectionError,
    LLMParseError,
    LLMResponseError,
    _parse_json,
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


def call_llm(prompt: str, max_new_tokens: int = 256, temperature: float = 0.2) -> str:
    """Call the active LLM backend and return raw text. "" on failure.

    Same signature as the legacy `rag_engine._call_llm` so the
    definition pipeline can swap call sites with no other changes.
    """
    if remote_llm_client.is_configured():
        return remote_llm_client.call_llm(prompt, max_new_tokens, temperature)

    try:
        return llm_client.generate(
            user_prompt=prompt,
            system_prompt=_PASSTHROUGH_SYSTEM,
            temperature=temperature,
        )
    except (llm_client.LLMConnectionError, llm_client.LLMResponseError):
        return ""


def generate_json(
    user_prompt: str,
    system_prompt: str,
    temperature: float = 0.15,
    max_new_tokens: int = 800,
) -> dict:
    """Return a parsed JSON dict from the active backend.

    Local Ollama uses its native `format=json` mode (strict, fast).
    Remote (Colab Flask) has no JSON mode, so we instruct the model
    to output JSON in the prompt and parse the response. On a parse
    failure we retry once with a correction prompt.

    Raises:
        LLMConnectionError: backend unreachable / empty response
        LLMResponseError:   non-200 / empty content
        LLMParseError:      invalid JSON after one retry
    """
    if not remote_llm_client.is_configured():
        return llm_client.generate_json(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )

    # Remote path: combine system + user into one prompt the Flask
    # /generate endpoint can accept. Append a hard JSON instruction
    # so chat-tuned models (Qwen / Mistral / Llama) reliably emit JSON.
    json_guard = (
        "\n\n--- OUTPUT FORMAT ---\n"
        "Respond with ONE valid JSON object only. "
        "No markdown, no code fences, no commentary before or after."
    )
    combined = f"{system_prompt}\n\n{user_prompt}{json_guard}"

    raw = remote_llm_client.call_llm(
        combined,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
    )
    if not raw:
        raise LLMConnectionError(
            "Remote LLM returned an empty response. "
            "Check that the Colab notebook is still running and reachable."
        )

    try:
        return _parse_json(raw)
    except LLMParseError:
        pass  # fall through to retry

    correction = (
        f"{combined}\n\n"
        "Your previous response could not be parsed as JSON.\n"
        f"Previous response (truncated):\n{raw[:400]}\n\n"
        "Respond ONLY with valid JSON. No explanation, no markdown."
    )
    raw_retry = remote_llm_client.call_llm(
        correction,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
    )
    if not raw_retry:
        raise LLMConnectionError("Remote LLM returned empty on retry.")
    try:
        return _parse_json(raw_retry)
    except LLMParseError as exc:
        raise LLMParseError(
            f"Remote LLM returned unparseable JSON on both attempts. "
            f"Last raw output (truncated): {raw_retry[:300]}"
        ) from exc
