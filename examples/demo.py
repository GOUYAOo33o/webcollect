"""Minimal demo: header-aligned table extraction (no browser needed).

Run:  python examples/demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webcollect.table import TableExtractor, to_number


def main() -> None:
    ext = TableExtractor(
        labels=["Cost", "ROI"],
        fields={
            "name": ("Name", None),
            "cost": ("Cost", to_number),
            "roi": ("ROI", to_number),
        },
    )
    rows = [
        ["#", "Name", "Cost (¥)", "ROI"],
        ["1", "A", "1,234.5", "2.5%"],
        ["2", "B", "200", "3.0"],
    ]
    for record in ext(rows):
        print(record)


if __name__ == "__main__":
    main()
