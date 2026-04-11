"""
RAG + LLM Engine for Patent Element Definition Extraction
Based on the Colab notebook: unsurtanımıçıkarımı(RAG+LLM)
"""

import os
import numpy as np
import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Globals (lazy-loaded)
# ---------------------------------------------------------------------------
_embedder = None
_index = None
_df = None
_embeddings = None
_llm_model = None
_llm_tokenizer = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        print("[RAG] Loading sentence-transformers model …")
        _embedder = SentenceTransformer("intfloat/multilingual-e5-base")
        print("[RAG] Embedder ready.")
    return _embedder


def _build_document(row):
    return (
        f"element_name_en: {row['element_name_en']}\n"
        f"definition_en: {row['definition_en']}\n"
        f"title_en: {row['description_title_en']}\n"
        f"context_en: {row['all_elements_context_en']}\n\n"
        f"element_name_tr: {row['element_name_tr']}\n"
        f"definition_tr: {row['definition_tr']}\n"
        f"title_tr: {row['description_title_tr']}\n"
        f"context_tr: {row['all_elements_context_tr']}"
    )


def _auto_rename_columns(df):
    """Map common alternative column names to the expected canonical names."""
    alias_map = {
        "element_name_en": ["Element Name (EN)", "element_name_en"],
        "definition_en": ["Definition (EN)", "definition_en"],
        "description_title_en": ["Specification Title (EN)", "description_title_en"],
        "all_elements_context_en": ["All Elements in Specification (EN)", "all_elements_context_en"],
        "element_name_tr": ["Unsur İsmi", "element_name_tr"],
        "definition_tr": ["Tanım", "definition_tr"],
        "description_title_tr": ["Tarifname Başlığı", "description_title_tr"],
        "all_elements_context_tr": ["Tarifnamede Geçen Tüm Unsurlar", "all_elements_context_tr"],
    }
    rename = {}
    for canonical, aliases in alias_map.items():
        if canonical in df.columns:
            continue
        for alias in aliases:
            # Try exact match first, then normalized match
            for col in df.columns:
                if col == alias or col.strip() == alias:
                    rename[col] = canonical
                    break
            if canonical in rename.values():
                break
    if rename:
        print(f"[RAG] Auto-renamed columns: {rename}")
        df.rename(columns=rename, inplace=True)
    return df


