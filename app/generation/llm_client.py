"""
LLM client wrapper.

Single integration point between the generation pipeline / assistant and
the configured LLM backend. Nothing else in the codebase talks to the
inference server directly.

Two wire protocols are supported and auto-selected from the base URL:

  - Ollama native        — base URL has no `/v1` suffix.
                           Endpoint: POST {base}/api/chat
                           JSON mode: `"format": "json"`
  - OpenAI-compatible    — base URL ends with `/v1` (or contains `/v1/`).
                           Endpoint: POST {base}/chat/completions
                           JSON mode: `"response_format": {"type": "json_object"}`
                           Works with llama-cpp-python, vLLM, LM Studio, etc.

Swap the backend by pointing the remote URL at the right server. Model name
in `settings.ollama_model` is forwarded as-is; OpenAI-compatible servers that
only load one model treat the field as a hint.
"""

from __future__ import annotations

import json
import re
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_TEMPERATURE = 0.5
_DEFAULT_TIMEOUT = settings.ollama_timeout


# ---------------------------------------------------------------------------
# Protocol detection
# ---------------------------------------------------------------------------

def _resolve_endpoint(base_url: str) -> tuple[str, str, str]:
    """Return (root_url, protocol, chat_url) for the given base URL.

    `root_url` has any trailing `/v1` or `/` stripped — useful for building
    sibling endpoints (e.g. /v1/models, /api/tags) consistently.

    `protocol` is "openai" if the URL ends with `/v1` (or contains `/v1/`),
    otherwise "ollama".

    `chat_url` is the fully-formed chat endpoint to POST to.
    """
    stripped = (base_url or "").rstrip("/")

    if stripped.endswith("/v1"):
        root = stripped[:-3].rstrip("/")
        return root, "openai", f"{root}/v1/chat/completions"

    if "/v1/" in stripped:
        root = stripped.split("/v1/", 1)[0].rstrip("/")
        return root, "openai", f"{root}/v1/chat/completions"

    return stripped, "ollama", f"{stripped}/api/chat"


def _request_headers() -> dict[str, str]:
    # ngrok free tier injects an HTML interstitial unless this header is set.
    return {"ngrok-skip-browser-warning": "true"}


def _post_chat(
    chat_url: str,
    payload: dict,
    timeout: float,
    effective_url_for_errors: str,
) -> httpx.Response:
    try:
        return httpx.post(
            chat_url, json=payload, timeout=timeout, headers=_request_headers()
        )
    except httpx.ConnectError as exc:
        raise LLMConnectionError(
            f"Cannot reach LLM backend at {effective_url_for_errors}. "
            "Ensure the inference server is running and the base URL is correct."
        ) from exc
    except httpx.TimeoutException as exc:
        raise LLMConnectionError(
            f"LLM request timed out after {timeout}s. "
            "The model may be loading or the prompt may be too long."
        ) from exc


# ---------------------------------------------------------------------------
# Core generation functions
# ---------------------------------------------------------------------------

def generate(
    user_prompt: str,
    system_prompt: str,
    temperature: float = _DEFAULT_TEMPERATURE,
    timeout: float = _DEFAULT_TIMEOUT,
    base_url: str | None = None,
    model_name: str | None = None,
) -> str:
    """Send a chat request to the configured backend and return raw text.

    Auto-selects between Ollama `/api/chat` and OpenAI `/v1/chat/completions`
    based on the URL. Does not parse or validate the response — callers handle that.

    Raises:
        LLMConnectionError: if the backend is unreachable or times out.
        LLMResponseError:   if the backend returns a non-200 status or empty content.
    """
    effective_url = base_url or settings.ollama_base_url
    effective_model = model_name or settings.ollama_model
    root_url, protocol, chat_url = _resolve_endpoint(effective_url)

    if protocol == "openai":
        payload = {
            "model": effective_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "stream": False,
            "temperature": temperature,
        }
    else:
        payload = {
            "model": effective_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }

    response = _post_chat(chat_url, payload, timeout, root_url)

    if response.status_code != 200:
        raise LLMResponseError(
            f"LLM backend returned status {response.status_code} from {chat_url}: "
            f"{response.text[:300]}"
        )

    data = response.json()
    content = _extract_content(data, protocol)
    if not content:
        raise LLMResponseError(f"LLM backend returned empty content via {protocol} protocol.")
    return content


