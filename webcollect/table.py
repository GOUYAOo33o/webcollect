"""Header-aligned table extraction.

The core idea: **never hard-code a column index**. Real web tables reorder
columns, insert an ad row, or add a checkbox column between releases. Instead,
locate the header row by its text, map each wanted field to its column by
matching the header label, then read data rows by those discovered indices.

All functions here are pure and dependency-free, so they can be unit-tested
without a browser.
"""
from __future__ import annotations

import re
from typing import Callable, Iterable, Sequence

Row = Sequence[str]


def normalize(text) -> str:
    """Collapse internal whitespace and trim — table cells are full of \\n and NBSP."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text).replace("\u00a0", " ")).strip()


def find_header(rows: Iterable[Row], labels: Sequence[str],
                match: str = "contains") -> tuple[int, dict[str, int]] | None:
    """Find the header row and the column index for each wanted label.

    Args:
        rows: sequence of rows, each a sequence of cell strings.
        labels: header texts to locate (e.g. ["Cost", "ROI"]).
        match: "exact" for equality after normalize, "contains" for substring.

    Returns:
        (header_row_index, {label: column_index}) or None if no row matches
        all labels. Requiring *all* labels avoids false positives on a
        toolbar row that happens to contain one of the words.
    """
    rows = list(rows)
    if not rows:
        return None
    for ri, row in enumerate(rows):
        cells = [normalize(c) for c in row]
        found: dict[str, int] = {}
        for label in labels:
            lab = normalize(label)
            idx = -1
            for ci, cell in enumerate(cells):
                hit = (cell == lab) if match == "exact" else (lab in cell)
                if hit:
                    idx = ci
                    break
            if idx < 0:
                break
            found[label] = idx
        if len(found) == len(labels):
            return ri, found
    return None


def extract(rows: Sequence[Row], header: tuple[int, dict[str, int]],
            fields: dict[str, tuple[str, Callable[[str], object] | None]],
            skip: Callable[[Row], bool] | None = None) -> list[dict]:
    """Extract data rows below the header into dicts.

    Args:
        rows: all table rows (including the header row).
        header: result of :func:`find_header` — (header_index, label→col).
        fields: {output_key: (header_label, converter)}. converter defaults to
                :func:`normalize` when None.
        skip: optional predicate to drop junk rows (e.g. summary/footer rows).

    Returns:
        list of dicts, one per data row that has any non-empty field.
    """
    hi, index = header
    out: list[dict] = []
    for row in rows[hi + 1:]:
        if skip and skip(row):
            continue
        record: dict = {}
        for key, (label, conv) in fields.items():
            ci = index.get(label, index.get(normalize(label), -1))
            raw = row[ci] if 0 <= ci < len(row) else ""
            record[key] = (conv or normalize)(raw)
        if any(v not in (None, "") for v in record.values()):
            out.append(record)
    return out


def to_number(text) -> float | None:
    """Parse a display number like '1,234.5' / '12.3%' / '¥89' into a float.

    Percent signs are stripped (the caller decides what they mean). Returns
    None for empty or non-numeric cells rather than raising — a single bad
    cell must not abort a whole scrape.
    """
    s = normalize(text).replace(",", "").replace("%", "").replace("¥", "")
    s = s.replace("￥", "").replace("$", "").strip()
    if not s:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


class TableExtractor:
    """Convenience wrapper binding a header spec to a reusable extractor.

    Example::

        ext = TableExtractor(
            labels=["Cost", "ROI"],
            fields={"cost": ("Cost", to_number), "roi": ("ROI", to_number)},
        )
        rows = ext([[...header...], ["A", "100", "2.5"]])
    """

    def __init__(self, labels: Sequence[str] | None,
                 fields: dict[str, tuple[str, Callable[[str], object] | None]],
                 match: str = "contains",
                 skip: Callable[[Row], bool] | None = None):
        # Auto-collect every header label used by fields, so callers never
        # have to declare labels twice (a classic source of silent empties).
        wanted = list(labels or [])
        for _key, (label, _conv) in fields.items():
            if label not in wanted:
                wanted.append(label)
        self.labels = wanted
        self.fields = fields
        self.match = match
        self.skip = skip

    def __call__(self, rows: Sequence[Row]) -> list[dict]:
        header = find_header(rows, self.labels, match=self.match)
        if header is None:
            return []
        return extract(rows, header, self.fields, skip=self.skip)
