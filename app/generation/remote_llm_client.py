"""Remote Ollama URL setting.

The remote backend is just an Ollama instance reachable via a different
base URL (typically an ngrok tunnel pointing at a Colab/Cloud Ollama
server). The HTTP protocol is identical to the local Ollama path, so
all generation logic lives in `llm_client`. This module only stores
the URL and persists it across restarts via `app_setting`.

If a remote URL is configured, `llm_router` forwards both `call_llm`
and `generate_json` to the local Ollama client with `base_url` set to
the remote URL. Otherwise the local default applies.
"""

from __future__ import annotations


_remote_llm_url: str = ""
_hydrated: bool = False

# Settings key under which the URL is stored.
_LLM_URL_KEY = "llm_remote_url"


def _hydrate_from_db_once() -> None:
    """Load the persisted URL on first access. Best-effort: if the DB
    is unreachable (e.g. pre-migration import), keep the empty default
    and let the user re-set it."""
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
    """Set the remote Ollama base URL. Pass "" to clear.

    The new value is persisted to `app_setting` so it survives a restart.
    """
    global _remote_llm_url, _hydrated
    cleaned = (url or "").strip().rstrip("/")
    if cleaned and not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        raise ValueError(
            "LLM URL must start with http:// or https:// "
            "(e.g. https://abc.ngrok-free.app). Paste the public URL "
            "printed by your Colab notebook, not the ngrok auth token."
        )
    _remote_llm_url = cleaned
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


def is_configured() -> bool:
    return bool(get_remote_llm_url())
