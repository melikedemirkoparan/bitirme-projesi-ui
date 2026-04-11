"""
Development test script for the A.1 ingestion logic layer.
Run from the project root:
    .venv/bin/python scripts/test_ingestion.py

Tests:
  1. Parser — column resolution, row extraction, found_targets
  2. Missing mandatory column — service returns error, no collections built
  3. Full ingestion — against the real Excel file in data/
"""

import sys
import os

# Ensure project root is on the path so `app.*` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.excel_parser import parse_excel
from app.ingestion.ingest_service import run_ingestion

EXCEL_PATH = "data/TUSAŞ_Tarifname_Translated.xlsx"
SEP = "─" * 60


# ── Helper ────────────────────────────────────────────────────────

def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


# ── Test 1: Parser ────────────────────────────────────────────────

def test_parser():
    print(SEP)
    print("TEST 1 — Parser: column resolution + row extraction")
    print(SEP)

    file_bytes = _read(EXCEL_PATH)
    rows, found_targets = parse_excel(file_bytes)

    print(f"  Total rows parsed : {len(rows)}")
    print(f"  Found targets     : {sorted(found_targets)}")

    # Inspect first row canonical keys and values
    print("\n  First row (canonical):")
    for k, v in rows[0].items():
        preview = (v[:80] + "…") if v and len(v) > 80 else v
        print(f"    {k:30s}: {preview!r}")

    # Count None values per target key across all rows
    print("\n  None counts per target key:")
    for key in ["definition_en", "description_title_en", "all_elements_context_en"]:
        none_count = sum(1 for r in rows if r.get(key) is None)
        print(f"    {key:35s}: {none_count} None / {len(rows)} total")

    assert len(rows) > 0, "Expected at least one row"
    assert "definition_en" in found_targets, "definition_en must be found"
    assert "all_elements_context_en" in found_targets, "all_elements_context_en must be found"
    print("\n  PASSED\n")


# ── Test 2: Missing mandatory column ─────────────────────────────

def test_missing_mandatory_column():
    print(SEP)
    print("TEST 2 — Service: missing definition_en → early error")
    print(SEP)

    # Build a minimal fake Excel with no definition_en column
    import io
    import pandas as pd

    df = pd.DataFrame({
        "All Elements in Specification (EN)": ["foo", "bar"],
        "Element Name (EN)": ["A", "B"],
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    fake_bytes = buf.getvalue()

    result = run_ingestion(fake_bytes, "fake_no_definition.xlsx")

    print(f"  result.success : {result.success}")
    print(f"  result.error   : {result.error!r}")
    print(f"  collections    : {result.collections}")

    assert not result.success, "Should not succeed when definition_en is missing"
    assert "definition_en" in result.error.lower(), "Error message should mention definition_en"
    assert result.collections == [], "No collections should be built"
    print("\n  PASSED\n")


# ── Test 3: Full ingestion ────────────────────────────────────────

def test_full_ingestion():
    print(SEP)
    print("TEST 3 — Full ingestion against real Excel file")
    print(SEP)

    file_bytes = _read(EXCEL_PATH)
    result = run_ingestion(file_bytes, os.path.basename(EXCEL_PATH))

    print(f"  filename       : {result.filename}")
    print(f"  success        : {result.success}")
    print(f"  error          : {result.error!r}")
    print()
    for cr in result.collections:
        print(f"  [{cr.status.upper():7s}] {cr.collection_name}")
        if cr.doc_count:
            print(f"           docs  : {cr.doc_count}")
        if cr.reason:
            print(f"           reason: {cr.reason}")

    assert result.success, f"Ingestion should succeed. error={result.error!r}"
    created = [c for c in result.collections if c.status == "created"]
    assert any(c.collection_name == "patent_definition_en" for c in created), \
        "patent_definition_en must be created"
    print("\n  PASSED\n")


# ── Run all ───────────────────────────────────────────────────────

if __name__ == "__main__":
    test_parser()
    test_missing_mandatory_column()
    test_full_ingestion()
    print(SEP)
    print("ALL TESTS PASSED")
    print(SEP)
