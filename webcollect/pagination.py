"""Resilient paginated collection.

Collecting rows from a paged table has recurring failure modes: the "next"
button is a custom element that ignores a plain click, the DOM updates
asynchronously so an immediate read gets stale rows, and identical rows can
appear across page boundaries. This module captures the reusable patterns:

  * a :class:`PageCollector` that loops pages through injected callbacks,
  * row de-duplication by key,
  * a :func:`wait_stable` polling helper that waits for the DOM to settle.

Browser interactions are injected as callables, so the loop logic is pure and
unit-testable without a browser.
"""
from __future__ import annotations

import time
from typing import Callable, Hashable, Iterable


def wait_stable(read: Callable[[], object], max_wait: float = 15.0,
                need_stable: int = 2, interval: float = 0.3,
                sleep: Callable[[float], None] = time.sleep) -> bool:
    """Poll ``read`` until its result stays unchanged ``need_stable`` times.

    Returns True if stability was reached, False on timeout. Used after a page
    navigation or filter change, where the table re-renders asynchronously.
    ``sleep`` is injectable for fast tests.
    """
    deadline = time.monotonic() + max_wait
    last: object = object()
    streak = 0
    while True:
        try:
            current = read()
        except Exception:  # noqa: BLE001 - transient DOM errors are normal
            current = None
        if current == last and current is not None:
            streak += 1
            if streak >= need_stable:
                return True
        else:
            streak = 0
            last = current
        if time.monotonic() >= deadline:
            return False
        sleep(interval)


class PageCollector:
    """Loop through pages, collect rows, stop cleanly.

    Args:
        read_page: () -> list[dict]  — rows visible on the current page.
        has_next: () -> bool         — whether a next page exists / is enabled.
        go_next: () -> bool          — advance; return False if it failed.
        key: callable(row) -> Hashable — dedup key (default: full row tuple).

    The callbacks are supplied by the caller because they are site-specific;
    everything generic about pagination lives here.
    """

    def __init__(self, read_page: Callable[[], list[dict]],
                 has_next: Callable[[], bool],
                 go_next: Callable[[], bool],
                 key: Callable[[dict], Hashable] | None = None):
        self.read_page = read_page
        self.has_next = has_next
        self.go_next = go_next
        self.key = key or (lambda r: tuple(sorted(r.items())))

    def collect(self, max_pages: int = 50,
                on_page: Callable[[int, list[dict]], None] | None = None) -> list[dict]:
        """Collect up to ``max_pages`` pages, de-duplicating rows by key."""
        out: list[dict] = []
        seen: set[Hashable] = set()
        page = 0
        while page < max_pages:
            rows = self.read_page() or []
            fresh = []
            for row in rows:
                k = self.key(row)
                if k in seen:
                    continue
                seen.add(k)
                fresh.append(row)
            out.extend(fresh)
            page += 1
            if on_page:
                on_page(page, fresh)
            if not self.has_next():
                break
            if not self.go_next():
                break
        return out
