#!/usr/bin/env python3
"""BBF + Arastirma Raporu unsur/iliski cikarma pipeline.

Bu script sadece BBF ve arastirma raporu belgelerinden unsur ve unsur iliskilerini
TR+EN bicimde cikarir; JSON ve Excel (.xlsx) ciktisi uretir.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape


# =============================================================================
# [SECTION 00] MODIFICATION GUIDE (HIZLI BASLANGIC)
# =============================================================================
# Bu dosya TEK DOSYA mimarisinde, modifiye kolayligi icin bolumlenmistir:
#   [SECTION 01] Quick Tunables
#   [SECTION 02] Sabitler / Regexler
#   [SECTION 03] Veri Modelleri
#   [SECTION 04] Yardimci Fonksiyonlar
#   [SECTION 05] XLSX Reader/Writer
#   [SECTION 06] Document Loader
#   [SECTION 07] Section Extractor
#   [SECTION 08] Rule Extractor
#   [SECTION 09] Relation Cue Library
#   [SECTION 10] LLM Clients/Extractors
#   [SECTION 11] Merger
#   [SECTION 12] Output Writer
#   [SECTION 13] Pipeline
#   [SECTION 14] Batch Pairing
#   [SECTION 15] Factory + CLI
#
# En hizli modifiye noktasi: TunableSettings ve parse_args() defaultlari.
# =============================================================================


# =============================================================================
# [SECTION 01] QUICK TUNABLES (MODIFIYE EDILEBILIR)
# =============================================================================


@dataclass
class TunableSettings:
    # PDF metni cok azsa OCR fallback tetik egi.
    pdf_low_density_threshold: int = 300

    # Unsur birlestirme egi (fuzzy dedup).
    dedup_threshold: float = 0.75

    # Iliski oznesi/nesnesi elemente map edilirken gereken minimum benzerlik.
    element_resolve_threshold: float = 0.65

    # Rule-based unsur confidence degerleri.
    rule_unsur_confidence: float = 0.82
    rule_bullet_confidence: float = 0.72

    # Heuristic relation fallback ayarlari.
    enable_heuristic_relation_fallback: bool = True
    heuristic_relation_confidence: float = 0.35

    # LLM relation extraction'da en fazla aday cumle sayisi.
    max_relation_candidates: int = 200

    # LLM confidence bilgisi yoksa uygulanacak varsayilan.
    llm_default_confidence: float = 0.78

    # Unsur adini kisa tutmak icin maksimum kelime.
    max_component_words: int = 3


# ---------------------------------------------------------------------------
# [SECTION 02] Constants
# ---------------------------------------------------------------------------

DEFAULT_CUE_XLSX = (
    Path(__file__).resolve().parent
    / "excels"
    / "Konum Form Fonksiyon İfadeleri.xlsx"
)

FALLBACK_RELATION_CUES = [
    "uzerinde yer alan",
    "ile bagli",
    "baglanan",
    "arasinda",
    "dogrultusu ile uzanan",
    "donebilir sekilde",
    "cikarilabilir",
    "allowing",
    "connected",
    "coupled",
    "located on",
    "extending",
]

BBF_FILE_PATTERNS: Sequence[Tuple[str, int]] = (
    (r"bbf", 5),
    (r"fm\.?str\.?0024", 5),
    (r"bulus\s*bildirim", 4),
    (r"fm\.str", 3),
)

REPORT_FILE_PATTERNS: Sequence[Tuple[str, int]] = (
    (r"arastirma\s*raporu", 6),
    (r"araştırma\s*raporu", 6),
    (r"rapor", 3),
)


# ---------------------------------------------------------------------------
# [SECTION 03] Data Models
# ---------------------------------------------------------------------------


@dataclass
class LoadedDocument:
    text: str
    ocr_used: bool


@dataclass
class RawElement:
    source: str
    name_tr: str
    definition_tr: str
    name_en: str = ""
    definition_en: str = ""
    aliases_tr: List[str] = field(default_factory=list)
    evidence: List[Dict[str, str]] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class MergedElement:
    element_id: str
    name_tr: str
    name_en: str
    definition_tr: str
    definition_en: str
    aliases_tr: List[str]
    evidence: List[Dict[str, str]]
    confidence: float


@dataclass
class RawRelation:
    source: str
    subject_name_tr: str
    object_name_tr: str
    relation_sentence_tr: str
    relation_sentence_en: str
    evidence_text_tr: str
    confidence: float = 0.0


@dataclass
class MergedRelation:
    relation_id: str
    subject_element_id: str
    object_element_id: str
    relation_sentence_tr: str
    relation_sentence_en: str
    evidence: Dict[str, str]
    confidence: float


# ---------------------------------------------------------------------------
# [SECTION 04] Helpers
# ---------------------------------------------------------------------------


def debug_print(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[DEBUG] {message}")


def normalize_for_match(text: str) -> str:
    text = text or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9çğıöşü\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def sentence_split(text: str) -> List[str]:
    normalized = text.replace("\r", "\n")
    parts = re.split(r"(?<=[\.!?])\s+|\n+", normalized)
    return [p.strip() for p in parts if p.strip()]


def text_similarity(a: str, b: str) -> float:
    a_n = normalize_for_match(a)
    b_n = normalize_for_match(b)
    if not a_n or not b_n:
        return 0.0

    a_tokens = set(a_n.split())
    b_tokens = set(b_n.split())
    if not a_tokens or not b_tokens:
        return 0.0

    inter = a_tokens & b_tokens
    union = a_tokens | b_tokens
    jaccard = len(inter) / max(1, len(union))

    seq = SequenceMatcher(None, a_n, b_n).ratio()

    tok_a = " ".join(sorted(a_tokens))
    tok_b = " ".join(sorted(b_tokens))
    token_ratio = SequenceMatcher(None, tok_a, tok_b).ratio()

    return (0.4 * jaccard) + (0.3 * seq) + (0.3 * token_ratio)


def infer_project_id(*paths: Path) -> str:
    pattern = re.compile(r"(P\d{3,4})", re.IGNORECASE)
    for path in paths:
        text = str(path)
        m = pattern.search(text)
        if m:
            return m.group(1).upper()
    stem = paths[0].stem if paths else "project"
    stem = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_")
    return stem or "project"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r", "\n")

    # Remove figure captions and noisy repeated labels.
    text = re.sub(r"^\s*Şekil\s*\d+\s*[:\-].*$", " ", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"\(\s*Şekil\s*\d+\s*\)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*•\s*", "\n• ", text)

    # Collapse whitespace but preserve sentence boundaries.
    text = re.sub(r"[\t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    text = text.strip()
    return text


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def extract_evidence_text(raw_value: Any) -> str:
    if isinstance(raw_value, str):
        return raw_value.strip()
    if isinstance(raw_value, list):
        parts = []
        for item in raw_value:
            if isinstance(item, str):
                parts.append(item.strip())
            elif isinstance(item, dict):
                parts.append(str(item.get("text_tr", "")).strip())
        return " ".join(p for p in parts if p)
    if isinstance(raw_value, dict):
        return str(raw_value.get("text_tr", "")).strip()
    return str(raw_value).strip() if raw_value else ""


def parse_json_fragment(text: str) -> Any:
    if not text:
        raise ValueError("Empty JSON response")

    # Direct parse first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try fenced JSON.
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        return json.loads(fence.group(1))

    # Try first array/object fragment.
    for open_char, close_char in (("[", "]"), ("{", "}")):
        start = text.find(open_char)
        end = text.rfind(close_char)
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    raise ValueError("Could not parse JSON from response")


# ---------------------------------------------------------------------------
# [SECTION 05] Minimal XLSX Reader/Writer (stdlib only)
# ---------------------------------------------------------------------------


XLSX_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XLSX_NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _xlsx_col_to_index(col: str) -> int:
    n = 0
    for c in col:
        if c.isalpha():
            n = n * 26 + (ord(c.upper()) - 64)
    return n - 1


def _xlsx_index_to_col(idx: int) -> str:
    idx += 1
    out = []
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        out.append(chr(65 + rem))
    return "".join(reversed(out))


def read_xlsx_values(path: Path, sheet_name_filters: Optional[Sequence[str]] = None) -> Dict[str, List[List[str]]]:
    result: Dict[str, List[List[str]]] = {}

    with zipfile.ZipFile(path) as zf:
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            ns = {"a": XLSX_NS_MAIN}
            for si in root.findall("a:si", ns):
                text = "".join(t.text or "" for t in si.findall(".//a:t", ns))
                shared_strings.append(text)

        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
        }

        ns = {"a": XLSX_NS_MAIN, "r": XLSX_NS_REL}
        for sheet in wb.findall("a:sheets/a:sheet", ns):
            name = sheet.attrib.get("name", "Sheet")
            if sheet_name_filters:
                lowered = name.lower()
                if not any(token.lower() in lowered for token in sheet_name_filters):
                    continue

            rel_id = sheet.attrib.get(f"{{{XLSX_NS_REL}}}id")
            if not rel_id or rel_id not in rel_map:
                continue

            target = rel_map[rel_id]
            if target.startswith("/"):
                target = target[1:]
            if not target.startswith("xl/"):
                target = f"xl/{target}"

            rows: List[List[str]] = []
            sheet_root = ET.fromstring(zf.read(target))
            for row in sheet_root.findall("a:sheetData/a:row", ns):
                vals: Dict[int, str] = {}
                for cell in row.findall("a:c", ns):
                    ref = cell.attrib.get("r", "")
                    m = re.match(r"([A-Z]+)", ref)
                    if not m:
                        continue
                    idx = _xlsx_col_to_index(m.group(1))
                    typ = cell.attrib.get("t")
                    value = ""
                    if typ == "s":
                        v = cell.find("a:v", ns)
                        if v is not None and v.text:
                            pos = int(v.text)
                            if 0 <= pos < len(shared_strings):
                                value = shared_strings[pos]
                    elif typ == "inlineStr":
                        t = cell.find("a:is/a:t", ns)
                        value = t.text if t is not None and t.text else ""
                    else:
                        v = cell.find("a:v", ns)
                        value = v.text if v is not None and v.text else ""
                    vals[idx] = value

                if vals:
                    max_idx = max(vals)
                    row_arr = [""] * (max_idx + 1)
                    for i, v in vals.items():
                        row_arr[i] = v
                    rows.append(row_arr)

            result[name] = rows

    return result


class SimpleXlsxWriter:
    """Very small XLSX writer with inline strings, no third-party dependency."""

    @staticmethod
    def write(path: Path, sheets: Dict[str, List[List[Any]]]) -> None:
        sheet_items = list(sheets.items())
        if not sheet_items:
            raise ValueError("No sheets provided for xlsx writing")

        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", SimpleXlsxWriter._content_types_xml(len(sheet_items)))
            zf.writestr("_rels/.rels", SimpleXlsxWriter._root_rels_xml())
            zf.writestr("xl/workbook.xml", SimpleXlsxWriter._workbook_xml([name for name, _ in sheet_items]))
            zf.writestr("xl/_rels/workbook.xml.rels", SimpleXlsxWriter._workbook_rels_xml(len(sheet_items)))

            for i, (_, rows) in enumerate(sheet_items, start=1):
                zf.writestr(f"xl/worksheets/sheet{i}.xml", SimpleXlsxWriter._sheet_xml(rows))

    @staticmethod
    def _content_types_xml(sheet_count: int) -> str:
        parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
            '<Default Extension="xml" ContentType="application/xml"/>',
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        ]
        for i in range(1, sheet_count + 1):
            parts.append(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            )
        parts.append("</Types>")
        return "".join(parts)

    @staticmethod
    def _root_rels_xml() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            "</Relationships>"
        )

    @staticmethod
    def _workbook_xml(sheet_names: Sequence[str]) -> str:
        parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
            "<sheets>",
        ]
        for i, name in enumerate(sheet_names, start=1):
            safe_name = xml_escape(name)[:31]
            parts.append(f'<sheet name="{safe_name}" sheetId="{i}" r:id="rId{i}"/>')
        parts.extend(["</sheets>", "</workbook>"])
        return "".join(parts)

    @staticmethod
    def _workbook_rels_xml(sheet_count: int) -> str:
        parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
        ]
        for i in range(1, sheet_count + 1):
            parts.append(
                f'<Relationship Id="rId{i}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/sheet{i}.xml"/>'
            )
        parts.append("</Relationships>")
        return "".join(parts)

    @staticmethod
    def _sheet_xml(rows: List[List[Any]]) -> str:
        lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
            "<sheetData>",
        ]

        for r_idx, row in enumerate(rows, start=1):
            lines.append(f'<row r="{r_idx}">')
            for c_idx, value in enumerate(row, start=1):
                if value is None:
                    continue
                cell_ref = f"{_xlsx_index_to_col(c_idx - 1)}{r_idx}"
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    lines.append(f'<c r="{cell_ref}"><v>{value}</v></c>')
                else:
                    txt = xml_escape(str(value))
                    lines.append(
                        f'<c r="{cell_ref}" t="inlineStr"><is><t>{txt}</t></is></c>'
                    )
            lines.append("</row>")

        lines.extend(["</sheetData>", "</worksheet>"])
        return "".join(lines)


# ---------------------------------------------------------------------------
# [SECTION 06] Document Loading
# ---------------------------------------------------------------------------


class DocumentLoader:
    def __init__(
        self,
        disable_ocr: bool = False,
        debug: bool = False,
        pdf_low_density_threshold: int = 300,
    ):
        self.disable_ocr = disable_ocr
        self.debug = debug
        self.pdf_low_density_threshold = pdf_low_density_threshold

    def load(self, path: Path) -> LoadedDocument:
        suffix = path.suffix.lower()

        if suffix == ".docx":
            text = self._extract_docx_text(path)
            return LoadedDocument(text=text, ocr_used=False)

        if suffix == ".pdf":
            text = self._extract_pdf_text(path)
            low_density = self._is_low_density(text, threshold=self.pdf_low_density_threshold)
            if low_density and not self.disable_ocr:
                debug_print(self.debug, f"Low-density PDF detected, OCR fallback: {path}")
                text = self._ocr_pdf(path)
                return LoadedDocument(text=text, ocr_used=True)
            return LoadedDocument(text=text, ocr_used=False)

        if suffix in {".txt", ".md"}:
            return LoadedDocument(text=path.read_text(encoding="utf-8", errors="ignore"), ocr_used=False)

        raise ValueError(f"Unsupported document type: {path}")

    def _extract_docx_text(self, path: Path) -> str:
        with zipfile.ZipFile(path) as zf:
            xml_bytes = zf.read("word/document.xml")

        root = ET.fromstring(xml_bytes)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        chunks = []
        for para in root.findall(".//w:p", ns):
            texts = [t.text or "" for t in para.findall(".//w:t", ns)]
            line = "".join(texts).strip()
            if line:
                chunks.append(line)
        return "\n".join(chunks)

    def _extract_pdf_text(self, path: Path) -> str:
        text = ""

        # 1) pypdf optional.
        try:
            import pypdf  # type: ignore

            reader = pypdf.PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages)
            if text.strip():
                return text
        except Exception:
            pass

        # 2) pdftotext optional command.
        if self._command_exists("pdftotext"):
            try:
                completed = subprocess.run(
                    ["pdftotext", str(path), "-"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                text = completed.stdout
                if text.strip():
                    return text
            except Exception:
                pass

        # 3) macOS textutil fallback.
        if self._command_exists("textutil"):
            try:
                completed = subprocess.run(
                    ["textutil", "-convert", "txt", "-stdout", str(path)],
                    check=True,
                    capture_output=True,
                    text=True,
                    errors="ignore",
                )
                text = completed.stdout
                if text.strip():
                    return text
            except Exception:
                pass

        return text

    def _ocr_pdf(self, path: Path) -> str:
        has_tesseract = self._command_exists("tesseract")
        has_pdftoppm = self._command_exists("pdftoppm")

        if not has_tesseract or not has_pdftoppm:
            missing = []
            if not has_pdftoppm:
                missing.append("pdftoppm")
            if not has_tesseract:
                missing.append("tesseract")
            raise RuntimeError(
                "OCR fallback requested but missing dependencies: "
                + ", ".join(missing)
                + ". Install poppler + tesseract or run with --disable-ocr."
            )

        with tempfile.TemporaryDirectory(prefix="bbf_pdf_ocr_") as td:
            prefix = Path(td) / "page"
            subprocess.run(
                ["pdftoppm", "-png", str(path), str(prefix)],
                check=True,
                capture_output=True,
                text=True,
            )

            images = sorted(Path(td).glob("page-*.png"))
            if not images:
                return ""

            out_chunks: List[str] = []
            for image in images:
                # Try TR+EN, fallback EN.
                cmd = ["tesseract", str(image), "stdout", "-l", "tur+eng"]
                completed = subprocess.run(cmd, capture_output=True, text=True)
                if completed.returncode != 0:
                    completed = subprocess.run(
                        ["tesseract", str(image), "stdout", "-l", "eng"],
                        capture_output=True,
                        text=True,
                    )
                out_chunks.append(completed.stdout or "")

            return "\n".join(out_chunks)

    @staticmethod
    def _is_low_density(text: str, threshold: int = 300) -> bool:
        letters = len(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]", text or ""))
        return letters < threshold

    @staticmethod
    def _command_exists(cmd: str) -> bool:
        from shutil import which

        return which(cmd) is not None


# ---------------------------------------------------------------------------
# [SECTION 07] Section Extraction
# ---------------------------------------------------------------------------


class SectionExtractor:
    def __init__(self, debug: bool = False):
        self.debug = debug

    def extract(self, text: str, doc_type: str) -> Dict[str, str]:
        text = clean_text(text)
        sections = {
            "background": "",
            "elements": "",
            "summary": "",
            "raw": text,
        }

        if doc_type == "bbf":
            sections["background"] = self._slice_between(
                text,
                start_patterns=[
                    r"tekniğin\s+bilinen\s+durumunu",
                    r"teknigin\s+bilinen\s+durumunu",
                ],
                end_patterns=[
                    r"tekniğin\s+bilinen\s+durumunda\s+yer\s+alan",
                    r"buluşunuzun,\s*tekniğin\s*bilenen\s*durumundan\s*farklı\s*olan\s*unsurlar",
                    r"buluşunuzun,\s*tekniğin\s*bilinen\s*durumundan\s*farklı\s*olan\s*unsurlar",
                ],
            )
            sections["elements"] = self._slice_between(
                text,
                start_patterns=[
                    r"buluşunuzun,\s*tekniğin\s*bilenen\s*durumundan\s*farklı\s*olan\s*unsurlar",
                    r"buluşunuzun,\s*tekniğin\s*bilinen\s*durumundan\s*farklı\s*olan\s*unsurlar",
                ],
                end_patterns=[
                    r"buluşunuza\s*ait\s*fotoğraf",
                    r"başlıklı\s*buluşun\s*sahibi",
                    r"buluş\s*sahibinin",
                ],
            )
        elif doc_type == "report":
            sections["summary"] = self._slice_between(
                text,
                start_patterns=[r"yönetici\s+özeti", r"yonetici\s+ozeti"],
                end_patterns=[r"amaç", r"amac"],
            )
            sections["elements"] = self._slice_between(
                text,
                start_patterns=[r"buluşta\s+yer\s+alan\s+unsurlar\s+aşağıdaki\s+gibidir"],
                end_patterns=[
                    r"amaç",
                    r"anahtar\s+kelimeler",
                    r"sınıflandırma",
                    r"buluşta\s+yer\s+alan\s+unsurların\s+mevcut\s+patentler",
                ],
            )

        for key in ("background", "elements", "summary"):
            sections[key] = clean_text(sections[key])
        debug_print(self.debug, f"{doc_type} sections extracted: { {k: len(v) for k, v in sections.items()} }")
        return sections

    def _slice_between(self, text: str, start_patterns: Sequence[str], end_patterns: Sequence[str]) -> str:
        lowered = text.lower()

        start_idx = None
        for pat in start_patterns:
            m = re.search(pat, lowered, flags=re.IGNORECASE)
            if m and (start_idx is None or m.start() < start_idx):
                start_idx = m.end()

        if start_idx is None:
            return ""

        rest = lowered[start_idx:]
        end_abs = len(text)
        for pat in end_patterns:
            m = re.search(pat, rest, flags=re.IGNORECASE)
            if m:
                end_abs = min(end_abs, start_idx + m.start())

        return text[start_idx:end_abs].strip()


# ---------------------------------------------------------------------------
# [SECTION 08] Rule-based Extraction
# ---------------------------------------------------------------------------


class RuleExtractor:
    def __init__(
        self,
        debug: bool = False,
        unsur_confidence: float = 0.55,
        bullet_confidence: float = 0.45,
        max_component_words: int = 3,
    ):
        self.debug = debug
        self.unsur_confidence = unsur_confidence
        self.bullet_confidence = bullet_confidence
        self.max_component_words = max_component_words

    def extract_elements(self, section_text: str, source: str) -> List[RawElement]:
        candidates: List[RawElement] = []

        unsur_blocks = self._extract_unsur_blocks(section_text)
        for no, definition in unsur_blocks:
            extracted_terms = self._extract_component_terms(definition)
            if extracted_terms:
                for term in extracted_terms:
                    evidence_sentence = self._pick_evidence_sentence(definition, term) or definition
                    candidates.append(
                        RawElement(
                            source=source,
                            name_tr=term,
                            definition_tr=evidence_sentence,
                            aliases_tr=[f"Unsur {no}", term],
                            evidence=[{"source": source, "text_tr": evidence_sentence}],
                            confidence=self.unsur_confidence,
                        )
                    )
            else:
                name_guess = self._guess_name_from_definition(definition, fallback=f"Unsur {no}")
                candidates.append(
                    RawElement(
                        source=source,
                        name_tr=name_guess,
                        definition_tr=definition,
                        aliases_tr=[f"Unsur {no}", name_guess],
                        evidence=[{"source": source, "text_tr": definition}],
                        confidence=self.unsur_confidence,
                    )
                )

        if not candidates:
            bullets = self._extract_bullet_elements(section_text)
            for idx, bullet in enumerate(bullets, start=1):
                extracted_terms = self._extract_component_terms(bullet)
                if extracted_terms:
                    for term in extracted_terms:
                        evidence_sentence = self._pick_evidence_sentence(bullet, term) or bullet
                        candidates.append(
                            RawElement(
                                source=source,
                                name_tr=term,
                                definition_tr=evidence_sentence,
                                aliases_tr=[f"Unsur {idx}", term],
                                evidence=[{"source": source, "text_tr": evidence_sentence}],
                                confidence=self.bullet_confidence,
                            )
                        )
                else:
                    name_guess = self._guess_name_from_definition(bullet, fallback=f"Unsur {idx}")
                    candidates.append(
                        RawElement(
                            source=source,
                            name_tr=name_guess,
                            definition_tr=bullet,
                            aliases_tr=[name_guess],
                            evidence=[{"source": source, "text_tr": bullet}],
                            confidence=self.bullet_confidence,
                        )
                    )

        # Son fallback: tum section text'ten kisa bilesen terimleri cek.
        if not candidates:
            global_terms = self._extract_component_terms(section_text)
            for idx, term in enumerate(global_terms, start=1):
                evidence_sentence = self._pick_evidence_sentence(section_text, term) or section_text[:220]
                candidates.append(
                    RawElement(
                        source=source,
                        name_tr=term,
                        definition_tr=evidence_sentence,
                        aliases_tr=[f"Unsur {idx}", term],
                        evidence=[{"source": source, "text_tr": evidence_sentence}],
                        confidence=self.bullet_confidence,
                    )
                )

        cleaned: List[RawElement] = []
        for c in candidates:
            if len(c.name_tr.split()) > 5:
                c.name_tr = " ".join(c.name_tr.split()[:4])
            if len(c.definition_tr) > 300:
                c.definition_tr = c.definition_tr[:300].rsplit(" ", 1)[0] + "..."
            cleaned.append(c)

        cleaned = self._dedup_candidates(cleaned)
        debug_print(self.debug, f"Rule extracted {len(cleaned)} elements from {source}")
        return cleaned

    @staticmethod
    def _extract_unsur_blocks(text: str) -> List[Tuple[int, str]]:
        normalized = text.replace("\r", "\n")
        pattern = re.compile(
            r"(?:^|\n)\s*(?:Unsur|UNSUR|Element)\s*(\d+)\s*[\-–:.]\s*(.*?)"
            r"(?=(?:\n\s*(?:Unsur|UNSUR|Element)\s*\d+\s*[\-–:.])|$)",
            flags=re.IGNORECASE | re.DOTALL,
        )
        out: List[Tuple[int, str]] = []
        for m in pattern.finditer(normalized):
            no = int(m.group(1))
            block = clean_text(m.group(2))
            if block:
                out.append((no, block))
        return out

    @staticmethod
    def _extract_bullet_elements(text: str) -> List[str]:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        bullets = []
        for ln in lines:
            if re.match(r"^[•\-]\s+", ln):
                val = re.sub(r"^[•\-]\s+", "", ln).strip()
                if len(val) > 10:
                    bullets.append(val)
        # Inline bullet fallback: "• A ... • B ..."
        if not bullets and "•" in text:
            for match in re.finditer(r"•\s*(.*?)(?=\s*•|$)", text, flags=re.DOTALL):
                val = clean_text(match.group(1))
                if len(val) > 10:
                    bullets.append(val)
        return bullets

    @staticmethod
    def _guess_name_from_definition(definition: str, fallback: str) -> str:
        text = definition.strip().strip(".")
        text = re.sub(r"^en\s+az\s+bir\s+", "", text, flags=re.IGNORECASE)
        parts = re.split(
            r"[,;]|\s+ile\s+|\s+olan\s+|\s+içeren\s+|\s+iceren\s+|\s+kullanımı\s+|\s+sayesinde\s+",
            text, maxsplit=1, flags=re.IGNORECASE,
        )
        candidate = parts[0].strip(" -") if parts else ""

        words = candidate.split()
        if len(words) > 4:
            candidate = " ".join(words[:4])

        if len(candidate) < 3:
            return fallback
        return candidate

    def _extract_component_terms(self, text: str) -> List[str]:
        terms: List[str] = []
        head_pattern = (
            r"(kanat|kuyruk|fitting|cıvata|civata|delik|plaka|parça|parca|montaj|"
            r"kutu|kutus|bağlant|baglant|gövde|govde|şaft|saft|kanal|stabiliz|"
            r"merkez|sistem|mekanizma|bolt|hole|wing|tail|box|assembly|bracket|clevis|rod|lug|"
            r"ayna|mirror|lens|mercek|sensör|sensor|modül|module|düzlem|plane|"
            r"optik|optic|detektor|detector|filtre|filter|prizma|prism|"
            r"motor|pompa|valf|valve|piston|silindir|cylinder|"
            r"kamera|camera|anten|antenna|devre|circuit|kart|board|"
            r"yatak|bearing|mil|shaft|dişli|gear|kayış|belt|kapak|cover|"
            r"çerçeve|frame|gövde|body|taban|base|platform|"
            r"boru|pipe|tube|hortum|hose|conta|gasket|seal|"
            r"yay|spring|amortisör|damper|tampon|buffer|"
            r"ekran|screen|display|panel|düğme|button|"
            r"rotor|stator|türbin|turbine|jeneratör|generator|"
            r"aparat|apparatus|fikstür|fixture|tutucu|holder|gripper)\w*"
        )

        # 1) Ref-id parantezli yapilar: "arka fitting (4)"
        for m in re.finditer(
            r"([A-Za-zÇĞİÖŞÜçğıöşü0-9][A-Za-zÇĞİÖŞÜçğıöşü0-9\- ]{1,60})\s*\(([A-Za-z0-9]+)\)",
            text,
        ):
            raw = m.group(1).strip()
            norm = self._compress_component_term(raw)
            if norm:
                terms.append(norm)

        # 2) Teknik bas-kelime odakli phrase yakalama.
        for m in re.finditer(
            rf"\b((?:[A-Za-zÇĞİÖŞÜçğıöşü]+\s+){{0,2}}{head_pattern})\b",
            text,
            flags=re.IGNORECASE,
        ):
            raw = m.group(1)
            norm = self._compress_component_term(raw)
            if norm:
                terms.append(norm)

        # 3) Domain patternleri (baglanti vb. ikili yapilar)
        for m in re.finditer(
            r"\b([A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-Za-zÇĞİÖŞÜçğıöşü]+){0,3})\s+"
            r"(bağlantısı|baglantisi|fitting|parça|parcasi|montaj|kanat|kuyruk|cıvata|civata|delik|plaka|şaft|saft)\b",
            text,
            flags=re.IGNORECASE,
        ):
            raw = f"{m.group(1)} {m.group(2)}"
            norm = self._compress_component_term(raw)
            if norm:
                terms.append(norm)

        # Dedup + kalite filtresi.
        out: List[str] = []
        seen = set()
        for t in terms:
            n = normalize_for_match(t)
            if not n:
                continue
            # Asiri genel veya tek harf benzeri adaylari ele.
            if len(n) < 3:
                continue
            if n in {"bulus", "unsur", "tasarim", "cozum", "problem"}:
                continue
            if n in seen:
                continue
            seen.add(n)
            out.append(t)
        return out

    def _compress_component_term(self, text: str) -> str:
        t = text.strip()
        if not t:
            return ""

        t = re.sub(r"\([^)]*\)", " ", t)
        t = re.sub(r"[^\wçğıöşüÇĞİÖŞÜ\- ]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        if not t:
            return ""

        # Soldan gereksiz giris kaliplari.
        t = re.sub(
            r"^(en az\s+)?(bir|iki|üç|uc|dört|dort|beş|bes|birinci|ikinci|üçüncü|ucuncu)\s+",
            "",
            t,
            flags=re.IGNORECASE,
        ).strip()

        stop_tokens = {
            "ile", "ve", "veya", "olan", "olarak", "icin", "için", "uzerinde", "üzerinde",
            "altinda", "altında", "ustunde", "üstünde", "yer", "alan", "bagli", "bağlı",
            "sekilde", "şekilde", "sayesinde", "vasitasiyla", "vasıtasıyla", "dogru", "doğru",
            "boyunca", "gibi", "ayni", "aynı", "kendi", "etrafinda", "etrafında", "olacak",
            "olanak", "saglayan", "sağlayan", "edilen", "tasarlanan", "tasarlanmis", "tasarlanmış",
            "olusan", "oluşan", "uygun", "ozel", "özel", "minimum", "maksimum", "kademeli",
            "olusmalidir", "oluşmalıdır", "baglanmaktadir", "bağlanmaktadır", "tasarlanmistir",
            "tasarlanmıştır", "donmektedir", "dönmektedir", "vermektedir", "kullanilacak",
            "kullanılacak", "oldugu", "olduğu", "degil", "değil",
            "bulunan", "ortasinda", "ortasında", "ortada", "ondeki", "öndeki", "arkadaki",
            "altindaki", "altındaki", "ustundeki", "üstündeki", "tarayan", "sag", "sağ", "sol",
            "diger", "diğer", "her", "kadar", "minimum", "maksimum",
            "cozumu", "çözümü", "yapisi", "yapısı", "tarafındaki", "tarafindaki",
            "tarafin", "tarafın", "dondurulmesi", "döndürülmesi", "sistemin", "saglayabilmek",
            "tasarim", "tasarım", "sayida", "sayıda", "bulunun", "de", "da", "ortadaki",
        }

        # Bilesen basi olarak kabul edilen teknik kokler.
        head_roots = {
            "kanat", "kuyruk", "fitting", "civata", "cıvata", "delik", "plaka", "parca", "parça",
            "montaj", "kutu", "kutus", "baglanti", "bağlantı", "govde", "gövde", "şaft",
            "saft", "kanal", "stabilizor", "stabilizör", "merkez", "rod", "lug", "bolt", "hole",
            "bracket", "clevis", "wing", "tail", "box", "assembly", "sistem", "mekanizma",
            "ayna", "mirror", "lens", "mercek", "sensör", "sensor", "modül", "module",
            "düzlem", "plane", "optik", "optic", "detektor", "detector", "filtre", "filter",
            "prizma", "prism", "motor", "pompa", "valf", "valve", "piston", "silindir", "cylinder",
            "kamera", "camera", "anten", "antenna", "devre", "circuit", "kart", "board",
            "yatak", "bearing", "mil", "shaft", "dişli", "gear", "kayış", "belt", "kapak", "cover",
            "çerçeve", "frame", "taban", "base", "platform",
            "boru", "pipe", "tube", "hortum", "hose", "conta", "gasket", "seal",
            "yay", "spring", "amortisör", "damper", "tampon", "buffer",
            "ekran", "screen", "display", "panel", "düğme", "button",
            "rotor", "stator", "türbin", "turbine", "jeneratör", "generator",
            "aparat", "apparatus", "fikstür", "fixture", "tutucu", "holder", "gripper",
        }

        raw_tokens = [tok for tok in t.split() if tok]
        tokens: List[Tuple[str, str, str]] = []
        for tok in raw_tokens:
            low = normalize_for_match(tok)
            if not low:
                continue
            if low.isdigit():
                continue
            if low in stop_tokens:
                continue
            if self._looks_verb_like(low):
                continue
            stem = self._stem_token(low)
            tokens.append((tok, low, stem))

        if not tokens:
            return ""

        head_indexes = [i for i, (_tok, low, stem) in enumerate(tokens) if low in head_roots or stem in head_roots]
        if not head_indexes:
            return ""

        head_idx = head_indexes[-1]
        start = max(0, head_idx - (self.max_component_words - 1))
        selected_triplets = tokens[start : head_idx + 1]
        selected = [self._canonical_token(tok, low, stem) for tok, low, stem in selected_triplets]
        # Yan yana tekrar eden kelimeleri sadeleştir.
        compact: List[str] = []
        for tok in selected:
            if not compact or normalize_for_match(compact[-1]) != normalize_for_match(tok):
                compact.append(tok)
        selected = compact
        result = " ".join(selected).strip()

        # Son kalite kapisi: bas kelime filtreleri.
        first = normalize_for_match(result.split()[0]) if result else ""
        blocked_first = {"tasarim", "sayida", "yapisi", "bulunun", "acilar", "kanallari"}
        if first in blocked_first:
            return ""
        return result

    @staticmethod
    def _pick_evidence_sentence(definition: str, term: str) -> str:
        term_n = normalize_for_match(term)
        for s in sentence_split(definition):
            if term_n and term_n in normalize_for_match(s):
                return s.strip()
        return ""

    @staticmethod
    def _dedup_candidates(candidates: List[RawElement]) -> List[RawElement]:
        out: List[RawElement] = []
        seen = set()
        for c in candidates:
            key = (
                c.source,
                normalize_for_match(c.name_tr),
                normalize_for_match(c.definition_tr),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
        return out

    @staticmethod
    def _looks_verb_like(token: str) -> bool:
        suffixes = (
            "mektedir", "maktadır", "mistir", "mıştır", "mustur", "muştur",
            "maktadir", "iyor", "iyorlar", "acak", "ecek", "acaktir", "ecektir",
            "malidir", "melidir", "abilir", "ebilir", "mektedirler",
        )
        return any(token.endswith(sfx) for sfx in suffixes)

    @staticmethod
    def _stem_token(token: str) -> str:
        suffixes = (
            "lardan", "lerden", "larini", "lerini", "ları", "leri",
            "daki", "deki", "nin", "nın", "nun", "nün", "dan", "den", "tan", "ten",
            "in", "ın", "un", "ün",
        )
        out = token
        for sfx in suffixes:
            if len(out) > len(sfx) + 2 and out.endswith(sfx):
                out = out[: -len(sfx)]
                break
        return out

    @staticmethod
    def _canonical_token(original: str, low: str, stem: str) -> str:
        low_n = normalize_for_match(low)
        if low_n.startswith("civata") or low_n.startswith("cıvata"):
            return "cıvata"
        if low_n.startswith("baglant") or low_n.startswith("bağlant"):
            return "bağlantı"
        if low_n.startswith("parca") or low_n.startswith("parça"):
            return "parça"
        if low_n.startswith("govde") or low_n.startswith("gövde"):
            return "gövde"
        if low_n.startswith("stabiliz"):
            return "stabilizör"

        root_map = {
            "baglant": "bağlantı",
            "parc": "parça",
            "govd": "gövde",
            "civat": "cıvata",
            "kutus": "kutu",
            "stabiliz": "stabilizör",
        }
        if stem in root_map:
            return root_map[stem]
        return original


# ---------------------------------------------------------------------------
# [SECTION 09] Relation Cue Library
# ---------------------------------------------------------------------------


class RelationCueLibrary:
    def __init__(self, xlsx_path: Optional[Path] = None, debug: bool = False):
        self.xlsx_path = xlsx_path or DEFAULT_CUE_XLSX
        self.debug = debug
        self.cues = self._load_cues()

    def _load_cues(self) -> List[str]:
        cues: List[str] = []

        if self.xlsx_path.exists():
            try:
                data = read_xlsx_values(
                    self.xlsx_path,
                    sheet_name_filters=["konum", "form", "fonksiyon", "position", "function"],
                )
                for _sheet, rows in data.items():
                    for row in rows:
                        if not row:
                            continue
                        first = (row[0] or "").strip()
                        if not first:
                            continue
                        if any(token in normalize_for_match(first) for token in ("ifadeleri", "not", "degisken")):
                            continue
                        cues.append(first)
            except Exception as exc:
                debug_print(self.debug, f"Relation cue xlsx read failed: {exc}")

        if not cues:
            cues = list(FALLBACK_RELATION_CUES)

        normalized_unique = []
        seen = set()
        for cue in cues + list(FALLBACK_RELATION_CUES):
            cue_n = normalize_for_match(cue)
            if not cue_n or cue_n in seen:
                continue
            seen.add(cue_n)
            normalized_unique.append(cue)

        debug_print(self.debug, f"Loaded {len(normalized_unique)} relation cues")
        return normalized_unique

    def find_relation_sentences(self, text: str, element_names: Sequence[str]) -> List[str]:
        if not text:
            return []

        name_norm_pairs = [(name, normalize_for_match(name)) for name in element_names if name.strip()]
        sentences = sentence_split(text)
        out: List[str] = []

        for sentence in sentences:
            sentence_n = normalize_for_match(sentence)
            if len(sentence_n) < 12:
                continue

            cue_hit = any(normalize_for_match(cue) in sentence_n for cue in self.cues)
            if not cue_hit:
                continue

            present = 0
            for _, n in name_norm_pairs:
                if n and n in sentence_n:
                    present += 1
            if present >= 2:
                out.append(sentence.strip())

        # Deduplicate preserving order.
        seen = set()
        dedup = []
        for s in out:
            n = normalize_for_match(s)
            if n not in seen:
                seen.add(n)
                dedup.append(s)

        return dedup


# ---------------------------------------------------------------------------
# [SECTION 10] LLM Client/Extractor
# ---------------------------------------------------------------------------


def _translate_tr_to_en(text: str) -> str:
    """Translate Turkish text to English using deep_translator (Google Translate)."""
    if not text or not text.strip():
        return text
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="tr", target="en").translate(text)
    except Exception:
        return text


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.1,
        timeout: int = 120,
        debug: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.debug = debug

    def chat(self, messages: List[Dict[str, str]]) -> str:
        if not self.base_url:
            raise RuntimeError("LLM base URL is empty")
        if not self.model:
            raise RuntimeError("LLM model is empty")

        url = self.base_url
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"LLM HTTP error {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM connection error: {exc}") from exc

        try:
            return data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError(f"Unexpected LLM response format: {data}") from exc


class HeuristicLLMExtractor:
    """Fallback extractor used when no external LLM is configured."""

    def __init__(
        self,
        debug: bool = False,
        enable_relation_fallback: bool = True,
        fallback_relation_confidence: float = 0.35,
    ):
        self.debug = debug
        self.enable_relation_fallback = enable_relation_fallback
        self.fallback_relation_confidence = fallback_relation_confidence

    def enrich_elements(
        self,
        source: str,
        candidates: List[RawElement],
        context_text: str,
        max_chars_per_chunk: int,
    ) -> List[RawElement]:
        _ = (source, context_text, max_chars_per_chunk)
        out: List[RawElement] = []
        for cand in candidates:
            name_en = self._to_simple_english(cand.name_tr)
            def_en = self._to_simple_english(cand.definition_tr)
            out.append(
                RawElement(
                    source=cand.source,
                    name_tr=cand.name_tr,
                    definition_tr=cand.definition_tr,
                    name_en=name_en,
                    definition_en=def_en,
                    aliases_tr=list(dict.fromkeys(cand.aliases_tr + [cand.name_tr])),
                    evidence=cand.evidence,
                    confidence=max(cand.confidence, 0.5),
                )
            )
        return out

    def extract_relations(
        self,
        source: str,
        elements: List[MergedElement],
        candidate_sentences: List[str],
        max_chars_per_chunk: int,
    ) -> List[RawRelation]:
        _ = (source, max_chars_per_chunk)
        names = [e.name_tr for e in elements]
        out: List[RawRelation] = []

        for sent in candidate_sentences:
            sent_n = normalize_for_match(sent)
            hits = [name for name in names if normalize_for_match(name) in sent_n]
            if len(hits) < 2:
                continue

            subj, obj = hits[0], hits[1]
            out.append(
                RawRelation(
                    source=source,
                    subject_name_tr=subj,
                    object_name_tr=obj,
                    relation_sentence_tr=sent,
                    relation_sentence_en=self._to_simple_english(sent),
                    evidence_text_tr=sent,
                    confidence=0.45,
                )
            )

        # Fallback: if sentence matching could not map two elements, create
        # conservative sequential relations so downstream workflow stays usable.
        if self.enable_relation_fallback and not out and len(elements) >= 2:
            fallback_sentences = candidate_sentences or [e.definition_tr for e in elements]
            for idx in range(len(elements) - 1):
                sentence = fallback_sentences[idx % len(fallback_sentences)] if fallback_sentences else ""
                if not sentence:
                    sentence = f"{elements[idx].name_tr} ile {elements[idx+1].name_tr} bağlantılıdır."
                out.append(
                    RawRelation(
                        source=source,
                        subject_name_tr=elements[idx].name_tr,
                        object_name_tr=elements[idx + 1].name_tr,
                        relation_sentence_tr=sentence,
                        relation_sentence_en=self._to_simple_english(sentence),
                        evidence_text_tr=sentence,
                        confidence=self.fallback_relation_confidence,
                    )
                )

        return out

    @staticmethod
    def _to_simple_english(text: str) -> str:
        return _translate_tr_to_en(text)


class LLMExtractor:
    def __init__(
        self,
        client: OpenAICompatibleClient,
        debug: bool = False,
        max_relation_candidates: int = 200,
        default_confidence: float = 0.78,
    ):
        self.client = client
        self.debug = debug
        self.max_relation_candidates = max_relation_candidates
        self.default_confidence = default_confidence

    def enrich_elements(
        self,
        source: str,
        candidates: List[RawElement],
        context_text: str,
        max_chars_per_chunk: int,
    ) -> List[RawElement]:
        context = context_text[:max_chars_per_chunk]
        payload_candidates = [
            {
                "name_tr": c.name_tr,
                "definition_tr": c.definition_tr,
                "aliases_tr": c.aliases_tr,
            }
            for c in candidates
        ]

        system_prompt = (
            "Sen bir patent unsur çıkarma modelisin.\n\n"
            "Patent unsuru (element), bir buluşu oluşturan FİZİKSEL BİLEŞEN veya ALT SİSTEMDİR.\n"
            "Unsur adı KISA olmalı: 1-4 kelime. Örnekler:\n"
            "  - \"optik sistem\", \"birinci ayna\", \"ikinci ayna\", \"ara görüntü düzlemi\"\n"
            "  - \"açılır kanat\", \"arka fitting\", \"bağlantı parçası\", \"montaj plakası\"\n"
            "  - \"dalga boyu ayırıcı\", \"zoom mekanizması\", \"sensör modülü\"\n\n"
            "Unsur adı ASLA cümle veya fiil içermemeli. Sadece isim tamlaması olmalı.\n"
            "Her unsur için ayrıca 1-2 cümlelik tanım (definition) yaz.\n\n"
            "Kurallar:\n"
            "- Sana verilen aday listesini düzelt ve iyileştir.\n"
            "- Aday adı çok uzunsa veya cümle gibiyse, kısalt.\n"
            "- Aday adı yanlışsa veya unsur değilse (ör. genel kavram, eylem), listeden çıkar.\n"
            "- Bağlamda (context) bulunan ama aday listesinde olmayan unsurları da ekle.\n"
            "- TR ve EN alanları doldur.\n\n"
            "SADECE geçerli JSON array döndür. Markdown kullanma."
        )

        user_content = json.dumps({
            "candidates": payload_candidates,
            "context_tr": context,
            "output_fields": [
                "name_tr", "name_en", "definition_tr", "definition_en",
                "aliases_tr", "evidence_tr", "confidence",
            ],
        }, ensure_ascii=False)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        response = self.client.chat(messages)
        parsed = parse_json_fragment(response)
        if not isinstance(parsed, list):
            raise ValueError("Element LLM output must be a JSON array")

        out: List[RawElement] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            name_tr = str(item.get("name_tr", "")).strip()
            definition_tr = str(item.get("definition_tr", "")).strip()
            if not name_tr or not definition_tr:
                continue
            evidence_tr = extract_evidence_text(item.get("evidence_tr"))
            if not evidence_tr:
                evidence_tr = definition_tr
            out.append(
                RawElement(
                    source=source,
                    name_tr=name_tr,
                    definition_tr=definition_tr,
                    name_en=str(item.get("name_en", "")).strip(),
                    definition_en=str(item.get("definition_en", "")).strip(),
                    aliases_tr=[str(a).strip() for a in (item.get("aliases_tr") or []) if str(a).strip()],
                    evidence=[{"source": source, "text_tr": evidence_tr}],
                    confidence=max(0.0, min(1.0, safe_float(item.get("confidence"), self.default_confidence))),
                )
            )

        return out

    def extract_elements_from_text(
        self,
        source: str,
        text: str,
        max_chars_per_chunk: int,
    ) -> List[RawElement]:
        context = text[:max_chars_per_chunk]

        system_prompt = (
            "Sen bir patent unsur çıkarma modelisin.\n\n"
            "Patent unsuru (element), bir buluşu oluşturan FİZİKSEL BİLEŞEN veya ALT SİSTEMDİR.\n"
            "Unsur adı KISA olmalı: 1-4 kelime. Örnekler:\n"
            "  - \"optik sistem\", \"birinci ayna\", \"ikinci ayna\", \"ara görüntü düzlemi\"\n"
            "  - \"açılır kanat\", \"arka fitting\", \"bağlantı parçası\", \"montaj plakası\"\n"
            "  - \"dalga boyu ayırıcı\", \"zoom mekanizması\", \"sensör modülü\"\n\n"
            "Unsur adı ASLA cümle veya fiil içermemeli. Sadece isim tamlaması olmalı.\n"
            "Her unsur için ayrıca 1-2 cümlelik tanım (definition) yaz.\n\n"
            "Kurallar:\n"
            "- Verilen metinden TÜM fiziksel bileşenleri/alt sistemleri çıkar.\n"
            "- Genel kavramlar (ör. 'matematiksel hesaplama', 'birden fazla dalga boyu') unsur DEĞİLDİR.\n"
            "- Sadece somut, fiziksel bileşenleri unsur olarak al.\n"
            "- TR ve EN alanları doldur.\n"
            "- Minimum 3, hedef 5-15 unsur çıkar.\n\n"
            "SADECE geçerli JSON array döndür. Markdown kullanma."
        )

        user_content = json.dumps({
            "document_text_tr": context,
            "source": source,
            "output_fields": [
                "name_tr", "name_en", "definition_tr", "definition_en",
                "aliases_tr", "evidence_tr", "confidence",
            ],
        }, ensure_ascii=False)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        response = self.client.chat(messages)
        parsed = parse_json_fragment(response)
        if not isinstance(parsed, list):
            raise ValueError("Direct element LLM output must be a JSON array")

        out: List[RawElement] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            name_tr = str(item.get("name_tr", "")).strip()
            definition_tr = str(item.get("definition_tr", "")).strip()
            if not name_tr or not definition_tr:
                continue
            evidence_tr = extract_evidence_text(item.get("evidence_tr"))
            if not evidence_tr:
                evidence_tr = definition_tr
            out.append(
                RawElement(
                    source=source,
                    name_tr=name_tr,
                    definition_tr=definition_tr,
                    name_en=str(item.get("name_en", "")).strip(),
                    definition_en=str(item.get("definition_en", "")).strip(),
                    aliases_tr=[str(a).strip() for a in (item.get("aliases_tr") or []) if str(a).strip()],
                    evidence=[{"source": source, "text_tr": evidence_tr}],
                    confidence=max(0.0, min(1.0, safe_float(item.get("confidence"), self.default_confidence))),
                )
            )

        return out

    def extract_relations(
        self,
        source: str,
        elements: List[MergedElement],
        candidate_sentences: List[str],
        max_chars_per_chunk: int,
    ) -> List[RawRelation]:
        if not candidate_sentences:
            return []

        system_prompt = (
            "Sen patent unsurları arasındaki fiziksel/fonksiyonel ilişkileri çıkaran bir modelsin.\n\n"
            "Görevin: verilen aday cümlelerden, hangi unsurların birbiriyle nasıl ilişkili olduğunu bul.\n"
            "İlişki cümlesi, iki unsur arasındaki bağlantıyı (konum, bağlantı, fonksiyon) açıklamalı.\n\n"
            "Kurallar:\n"
            "- subject_name_tr ve object_name_tr, verilen unsur listesindeki isimlerden olmalı.\n"
            "- İlişki tipi sınıflaması yapma, doğal cümle döndür.\n"
            "- Sadece metinde kanıtı olan ilişkileri döndür.\n"
            "- TR ve EN cümleleri doldur.\n\n"
            "SADECE geçerli JSON array döndür. Markdown kullanma."
        )

        payload = {
            "elements": [{"element_id": e.element_id, "name_tr": e.name_tr, "name_en": e.name_en} for e in elements],
            "candidate_sentences_tr": candidate_sentences[: self.max_relation_candidates],
            "output_fields": [
                "subject_name_tr", "object_name_tr",
                "relation_sentence_tr", "relation_sentence_en",
                "evidence_tr", "confidence",
            ],
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

        response = self.client.chat(messages)
        parsed = parse_json_fragment(response)
        if not isinstance(parsed, list):
            raise ValueError("Relation LLM output must be a JSON array")

        out: List[RawRelation] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            subj = str(item.get("subject_name_tr", "")).strip()
            obj = str(item.get("object_name_tr", "")).strip()
            rel_tr = str(item.get("relation_sentence_tr", "")).strip()
            rel_en = str(item.get("relation_sentence_en", "")).strip()
            evidence = str(item.get("evidence_tr", rel_tr)).strip()
            if not subj or not obj or not rel_tr:
                continue
            out.append(
                RawRelation(
                    source=source,
                    subject_name_tr=subj,
                    object_name_tr=obj,
                    relation_sentence_tr=rel_tr,
                    relation_sentence_en=rel_en,
                    evidence_text_tr=evidence,
                    confidence=max(0.0, min(1.0, safe_float(item.get("confidence"), self.default_confidence))),
                )
            )

        return out


# ---------------------------------------------------------------------------
# [SECTION 11] Merger
# ---------------------------------------------------------------------------


class Merger:
    def __init__(
        self,
        debug: bool = False,
        dedup_threshold: float = 0.82,
        relation_resolve_threshold: float = 0.65,
    ):
        self.debug = debug
        self.dedup_threshold = dedup_threshold
        self.relation_resolve_threshold = relation_resolve_threshold

    def merge_elements(self, raw_elements: List[RawElement]) -> List[MergedElement]:
        clusters: List[List[RawElement]] = []

        for elem in raw_elements:
            best_idx = -1
            best_score = 0.0
            for idx, cluster in enumerate(clusters):
                score = max(text_similarity(elem.name_tr, c.name_tr) for c in cluster)
                if score > best_score:
                    best_score = score
                    best_idx = idx
            if best_idx >= 0 and best_score >= self.dedup_threshold:
                clusters[best_idx].append(elem)
            else:
                clusters.append([elem])

        merged: List[MergedElement] = []

        for i, cluster in enumerate(clusters, start=1):
            all_names = [c.name_tr for c in cluster if c.name_tr]
            all_aliases = []
            all_evidence = []
            all_conf = []
            name_en_candidates = []
            def_tr_candidates = []
            def_en_candidates = []

            for c in cluster:
                all_aliases.extend(c.aliases_tr)
                all_aliases.append(c.name_tr)
                all_evidence.extend(c.evidence)
                all_conf.append(c.confidence)
                if c.name_en:
                    name_en_candidates.append(c.name_en)
                if c.definition_tr:
                    def_tr_candidates.append(c.definition_tr)
                if c.definition_en:
                    def_en_candidates.append(c.definition_en)

            canonical_name = self._pick_canonical_name(all_names)
            canonical_en = self._pick_longest(name_en_candidates) if name_en_candidates else canonical_name
            canonical_def_tr = self._pick_longest(def_tr_candidates)
            canonical_def_en = self._pick_longest(def_en_candidates) if def_en_candidates else canonical_def_tr

            aliases = sorted({a.strip() for a in all_aliases if a.strip() and normalize_for_match(a) != normalize_for_match(canonical_name)})
            evidence = self._dedup_evidence(all_evidence)
            confidence = sum(all_conf) / max(1, len(all_conf))

            merged.append(
                MergedElement(
                    element_id=f"E{i:03d}",
                    name_tr=canonical_name,
                    name_en=canonical_en,
                    definition_tr=canonical_def_tr,
                    definition_en=canonical_def_en,
                    aliases_tr=aliases,
                    evidence=evidence,
                    confidence=round(confidence, 4),
                )
            )

        debug_print(self.debug, f"Merged elements: {len(raw_elements)} -> {len(merged)}")
        return merged

    def merge_relations(
        self,
        raw_relations: List[RawRelation],
        elements: List[MergedElement],
    ) -> List[MergedRelation]:
        if not raw_relations:
            return []

        name_map = {e.name_tr: e.element_id for e in elements}
        dedup_keys = set()
        merged: List[MergedRelation] = []

        for rel in raw_relations:
            subj_id = self._resolve_element_id(rel.subject_name_tr, elements, name_map)
            obj_id = self._resolve_element_id(rel.object_name_tr, elements, name_map)
            if not subj_id or not obj_id or subj_id == obj_id:
                continue

            key = (subj_id, obj_id, normalize_for_match(rel.relation_sentence_tr))
            if key in dedup_keys:
                continue
            dedup_keys.add(key)

            merged.append(
                MergedRelation(
                    relation_id=f"R{len(merged)+1:03d}",
                    subject_element_id=subj_id,
                    object_element_id=obj_id,
                    relation_sentence_tr=rel.relation_sentence_tr,
                    relation_sentence_en=rel.relation_sentence_en or rel.relation_sentence_tr,
                    evidence={"source": rel.source, "text_tr": rel.evidence_text_tr},
                    confidence=round(rel.confidence, 4),
                )
            )

        debug_print(self.debug, f"Merged relations: {len(raw_relations)} -> {len(merged)}")
        return merged

    @staticmethod
    def _pick_canonical_name(names: List[str]) -> str:
        # Prefer frequently repeated, then longer technical label.
        if not names:
            return ""
        norm_count: Dict[str, int] = {}
        original: Dict[str, str] = {}
        for n in names:
            nn = normalize_for_match(n)
            norm_count[nn] = norm_count.get(nn, 0) + 1
            if nn not in original or len(n) > len(original[nn]):
                original[nn] = n

        ranked = sorted(norm_count.items(), key=lambda kv: (kv[1], len(original[kv[0]])), reverse=True)
        return original[ranked[0][0]]

    @staticmethod
    def _pick_longest(values: List[str]) -> str:
        values = [v for v in values if v]
        if not values:
            return ""
        return sorted(values, key=lambda x: len(x), reverse=True)[0]

    @staticmethod
    def _dedup_evidence(evidence: List[Dict[str, str]]) -> List[Dict[str, str]]:
        seen = set()
        out = []
        for ev in evidence:
            src = (ev.get("source") or "").strip()
            txt = (ev.get("text_tr") or "").strip()
            key = (src, normalize_for_match(txt))
            if txt and key not in seen:
                seen.add(key)
                out.append({"source": src, "text_tr": txt})
        return out

    def _resolve_element_id(
        self,
        name_tr: str,
        elements: List[MergedElement],
        direct_map: Dict[str, str],
    ) -> Optional[str]:
        if name_tr in direct_map:
            return direct_map[name_tr]

        best = None
        best_score = 0.0
        for e in elements:
            score = text_similarity(name_tr, e.name_tr)
            if score > best_score:
                best_score = score
                best = e.element_id
        if best and best_score >= self.relation_resolve_threshold:
            return best
        return None


# ---------------------------------------------------------------------------
# [SECTION 12] Output
# ---------------------------------------------------------------------------


class OutputWriter:
    def __init__(self, debug: bool = False):
        self.debug = debug

    def write(
        self,
        out_dir: Path,
        project_id: str,
        payload: Dict[str, Any],
        llm_model: str,
        ocr_used: bool,
    ) -> Tuple[Path, Path]:
        ensure_dir(out_dir)

        json_path = out_dir / f"{project_id}_unsur_relations.json"
        xlsx_path = out_dir / f"{project_id}_unsur_relations.xlsx"

        with json_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        sheets = self._build_excel_sheets(payload, llm_model=llm_model, ocr_used=ocr_used)
        SimpleXlsxWriter.write(xlsx_path, sheets)

        debug_print(self.debug, f"Wrote JSON: {json_path}")
        debug_print(self.debug, f"Wrote XLSX: {xlsx_path}")
        return json_path, xlsx_path

    def _build_excel_sheets(
        self,
        payload: Dict[str, Any],
        llm_model: str,
        ocr_used: bool,
    ) -> Dict[str, List[List[Any]]]:
        project_id = payload.get("project_id", "")

        element_rows: List[List[Any]] = [
            [
                "project_id",
                "element_id",
                "name_tr",
                "name_en",
                "definition_tr",
                "definition_en",
                "aliases_tr",
                "source_count",
                "confidence",
                "evidence_tr",
            ]
        ]

        for e in payload.get("elements", []):
            evidence = e.get("evidence") or []
            evidence_text = " | ".join((ev.get("text_tr") or "") for ev in evidence)
            element_rows.append(
                [
                    project_id,
                    e.get("element_id", ""),
                    e.get("name_tr", ""),
                    e.get("name_en", ""),
                    e.get("definition_tr", ""),
                    e.get("definition_en", ""),
                    ", ".join(e.get("aliases_tr") or []),
                    len({(ev.get("source") or "") for ev in evidence}),
                    e.get("confidence", 0.0),
                    evidence_text,
                ]
            )

        relation_rows: List[List[Any]] = [
            [
                "project_id",
                "relation_id",
                "subject_element_id",
                "object_element_id",
                "relation_sentence_tr",
                "relation_sentence_en",
                "confidence",
                "source",
                "evidence_tr",
            ]
        ]

        for r in payload.get("relations", []):
            ev = r.get("evidence") or {}
            relation_rows.append(
                [
                    project_id,
                    r.get("relation_id", ""),
                    r.get("subject_element_id", ""),
                    r.get("object_element_id", ""),
                    r.get("relation_sentence_tr", ""),
                    r.get("relation_sentence_en", ""),
                    r.get("confidence", 0.0),
                    ev.get("source", ""),
                    ev.get("text_tr", ""),
                ]
            )

        docs = payload.get("documents") or []
        bbf_path = ""
        report_path = ""
        for doc in docs:
            if doc.get("type") == "bbf":
                bbf_path = doc.get("path", "")
            if doc.get("type") == "report":
                report_path = doc.get("path", "")

        meta_rows = [
            [
                "project_id",
                "bbf_path",
                "report_path",
                "llm_model",
                "run_timestamp",
                "ocr_used",
            ],
            [
                project_id,
                bbf_path,
                report_path,
                llm_model,
                dt.datetime.now(dt.timezone.utc).isoformat(),
                str(bool(ocr_used)),
            ],
        ]

        return {
            "elements": element_rows,
            "relations": relation_rows,
            "meta": meta_rows,
        }


# ---------------------------------------------------------------------------
# [SECTION 13] Pipeline
# ---------------------------------------------------------------------------


class BBFReportPipeline:
    def __init__(
        self,
        loader: DocumentLoader,
        section_extractor: SectionExtractor,
        rule_extractor: RuleExtractor,
        relation_cues: RelationCueLibrary,
        llm_extractor: Any,
        merger: Merger,
        output_writer: OutputWriter,
        max_chars_per_chunk: int = 12000,
        debug: bool = False,
    ):
        self.loader = loader
        self.section_extractor = section_extractor
        self.rule_extractor = rule_extractor
        self.relation_cues = relation_cues
        self.llm_extractor = llm_extractor
        self.merger = merger
        self.output_writer = output_writer
        self.max_chars_per_chunk = max_chars_per_chunk
        self.debug = debug

    def run_from_files(
        self,
        bbf_path: Path,
        report_path: Path,
        out_dir: Path,
        project_id: Optional[str] = None,
        llm_model: str = "",
        extra_doc_paths: Optional[List[Path]] = None,
    ) -> Dict[str, Any]:
        bbf_loaded = self.loader.load(bbf_path)
        report_loaded = self.loader.load(report_path)
        ocr_used = bbf_loaded.ocr_used or report_loaded.ocr_used

        extra_texts: List[Tuple[str, Path]] = []
        for doc_path in (extra_doc_paths or []):
            try:
                loaded = self.loader.load(doc_path)
                extra_texts.append((loaded.text, doc_path))
                ocr_used = ocr_used or loaded.ocr_used
            except Exception as exc:
                debug_print(self.debug, f"Failed to load extra doc {doc_path}: {exc}")

        payload = self.run_from_texts(
            bbf_text=bbf_loaded.text,
            report_text=report_loaded.text,
            bbf_path=bbf_path,
            report_path=report_path,
            project_id=project_id,
            extra_texts=extra_texts,
        )

        pid = payload["project_id"]
        self.output_writer.write(out_dir, pid, payload, llm_model=llm_model, ocr_used=ocr_used)
        return payload

    def run_from_texts(
        self,
        bbf_text: str,
        report_text: str,
        bbf_path: Optional[Path] = None,
        report_path: Optional[Path] = None,
        project_id: Optional[str] = None,
        extra_texts: Optional[List[Tuple[str, Path]]] = None,
    ) -> Dict[str, Any]:
        bbf_path = bbf_path or Path("bbf")
        report_path = report_path or Path("report")
        project_id = project_id or infer_project_id(bbf_path, report_path)

        bbf_clean = clean_text(bbf_text)
        report_clean = clean_text(report_text)

        bbf_sections = self.section_extractor.extract(bbf_clean, "bbf")
        report_sections = self.section_extractor.extract(report_clean, "report")

        bbf_element_text = bbf_sections.get("elements") or bbf_sections.get("raw") or ""
        report_element_text = (
            report_sections.get("elements")
            or report_sections.get("summary")
            or report_sections.get("raw")
            or ""
        )

        bbf_rule = self.rule_extractor.extract_elements(section_text=bbf_element_text, source="bbf")
        report_rule = self.rule_extractor.extract_elements(section_text=report_element_text, source="report")

        bbf_enriched = self._safe_enrich_elements("bbf", bbf_rule, bbf_sections.get("raw", ""))
        report_enriched = self._safe_enrich_elements("report", report_rule, report_sections.get("raw", ""))

        bbf_direct = self._safe_extract_elements_from_text("bbf", bbf_sections.get("raw", ""))
        report_direct = self._safe_extract_elements_from_text("report", report_sections.get("raw", ""))

        raw_elements = bbf_enriched + report_enriched + bbf_direct + report_direct

        extra_doc_entries: List[Dict[str, str]] = []
        for extra_text, extra_path in (extra_texts or []):
            extra_clean = clean_text(extra_text)
            source_label = f"extra:{extra_path.stem}"
            extra_doc_entries.append({"type": "extra", "path": str(extra_path), "language": "tr"})

            extra_direct = self._safe_extract_elements_from_text(source_label, extra_clean)
            raw_elements.extend(extra_direct)

            extra_rule = self.rule_extractor.extract_elements(section_text=extra_clean, source=source_label)
            if extra_rule:
                extra_enriched = self._safe_enrich_elements(source_label, extra_rule, extra_clean)
                raw_elements.extend(extra_enriched)

        merged_elements = self.merger.merge_elements(raw_elements)

        full_text_bbf = "\n".join(
            [bbf_sections.get("elements", ""), bbf_sections.get("background", ""), bbf_sections.get("raw", "")]
        )
        full_text_report = "\n".join(
            [report_sections.get("elements", ""), report_sections.get("summary", ""), report_sections.get("raw", "")]
        )

        element_names = [e.name_tr for e in merged_elements]
        rel_candidates_bbf = self.relation_cues.find_relation_sentences(full_text_bbf, element_names)
        rel_candidates_report = self.relation_cues.find_relation_sentences(full_text_report, element_names)

        if not rel_candidates_bbf and len(merged_elements) >= 2:
            rel_candidates_bbf = [e.definition_tr for e in merged_elements if e.definition_tr]
        if not rel_candidates_report and len(merged_elements) >= 2:
            rel_candidates_report = [e.definition_tr for e in merged_elements if e.definition_tr]

        raw_relations: List[RawRelation] = []
        raw_relations.extend(self._safe_extract_relations("bbf", merged_elements, rel_candidates_bbf))
        raw_relations.extend(self._safe_extract_relations("report", merged_elements, rel_candidates_report))
        merged_relations = self.merger.merge_relations(raw_relations, merged_elements)

        documents = [
            {"type": "bbf", "path": str(bbf_path), "language": "tr"},
            {"type": "report", "path": str(report_path), "language": "tr"},
        ] + extra_doc_entries

        payload = {
            "project_id": project_id,
            "documents": documents,
            "elements": [
                {
                    "element_id": e.element_id,
                    "name_tr": e.name_tr,
                    "name_en": e.name_en,
                    "definition_tr": e.definition_tr,
                    "definition_en": e.definition_en,
                    "aliases_tr": e.aliases_tr,
                    "evidence": e.evidence,
                    "confidence": e.confidence,
                }
                for e in merged_elements
            ],
            "relations": [
                {
                    "relation_id": r.relation_id,
                    "subject_element_id": r.subject_element_id,
                    "object_element_id": r.object_element_id,
                    "relation_sentence_tr": r.relation_sentence_tr,
                    "relation_sentence_en": r.relation_sentence_en,
                    "evidence": r.evidence,
                    "confidence": r.confidence,
                }
                for r in merged_relations
            ],
        }

        return payload

    def _safe_extract_elements_from_text(
        self,
        source: str,
        text: str,
    ) -> List[RawElement]:
        if not text:
            return []
        if not hasattr(self.llm_extractor, "extract_elements_from_text"):
            return []
        try:
            return self.llm_extractor.extract_elements_from_text(
                source=source,
                text=text,
                max_chars_per_chunk=self.max_chars_per_chunk,
            )
        except Exception as exc:
            debug_print(self.debug, f"LLM direct extraction failed ({source}): {exc}")
            return []

    def _safe_enrich_elements(
        self,
        source: str,
        candidates: List[RawElement],
        context_text: str,
    ) -> List[RawElement]:
        if not candidates:
            return []
        try:
            llm_items = self.llm_extractor.enrich_elements(
                source=source,
                candidates=candidates,
                context_text=context_text,
                max_chars_per_chunk=self.max_chars_per_chunk,
            )
            if not llm_items:
                return candidates
            return self._merge_llm_with_rule_candidates(llm_items, candidates)
        except Exception as exc:
            debug_print(self.debug, f"LLM enrich failed ({source}), fallback to rule candidates: {exc}")
            return candidates

    def _merge_llm_with_rule_candidates(
        self,
        llm_items: List[RawElement],
        rule_items: List[RawElement],
    ) -> List[RawElement]:
        # LLM ciktilari adaylardan az gelirse unsur kaybini engelle.
        merged = list(llm_items)

        for rule in rule_items:
            best_idx = -1
            best_score = 0.0
            for i, cur in enumerate(merged):
                name_score = text_similarity(rule.name_tr, cur.name_tr)
                def_score = text_similarity(rule.definition_tr, cur.definition_tr)
                score = max(name_score, def_score)
                if score > best_score:
                    best_score = score
                    best_idx = i

            if best_idx >= 0 and best_score >= 0.80:
                cur = merged[best_idx]
                cur.aliases_tr = sorted(set((cur.aliases_tr or []) + (rule.aliases_tr or []) + [rule.name_tr]))
                cur.evidence = self.merger._dedup_evidence((cur.evidence or []) + (rule.evidence or []))
                cur.confidence = max(cur.confidence, rule.confidence)
            else:
                merged.append(rule)

        # Son dedup pass: ayni isimli tekrarlar varsa tekille.
        out: List[RawElement] = []
        for item in merged:
            found = False
            for cur in out:
                if text_similarity(item.name_tr, cur.name_tr) >= 0.92:
                    cur.aliases_tr = sorted(set((cur.aliases_tr or []) + (item.aliases_tr or []) + [item.name_tr]))
                    cur.evidence = self.merger._dedup_evidence((cur.evidence or []) + (item.evidence or []))
                    cur.confidence = max(cur.confidence, item.confidence)
                    if len(item.definition_tr) > len(cur.definition_tr):
                        cur.definition_tr = item.definition_tr
                    if len(item.definition_en) > len(cur.definition_en):
                        cur.definition_en = item.definition_en
                    if len(item.name_en) > len(cur.name_en):
                        cur.name_en = item.name_en
                    found = True
                    break
            if not found:
                out.append(item)

        return out

    def _safe_extract_relations(
        self,
        source: str,
        merged_elements: List[MergedElement],
        candidate_sentences: List[str],
    ) -> List[RawRelation]:
        if not candidate_sentences:
            return []
        try:
            return self.llm_extractor.extract_relations(
                source=source,
                elements=merged_elements,
                candidate_sentences=candidate_sentences,
                max_chars_per_chunk=self.max_chars_per_chunk,
            )
        except Exception as exc:
            debug_print(self.debug, f"LLM relation extraction failed ({source}): {exc}")
            return []


# ---------------------------------------------------------------------------
# [SECTION 14] Batch matching
# ---------------------------------------------------------------------------


def normalize_filename(name: str) -> str:
    return normalize_for_match(name)


def score_file(name: str, patterns: Sequence[Tuple[str, int]]) -> int:
    normalized = normalize_filename(name)
    score = 0
    for pat, w in patterns:
        if re.search(pat, normalized, flags=re.IGNORECASE):
            score += w
    return score


def pick_best_file(candidates: List[Path], patterns: Sequence[Tuple[str, int]]) -> Tuple[Optional[Path], bool]:
    if not candidates:
        return None, False

    scored = [(p, score_file(p.name, patterns)) for p in candidates]
    scored = [item for item in scored if item[1] > 0]
    if not scored:
        return None, False

    scored.sort(key=lambda x: x[1], reverse=True)
    best_score = scored[0][1]
    best = [p for p, s in scored if s == best_score]
    if len(best) > 1:
        return None, True
    return best[0], False


def find_case_pairs(input_dir: Path, debug: bool = False) -> List[Tuple[Path, Path, Path, List[Path]]]:
    pairs: List[Tuple[Path, Path, Path, List[Path]]] = []

    for root, _dirs, files in os.walk(input_dir):
        if not files:
            continue

        current_dir = Path(root)
        doc_candidates = [
            current_dir / f
            for f in files
            if Path(f).suffix.lower() in {".docx", ".pdf", ".txt"}
        ]
        if not doc_candidates:
            continue

        bbf, bbf_tie = pick_best_file(doc_candidates, BBF_FILE_PATTERNS)
        report, report_tie = pick_best_file(doc_candidates, REPORT_FILE_PATTERNS)

        if bbf_tie or report_tie:
            debug_print(debug, f"Skipping {current_dir}: tie on candidate selection")
            continue

        if bbf and report:
            extras = [p for p in doc_candidates if p != bbf and p != report]
            pairs.append((current_dir, bbf, report, extras))

    return pairs


# ---------------------------------------------------------------------------
# [SECTION 15] Factory and CLI
# ---------------------------------------------------------------------------


def build_pipeline(args: argparse.Namespace) -> Tuple[BBFReportPipeline, str]:
    tunables = TunableSettings(
        pdf_low_density_threshold=args.pdf_low_density_threshold,
        dedup_threshold=args.dedup_threshold,
        element_resolve_threshold=args.element_resolve_threshold,
        rule_unsur_confidence=args.rule_unsur_confidence,
        rule_bullet_confidence=args.rule_bullet_confidence,
        enable_heuristic_relation_fallback=not args.disable_heuristic_relation_fallback,
        heuristic_relation_confidence=args.heuristic_relation_confidence,
        max_relation_candidates=args.max_relation_candidates,
        llm_default_confidence=args.llm_default_confidence,
        max_component_words=args.max_component_words,
    )

    loader = DocumentLoader(
        disable_ocr=args.disable_ocr,
        debug=args.debug,
        pdf_low_density_threshold=tunables.pdf_low_density_threshold,
    )
    section_extractor = SectionExtractor(debug=args.debug)
    rule_extractor = RuleExtractor(
        debug=args.debug,
        unsur_confidence=tunables.rule_unsur_confidence,
        bullet_confidence=tunables.rule_bullet_confidence,
        max_component_words=tunables.max_component_words,
    )
    relation_cues = RelationCueLibrary(
        xlsx_path=Path(args.relation_cue_xlsx) if args.relation_cue_xlsx else DEFAULT_CUE_XLSX,
        debug=args.debug,
    )

    llm_base_url = args.llm_base_url or os.getenv("LLM_BASE_URL", "")
    llm_api_key = args.llm_api_key or os.getenv("LLM_API_KEY", "")
    llm_model = args.llm_model or os.getenv("LLM_MODEL", "")
    local_model = args.local_model or os.getenv("LOCAL_MODEL", "")

    if local_model:
        # Local model seçildiğinde: unsur/ilişki çıkarma kural tabanlı yapılır,
        # TR->EN çevirisi Google Translate ile otomatik yapılır.
        llm_extractor: Any = HeuristicLLMExtractor(
            debug=args.debug,
            enable_relation_fallback=tunables.enable_heuristic_relation_fallback,
            fallback_relation_confidence=tunables.heuristic_relation_confidence,
        )
    elif llm_base_url and llm_model:
        client = OpenAICompatibleClient(
            base_url=llm_base_url,
            api_key=llm_api_key,
            model=llm_model,
            temperature=args.temperature,
            debug=args.debug,
        )
        llm_extractor = LLMExtractor(
            client=client,
            debug=args.debug,
            max_relation_candidates=tunables.max_relation_candidates,
            default_confidence=tunables.llm_default_confidence,
        )
    else:
        debug_print(
            args.debug,
            "LLM configuration not set; using heuristic extractor fallback.",
        )
        llm_extractor = HeuristicLLMExtractor(
            debug=args.debug,
            enable_relation_fallback=tunables.enable_heuristic_relation_fallback,
            fallback_relation_confidence=tunables.heuristic_relation_confidence,
        )

    merger = Merger(
        debug=args.debug,
        dedup_threshold=tunables.dedup_threshold,
        relation_resolve_threshold=tunables.element_resolve_threshold,
    )
    output_writer = OutputWriter(debug=args.debug)

    pipeline = BBFReportPipeline(
        loader=loader,
        section_extractor=section_extractor,
        rule_extractor=rule_extractor,
        relation_cues=relation_cues,
        llm_extractor=llm_extractor,
        merger=merger,
        output_writer=output_writer,
        max_chars_per_chunk=args.max_chars_per_chunk,
        debug=args.debug,
    )

    return pipeline, llm_model


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BBF + Arastirma Raporu unsur/iliski cikarma pipeline")

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input-dir", type=str, help="Batch mode input directory")
    mode.add_argument("--bbf", type=str, help="Single mode BBF file path")

    p.add_argument("--report", type=str, help="Single mode report file path")
    p.add_argument("--extra-docs", nargs="*", default=[], help="Additional documents (conversation notes, etc.)")
    p.add_argument("--out-dir", type=str, required=True, help="Output directory")
    p.add_argument("--project-id", type=str, default="", help="Override project id")

    p.add_argument("--llm-base-url", type=str, default="", help="OpenAI-compatible base URL, e.g. http://localhost:1234/v1")
    p.add_argument("--llm-api-key", type=str, default="", help="API key for endpoint")
    p.add_argument("--llm-model", type=str, default="", help="Model name")
    p.add_argument("--local-model", type=str, default="", help="Local HuggingFace model id, e.g. TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    p.add_argument("--temperature", type=float, default=0.1, help="LLM temperature")

    p.add_argument("--max-chars-per-chunk", type=int, default=12000)
    p.add_argument("--disable-ocr", action="store_true", help="Disable OCR fallback for low-density PDFs")
    p.add_argument("--relation-cue-xlsx", type=str, default=str(DEFAULT_CUE_XLSX), help="Relation cue xlsx path")

    # Modifiye edilebilir tuning parametreleri (tek dosyada hizli ayar).
    p.add_argument("--pdf-low-density-threshold", type=int, default=300, help="PDF low text threshold for OCR fallback")
    p.add_argument("--dedup-threshold", type=float, default=0.75, help="Element dedup similarity threshold")
    p.add_argument("--element-resolve-threshold", type=float, default=0.65, help="Relation element resolve similarity threshold")
    p.add_argument("--rule-unsur-confidence", type=float, default=0.82, help="Rule extractor confidence for Unsur blocks")
    p.add_argument("--rule-bullet-confidence", type=float, default=0.72, help="Rule extractor confidence for bullet items")
    p.add_argument("--max-component-words", type=int, default=3, help="Max words for extracted element names")
    p.add_argument("--max-relation-candidates", type=int, default=200, help="Max candidate sentences sent to LLM for relation extraction")
    p.add_argument("--heuristic-relation-confidence", type=float, default=0.35, help="Heuristic relation fallback confidence")
    p.add_argument("--llm-default-confidence", type=float, default=0.78, help="Default confidence when LLM does not provide confidence")
    p.add_argument("--disable-heuristic-relation-fallback", action="store_true", help="Disable heuristic sequential fallback when no relation found")

    p.add_argument("--debug", action="store_true")

    args = p.parse_args(argv)

    if args.bbf and not args.report:
        p.error("--report is required when using --bbf")

    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    pipeline, llm_model = build_pipeline(args)

    out_dir = Path(args.out_dir).resolve()
    ensure_dir(out_dir)

    if args.input_dir:
        input_dir = Path(args.input_dir).resolve()
        pairs = find_case_pairs(input_dir, debug=args.debug)
        if not pairs:
            print(f"No valid BBF+report pairs found in: {input_dir}")
            return 1

        print(f"Found {len(pairs)} case(s) for batch processing")
        for case_dir, bbf_path, report_path, extra_docs in pairs:
            pid = args.project_id or infer_project_id(case_dir, bbf_path, report_path)
            case_out = out_dir / pid
            ensure_dir(case_out)
            extras_str = f"\n  Extra docs: {len(extra_docs)}" if extra_docs else ""
            print(f"[CASE] {pid}\n  BBF: {bbf_path}\n  Report: {report_path}{extras_str}")
            payload = pipeline.run_from_files(
                bbf_path=bbf_path,
                report_path=report_path,
                out_dir=case_out,
                project_id=pid,
                llm_model=llm_model,
                extra_doc_paths=extra_docs,
            )
            print(
                f"  -> elements={len(payload.get('elements', []))}, "
                f"relations={len(payload.get('relations', []))}"
            )
        return 0

    bbf_path = Path(args.bbf).resolve()
    report_path = Path(args.report).resolve()
    extra_doc_paths = [Path(p).resolve() for p in (args.extra_docs or [])]
    project_id = args.project_id or infer_project_id(bbf_path, report_path)

    payload = pipeline.run_from_files(
        bbf_path=bbf_path,
        report_path=report_path,
        out_dir=out_dir,
        project_id=project_id,
        llm_model=llm_model,
        extra_doc_paths=extra_doc_paths,
    )

    print(
        f"Done: {project_id} | elements={len(payload.get('elements', []))} "
        f"relations={len(payload.get('relations', []))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
