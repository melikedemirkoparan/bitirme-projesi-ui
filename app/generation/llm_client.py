"""
Ollama LLM client wrapper.

Single integration point between the definition generation pipeline and
the local offline LLM. All generation modules call this module — nothing
else in the codebase talks to Ollama directly.

Swapping the local model or inference backend only requires changes here
and in config.py. The rest of the pipeline is unaffected.

API used: Ollama /api/chat
  - Supports system + user message separation
  - format=json forces structured JSON output (Ollama >= 0.1.9)
  - Works with Qwen, Llama, Mistral, and other Ollama-supported models
"""

from __future__ import annotations

import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level defaults
# ---------------------------------------------------------------------------

_DEFAULT_TEMPERATURE = 0.3
# Low temperature keeps output focused and deterministic.
# Patent-style generation requires precision, not creativity.

_DEFAULT_TIMEOUT = settings.ollama_timeout
# Seconds to wait for a response from Ollama. Configured via OLLAMA_TIMEOUT.
# 7B+ models on consumer CPU/iGPU can take several minutes for long prompts
# (e.g. P2 over a full element-patent analysis), so the default is generous.


# ---------------------------------------------------------------------------
# Core generation functions
# ---------------------------------------------------------------------------

def generate(
    user_prompt: str,
    system_prompt: str,
    temperature: float = _DEFAULT_TEMPERATURE,
    timeout: float = _DEFAULT_TIMEOUT,
) -> str:
    """Send a chat request to Ollama and return the raw response text.

    Uses the /api/chat endpoint with a system message and a user message.
    Does not parse or validate the response — callers handle that.

    Raises:
        LLMConnectionError: if Ollama is unreachable or times out.
        LLMResponseError:   if Ollama returns a non-200 status or empty content.
    """
    url = f"{settings.ollama_base_url}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": temperature},
    }

    try:
        response = httpx.post(url, json=payload, timeout=timeout)
    except httpx.ConnectError as exc:
        raise LLMConnectionError(
            f"Cannot reach Ollama at {settings.ollama_base_url}. "
            "Ensure Ollama is running and the base URL in config is correct."
        ) from exc
    except httpx.TimeoutException as exc:
        raise LLMConnectionError(
            f"Ollama request timed out after {timeout}s. "
            "The model may be loading or the prompt may be too long."
        ) from exc

    if response.status_code != 200:
        raise LLMResponseError(
            f"Ollama returned status {response.status_code}: {response.text[:300]}"
        )

    data = response.json()
    content = data.get("message", {}).get("content", "")
    if not content:
        raise LLMResponseError("Ollama returned an empty message content.")
    return content


