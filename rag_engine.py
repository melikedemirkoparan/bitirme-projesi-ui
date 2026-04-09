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


def load_data(excel_path: str):
    """Load Excel, build embeddings & FAISS index. Caches to disk."""
    global _df, _index, _embeddings

    print(f"[RAG] Loading data from {excel_path} …")
    _df = pd.read_excel(excel_path)
    _df = _df.fillna("")

    required = [
        "element_name_en", "definition_en", "description_title_en",
        "all_elements_context_en", "element_name_tr", "definition_tr",
        "description_title_tr", "all_elements_context_tr",
    ]
    for col in required:
        if col not in _df.columns:
            raise ValueError(f"Missing column: {col}")

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
# LLM helpers  (lightweight — uses pipeline or falls back to template)
# ---------------------------------------------------------------------------

def _try_load_llm():
    """Attempt to load a small local model. Returns True on success."""
    global _llm_model, _llm_tokenizer
    if _llm_model is not None:
        return True
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch

        model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
        print(f"[LLM] Trying to load {model_name} …")
        _llm_tokenizer = AutoTokenizer.from_pretrained(model_name)
        _llm_model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=torch.float32, device_map="cpu",
        )
        print("[LLM] Model loaded on CPU.")
        return True
    except Exception as e:
        print(f"[LLM] Could not load local model: {e}")
        return False


def _call_llm(prompt: str, max_new_tokens: int = 100) -> str:
    if _try_load_llm():
        import torch
        inputs = _llm_tokenizer(prompt, return_tensors="pt").to(_llm_model.device)
        with torch.no_grad():
            out = _llm_model.generate(
                **inputs, max_new_tokens=max_new_tokens,
                temperature=0.2, do_sample=True, top_p=0.9,
                pad_token_id=_llm_tokenizer.eos_token_id,
            )
        return _llm_tokenizer.decode(out[0], skip_special_tokens=True)
    return ""


def _template_fallback_rag(element_name, retrieved):
    """If no LLM is available, build a definition from retrieved examples."""
    if not retrieved:
        return f"a component configured for use in the invention"
    best = retrieved[0]
    return best["definition_en"][:200]


def _template_fallback_bbf(element_name, bbf_text):
    """Extract a rough fragment from BBF text mentioning the element."""
    sentences = bbf_text.replace("\n", " ").split(".")
    for s in sentences:
        if element_name.lower() in s.lower():
            return s.strip()
    return ""


# ---------------------------------------------------------------------------
# Public generation functions
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

    prompt = f"""<|system|>You are a technical patent drafting assistant.</s>
<|user|>
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

Invention context: {context}
Target element: {element_name}

Retrieved examples:
{retrieved_text}

Output:</s>
<|assistant|>
"""
    raw = _call_llm(prompt, max_new_tokens=80)
    if raw:
        fragment = raw.split("Output:")[-1].strip().split("</s>")[0].strip()
        if len(fragment) > 10:
            return fragment, retrieved

    return _template_fallback_rag(element_name, retrieved), retrieved


def generate_bbf_fragment(element_name, context="", bbf_text=""):
    if not bbf_text.strip():
        return ""

    prompt = f"""<|system|>You are a patent drafting assistant.</s>
<|user|>
From the BBF text, extract only the case-specific positional, relational, geometrical, or placement-related fragment for the target element.

Rules:
- Output only a short fragment in English.
- Do NOT provide the generic definition of the element.
- Do NOT repeat the element name.
- Keep reference numbers if they appear in the BBF text.
- Focus on phrases such as "located between", "disposed on", "extending from", etc.
- If no clear case-specific fragment exists, output only EMPTY.

Invention context: {context}
Target element: {element_name}

BBF text:
{bbf_text}

Output:</s>
<|assistant|>
"""
    raw = _call_llm(prompt, max_new_tokens=80)
    if raw:
        fragment = raw.split("Output:")[-1].strip().split("</s>")[0].strip()
        if fragment.upper().startswith("EMPTY"):
            return ""
        if len(fragment) > 10:
            return fragment

    return _template_fallback_bbf(element_name, bbf_text)


def fuse_fragments(element_name, context, bbf_fragment, rag_fragment):
    if not bbf_fragment:
        return rag_fragment
    if not rag_fragment:
        return bbf_fragment

    prompt = f"""<|system|>You are a patent drafting expert.</s>
<|user|>
Combine the following two fragments into a single, fluent, short, patent-style English definition phrase.

Rules:
- Output only one final phrase.
- Do NOT repeat the element name.
- Keep reference numbers if present.
- Keep it concise.

Invention context: {context}
Target element: {element_name}
BBF fragment: {bbf_fragment}
RAG fragment: {rag_fragment}

Final output:</s>
<|assistant|>
"""
    raw = _call_llm(prompt, max_new_tokens=80)
    if raw:
        final = raw.split("Final output:")[-1].strip().split("</s>")[0].strip()
        if len(final) > 10:
            return final

    return f"{bbf_fragment}, {rag_fragment}"


def generate_definition(element_name, context="", bbf_text="", top_k=5):
    """Full pipeline: RAG fragment + BBF fragment -> fused definition."""
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
