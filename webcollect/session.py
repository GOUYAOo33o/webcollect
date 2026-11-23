"""Browser session persistence — save and restore login state.

Key insight from production: persisting only a browser *profile directory*
is not enough. Many sites keep the auth token in a **session cookie**, which
is dropped when the browser closes. Saving the full storage state (cookies +
localStorage) and injecting it on the next launch avoids re-login every run.

This module is browser-agnostic: it works with any context object exposing
``storage_state(path=...)``, ``add_cookies(...)`` and ``cookies()`` (e.g. a
Playwright BrowserContext). No direct playwright import — easy to test with a
fake context.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any


def default_state_dir() -> str:
    """Platform-appropriate directory for persisted session files."""
    base = os.environ.get("WEBCOLLECT_STATE_DIR")
    if base:
        return base
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "webcollect", "states")
    return os.path.join(os.path.expanduser("~"), ".webcollect", "states")


def state_path(profile: str, state_dir: str | None = None) -> str:
    """Map a profile name to a safe, flat filename.

    Sanitise the *whole* string, not ``os.path.basename``: on Windows a value
    like ``a:b`` is parsed as a drive-qualified path, so basename would drop
    the leading part. Replacing every non-safe char first avoids that trap.
    """
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(profile))
    safe = safe.strip("._") or "default"
    return os.path.join(state_dir or default_state_dir(), safe + ".json")


def save_state(ctx: Any, profile: str, state_dir: str | None = None,
               log=None) -> str | None:
    """Write the context's cookies + localStorage to disk. Returns the path."""
    path = state_path(profile, state_dir)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        ctx.storage_state(path=path)
        if log:
            log(f"login state saved -> {path}")
        return path
    except Exception as e:  # noqa: BLE001 - a failed save must not abort the run
        if log:
            log(f"login state save failed: {str(e)[:100]}")
        return None


def load_state(ctx: Any, profile: str, state_dir: str | None = None,
               log=None) -> bool:
    """Inject a previously saved state into a fresh context.

    Restores cookies and localStorage origins. Malformed or stale files are
    skipped silently so a corrupted state can never break startup.
    """
    path = state_path(profile, state_dir)
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return False

    ok = False
    for cookie in data.get("cookies") or []:
        try:
            ctx.add_cookies([cookie])
            ok = True
        except Exception:  # noqa: BLE001 - some cookies expire / are malformed
            continue

    for origin in data.get("origins") or []:
        entries = origin.get("localStorage") or []
        if not entries:
            continue
        # Prefer a dedicated helper if the context provides one; otherwise
        # fall back to evaluating code in a page (caller can wire this hook).
        setter = getattr(ctx, "set_local_storage", None)
        if callable(setter):
            try:
                setter(origin.get("origin", ""), entries)
                ok = True
            except Exception:  # noqa: BLE001
                continue
    if log:
        log(f"login state loaded: {ok} ({len(data.get('cookies') or [])} cookies)")
    return ok


def is_fresh(path: str, max_age_days: float = 7) -> bool:
    """Whether a saved state is recent enough to be worth reusing."""
    try:
        age = time.time() - os.path.getmtime(path)
    except OSError:
        return False
    return age <= max_age_days * 86400


def cookies_logged_in(cookies: list[dict], markers: list[str]) -> bool:
    """Check login by presence of named auth cookies.

    ``markers`` are cookie names known to indicate a live session. Using
    names (not values) avoids logging secrets and stays valid across tokens.
    """
    names = {c.get("name") for c in cookies if isinstance(c, dict)}
    return any(m in names for m in markers)
