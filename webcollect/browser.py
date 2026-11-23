"""Browser launch with profile locking — generic helpers.

Two production problems solved here:

1. **Concurrent runs corrupt a profile.** Two processes using the same browser
   profile fight over lock files. A simple file-based lock serialises them.
2. **Stale locks after a crash.** A killed browser leaves ``SingletonLock`` /
   ``lockfile`` behind, and the next launch silently opens a blank page. A
   targeted cleanup removes only those known lock files — never the profile.

The actual browser launch is left to the caller (passed as a factory), keeping
this module independent of any specific automation library.
"""
from __future__ import annotations

import os
import time
from typing import Callable


class ProfileLocked(RuntimeError):
    """Raised when a profile is already in use by another process."""


class ProfileGuard:
    """File-based lock for one browser profile.

    Uses atomic ``os.mkdir`` (works on Windows and POSIX). ``stale_after``
    lets a crashed process's lock expire automatically.

    Usage::

        with ProfileGuard(profile):
            launch_browser(profile)
    """

    def __init__(self, profile: str, stale_after: float = 1800.0):
        self.lock = os.path.join(str(profile).rstrip("\\/") + ".lock")
        self.stale_after = stale_after
        self._held = False

    def acquire(self, timeout: float = 0.0) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            try:
                os.mkdir(self.lock)
                with open(os.path.join(self.lock, "owner"), "w", encoding="utf-8") as f:
                    f.write(f"{os.getpid()}")
                self._held = True
                return True
            except FileExistsError:
                if self._is_stale():
                    self._remove()
                    continue
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.2)

    def _is_stale(self) -> bool:
        try:
            age = time.time() - os.path.getmtime(self.lock)
        except OSError:
            return True
        return age > self.stale_after

    def _remove(self) -> None:
        try:
            for name in os.listdir(self.lock):
                try:
                    os.remove(os.path.join(self.lock, name))
                except OSError:
                    pass
            os.rmdir(self.lock)
        except OSError:
            pass
        self._held = False

    def release(self) -> None:
        if self._held:
            self._remove()

    def __enter__(self) -> "ProfileGuard":
        if not self.acquire():
            raise ProfileLocked(f"profile in use: {self.lock}")
        return self

    def __exit__(self, *_exc) -> None:
        self.release()


# Lock file names left by Chromium-based browsers after an unclean exit.
_STALE_LOCK_FILES = (
    "SingletonLock", "SingletonCookie", "SingletonSocket",
    "lockfile", ".lock",
)


def clean_profile_locks(profile: str, dry_run: bool = False) -> list[str]:
    """Remove known stale browser lock files inside ``profile``.

    Purpose: after a crash these files make the next launch open a blank page
    instead of restoring the session. Only the whitelisted lock file names are
    touched — profile data (cookies, history, cache) is never removed.

    Returns the list of files removed (or that would be removed in dry-run).
    """
    removed: list[str] = []
    if not os.path.isdir(profile):
        return removed
    for name in _STALE_LOCK_FILES:
        path = os.path.join(profile, name)
        if not os.path.exists(path):
            continue
        if not dry_run:
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    os.rmdir(path)
                else:
                    os.remove(path)
            except OSError:
                continue
        removed.append(path)
    return removed