def load_data(excel_path: str):
    """Load Excel, build embeddings & FAISS index. Caches to disk."""
    global _df, _index, _embeddings

    print(f"[RAG] Loading data from {excel_path} …")
    _df = pd.read_excel(excel_path)
    _df = _df.fillna("")

    # Auto-rename columns from alternative formats
    _df = _auto_rename_columns(_df)

    required = [
        "element_name_en", "definition_en", "description_title_en",
        "all_elements_context_en", "element_name_tr", "definition_tr",
        "description_title_tr", "all_elements_context_tr",
    ]
    missing = [col for col in required if col not in _df.columns]
    # Fill missing columns with empty strings instead of failing
    for col in missing:
        print(f"[RAG] Warning: column '{col}' not found, filling with empty")
        _df[col] = ""

    _df["document"] = _df.apply(_build_document, axis=1)
    documents = _df["document"].tolist()

    # Check for cached embeddings
    cache_dir = os.path.join(os.path.dirname(excel_path), ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_emb = os.path.join(cache_dir, "embeddings.npy")
    cache_idx = os.path.join(cache_dir, "faiss.index")

    if os.path.exists(cache_emb) and os.path.exists(cache_idx):
        print("[RAG] Found cached embeddings — loading from disk …")
        _embeddings = np.load(cache_emb)
        _index = faiss.read_index(cache_idx)
        # Still need the embedder loaded for queries
        _get_embedder()
        print(f"[RAG] Cache loaded — {_index.ntotal} vectors ready.")
        return len(documents)

    embedder = _get_embedder()
    print(f"[RAG] Encoding {len(documents)} documents (first time, please wait) …")
    _embeddings = embedder.encode(
        documents, convert_to_numpy=True,
        normalize_embeddings=True, show_progress_bar=True,
        batch_size=64,
    )

    dimension = _embeddings.shape[1]
    _index = faiss.IndexFlatIP(dimension)
    _index.add(_embeddings)

    # Save cache
    np.save(cache_emb, _embeddings)
    faiss.write_index(_index, cache_idx)
    print(f"[RAG] FAISS index built & cached — {_index.ntotal} vectors.")
    return len(documents)


def is_data_loaded():
    return _df is not None and _index is not None


def get_elements_list():
    """Return unique element names (EN + TR)."""
    if _df is None:
        return []
    pairs = _df[["element_name_en", "element_name_tr"]].drop_duplicates()
    return pairs.to_dict("records")


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(element_name: str, context: str = "", top_k: int = 5):
    query = (
        f"context: {context}\n"
        f"target element: {element_name}\n"
        "general technical definition of this element in the invention context"
    )
    embedder = _get_embedder()
    query_vec = embedder.encode(
        [query], convert_to_numpy=True, normalize_embeddings=True,
    )
    scores, indices = _index.search(query_vec, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        row = _df.iloc[idx]
        results.append({
            "score": round(float(score), 4),
            "element_name_en": row["element_name_en"],
            "definition_en": row["definition_en"],
            "title_en": row["description_title_en"],
            "context_en": row["all_elements_context_en"],
            "element_name_tr": row["element_name_tr"],
            "definition_tr": row["definition_tr"],
        })
    return results


# ---------------------------------------------------------------------------
# LLM helpers — Mistral-7B prompt style (fallback to smart template)
# ---------------------------------------------------------------------------

# Remote LLM URL (Colab ngrok endpoint) — set via /api/rag/set-llm-url
_remote_llm_url = ""


def set_remote_llm_url(url: str):
    global _remote_llm_url
    _remote_llm_url = url.rstrip("/")
    print(f"[LLM] Remote URL set: {_remote_llm_url}")


def get_remote_llm_url():
    return _remote_llm_url


def _call_llm(prompt: str, max_new_tokens: int = 120, temperature: float = 0.2) -> str:
    """Call LLM via remote Colab endpoint. Falls back to empty if unavailable."""
    if not _remote_llm_url:
        return ""
    try:
        import urllib.request
        import json
        data = json.dumps({
            "prompt": prompt,
            "max_tokens": max_new_tokens,
        }).encode("utf-8")
        req = urllib.request.Request(
            _remote_llm_url + "/generate",
            data=data,
            headers={
                "Content-Type": "application/json",
                "ngrok-skip-browser-warning": "true",
            },
        )
        resp = urllib.request.urlopen(req, timeout=120)
        result = json.loads(resp.read().decode())
        return result.get("text", "")
    except Exception as e:
        print(f"[LLM] Remote call failed: {e}")
        return ""


def _smart_fallback_rag(element_name, retrieved):
    """Build a definition from the best retrieved examples."""
    if not retrieved:
        return "a component configured for use in the invention"
    # Pick the best definition, clean it up
    best = retrieved[0]
    definition = best["definition_en"].strip()
    # If definition is very short, combine top 2
    if len(definition) < 30 and len(retrieved) > 1:
        second = retrieved[1]["definition_en"].strip()
        if second and second != definition:
            definition = definition + ", " + second
    return definition[:300]


def _translate_to_en(text):
    """Translate text to English if it appears to be Turkish."""
    if not text or len(text) < 5:
        return text
    # Quick check: if text has common Turkish chars, try to translate
    tr_chars = set("çğıöşüÇĞİÖŞÜ")
    if any(c in tr_chars for c in text):
        try:
            from deep_translator import GoogleTranslator
            return GoogleTranslator(source="tr", target="en").translate(text[:4000])
        except Exception:
            pass
    return text


def _smart_fallback_bbf(element_name, bbf_text):
    """Extract ALL relevant sentences from BBF text for the element, translate to English."""
    # Build search terms: English name + Turkish equivalent
    search_terms = [element_name.lower()]
    if _df is not None:
        matches = _df[_df["element_name_en"].str.lower() == element_name.lower()]
        if not matches.empty:
            tr_name = matches.iloc[0].get("element_name_tr", "")
            if tr_name:
                search_terms.append(tr_name.lower())

    # Split into sentences
    text = bbf_text.replace("\n", " ")
    sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 10]

    # Find ALL sentences mentioning the element
    relevant = []
    for s in sentences:
        s_lower = s.lower()
        for term in search_terms:
            if term and term in s_lower:
                relevant.append(s)
                break

    if relevant:
        result = ". ".join(relevant[:3])
        return _translate_to_en(result)

    # Fallback: return the first substantive part of BBF as context
    for s in sentences:
        if len(s) > 40:
            return _translate_to_en(s)
    return ""


# ---------------------------------------------------------------------------
# Public generation functions (Colab-style Mistral prompts)
# ---------------------------------------------------------------------------

def _format_retrieved(retrieved):
    text = ""
    for i, r in enumerate(retrieved, 1):
        text += (
            f"\nExample {i}\n"
            f"element_name_en: {r['element_name_en']}\n"
            f"definition_en: {r['definition_en']}\n"
            f"title_en: {r['title_en']}\n"
            f"context_en: {r['context_en']}\n"
        )
    return text.strip()


def generate_rag_fragment(element_name, context="", top_k=5):
    retrieved = retrieve(element_name, context, top_k)
    retrieved_text = _format_retrieved(retrieved)

    prompt = f"""You are a technical patent drafting assistant.

Task:
Using the retrieved examples, write a short general technical definition fragment for the target element.

Rules:
- Output only a short technical fragment in English.
- Make it suitable for a patent definition.
- Keep it short and context-aware.
- Do NOT include positional or relational information.
- Do NOT include reference numbers.
- Do NOT repeat the element name.
- Do NOT write a full sentence.
- Write it as a phrase that can naturally follow a comma.
- Prefer wording such as "extending...", "configured...", "formed...", "having...", "being..." when appropriate.

Invention context:
{context}

Target element:
{element_name}

Retrieved examples:
{retrieved_text}

Output:
"""
    raw = _call_llm(prompt, max_new_tokens=80, temperature=0.2)
    if raw:
        fragment = raw.split("Output:")[-1].strip()
        # Clean up any trailing content
        for stop in ["Example", "element_name", "Invention", "Target", "Rules"]:
            if stop in fragment:
                fragment = fragment[:fragment.index(stop)].strip()
        if len(fragment) > 10:
            return fragment, retrieved

    return _smart_fallback_rag(element_name, retrieved), retrieved


def generate_bbf_fragment(element_name, context="", bbf_text=""):
    if not bbf_text.strip():
        return ""

    # Truncate BBF text to avoid exceeding context window
    bbf_truncated = bbf_text[:6000]

    prompt = f"""You are a patent drafting assistant.

Task:
From the BBF text, extract only the case-specific positional, relational, geometrical, or placement-related fragment for the target element.

Rules:
- Output ONLY in English. If the BBF text is in Turkish or another language, translate your output to English.
- Output only a short fragment in English.
- Do NOT provide the generic definition of the element.
- Do NOT repeat the element name.
- Keep reference numbers if they appear in the BBF text.
- Focus on phrases such as "located between", "disposed on", "extending from", "surrounding", "connected to", "positioned within", "mounted on", etc.
- Do NOT write a full sentence.
- The output should be suitable to appear before a comma in a patent definition.
- If no clear case-specific fragment exists, output only EMPTY.

Invention context:
{context}

Target element:
{element_name}

BBF text:
{bbf_truncated}

Output:
"""
    raw = _call_llm(prompt, max_new_tokens=80, temperature=0.1)
    if raw:
        fragment = raw.split("Output:")[-1].strip()
        if fragment.upper().startswith("EMPTY"):
            return ""
        if len(fragment) > 10:
            return fragment

    return _smart_fallback_bbf(element_name, bbf_text)


def fuse_fragments(element_name, context, bbf_fragment, rag_fragment):
    if not bbf_fragment:
        return rag_fragment
    if not rag_fragment:
        return bbf_fragment

    prompt = f"""You are a patent drafting expert.

Task:
Combine the following two fragments into a single, fluent, short, patent-style English definition phrase.

Rules:
- Output ONLY in English. Translate any Turkish content to English.
- Output only one final phrase.
- The result must read as one coherent definition, not as two separate sentences.
- Do NOT repeat the element name.
- Keep reference numbers if present.
- Keep it concise and suitable for a patent specification.
- Do NOT add unnecessary words.
- Do NOT end with a period.
- Make the phrase sound natural and technically precise.

Invention context:
{context}

Target element:
{element_name}

BBF fragment:
{bbf_fragment if bbf_fragment else "NONE"}

RAG fragment:
{rag_fragment if rag_fragment else "NONE"}

Desired style example:
located between the body (2) and the stopper (3), extending in a cylindrical form along its length

Final output:
"""
    raw = _call_llm(prompt, max_new_tokens=80, temperature=0.15)
    if raw:
        final = raw.split("Final output:")[-1].strip()
        if len(final) > 10:
            return final

    # Smart fusion fallback
    return f"{bbf_fragment}. {rag_fragment}"


def generate_definition(element_name, context="", bbf_text="", top_k=5):
    """Full pipeline (Colab-style): RAG fragment + BBF fragment -> fused definition."""
    rag_fragment, retrieved = generate_rag_fragment(element_name, context, top_k)
    bbf_fragment = generate_bbf_fragment(element_name, context, bbf_text)
    final = fuse_fragments(element_name, context, bbf_fragment, rag_fragment)

    return {
        "element": element_name,
        "rag_fragment": rag_fragment,
        "bbf_fragment": bbf_fragment,
        "final_definition": final,
        "retrieved_examples": retrieved,
    }


def generate_definitions_batch(elements, context="", bbf_text="", top_k=5):
    return [
        generate_definition(el, context, bbf_text, top_k) for el in elements
    ]
