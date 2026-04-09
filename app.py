"""
Patent Drafting Tool — Flask Backend
"""

import os
import json
import threading
from flask import Flask, render_template, request, jsonify, send_from_directory
import rag_engine

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory project store (simple dict for demo)
projects = {}
current_project = None
_loading = {"status": "idle", "error": None, "count": 0}  # upload progress


# ── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── Data / Project API ───────────────────────────────────────────────────────

def _bg_load(path):
    try:
        _loading["status"] = "loading"
        count = rag_engine.load_data(path)
        _loading["count"] = count
        _loading["status"] = "done"
    except Exception as e:
        _loading["error"] = str(e)
        _loading["status"] = "error"


@app.route("/api/upload-excel", methods=["POST"])
def upload_excel():
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file"), 400
    path = os.path.join(UPLOAD_DIR, f.filename)
    f.save(path)
    # Start loading in background thread
    _loading["status"] = "loading"
    _loading["error"] = None
    threading.Thread(target=_bg_load, args=(path,), daemon=True).start()
    return jsonify(ok=True, status="loading")


@app.route("/api/data-status")
def data_status():
    return jsonify(
        loaded=rag_engine.is_data_loaded(),
        status=_loading["status"],
        error=_loading["error"],
        count=_loading["count"],
    )


@app.route("/api/elements")
def elements():
    return jsonify(elements=rag_engine.get_elements_list())


# ── Project CRUD (in-memory) ─────────────────────────────────────────────────

@app.route("/api/projects", methods=["GET"])
def list_projects():
    return jsonify(list(projects.values()))


@app.route("/api/projects", methods=["POST"])
def create_project():
    data = request.json
    pid = str(len(projects) + 1)
    proj = {
        "id": pid,
        "name": data.get("name", "Untitled"),
        "context": data.get("context", ""),
        "bbf_text": data.get("bbf_text", ""),
        "claims": [],
        "elements": [],
        "definitions": {},
        "draft": "",
    }
    projects[pid] = proj
    return jsonify(proj)


@app.route("/api/projects/<pid>", methods=["GET"])
def get_project(pid):
    p = projects.get(pid)
    if not p:
        return jsonify(error="Not found"), 404
    return jsonify(p)


@app.route("/api/projects/<pid>", methods=["PUT"])
def update_project(pid):
    p = projects.get(pid)
    if not p:
        return jsonify(error="Not found"), 404
    data = request.json
    p.update({k: v for k, v in data.items() if k != "id"})
    return jsonify(p)


# ── RAG / LLM API ────────────────────────────────────────────────────────────

@app.route("/api/retrieve", methods=["POST"])
def api_retrieve():
    data = request.json
    element = data.get("element_name", "")
    context = data.get("context", "")
    top_k = data.get("top_k", 5)
    if not rag_engine.is_data_loaded():
        return jsonify(error="Data not loaded yet"), 400
    results = rag_engine.retrieve(element, context, top_k)
    return jsonify(results=results)


@app.route("/api/generate-definition", methods=["POST"])
def api_generate_definition():
    data = request.json
    element = data.get("element_name", "")
    context = data.get("context", "")
    bbf_text = data.get("bbf_text", "")
    top_k = data.get("top_k", 5)
    if not rag_engine.is_data_loaded():
        return jsonify(error="Data not loaded yet"), 400
    result = rag_engine.generate_definition(element, context, bbf_text, top_k)
    return jsonify(result)


@app.route("/api/generate-definitions-batch", methods=["POST"])
def api_generate_definitions_batch():
    data = request.json
    elements = data.get("elements", [])
    context = data.get("context", "")
    bbf_text = data.get("bbf_text", "")
    top_k = data.get("top_k", 5)
    if not rag_engine.is_data_loaded():
        return jsonify(error="Data not loaded yet"), 400
    results = rag_engine.generate_definitions_batch(elements, context, bbf_text, top_k)
    return jsonify(results=results)


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n  Patent Drafting Tool")
    print("  http://localhost:5000\n")
    app.run(debug=True, port=5000)
