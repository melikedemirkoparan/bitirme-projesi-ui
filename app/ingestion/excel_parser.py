# ── Excel parser ─────────────────────────────────────────────────
# Reads the uploaded Excel file into a canonical row format that the
# rest of the ingestion pipeline works with regardless of the exact
# column headers present in any given file.
#
# The file may use Turkish or English column headers — COLUMN_ALIASES
# maps each canonical key to an ordered list of candidate header
# strings.  The first match found in the file wins.
#
# This module is responsible only for:
#   - reading the file (raises on unreadable input)
#   - resolving actual column headers to canonical keys
#   - extracting canonical row dicts
#
# Business rules (e.g. which columns are mandatory) live in the
# ingestion service, not here.

import io

import pandas as pd

# ── Canonical → candidate header strings ────────────────────────
# Order matters: more specific / expected variants come first.
COLUMN_ALIASES: dict[str, list[str]] = {
    "element_id":             ["Unsur Referansı",                    "element_id",                  "Element ID",               "Element Ref"],
    "element_name_en":        ["Element Name (EN)",                  "element_name_en",             "Element_Name_EN"],
    "element_name_tr":        ["Unsur İsmi",                         "element_name_tr",             "Element Name (TR)"],
    "definition_en":          ["Definition (EN)",                    "definition_en",               "Definition_EN"],
    "definition_tr":          ["Tanım",                              "definition_tr",               "Definition (TR)"],
    "all_elements_context_en":["All Elements in Specification (EN)", "all_elements_context_en"],
    "all_elements_context_tr":["Tarifnamede Geçen Tüm Unsurlar",     "all_elements_context_tr"],
    "description_title_en":   ["description_title_en",               "Description Title (EN)",      "Tarifname Başlığı (EN)"],
    "description_title_tr":   ["Tarifname Başlığı",                  "description_title_tr",        "Description Title (TR)"],
    "source_file":            ["File Name",                          "source_file",                 "file_name"],
    "location_ref":           ["Konum",                              "location_ref",                "Location"],
}

# The three columns the ingestion service may build collections from.
TARGET_CANONICAL_KEYS = ["definition_en", "description_title_en", "all_elements_context_en"]


def _resolve_columns(df_columns: list[str]) -> dict[str, str]:
    """
    Build a mapping { canonical_key: actual_column_name } for every
    canonical key whose candidate header appears in the dataframe.

    Comparison is case-insensitive and strips surrounding whitespace.
    """
    normalised = {c.strip().lower(): c for c in df_columns}
    resolved: dict[str, str] = {}
    for canonical, candidates in COLUMN_ALIASES.items():
        for candidate in candidates:
            if candidate.strip().lower() in normalised:
                resolved[canonical] = normalised[candidate.strip().lower()]
                break
    return resolved


def _is_valid_text(value) -> bool:
    """Return True only for non-null, non-empty, non-'nan' strings."""
    if value is None:
        return False
    s = str(value).strip()
    return bool(s) and s.lower() != "nan"


def parse_excel(file_bytes: bytes) -> tuple[list[dict], set[str]]:
    """
    Parse an Excel file and return:
      - rows: list of row dicts using canonical keys (only resolved
              columns are included; unresolved columns are absent)
      - found_targets: set of canonical target keys that were resolved
              (subset of TARGET_CANONICAL_KEYS)

    Raises ValueError if the bytes cannot be read as an Excel workbook.

    Does NOT enforce which target columns are mandatory — that is a
    business rule and belongs in the calling service.
    """
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    except Exception as exc:
        raise ValueError(f"Cannot read file as Excel workbook: {exc}") from exc

    col_map = _resolve_columns(list(df.columns))

    # Report which of the three target columns were found
    found_targets: set[str] = {
        key for key in TARGET_CANONICAL_KEYS if key in col_map
    }

    # Build canonical rows — only include keys that resolved
    rows: list[dict] = []
    for _, raw_row in df.iterrows():
        row: dict = {}
        for canonical, actual_col in col_map.items():
            val = raw_row.get(actual_col)
            row[canonical] = str(val).strip() if _is_valid_text(val) else None
        rows.append(row)

    return rows, found_targets
