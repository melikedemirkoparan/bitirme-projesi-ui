/* ═══════════════════════════════════════════════════════════════
   Patent Drafting Tool — Workspace JS (FastAPI + PostgreSQL)
   ═══════════════════════════════════════════════════════════════ */

// ── State ───────────────────────────────────────────────────────
let _patentId = null;
let _claims = [];
let _elements = [];
let _claimElements = {};   // { claim_id: [Element...] }
let _selectedClaimId = null;
let _selectedElement = { claimId: null, elementId: null };
let _claimExpanded = {};
let _elemTreeSearch = {};
let _projects = [];
let _dataLoaded = false;
let _context = '';
let _bbfText = '';
let _composerDraft = '';

// ── Helpers ─────────────────────────────────────────────────────
function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function escAttr(s) { return (s || '').replace(/'/g, "\\'").replace(/\n/g, ' ').substring(0, 200); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }

async function api(path, opts = {}) {
  const h = { ...opts.headers };
  if (opts.body && typeof opts.body === 'string') h['Content-Type'] = 'application/json';
  const res = await fetch('/api' + path, { ...opts, headers: h });
  if (!res.ok) { const e = await res.json().catch(() => ({ detail: 'Request failed' })); throw new Error(e.detail || 'Request failed'); }
  if (res.status === 204) return null;
  return res.json();
}

// ── Navigation ──────────────────────────────────────────────────
function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(id)?.classList.add('active');
}

function goHome() {
  _patentId = null;
  _selectedClaimId = null;
  document.getElementById('navPatentName').textContent = '';
  showPage('page-dashboard');
}

// ═══════════════════════════════════════════════════════════════
// Dashboard
// ═══════════════════════════════════════════════════════════════
function renderProjectList() {
  const list = document.getElementById('projectList');
  if (!list) return;
  if (_projects.length === 0) { list.innerHTML = '<p style="color:var(--text-muted);font-size:12px;padding:8px">No projects yet.</p>'; return; }
  list.innerHTML = _projects.map(p => `
    <div class="project-item" onclick="openProject(${p.patent_id})">
      <div><div class="project-item-name">${esc(p.patent_name)}</div><div class="project-item-sub">${esc(p.patent_owner||'')}</div></div>
      <span class="btn btn-sm btn-ghost">Open</span>
    </div>`).join('');
}

async function createNewProject() {
  const name = prompt('Project name:');
  if (!name) return;
  const owner = prompt('Patent owner (optional):') || 'TUSAS';
  try { const p = await api('/patents', { method: 'POST', body: JSON.stringify({ patent_name: name, patent_owner: owner }) }); _projects.unshift(p); renderProjectList(); } catch (e) { alert(e.message); }
}

async function openProject(patentId) {
  _patentId = patentId;
  try {
    const patent = await api('/patents/' + patentId);
    document.getElementById('navPatentName').textContent = patent.patent_name;

    const [claims, elements] = await Promise.all([api('/patents/' + patentId + '/claims'), api('/patents/' + patentId + '/elements')]);
    _claims = claims;
    _elements = elements;

    claims.forEach(c => { if (_claimExpanded[c.claim_id] === undefined) _claimExpanded[c.claim_id] = true; });
    const linkResults = await Promise.all(claims.map(c => api('/patents/' + patentId + '/claims/' + c.claim_id + '/elements').catch(() => [])));
    claims.forEach((c, i) => { _claimElements[c.claim_id] = linkResults[i]; });

    _selectedClaimId = null;
    showPage('page-editor');
    renderClaimList();
    renderElementQueue();
    updateQueueHint();
    resetDraftPanel();
  } catch (e) { alert('Failed: ' + e.message); }
}

// ═══════════════════════════════════════════════════════════════
// Claims Panel (Left)
// ═══════════════════════════════════════════════════════════════
function renderClaimList() {
  const c = document.getElementById('claimList');
  if (!c) return;
  if (_claims.length === 0) { c.innerHTML = '<p class="ws-empty-msg">No claims yet. Click "+ Add Claim".</p>'; return; }
  c.innerHTML = _claims.map(cl => renderClaimCard(cl)).join('');
}

function claimStatus(claimId) {
  const elems = _claimElements[claimId] || [];
  if (elems.length === 0) return null;
  return elems.every(e => e.definition_text && e.definition_text.trim()) ? 'Ready' : 'Incomplete';
}

function renderClaimCard(c) {
  const expanded = _claimExpanded[c.claim_id] !== false;
  const isSelected = c.claim_id === _selectedClaimId;
  const isIndep = c.claim_dependency_type === 'independent';
  const linked = _claimElements[c.claim_id] || [];
  const status = claimStatus(c.claim_id);
  const parent = c.parent_claim_id ? _claims.find(p => p.claim_id === c.parent_claim_id) : null;

  const statusBadge = status ? `<span class="claim-status-badge claim-status--${status.toLowerCase()}">${status === 'Ready' ? '✓' : '⚠'} ${status}</span>` : '';
  const chevron = expanded ? '∨' : '›';

  return `
  <div class="claim-card ${isIndep ? 'claim-card--independent' : 'claim-card--dependent'} ${isSelected ? 'claim-card--selected' : ''}"
       onclick="selectClaim(${c.claim_id})"
       ondragover="event.preventDefault();this.classList.add('drag-over')"
       ondragleave="this.classList.remove('drag-over')"
       ondrop="event.preventDefault();this.classList.remove('drag-over');dropElementOnClaim(event,${c.claim_id})">
    <div class="claim-card-header">
      <div class="claim-header-left">
        <button class="claim-collapse-btn" onclick="event.stopPropagation();toggleExpand(${c.claim_id})">${chevron}</button>
        <span class="claim-card-number">Claim ${c.claim_number}</span>
        ${statusBadge}
      </div>
      <div class="claim-header-right">
        <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();openLinkElemModal(${c.claim_id})">+ Add Elements</button>
        <button class="claim-delete-btn" onclick="event.stopPropagation();deleteClaim(${c.claim_id})" title="Delete">🗑</button>
      </div>
    </div>
    ${parent ? `<div class="claim-dep-hint">↳ depends on Claim ${parent.claim_number}</div>` : ''}
    ${expanded ? renderElemTree(c.claim_id, linked) : ''}
  </div>`;
}

function renderElemTree(claimId, linked) {
  const q = (_elemTreeSearch[claimId] || '').toLowerCase();
  const filtered = q ? linked.filter(e => e.element_name.toLowerCase().includes(q)) : linked;
  const selInThis = _selectedElement.claimId === claimId;
  const selIdx = selInThis ? linked.findIndex(e => e.element_id === _selectedElement.elementId) : -1;
  const canUp = selIdx > 0, canDown = selIdx >= 0 && selIdx < linked.length - 1;
  const selId = selInThis ? _selectedElement.elementId : null;

  const rows = filtered.length === 0
    ? `<p class="ws-empty-msg" style="padding:8px 0">${q ? 'No match.' : 'No elements linked yet. Click "+ Add Elements".'}</p>`
    : filtered.map(el => {
        const isSel = _selectedElement.claimId === claimId && _selectedElement.elementId === el.element_id;
        const hasDef = el.definition_text && el.definition_text.trim();
        return `<div class="tree-elem-row ${isSel ? 'tree-elem-row--selected' : ''}" onclick="event.stopPropagation();selectClaimElement(${claimId},${el.element_id})">
          <span class="tree-elem-bullet">·</span>
          <span class="tree-elem-name">${esc(el.element_name)}</span>
          ${isSel ? '<span class="tree-elem-selected-badge">SELECTED</span>' : ''}
          <div class="tree-elem-actions">
            <span class="tree-elem-def-icon ${hasDef ? 'def-icon--ready' : 'def-icon--incomplete'}" title="${hasDef ? 'Definition complete' : 'Definition missing'}">${hasDef ? '✓' : '⚠'}</span>
            <button class="tree-elem-unlink-btn" onclick="event.stopPropagation();unlinkElem(${claimId},${el.element_id})" title="Unlink">🗑</button>
          </div>
        </div>`;
      }).join('');

  return `
  <div class="claim-elem-tree">
    <div class="claim-elem-tree-hdr">
      <span class="elem-tree-label">ELEMENT TREE</span>
      <div class="elem-tree-controls">
        <button class="elem-tree-ctrl-btn${canUp ? '' : ' elem-tree-ctrl-btn--disabled'}" ${canUp ? `onclick="event.stopPropagation();reorderElem(${claimId},${selId},'up')"` : 'disabled'} title="Move up">∧</button>
        <button class="elem-tree-ctrl-btn${canDown ? '' : ' elem-tree-ctrl-btn--disabled'}" ${canDown ? `onclick="event.stopPropagation();reorderElem(${claimId},${selId},'down')"` : 'disabled'} title="Move down">∨</button>
        <button class="elem-tree-ctrl-btn" onclick="event.stopPropagation();refreshClaimElems(${claimId})" title="Refresh">↻</button>
      </div>
    </div>
    <div class="elem-tree-search-row">
      <div class="search-box" style="margin:4px 0"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input type="text" placeholder="Search elements" value="${esc(_elemTreeSearch[claimId]||'')}"
               oninput="event.stopPropagation();filterTree(${claimId},this.value)" onclick="event.stopPropagation()">
      </div>
    </div>
    ${linked.length > 0 ? `<div class="elem-tree-stats"><span>${filtered.length} visible</span><span>${linked.length} linked</span></div>` : ''}
    ${rows}
  </div>`;
}

// ── Claim actions ───────────────────────────────────────────────
function selectClaim(claimId) {
  _selectedClaimId = claimId;
  renderClaimList();
  updateQueueHint();
  onClaimSelected(claimId);
}

function toggleExpand(claimId) { _claimExpanded[claimId] = !(_claimExpanded[claimId] !== false); renderClaimList(); }

function selectClaimElement(claimId, elementId) {
  _selectedElement = { claimId, elementId };
  renderClaimList();
  openElemEditModal(elementId);
}

function filterTree(claimId, val) {
  _elemTreeSearch[claimId] = val;
  renderClaimList();
  const inp = document.querySelector(`[data-search-claim="${claimId}"]`);
  if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
}

async function refreshClaimElems(claimId) {
  try { _claimElements[claimId] = await api('/patents/' + _patentId + '/claims/' + claimId + '/elements'); renderClaimList(); } catch (e) { console.error(e); }
}

async function reorderElem(claimId, elementId, direction) {
  try {
    await api('/patents/' + _patentId + '/claims/' + claimId + '/elements/' + elementId, { method: 'PATCH', body: JSON.stringify({ direction }) });
    _claimElements[claimId] = await api('/patents/' + _patentId + '/claims/' + claimId + '/elements');
    renderClaimList();
  } catch (e) { alert(e.message); }
}

async function unlinkElem(claimId, elementId) {
  try {
    await api('/patents/' + _patentId + '/claims/' + claimId + '/elements/' + elementId, { method: 'DELETE' });
    if (_selectedElement.claimId === claimId && _selectedElement.elementId === elementId) _selectedElement = { claimId: null, elementId: null };
    _claimElements[claimId] = await api('/patents/' + _patentId + '/claims/' + claimId + '/elements');
    renderClaimList();
  } catch (e) { alert(e.message); }
}

async function deleteClaim(claimId) {
  if (!confirm('Delete this claim?')) return;
  try {
    await api('/patents/' + _patentId + '/claims/' + claimId, { method: 'DELETE' });
    delete _claimElements[claimId];
    if (_selectedClaimId === claimId) { _selectedClaimId = null; resetDraftPanel(); updateQueueHint(); }
    _claims = await api('/patents/' + _patentId + '/claims');
    renderClaimList();
  } catch (e) { alert(e.message); }
}

// ── Add Claim Modal ─────────────────────────────────────────────
function openAddClaimModal() {
  document.querySelectorAll('input[name="claimDepType"]').forEach(r => r.checked = r.value === 'independent');
  document.getElementById('claimCategory').value = 'apparatus';
  document.getElementById('parentClaimSection').style.display = 'none';
  const sel = document.getElementById('parentClaimSelect');
  sel.innerHTML = '<option value="">— select —</option>' + _claims.map(c => `<option value="${c.claim_id}">Claim ${c.claim_number}</option>`).join('');
  document.getElementById('addClaimModal').classList.add('active');
}
function toggleParentClaim() { document.getElementById('parentClaimSection').style.display = document.querySelector('input[name="claimDepType"]:checked').value === 'dependent' ? 'block' : 'none'; }

async function submitAddClaim() {
  const dep = document.querySelector('input[name="claimDepType"]:checked').value;
  const cat = document.getElementById('claimCategory').value;
  let pid = null;
  if (dep === 'dependent') { pid = parseInt(document.getElementById('parentClaimSelect').value); if (!pid) { alert('Select parent.'); return; } }
  try {
    await api('/patents/' + _patentId + '/claims', { method: 'POST', body: JSON.stringify({ claim_dependency_type: dep, claim_category: cat, parent_claim_id: pid }) });
    closeModal('addClaimModal');
    _claims = await api('/patents/' + _patentId + '/claims');
    _claims.forEach(c => { if (!_claimElements[c.claim_id]) _claimElements[c.claim_id] = []; if (_claimExpanded[c.claim_id] === undefined) _claimExpanded[c.claim_id] = true; });
    renderClaimList();
  } catch (e) { alert(e.message); }
}

// ── Link Element Modal ──────────────────────────────────────────
let _linkTargetClaimId = null;
function openLinkElemModal(claimId) {
  _linkTargetClaimId = claimId;
  const claim = _claims.find(c => c.claim_id === claimId);
  document.getElementById('linkElemTitle').textContent = claim ? 'Add Elements to Claim ' + claim.claim_number : 'Add Elements';
  const linked = new Set((_claimElements[claimId] || []).map(e => e.element_id));
  const avail = _elements.filter(e => !linked.has(e.element_id));
  const sel = document.getElementById('linkElemSelect');
  sel.innerHTML = avail.length === 0 ? '<option value="">All elements already linked</option>'
    : '<option value="">— select —</option>' + avail.map(e => `<option value="${e.element_id}">${esc(e.element_name)}${e.reference_number != null ? ' (Ref ' + e.reference_number + ')' : ''}</option>`).join('');
  document.getElementById('linkElementModal').classList.add('active');
}

async function submitLinkElement() {
  const eid = parseInt(document.getElementById('linkElemSelect').value);
  if (!eid) { alert('Select an element.'); return; }
  try {
    await api('/patents/' + _patentId + '/claims/' + _linkTargetClaimId + '/elements', { method: 'POST', body: JSON.stringify({ element_id: eid }) });
    _claimElements[_linkTargetClaimId] = await api('/patents/' + _patentId + '/claims/' + _linkTargetClaimId + '/elements');
    closeModal('linkElementModal');
    renderClaimList();
  } catch (e) { alert(e.message); }
}

// ═══════════════════════════════════════════════════════════════
// Element Queue (Center) — with drag support
// ═══════════════════════════════════════════════════════════════
function renderElementQueue() {
  const c = document.getElementById('elementQueue');
  if (!c) return;
  if (_elements.length === 0) { c.innerHTML = '<p class="ws-empty-msg">No elements yet. Add an element to start.</p>'; return; }
  c.innerHTML = _elements.map(el => `
    <div class="element-card" draggable="true"
         ondragstart="event.dataTransfer.setData('text/plain','${el.element_id}');event.dataTransfer.effectAllowed='copy'">
      <div class="element-drag-handle" aria-hidden="true">
        <svg viewBox="0 0 10 16" fill="currentColor" width="10" height="16">
          <circle cx="3" cy="2" r="1.5"/><circle cx="7" cy="2" r="1.5"/>
          <circle cx="3" cy="7" r="1.5"/><circle cx="7" cy="7" r="1.5"/>
          <circle cx="3" cy="12" r="1.5"/><circle cx="7" cy="12" r="1.5"/>
        </svg>
      </div>
      <div class="element-card-main">
        <div class="element-card-name">${esc(el.element_name)}</div>
        <div class="element-card-meta">${el.reference_number != null ? 'Ref ' + el.reference_number : '<span style="color:var(--text-muted)">No ref</span>'}</div>
      </div>
      <div class="element-card-actions">
        <span class="element-drag-label">DRAG</span>
        <button class="btn btn-sm btn-ghost element-edit-btn" onclick="openElemEditModal(${el.element_id})">Edit</button>
        <button class="element-delete-btn" onclick="deleteElement(${el.element_id})" title="Delete">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
          </svg>
        </button>
      </div>
    </div>`).join('');
}

function updateQueueHint() {
  const hint = document.getElementById('queueHint');
  if (!hint) return;
  if (!_selectedClaimId) { hint.textContent = 'No claim selected.'; return; }
  const cl = _claims.find(c => c.claim_id === _selectedClaimId);
  hint.textContent = cl ? 'Selected: Claim ' + cl.claim_number : 'No claim selected.';
}

// ── Drag & Drop ─────────────────────────────────────────────────
async function dropElementOnClaim(event, claimId) {
  const eid = parseInt(event.dataTransfer.getData('text/plain'));
  if (!eid || !_patentId) return;
  const linked = (_claimElements[claimId] || []).map(e => e.element_id);
  if (linked.includes(eid)) return; // already linked
  try {
    await api('/patents/' + _patentId + '/claims/' + claimId + '/elements', { method: 'POST', body: JSON.stringify({ element_id: eid }) });
    _claimElements[claimId] = await api('/patents/' + _patentId + '/claims/' + claimId + '/elements');
    renderClaimList();
  } catch (e) { console.error('Drop failed:', e); }
}

// ── Add Element (opens Element Definition modal in create mode) ──
function openAddElementModal() {
  _elemDefMode = 'create';
  _elemDefId = null;
  document.getElementById('defElemName').value = '';
  document.getElementById('defElemRef').value = '';
  document.getElementById('defElemText').value = '';
  document.getElementById('defSaveStatus').innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Not saved yet';
  document.getElementById('elemContextRow').style.display = 'none';
  document.getElementById('linkedClaimsList').innerHTML = '<p style="font-size:12px;color:var(--text-muted)">No linked claims yet.</p>';
  document.getElementById('elemDefModal').classList.add('active');
  document.getElementById('defElemName').focus();
}

async function deleteElement(elementId) {
  if (!confirm('Delete this element?')) return;
  try {
    await api('/patents/' + _patentId + '/elements/' + elementId, { method: 'DELETE' });
    _elements = await api('/patents/' + _patentId + '/elements');
    renderElementQueue();
    // Reload all claim elements
    for (const c of _claims) { _claimElements[c.claim_id] = await api('/patents/' + _patentId + '/claims/' + c.claim_id + '/elements').catch(() => []); }
    renderClaimList();
  } catch (e) { alert(e.message); }
}

// ═══════════════════════════════════════════════════════════════
// Element Definition Modal
// ═══════════════════════════════════════════════════════════════
let _elemDefMode = 'create';
let _elemDefId = null;

function openElemEditModal(elementId) {
  const el = _elements.find(e => e.element_id === elementId);
  if (!el) return;
  _elemDefMode = 'edit';
  _elemDefId = elementId;
  document.getElementById('defElemName').value = el.element_name;
  document.getElementById('defElemRef').value = el.reference_number ?? '';
  document.getElementById('defElemText').value = el.definition_text ?? '';
  document.getElementById('defSaveStatus').textContent = 'Not saved yet';
  document.getElementById('elemContextRow').style.display = 'flex';
  document.getElementById('elemBreadcrumb').textContent = 'CLAIMS › ' + el.element_name;
  document.getElementById('elemIdBadge').textContent = 'ID: ' + el.element_id;

  // Load linked claims
  api('/patents/' + _patentId + '/elements/' + elementId + '/links').then(links => {
    const list = document.getElementById('linkedClaimsList');
    if (links.length === 0) { list.innerHTML = '<p style="font-size:12px;color:var(--text-muted)">No linked claims yet.</p>'; return; }
    list.innerHTML = links.map(l => `<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:12px"><span>Claim ${l.claim_number}</span><span style="color:var(--text-muted)">Slot ${l.order_index}</span></div>`).join('');
  }).catch(() => {});

  document.getElementById('elemDefModal').classList.add('active');
}

async function submitElemDef() {
  const name = document.getElementById('defElemName').value.trim();
  if (!name) { alert('Name required.'); return; }
  const ref = document.getElementById('defElemRef').value.trim();
  const defText = document.getElementById('defElemText').value.trim();
  try {
    if (_elemDefMode === 'edit') {
      await api('/patents/' + _patentId + '/elements/' + _elemDefId, { method: 'PATCH', body: JSON.stringify({ element_name: name, reference_number: ref ? parseInt(ref) : null, definition_text: defText || null }) });
    } else {
      await api('/patents/' + _patentId + '/elements', { method: 'POST', body: JSON.stringify({ element_name: name, reference_number: ref ? parseInt(ref) : null, definition_text: defText || null }) });
    }
    closeModal('elemDefModal');
    _elements = await api('/patents/' + _patentId + '/elements');
    renderElementQueue();
    for (const c of _claims) { _claimElements[c.claim_id] = await api('/patents/' + _patentId + '/claims/' + c.claim_id + '/elements').catch(() => []); }
    renderClaimList();
  } catch (e) { alert(e.message); }
}

async function aiSuggestDef() {
  if (!_dataLoaded) { alert('Upload Excel data first.'); return; }
  const name = document.getElementById('defElemName').value.trim();
  if (!name) { alert('Enter element name first.'); return; }
  const btn = document.getElementById('btnAiSuggest');
  btn.innerHTML = '<span class="spinner"></span> Generating…'; btn.disabled = true;
  try {
    const r = await api('/rag/generate-definition', { method: 'POST', body: JSON.stringify({ element_name: name, context: _context, bbf_text: _bbfText, top_k: 5 }) });
    document.getElementById('defElemText').value = r.final_definition || '';
    document.getElementById('defSaveStatus').textContent = 'AI suggestion applied — unsaved';
    // Show suggestions
    const sc = document.getElementById('suggestionsContent');
    const ret = r.retrieved_examples || [];
    sc.innerHTML = `<div class="suggestions-grid">
      <div class="suggestion-col"><h5>RAG Fragment</h5><p style="font-size:12px;color:var(--text-secondary)">${esc(r.rag_fragment||'')}</p>
        <h5 style="margin-top:12px">Retrieved Examples</h5><ul>${ret.map(x => `<li onclick="document.getElementById('defElemText').value='${escAttr(x.definition_en)}'" title="${esc(x.title_en||'')}"><strong>${esc(x.element_name_en)}</strong><br><span style="font-size:11px;color:var(--text-muted)">${esc((x.definition_en||'').substring(0,120))}…</span></li>`).join('')}</ul></div>
      <div class="suggestion-col"><h5>BBF Fragment</h5><p style="font-size:12px;color:var(--text-secondary)">${esc(r.bbf_fragment||'')||'<em>No BBF</em>'}</p></div>
      <div class="suggestion-col"><h5>Final Definition</h5><p style="font-size:13px;font-weight:500">${esc(r.final_definition||'')}</p></div>
    </div>`;
    document.getElementById('suggestionsModal').classList.add('active');
  } catch (e) { alert(e.message); }
  finally { btn.innerHTML = '⚡ AI Suggest Definition'; btn.disabled = false; }
}

// ═══════════════════════════════════════════════════════════════
// Draft Editor (Right Panel)
// ═══════════════════════════════════════════════════════════════
function resetDraftPanel() {
  document.getElementById('draftClaimLabel').textContent = 'Select a claim to edit its draft text.';
  document.getElementById('draftBody').innerHTML = '<textarea class="draft-textarea" id="draftTextarea" placeholder="Select a claim or use Assemble / AI Draft buttons…"></textarea>';
  document.getElementById('btnSaveDraft').disabled = true;
}

function onClaimSelected(claimId) {
  const cl = _claims.find(c => c.claim_id === claimId);
  if (!cl) return;
  document.getElementById('draftClaimLabel').textContent = `Claim ${cl.claim_number} — ${cl.claim_dependency_type}, ${cl.claim_category}`;
  document.getElementById('draftBody').innerHTML = '<textarea class="draft-textarea" id="draftTextarea" placeholder="Enter draft text for this claim…"></textarea>';
  document.getElementById('draftTextarea').value = cl.claim_text || '';
  document.getElementById('btnSaveDraft').disabled = false;
}

async function saveDraftText() {
  if (!_selectedClaimId) { alert('Please select a claim first to save draft text.'); return; }
  const ta = document.getElementById('draftTextarea');
  if (!ta) return;
  try {
    await api('/patents/' + _patentId + '/claims/' + _selectedClaimId + '/text', { method: 'PATCH', body: JSON.stringify({ claim_text: ta.value }) });
    const cl = _claims.find(c => c.claim_id === _selectedClaimId);
    if (cl) cl.claim_text = ta.value;
  } catch (e) { alert(e.message); }
}

function insertDraftReport() {
  const defs = [];
  _claims.forEach(cl => { (_claimElements[cl.claim_id] || []).forEach(el => {
    if (el.definition_text) defs.push(el.element_name + (el.reference_number ? ' (' + el.reference_number + ')' : '') + ': ' + el.definition_text);
  }); });
  const report = 'ELEMENT DEFINITIONS REPORT\n' + '═'.repeat(40) + '\n\n' + defs.join('\n\n') + '\n';
  let ta = document.getElementById('draftTextarea');
  if (!ta) { document.getElementById('draftBody').innerHTML = '<textarea class="draft-textarea" id="draftTextarea"></textarea>'; ta = document.getElementById('draftTextarea'); }
  ta.value = report;
}

function goToAiDraft() {
  let text = '';
  _claims.forEach(cl => {
    text += 'Claim ' + cl.claim_number + ':\n';
    (_claimElements[cl.claim_id] || []).forEach(el => {
      if (el.definition_text) text += '  ' + el.element_name + (el.reference_number ? ' (' + el.reference_number + ')' : '') + ': ' + el.definition_text + '\n';
    });
    text += '\n';
  });
  let ta = document.getElementById('draftTextarea');
  if (!ta) { document.getElementById('draftBody').innerHTML = '<textarea class="draft-textarea" id="draftTextarea"></textarea>'; ta = document.getElementById('draftTextarea'); }
  ta.value = text;
}

// ═══════════════════════════════════════════════════════════════
// Draft Composer
// ═══════════════════════════════════════════════════════════════
function openComposer() {
  let t = '';
  _claims.forEach(cl => {
    t += 'Claim ' + cl.claim_number + ':\n';
    (_claimElements[cl.claim_id] || []).forEach(el => {
      t += '  - ' + el.element_name + (el.reference_number ? ' (' + el.reference_number + ')' : '');
      if (el.definition_text) t += ' — ' + el.definition_text;
      t += '\n';
    });
    t += '\n';
  });
  document.getElementById('composerClaimsInput').value = t;
  document.getElementById('composerDraftOutput').innerHTML = _composerDraft || '<p style="color:var(--text-muted)">Click "Generate Draft"…</p>';
  showPage('page-composer');
}

async function generateDraft() {
  const btn = document.getElementById('btnGenerateDraft');
  btn.innerHTML = '<span class="spinner"></span> Generating…'; btn.disabled = true;
  const ct = document.getElementById('composerClaimsInput').value;
  let d = '<h4>1. Title</h4><p>' + esc(document.getElementById('navPatentName').textContent || 'Patent') + '</p>';
  d += '<h4>2. Technical Field</h4><p>The present invention relates to ' + esc(_context || 'the described technical field') + '.</p>';
  d += '<h4>3. Element Definitions</h4>';
  _claims.forEach(cl => { (_claimElements[cl.claim_id] || []).forEach(el => { if (el.definition_text) d += '<p><strong>' + esc(el.element_name) + '</strong>: ' + esc(el.definition_text) + '</p>'; }); });
  d += '<h4>4. Claims</h4><pre style="white-space:pre-wrap;color:var(--text-secondary)">' + esc(ct) + '</pre>';
  await new Promise(r => setTimeout(r, 400));
  _composerDraft = d;
  document.getElementById('composerDraftOutput').innerHTML = d;
  btn.innerHTML = '⚡ Generate Draft'; btn.disabled = false;
}
function backToEditor() { showPage('page-editor'); }

// ═══════════════════════════════════════════════════════════════
// Extract Pipeline
// ═══════════════════════════════════════════════════════════════
function openExtractModal() {
  document.getElementById('bbfFileInput').value = '';
  document.getElementById('reportFileInput').value = '';
  document.getElementById('bbfFileName').textContent = 'Click to select BBF file';
  document.getElementById('reportFileName').textContent = 'Click to select Report file';
  document.getElementById('extractStatus').innerHTML = '';
  document.getElementById('btnExtract').disabled = false;
  document.getElementById('btnExtract').innerHTML = '⚡ Extract Elements';
  document.getElementById('extractModal').classList.add('active');
}

async function startExtraction() {
  const bbf = document.getElementById('bbfFileInput').files[0];
  const rep = document.getElementById('reportFileInput').files[0];
  if (!bbf || !rep) { alert('Both files required.'); return; }
  const btn = document.getElementById('btnExtract');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Extracting…';
  document.getElementById('extractStatus').innerHTML = '<span class="loading-text"><span class="spinner"></span> Running pipeline…</span>';
  try {
    const form = new FormData(); form.append('bbf', bbf); form.append('report', rep);
    await fetch('/api/pipeline/extract-elements', { method: 'POST', body: form });
    const poll = setInterval(async () => {
      const s = await api('/pipeline/extract-elements-status');
      if (s.status === 'done') {
        clearInterval(poll);
        document.getElementById('extractStatus').innerHTML = '<span style="color:var(--success)">✓ Extracted ' + s.elements.length + ' elements!</span>';
        btn.innerHTML = '⚡ Extract Elements'; btn.disabled = false;
        // Store BBF text for AI Suggest Definition
        if (s.bbf_text) _bbfText = s.bbf_text;
        await addExtractedElements(s.elements);
      } else if (s.status === 'error') {
        clearInterval(poll);
        document.getElementById('extractStatus').innerHTML = '<span style="color:var(--danger)">Error: ' + (s.error || 'Failed') + '</span>';
        btn.innerHTML = '⚡ Extract Elements'; btn.disabled = false;
      }
    }, 2000);
  } catch (e) {
    document.getElementById('extractStatus').innerHTML = '<span style="color:var(--danger)">Failed: ' + e.message + '</span>';
    btn.innerHTML = '⚡ Extract Elements'; btn.disabled = false;
  }
}

async function addExtractedElements(elems) {
  if (!_patentId) return;
  for (const el of elems) {
    const name = (el.name_en || '').trim();
    if (!name || _elements.find(e => e.element_name.toLowerCase() === name.toLowerCase())) continue;
    try { await api('/patents/' + _patentId + '/elements', { method: 'POST', body: JSON.stringify({ element_name: name, definition_text: el.definition_en || null }) }); } catch (_) {}
  }
  _elements = await api('/patents/' + _patentId + '/elements');
  renderElementQueue();
}

// ═══════════════════════════════════════════════════════════════
// Upload / Settings
// ═══════════════════════════════════════════════════════════════
async function handleFileUpload(input) {
  const file = input.files[0];
  if (!file) return;
  const st = document.getElementById('uploadStatus');
  st.innerHTML = '<span class="loading-text"><span class="spinner"></span> Uploading…</span>';
  try {
    const form = new FormData(); form.append('file', file);
    const res = await fetch('/api/rag/upload-excel', { method: 'POST', body: form });
    if (!res.ok) { const e = await res.json().catch(() => ({})); st.innerHTML = '<span style="color:var(--danger)">Error: ' + (e.detail || 'Upload failed') + '</span>'; return; }
    st.innerHTML = '<span class="loading-text"><span class="spinner"></span> Building embeddings… May take a few minutes.</span>';
    const poll = setInterval(async () => {
      try {
        const s = await api('/rag/data-status');
        if (s.loaded && (s.status === 'done' || s.status === 'idle')) {
          clearInterval(poll); _dataLoaded = true;
          st.innerHTML = '<span style="color:var(--success)">✓ Loaded ' + (s.count || '') + ' docs. FAISS index ready.</span>';
          document.getElementById('statusBadge').textContent = 'Data Loaded';
          document.getElementById('statusBadge').classList.add('ws-status-badge--loaded');
        } else if (s.status === 'error') { clearInterval(poll); st.innerHTML = '<span style="color:var(--danger)">Error: ' + (s.error||'') + '</span>'; }
      } catch (_) {}
    }, 2000);
  } catch (e) { st.innerHTML = '<span style="color:var(--danger)">Failed: ' + e.message + '</span>'; }
}

function openSettingsModal() {
  document.getElementById('settingsContext').value = _context;
  document.getElementById('settingsBBF').value = _bbfText;
  // Load current LLM URL
  api('/rag/llm-status').then(s => {
    document.getElementById('settingsLLMUrl').value = s.url || '';
  }).catch(() => {});
  document.getElementById('settingsModal').classList.add('active');
}
async function saveSettings() {
  _context = document.getElementById('settingsContext').value;
  _bbfText = document.getElementById('settingsBBF').value;
  const llmUrl = document.getElementById('settingsLLMUrl').value.trim();
  if (llmUrl) {
    try { await api('/rag/set-llm-url', { method: 'POST', body: JSON.stringify({ url: llmUrl }) }); } catch (_) {}
  }
  closeModal('settingsModal');
}
function openUploadModal() { document.getElementById('uploadModal').classList.add('active'); }

// ═══════════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const rag = await api('/rag/data-status').catch(() => ({ loaded: false }));
    _dataLoaded = rag.loaded;
    if (_dataLoaded) { document.getElementById('statusBadge').textContent = 'Data Loaded'; document.getElementById('statusBadge').classList.add('ws-status-badge--loaded'); }
  } catch (_) {}
  try { _projects = await api('/patents'); renderProjectList(); } catch (_) {}

  // Load cached BBF text and LLM URL
  try {
    const ps = await api('/pipeline/extract-elements-status');
    if (ps.bbf_text) _bbfText = ps.bbf_text;
  } catch (_) {}
  try {
    const ls = await api('/rag/llm-status');
    if (ls.url) console.log('[LLM] Remote URL:', ls.url);
  } catch (_) {}

  showPage('page-dashboard');
});
