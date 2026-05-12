"""Remote LLM client (ngrok-style /generate endpoint).

One of two LLM backends supported by the pipeline. The other is
`llm_client` (local Ollama). The router (`llm_router.call_llm`) picks
between them at call time:

  - If a remote URL is configured here, requests go to the remote.
  - Otherwise, the router falls through to local Ollama.

The URL is set at runtime via /api/rag/set-llm-url and persisted to
the `app_setting` table so it survives server restarts. On import we
hydrate the in-process cache from the DB; on each `set_remote_llm_url`
we update both.
"""

from __future__ import annotations

import json
import urllib.request


_remote_llm_url: str = ""
_last_llm_error: str = ""
_hydrated: bool = False

# Settings key under which the URL is stored.
_LLM_URL_KEY = "llm_remote_url"


def _hydrate_from_db_once() -> None:
    """Load the persisted URL on first access. Best-effort: if the DB
    is unreachable (e.g. pre-migration import), we silently keep the
    empty default and let the user re-set it."""
    global _remote_llm_url, _hydrated
    if _hydrated:
        return
    _hydrated = True
    try:
        from app.services.app_setting_service import get_value_standalone

        stored = get_value_standalone(_LLM_URL_KEY)
        if stored:
            _remote_llm_url = stored.strip().rstrip("/")
            print(f"[LLM] Hydrated remote URL from DB: {_remote_llm_url}")
    except Exception as e:
        print(f"[LLM] Could not hydrate remote URL from DB: {e}")


def set_remote_llm_url(url: str) -> None:
    """Set the remote /generate endpoint base URL. Pass "" to clear.

    The new value is persisted to `app_setting` so it survives a
    restart.
    """
    global _remote_llm_url, _last_llm_error, _hydrated
    cleaned = (url or "").strip().rstrip("/")
    if cleaned and not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        raise ValueError(
            "LLM URL must start with http:// or https:// (e.g. https://abc.ngrok-free.app). "
            "Do not paste your ngrok auth token here — paste the public URL printed by your Colab notebook."
        )
    _remote_llm_url = cleaned
    _last_llm_error = ""
    _hydrated = True
    try:
        from app.services.app_setting_service import set_value_standalone

        set_value_standalone(_LLM_URL_KEY, cleaned or None)
    except Exception as e:
        print(f"[LLM] Could not persist remote URL: {e}")
    print(f"[LLM] Remote URL set: {_remote_llm_url}")


def get_remote_llm_url() -> str:
    _hydrate_from_db_once()
    return _remote_llm_url


def get_last_llm_error() -> str:
    return _last_llm_error


def is_configured() -> bool:
    return bool(get_remote_llm_url())


def call_llm(prompt: str, max_new_tokens: int = 120, temperature: float = 0.2) -> str:
    """Call the remote LLM via /generate. Returns "" on any failure.

    `temperature` is accepted for API compatibility — the current
    /generate endpoint ignores it but a future version may honor it.
    """
    global _last_llm_error
    url = get_remote_llm_url()
    if not url:
        return ""
    try:
        data = json.dumps({
            "prompt": prompt,
            "max_tokens": max_new_tokens,
        }).encode("utf-8")
        req = urllib.request.Request(
            url + "/generate",
            data=data,
            headers={
                "Content-Type": "application/json",
                "ngrok-skip-browser-warning": "true",
            },
        )
        resp = urllib.request.urlopen(req, timeout=120)
        result = json.loads(resp.read().decode())
        return result.get("text", "")
    except Exception as e:
        _last_llm_error = str(e)
        print(f"[LLM] Remote call failed: {e}")
        return ""