def generate_json(
    user_prompt: str,
    system_prompt: str,
    temperature: float = _DEFAULT_TEMPERATURE,
    timeout: float = _DEFAULT_TIMEOUT,
) -> dict:
    """Send a chat request to Ollama and return parsed JSON.

    Uses format=json to instruct Ollama to produce JSON output.
    On a parse failure, retries once with a stricter correction prompt
    containing the failed output and an explicit JSON-only instruction.

    If the retry also fails, raises LLMParseError. The pipeline catches
    this and produces a structured failure — never propagates garbage.

    Raises:
        LLMConnectionError: if Ollama is unreachable or times out.
        LLMResponseError:   if Ollama returns a non-200 status or empty content.
        LLMParseError:      if JSON cannot be parsed after one retry.
    """
    url = f"{settings.ollama_base_url}/api/chat"

    def _call(sp: str, up: str) -> str:
        payload = {
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": sp},
                {"role": "user",   "content": up},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
        }
        try:
            response = httpx.post(url, json=payload, timeout=timeout)
        except httpx.ConnectError as exc:
            raise LLMConnectionError(
                f"Cannot reach Ollama at {settings.ollama_base_url}."
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMConnectionError(
                f"Ollama request timed out after {timeout}s."
            ) from exc

        if response.status_code != 200:
            raise LLMResponseError(
                f"Ollama returned status {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        content = data.get("message", {}).get("content", "")
        if not content:
            raise LLMResponseError("Ollama returned an empty message content.")
        return content

    # First attempt
    raw = _call(system_prompt, user_prompt)
    try:
        return _parse_json(raw)
    except LLMParseError:
        logger.warning(
            "Ollama returned unparseable JSON on first attempt. Retrying with correction prompt."
        )

    # Single retry — include the failed output so the model can self-correct
    correction_prompt = (
        "Your previous response could not be parsed as JSON.\n\n"
        f"Previous response:\n{raw}\n\n"
        "Respond ONLY with valid JSON. "
        "Do not include any explanation, markdown, or code fences. "
        "Output only the raw JSON object."
    )
    raw_retry = _call(system_prompt, correction_prompt)
    try:
        return _parse_json(raw_retry)
    except LLMParseError as exc:
        raise LLMParseError(
            f"Ollama returned unparseable JSON on both attempts. "
            f"Last raw output: {raw_retry[:300]}"
        ) from exc


def _parse_json(raw: str) -> dict:
    """Parse a raw string as JSON, tolerating common LLM output variants.

    Layered strategy, each step a strict superset of the previous:

    1. Try parsing as-is (Ollama format=json path).
    2. Strip markdown code fences (``` or ```json … ```).
    3. Extract the first balanced top-level JSON object from the text.
       This handles remote-backend cases where the model echoes the
       prompt or adds commentary before/after the JSON. The extractor
       walks the string tracking brace depth and string-literal state
       so it does not get confused by braces inside string values.

    Raises LLMParseError if every strategy fails.
    """
    text = raw.strip()

    # Strategy 1: parse as-is.
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: strip markdown fences.
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
        try:
            result = json.loads(stripped)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            text = stripped  # fall through to extractor on the cleaner text

    # Strategy 3: walk the string and try every balanced JSON object,
    # preferring the LAST parseable one. Tolerates:
    #   - leading prose ("Here is the JSON: {...}")
    #   - prompt echoing (some remote backends repeat the user prompt
    #     before their own answer; the prompt itself contains example
    #     JSON, so the first match would be the example, not the answer)
    #   - models that produce multiple JSON objects in sequence
    candidates = _extract_balanced_json_objects(text)
    for candidate in reversed(candidates):
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue

    raise LLMParseError(
        f"JSON parse failed after all strategies. Raw (truncated): {raw[:300]}"
    )


def _extract_balanced_json_objects(text: str) -> list[str]:
    """Return every balanced top-level {...} substring in order.

    Tracks brace depth and string-literal state so braces inside
    string values do not throw off the count. Honors backslash
    escapes inside strings.
    """
    out: list[str] = []
    in_string = False
    escape = False
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    out.append(text[start : i + 1])
                    start = -1
    return out


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def check_ollama_health() -> tuple[bool, str]:
    """Check whether Ollama is running and the configured model is available.

    Returns:
        (True, "")       if healthy and model is present.
        (False, reason)  if unreachable or model is missing.

    Does not raise — safe to call at startup or from a status endpoint.
    """
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5.0)
    except Exception as exc:
        return False, f"Cannot reach Ollama: {exc}"

    if response.status_code != 200:
        return False, f"Ollama /api/tags returned status {response.status_code}"

    try:
        models = response.json().get("models", [])
        model_names = [m.get("name", "") for m in models]
    except Exception:
        return False, "Could not parse Ollama model list."

    configured = settings.ollama_model
    found = configured in model_names
    if not found:
        available = ", ".join(model_names) or "none"
        return False, f"Model '{configured}' not found in Ollama. Available: {available}"

    return True, ""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLMConnectionError(RuntimeError):
    """Raised when Ollama cannot be reached or times out."""


class LLMResponseError(RuntimeError):
    """Raised when Ollama returns an unexpected HTTP status or empty content."""


class LLMParseError(RuntimeError):
    """Raised when the LLM output cannot be parsed as valid JSON."""
