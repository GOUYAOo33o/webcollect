"""webcollect — reusable building blocks for robust browser-based collection.

Modules:
  table       — header-aligned table extraction (never hard-code a column index)
  session     — save/restore browser login state (cookies + localStorage)
  pagination  — resilient paginated collection with dedup and stability waits
  browser     — profile locking and stale-lock cleanup
"""
from . import browser, pagination, session, table

__all__ = ["browser", "pagination", "session", "table"]
__version__ = "0.1.0"