def generate_json(
    user_prompt: str,
    system_prompt: str,
    temperature: float = _DEFAULT_TEMPERATURE,
    timeout: float = _DEFAULT_TIMEOUT,
    base_url: str | None = None,
    model_name: str | None = None,
) -> dict:
    """Send a chat request in JSON mode and return parsed JSON.

    Uses the backend's native JSON mode:
      - Ollama:           "format": "json"
      - OpenAI-compat:    "response_format": {"type": "json_object"}

    On a parse failure, retries once with a correction prompt containing
    the failed output and an explicit JSON-only instruction.

    Raises:
        LLMConnectionError: backend unreachable / timeout.
        LLMResponseError:   non-200 / empty content.
        LLMParseError:      invalid JSON after one retry.
    """
    effective_url = base_url or settings.ollama_base_url
    effective_model = model_name or settings.ollama_model
    root_url, protocol, chat_url = _resolve_endpoint(effective_url)

    def _build_payload(sp: str, up: str) -> dict:
        if protocol == "openai":
            return {
                "model": effective_model,
                "messages": [
                    {"role": "system", "content": sp},
                    {"role": "user",   "content": up},
                ],
                "stream": False,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            }
        return {
            "model": effective_model,
            "messages": [
                {"role": "system", "content": sp},
                {"role": "user",   "content": up},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
        }

    def _call(sp: str, up: str) -> str:
        response = _post_chat(chat_url, _build_payload(sp, up), timeout, root_url)
        if response.status_code != 200:
            raise LLMResponseError(
                f"LLM backend returned status {response.status_code} from {chat_url}: "
                f"{response.text[:300]}"
            )
        data = response.json()
        content = _extract_content(data, protocol)
        if not content:
            raise LLMResponseError(f"LLM backend returned empty content via {protocol} protocol.")
        return content

    # First attempt
    raw = _call(system_prompt, user_prompt)
    try:
        return _parse_json(raw)
    except LLMParseError:
        logger.warning(
            "LLM returned unparseable JSON on first attempt. Retrying with correction prompt."
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
            f"LLM returned unparseable JSON on both attempts. "
            f"Last raw output: {raw_retry[:300]}"
        ) from exc


def _extract_content(data: dict, protocol: str) -> str:
    """Extract the assistant message content from a backend response."""
    if protocol == "openai":
        choices = data.get("choices") or []
        if not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        # OpenAI standard: choices[0].message.content
        msg = first.get("message") or {}
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, str):
                return content
        # Some servers (older llama.cpp) emit `text` under the choice directly
        text = first.get("text")
        if isinstance(text, str):
            return text
        return ""

    # Ollama
    return (data.get("message") or {}).get("content", "") or ""


def _parse_json(raw: str) -> dict:
    """Parse a raw string as JSON, tolerating common LLM output variants.

    Layered strategy, each step a strict superset of the previous:

    0. Strip <think>...</think> blocks (DeepSeek-R1 reasoning preamble).
    1. Try parsing as-is.
    2. Strip markdown code fences (``` or ```json … ```).
    3. Extract the first balanced top-level JSON object from the text.

    Raises LLMParseError if every strategy fails.
    """
    # Strategy 0: drop any <think>...</think> reasoning blocks emitted by
    # DeepSeek-R1 and similar reasoning models. The blocks may appear before
    # or interleaved with the JSON; remove them all (DOTALL for multiline).
    text = re.sub(r"<think\b[^>]*>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    # Some R1 variants emit only the opening tag and no closing tag — drop the
    # leading "<think>...\n\n" preamble up to the first { we see.
    if "<think" in text and "</think>" not in text:
        first_brace = text.find("{")
        if first_brace > 0:
            text = text[first_brace:]
    text = text.strip()

    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

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
            text = stripped

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
    """Check whether the configured LOCAL backend is reachable and the model is available.

    Auto-selects the probe based on the local URL's protocol:
      - Ollama:        GET /api/tags  → list of {name: ...}
      - OpenAI-compat: GET /v1/models → {"data": [{"id": ...}]}

    Returns:
        (True, "")       if healthy and model is present (Ollama) /
                         the server responds (OpenAI-compat).
        (False, reason)  otherwise.
    """
    root_url, protocol, _ = _resolve_endpoint(settings.ollama_base_url)

    if protocol == "openai":
        probe_url = f"{root_url}/v1/models"
    else:
        probe_url = f"{root_url}/api/tags"

    try:
        response = httpx.get(probe_url, timeout=5.0, headers=_request_headers())
    except Exception as exc:
        return False, f"Cannot reach LLM backend ({protocol}) at {probe_url}: {exc}"

    if response.status_code != 200:
        return False, f"{probe_url} returned status {response.status_code}"

    try:
        data = response.json()
    except Exception:
        return False, "Could not parse model list response."

    configured = settings.ollama_model

    if protocol == "openai":
        # llama-cpp.server returns {"data": [{"id": "<model_id>"}]} or similar.
        # For single-model servers the id may be a file path; accept any
        # non-empty list as healthy.
        items = data.get("data") if isinstance(data, dict) else None
        if not items:
            return False, "OpenAI-compat /v1/models returned no entries."
        return True, ""

    # Ollama
    models = data.get("models", []) if isinstance(data, dict) else []
    model_names = [m.get("name", "") for m in models]
    if configured not in model_names:
        available = ", ".join(model_names) or "none"
        return False, f"Model '{configured}' not found in Ollama. Available: {available}"
    return True, ""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLMConnectionError(RuntimeError):
    """Raised when the LLM backend cannot be reached or times out."""


class LLMResponseError(RuntimeError):
    """Raised when the LLM backend returns an unexpected HTTP status or empty content."""


class LLMParseError(RuntimeError):
    """Raised when the LLM output cannot be parsed as valid JSON."""
