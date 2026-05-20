"""Authentication and YTMusic client factory.

Uses browser-cookie auth via ytmusicapi. The user pastes request headers
from Chrome DevTools on music.youtube.com once; ytmusicapi parses the cookies
and saves them to ~/.config/ytmusic-mcp/browser.json (~2 year validity).
"""

from __future__ import annotations

from pathlib import Path

from ytmusicapi import YTMusic, setup

CONFIG_DIR = Path.home() / ".config" / "ytmusic-mcp"
BROWSER_JSON = CONFIG_DIR / "browser.json"


def ensure_config_dir() -> Path:
    """Create the config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def is_authenticated() -> bool:
    """Return True if the browser auth file exists on disk."""
    return BROWSER_JSON.exists()


def get_client() -> YTMusic:
    """Return an authenticated YTMusic client.

    Raises:
        RuntimeError: if the user has not run `ytmusic-mcp auth` yet.
    """
    if not is_authenticated():
        raise RuntimeError(
            f"Not authenticated. Run 'ytmusic-mcp auth' first.\n"
            f"Expected auth file at: {BROWSER_JSON}"
        )
    return YTMusic(str(BROWSER_JSON))


def setup_auth(headers_raw: str | None = None) -> Path:
    """Run the browser-cookie auth setup.

    Args:
        headers_raw: Raw HTTP request headers copied from Chrome DevTools.
            If None, ytmusicapi will prompt interactively.

    Returns:
        Path to the saved browser.json file.
    """
    ensure_config_dir()
    setup(filepath=str(BROWSER_JSON), headers_raw=headers_raw)
    return BROWSER_JSON


def auth_status() -> dict:
    """Return a dict describing current auth state, including a live API ping."""
    info = {
        "config_dir": str(CONFIG_DIR),
        "auth_file": str(BROWSER_JSON),
        "authenticated": is_authenticated(),
    }
    if not info["authenticated"]:
        return info
    try:
        yt = get_client()
        account = yt.get_account_info()
        info["account_name"] = account.get("accountName", "unknown")
        info["channel_handle"] = account.get("channelHandle", "unknown")
        info["valid"] = True
    except Exception as exc:  # noqa: BLE001 — we want to surface any failure
        info["valid"] = False
        info["error"] = str(exc)
    return info
