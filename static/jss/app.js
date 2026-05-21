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
let _editProjectId = null;

// ── Helpers ─────────────────────────────────────────────────────
function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function escAttr(s) { return (s || '').replace(/'/g, "\\'").replace(/\n/g, ' ').substring(0, 200); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }

async function api(path, opts = {}) {
  const h = { ...opts.headers };
  if (opts.body && typeof opts.body === 'string') h['Content-Type'] = 'application/json';
  const res = await fetch('/api' + path, { ...opts, headers: h });
  if (!res.ok) { const e = await res.json().catch(() => ({ detail: 'Request failed' })); const msg = Array.isArray(e.detail) ? e.detail.map(x => x.msg || JSON.stringify(x)).join('; ') : (e.detail || 'Request failed'); throw new Error(msg); }
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
  document.getElementById('navPatentOwner').textContent = '';
  const rb = document.getElementById('navRenameBtn'); if (rb) rb.style.display = 'none';
  document.body.classList.remove('assistant-active');
  if (typeof toggleAssistantDrawer === 'function') toggleAssistantDrawer(false);
  if (typeof _clearAssistantCache === 'function') _clearAssistantCache();
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
    <div class="project-item project-item--stacked" onclick="openProject(${p.patent_id})">
      <div class="project-item-info">
        <div class="project-item-name">${esc(p.patent_name)}</div>
        <div class="project-item-sub">${esc(p.patent_owner||'')}</div>
      </div>
      <div class="project-item-actions">
        <button class="btn btn-sm btn-ghost" onclick="event.stopPropagation();openPatentInputs(${p.patent_id})" title="Patent Inputs">📋 Inputs</button>
        <button class="btn btn-sm btn-ghost" onclick="event.stopPropagation();openEditProject(${p.patent_id})" title="Edit project">✎ Edit</button>
        <button class="btn btn-sm btn-ghost project-item-delete" onclick="event.stopPropagation();deleteProject(${p.patent_id}, '${escAttr(p.patent_name)}')" title="Delete project">🗑 Delete</button>
        <span class="btn btn-sm btn-ghost">Open</span>
      </div>
    </div>`).join('');
}

async function deleteProject(patentId, patentName) {
  // Two-step confirm — deletion is destructive (claims, elements,
  // documents, all related data are dropped server-side).
  const confirmed = confirm(
    `Delete project "${patentName}"?\n\n` +
    'This will permanently remove all claims, elements, documents, ' +
    'invention disclosure, research report, and inventor Q&A for this project.\n\n' +
    'This cannot be undone.'
  );
  if (!confirmed) return;
  try {
    await api('/patents/' + patentId, { method: 'DELETE' });
    // If the deleted project is currently open, snap back to the dashboard.
    if (_patentId === patentId) {
      goHome();
    }
    _projects = await api('/patents');
    renderProjectList();
  } catch (e) {
    alert('Delete failed: ' + e.message);
  }
}

function createNewProject() {
  document.getElementById('newProjectName').value = '';
  document.getElementById('newProjectOwner').value = '';
  document.getElementById('newProjectDomain').value = '';
  document.getElementById('newProjectModal').classList.add('active');
}

async function submitNewProject() {
  const name = document.getElementById('newProjectName').value.trim();
  const owner = document.getElementById('newProjectOwner').value.trim();
  const domain = document.getElementById('newProjectDomain').value.trim();
  if (!name) { alert('Project name is required'); return; }
  if (!owner) { alert('Patent owner is required'); return; }
  try {
    const payload = { patent_name: name, patent_owner: owner };
    if (domain) payload.domain = domain;
    const p = await api('/patents', { method: 'POST', body: JSON.stringify(payload) });
    _projects.unshift(p);
    renderProjectList();
    closeModal('newProjectModal');
  } catch (e) { alert(e.message); }
}

function openEditProject(patentId) {
  const p = _projects.find(x => x.patent_id === patentId);
  if (!p) return;
  _editProjectId = patentId;
  document.getElementById('editProjectName').value = p.patent_name || '';
  document.getElementById('editProjectOwner').value = p.patent_owner || '';
  document.getElementById('editProjectDomain').value = p.domain || '';
  document.getElementById('editProjectModal').classList.add('active');
}

async function submitEditProject() {
  if (!_editProjectId) return;
  const name = document.getElementById('editProjectName').value.trim();
  const owner = document.getElementById('editProjectOwner').value.trim();
  const domain = document.getElementById('editProjectDomain').value.trim();
  if (!name) { alert('Project name is required'); return; }
  if (!owner) { alert('Patent owner is required'); return; }
  try {
    const updated = await api('/patents/' + _editProjectId, { method: 'PATCH', body: JSON.stringify({ patent_name: name, patent_owner: owner, domain: domain }) });
    const idx = _projects.findIndex(x => x.patent_id === _editProjectId);
    if (idx !== -1) _projects[idx] = { ..._projects[idx], patent_name: updated.patent_name, patent_owner: updated.patent_owner, domain: updated.domain };
    renderProjectList();
    if (_patentId === _editProjectId) {
      document.getElementById('navPatentName').textContent = updated.patent_name;
      document.getElementById('navPatentOwner').textContent = updated.patent_owner ? '— ' + updated.patent_owner : '';
    }
    _editProjectId = null;
    closeModal('editProjectModal');
  } catch (e) { alert(e.message); }
}

function renameCurrentProject() {
  if (!_patentId) return;
  openEditProject(_patentId);
}

async function openProject(patentId) {
  _patentId = patentId;
  _context = '';
  _bbfText = '';
  _composerDraft = '';
  if (typeof _clearAssistantCache === 'function') _clearAssistantCache();
  document.body.classList.add('assistant-active');
  try {
    const patent = await api('/patents/' + patentId);
    document.getElementById('navPatentName').textContent = patent.patent_name;
    document.getElementById('navPatentOwner').textContent = patent.patent_owner ? '— ' + patent.patent_owner : '';
    const rb = document.getElementById('navRenameBtn'); if (rb) rb.style.display = 'inline-flex';

    _context = patent.invention_context || '';
    _composerDraft = patent.patent_draft || '';

    // Pull bbf_text alongside claims/elements so AI Suggest Definition
    // sees it without requiring a Settings modal open.
    const [claims, elements, idf] = await Promise.all([
      api('/patents/' + patentId + '/claims'),
      api('/patents/' + patentId + '/elements'),
      api('/patents/' + patentId + '/invention-disclosure').catch(() => null),
    ]);
    _claims = claims;
    _elements = elements;
    if (idf && idf.bbf_text) _bbfText = idf.bbf_text;

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
  const parentIds = c.parent_claim_ids || [];
  const parents = _claims.filter(p => parentIds.includes(p.claim_id));

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
      </div>
    </div>
    <div style="display:flex;justify-content:flex-end;gap:6px;padding:0 12px 6px 12px;">
      <button class="btn btn-sm" onclick="event.stopPropagation();openEditClaimModal(${c.claim_id})" title="Edit claim">✎ Edit</button>
      <button class="claim-delete-btn" onclick="event.stopPropagation();deleteClaim(${c.claim_id})" title="Delete claim">🗑</button>
    </div>
    ${parents.length ? `<div class="claim-dep-hint">↳ depends on ${parents.map(p => 'Claim ' + p.claim_number).join(', ')}</div>` : ''}
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

// ── Edit Claim Modal ────────────────────────────────────────────
let _editClaimId = null;

function openEditClaimModal(claimId) {
  _editClaimId = claimId;
  const claim = _claims.find(c => c.claim_id === claimId);
  if (!claim) return;

  // Set current values
  document.querySelectorAll('input[name="editClaimDepType"]').forEach(r => {
    r.checked = r.value === claim.claim_dependency_type;
  });
  document.getElementById('editClaimCategory').value = claim.claim_category;

  // Populate parent checkboxes (all other claims)
  const container = document.getElementById('editParentClaimCheckboxes');
  const currentParentIds = claim.parent_claim_ids || [];
  const others = _claims.filter(c => c.claim_id !== claimId);
  container.innerHTML = others.length === 0
    ? '<p style="font-size:12px;color:var(--text-muted)">No other claims available.</p>'
    : others.map(c => `
        <label style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:13px;cursor:pointer;">
          <input type="checkbox" name="editParentCheckbox" value="${c.claim_id}" ${currentParentIds.includes(c.claim_id) ? 'checked' : ''}>
          Claim ${c.claim_number} — ${c.claim_dependency_type}, ${c.claim_category}
        </label>`).join('');

  // Show/hide parent section
  document.getElementById('editParentSection').style.display =
    claim.claim_dependency_type === 'dependent' ? 'block' : 'none';

  document.getElementById('editClaimModal').classList.add('active');
}

function onEditDepTypeChange() {
  const dep = document.querySelector('input[name="editClaimDepType"]:checked')?.value;
  document.getElementById('editParentSection').style.display =
    dep === 'dependent' ? 'block' : 'none';
}

async function submitEditClaim() {
  if (!_editClaimId) return;
  const dep = document.querySelector('input[name="editClaimDepType"]:checked')?.value;
  const cat = document.getElementById('editClaimCategory').value;

  let parentClaimIds = [];
  if (dep === 'dependent') {
    parentClaimIds = [...document.querySelectorAll('input[name="editParentCheckbox"]:checked')]
      .map(cb => parseInt(cb.value, 10));
    if (parentClaimIds.length === 0) {
      alert('Please select at least one parent claim.');
      return;
    }
  }

  try {
    await api('/patents/' + _patentId + '/claims/' + _editClaimId, {
      method: 'PATCH',
      body: JSON.stringify({ claim_dependency_type: dep, claim_category: cat, parent_claim_ids: parentClaimIds }),
    });
    closeModal('editClaimModal');
    _claims = await api('/patents/' + _patentId + '/claims');
    renderClaimList();
  } catch (e) { alert(e.message || JSON.stringify(e)); }
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
  let parentClaimIds = [];
  if (dep === 'dependent') {
    const pid = parseInt(document.getElementById('parentClaimSelect').value);
    if (!pid) { alert('Select parent.'); return; }
    parentClaimIds = [pid];
  }
  try {
    await api('/patents/' + _patentId + '/claims', { method: 'POST', body: JSON.stringify({ claim_dependency_type: dep, claim_category: cat, parent_claim_ids: parentClaimIds }) });
    closeModal('addClaimModal');
    _claims = await api('/patents/' + _patentId + '/claims');
    _claims.forEach(c => { if (!_claimElements[c.claim_id]) _claimElements[c.claim_id] = []; if (_claimExpanded[c.claim_id] === undefined) _claimExpanded[c.claim_id] = true; });
    renderClaimList();
  } catch (e) { alert(e.message || JSON.stringify(e)); }
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
        <div class="element-card-meta">Ref ${esc(el.reference_number)}</div>
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

// ── Drag autoscroll ─────────────────────────────────────────────
// Browsers don't natively scroll the page (or scrollable containers)
// while a drag is in progress, so dragging an element from far below
// the visible claim cards has no way to reach them. We watch dragover
// at document level: when the cursor sits near the top/bottom edge
// of either the window or the closest scrollable ancestor, we scroll
// at a speed proportional to how deep into the trigger zone the
// cursor is. Stops on drop / dragend.

// Trigger zone covers the upper / lower third of the viewport — ~360 px
// on a typical laptop screen. Generous so the user does not need to
// aim precisely at the very edge while dragging.
const _AUTOSCROLL_EDGE_FRAC = 0.33;
const _AUTOSCROLL_EDGE_MIN = 200;
const _AUTOSCROLL_EDGE_MAX = 400;
const _AUTOSCROLL_MAX_SPEED = 90; // px per frame near the very edge
const _AUTOSCROLL_MIN_SPEED = 28; // px per frame anywhere in the band

function _autoscrollEdge() {
  return Math.min(
    _AUTOSCROLL_EDGE_MAX,
    Math.max(_AUTOSCROLL_EDGE_MIN, window.innerHeight * _AUTOSCROLL_EDGE_FRAC),
  );
}

let _dragAutoscrollRaf = null;
let _dragAutoscrollLastY = 0;

function _findScrollableAncestor(el) {
  let node = el;
  while (node && node !== document.body) {
    const style = getComputedStyle(node);
    const oy = style.overflowY;
    if ((oy === 'auto' || oy === 'scroll') && node.scrollHeight > node.clientHeight) {
      return node;
    }
    node = node.parentElement;
  }
  return null;
}

function _stepDragAutoscroll() {
  const y = _dragAutoscrollLastY;
  const vh = window.innerHeight;
  const edge = _autoscrollEdge();
  const inTopZone = y < edge;
  const inBottomZone = vh - y < edge;

  if (!inTopZone && !inBottomZone) {
    _dragAutoscrollRaf = null;
    return;
  }

  // Speed curve: fraction from 0 (outer band edge) to 1 (very edge).
  // sqrt() gives a snappy ramp; clamp to MIN_SPEED so anywhere in the
  // band moves obviously.
  const _speed = (distFromEdge) => {
    const t = Math.max(0, 1 - distFromEdge / edge);
    return Math.max(_AUTOSCROLL_MIN_SPEED, _AUTOSCROLL_MAX_SPEED * Math.sqrt(t));
  };

  // 1. Try the closest scrollable ancestor of whatever sits under the
  //    cursor. Handles tall side panels (claim list, element queue)
  //    that scroll independently of the window.
  const target = document.elementFromPoint(window.innerWidth / 2, y);
  const scroller = _findScrollableAncestor(target);
  let scrolled = false;
  if (scroller) {
    const rect = scroller.getBoundingClientRect();
    if (y - rect.top < edge && scroller.scrollTop > 0) {
      scroller.scrollTop -= _speed(y - rect.top);
      scrolled = true;
    } else if (rect.bottom - y < edge
               && scroller.scrollTop + scroller.clientHeight < scroller.scrollHeight) {
      scroller.scrollTop += _speed(rect.bottom - y);
      scrolled = true;
    }
  }

  // 2. Fall back to the window when no inner scroller engaged.
  if (!scrolled) {
    if (inTopZone && window.scrollY > 0) {
      window.scrollBy(0, -_speed(y));
    } else if (inBottomZone) {
      window.scrollBy(0, _speed(vh - y));
    }
  }

  // Self-chain so scrolling continues even when the cursor is held
  // still at the edge — dragover events stop firing the moment the
  // user stops moving the mouse, but the scroll loop must not.
  _dragAutoscrollRaf = requestAnimationFrame(_stepDragAutoscroll);
}

function _onDragAutoscroll(event) {
  // `drag` events report (0, 0) in some browsers when the cursor is
  // outside a drop target — fall back to the last known Y so the
  // scroll keeps going while the cursor sits at the edge.
  if (event.clientY > 0) {
    _dragAutoscrollLastY = event.clientY;
  }
  const y = _dragAutoscrollLastY;
  const vh = window.innerHeight;
  const edge = _autoscrollEdge();
  // Kick off the loop the first time the cursor enters a trigger zone.
  if ((y < edge || vh - y < edge) && _dragAutoscrollRaf == null) {
    _dragAutoscrollRaf = requestAnimationFrame(_stepDragAutoscroll);
  }
}

function _stopDragAutoscroll() {
  if (_dragAutoscrollRaf != null) {
    cancelAnimationFrame(_dragAutoscrollRaf);
    _dragAutoscrollRaf = null;
  }
}

// HTML5 only emits dragover on *valid* drop targets, so without help
// it never fires while the cursor crosses empty space — which is
// exactly when autoscroll matters most. Two safeties:
//   1. A global capture-phase dragover handler that calls
//      preventDefault — this turns the whole page into a valid drop
//      target so dragover keeps firing wherever the cursor goes.
//   2. The `drag` event on the source element bubbles to document
//      regardless of what's underneath, as a backup.
// Either is sufficient on its own; we keep both for defense in depth.
document.addEventListener('dragover', (event) => {
  event.preventDefault();
  _onDragAutoscroll(event);
}, { capture: true });
document.addEventListener('drag', _onDragAutoscroll);
// Drops on empty space would otherwise trigger default browser navigation
// (it interprets the dataTransfer text as a URL) — preventDefault here
// keeps the page intact when the user releases outside a claim card.
document.addEventListener('drop', (event) => {
  event.preventDefault();
  _stopDragAutoscroll();
});
document.addEventListener('dragend', _stopDragAutoscroll);

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

const REF_NUMBER_PATTERN = /^(?=.*[A-Za-z0-9])[A-Za-z0-9'\-]{1,10}$/;

async function submitElemDef() {
  const name = document.getElementById('defElemName').value.trim();
  if (!name) { alert('Name required.'); return; }
  const ref = document.getElementById('defElemRef').value.trim();
  if (!ref) { alert('Reference number is required.'); return; }
  if (!REF_NUMBER_PATTERN.test(ref)) {
    alert('Reference number must be 1-10 chars, letters/digits/apostrophe/hyphen only (e.g. 5, 12, 5a, M, 12-A).');
    return;
  }
  const defText = document.getElementById('defElemText').value.trim();
  try {
    if (_elemDefMode === 'edit') {
      await api('/patents/' + _patentId + '/elements/' + _elemDefId, { method: 'PATCH', body: JSON.stringify({ element_name: name, reference_number: ref, definition_text: defText || null }) });
    } else {
      await api('/patents/' + _patentId + '/elements', { method: 'POST', body: JSON.stringify({ element_name: name, reference_number: ref, definition_text: defText || null }) });
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
  if (_elemDefMode !== 'edit' || !_elemDefId) {
    alert('Save the element first, then click AI Suggest Definition.');
    return;
  }
  const btn = document.getElementById('btnAiSuggest');
  btn.innerHTML = '<span class="spinner"></span> Generating…'; btn.disabled = true;
  try {
    const r = await api('/patents/' + _patentId + '/elements/' + _elemDefId + '/generate-definition?top_k=15', { method: 'POST' });
    const final = r.final_candidate || '';
    if (final) {
      document.getElementById('defElemText').value = final;
      document.getElementById('defSaveStatus').textContent = 'AI suggestion applied — unsaved';
    } else {
      document.getElementById('defSaveStatus').textContent = r.message || 'No suggestion produced';
    }
    const s1 = (r.stage_outputs && r.stage_outputs.stage1_functional) || {};
    const s2 = (r.stage_outputs && r.stage_outputs.stage2_geometry) || {};
    const ret = r.rag_hits || [];
    const sc = document.getElementById('suggestionsContent');
    const ragCards = ret.map(x => {
      const defEn = (x.definition_en || '').trim();
      const defTr = (x.definition_tr || '').trim();
      const looksTurkish = /[çğıöşüÇĞİÖŞÜ]/.test(defEn);
      const shown = defEn || defTr;
      const langTag = !defEn
        ? '<em style="color:var(--accent);font-size:10px;">tr fallback</em> '
        : (looksTurkish ? '<em style="color:var(--accent);font-size:10px;">tr in en field</em> ' : '');
      return `<li style="list-style:none;padding:8px;border:1px solid var(--border);border-radius:6px;margin-bottom:6px;" title="${escAttr(x.title_en||'')}">
        <strong style="font-size:12px;">${esc(x.element_name_en)}</strong> · ${x.score}
        <span style="font-size:11px;display:block;color:var(--text-muted);margin-top:2px;white-space:normal;word-break:break-word;">${langTag}${esc(shown)}</span>
      </li>`;
    }).join('');
    sc.innerHTML = `<div class="suggestions-grid">
      <div class="suggestion-col">
        <h5>Stage 1 — Generic</h5>
        <p style="font-size:12px;color:var(--text-secondary);margin-bottom:4px">${esc(s1.generic_clause || s1.functional_clause || '<em>empty</em>')}</p>
        ${s1.source_sentence ? `<p style="font-size:11px;color:var(--accent);border-left:2px solid var(--accent);padding-left:6px;margin-bottom:4px;font-style:italic;">"${esc(s1.source_sentence)}"</p>` : ''}
        <p style="font-size:11px;color:var(--text-muted);margin-bottom:12px">${esc(s1.evidence_note || '')}</p>
        <h5 style="margin-top:8px">Retrieved (style ref) — ${ret.length} hit${ret.length !== 1 ? 's' : ''}</h5>
        <ul style="padding:0;margin:0;max-height:340px;overflow-y:auto;padding-right:4px;">${ragCards}</ul>
      </div>
      <div class="suggestion-col">
        <h5>Stage 2 — Geometry</h5>
        <p style="font-size:12px;color:var(--text-secondary);margin-bottom:4px">${esc(s2.geometry_clause || '<em>empty</em>')}</p>
        ${s2.source_sentence ? `<p style="font-size:11px;color:var(--accent);border-left:2px solid var(--accent);padding-left:6px;margin-bottom:4px;font-style:italic;">"${esc(s2.source_sentence)}"</p>` : ''}
        <p style="font-size:11px;color:var(--text-muted);margin-top:4px">${esc(s2.evidence_note || '')}</p>
      </div>
      <div class="suggestion-col">
        <h5>Stage 3 — Final Candidate</h5>
        <p style="font-size:13px;font-weight:500">${esc(final || '<em>insufficient evidence</em>')}</p>
        ${r.message ? `<p style="font-size:11px;color:var(--accent);margin-top:6px">${esc(r.message)}</p>` : ''}
      </div>
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
  const btn = document.getElementById('btnSaveDraft');
  const original = btn ? btn.innerHTML : null;
  if (btn) { btn.disabled = true; btn.innerHTML = 'Saving…'; }
  try {
    await api('/patents/' + _patentId + '/claims/' + _selectedClaimId + '/text', { method: 'PATCH', body: JSON.stringify({ claim_text: ta.value }) });
    const cl = _claims.find(c => c.claim_id === _selectedClaimId);
    if (cl) cl.claim_text = ta.value;
    if (btn) {
      btn.innerHTML = '✓ Saved';
      setTimeout(() => { btn.innerHTML = original; btn.disabled = false; }, 1200);
    }
  } catch (e) {
    if (btn) { btn.innerHTML = original; btn.disabled = false; }
    alert(e.message);
  }
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

function goToAiDraft(evt) {
  if (!_selectedClaimId) { alert('Please select a claim first.'); return; }
  const claim = _claims.find(c => c.claim_id === _selectedClaimId);
  if (!claim) return;

  const isIndependent = claim.claim_dependency_type === 'independent';
  const isApparatus   = claim.claim_category === 'apparatus';
  const isMethod      = claim.claim_category === 'method';

  document.getElementById('claimDraftModalTitle').textContent =
    `Claim ${claim.claim_number} — ${claim.claim_dependency_type} ${claim.claim_category}`;

  const patentName = (document.getElementById('navPatentName')?.textContent || '').trim();
  document.getElementById('draftSystemName').value = patentName;

  // System name input only shown for independent claims
  const sysRow = document.getElementById('draftSystemNameRow');
  if (sysRow) sysRow.style.display = isIndependent ? 'block' : 'none';

  document.getElementById('draftPurposeRow').style.display =
    (isIndependent && isMethod) ? 'block' : 'none';
  document.getElementById('draftMethodPurpose').value = '';

  const inventiveSection = document.getElementById('draftInventiveSection');
  inventiveSection.style.display = (isIndependent && isApparatus) ? 'block' : 'none';

  if (isIndependent && isApparatus) {
    const elems = _claimElements[_selectedClaimId] || [];
    document.getElementById('draftInventiveCheckboxes').innerHTML = elems.length === 0
      ? '<p style="font-size:12px;color:var(--text-muted)">No elements linked.</p>'
      : elems.map(e => `
          <label style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:13px;cursor:pointer;">
            <input type="checkbox" name="inventiveElem" value="${e.element_id}">
            <span>${esc(e.element_name)}${e.reference_number ? ' (' + esc(e.reference_number) + ')' : ''}</span>
          </label>`).join('');
  }

  document.getElementById('draftResultArea').innerHTML = '';
  document.getElementById('claimDraftModal').classList.add('active');
}

async function submitClaimDraftApp() {
  const claim = _claims.find(c => c.claim_id === _selectedClaimId);
  if (!claim) return;

  const systemName    = document.getElementById('draftSystemName').value.trim();
  const methodPurpose = document.getElementById('draftMethodPurpose').value.trim();
  const groupBIds     = [...document.querySelectorAll('input[name="inventiveElem"]:checked')]
                          .map(cb => parseInt(cb.value, 10));

  const resultArea = document.getElementById('draftResultArea');
  resultArea.innerHTML = '<p style="font-size:12px;color:var(--text-muted)">Generating…</p>';

  try {
    const res = await api('/patents/' + _patentId + '/claims/' + _selectedClaimId + '/generate-draft', {
      method: 'POST',
      body: JSON.stringify({ system_name: systemName, group_b_element_ids: groupBIds, method_purpose: methodPurpose, parent_claim_numbers: [] }),
    });

    if (!res.success) {
      resultArea.innerHTML = `<p style="color:var(--danger);font-size:13px;">⚠ ${esc(res.warning || 'Unknown error')}</p>`;
      return;
    }

    resultArea.innerHTML = `
      <p style="font-size:11px;color:var(--text-muted);margin-bottom:6px;">Generated draft — review and apply:</p>
      <textarea id="draftResultText" style="width:100%;min-height:120px;font-size:13px;font-family:inherit;
        padding:8px;border:1px solid var(--border);border-radius:6px;
        background:var(--bg-secondary);color:var(--text-primary);resize:vertical;"
      >${esc(res.claim_text)}</textarea>
      <div style="display:flex;gap:8px;margin-top:8px;">
        <button class="btn btn-primary btn-sm" onclick="applyClaimDraftApp()">Apply to claim</button>
        <button class="btn btn-sm" onclick="closeModal('claimDraftModal')">Discard</button>
      </div>`;
  } catch (e) {
    resultArea.innerHTML = `<p style="color:var(--danger);font-size:13px;">Error: ${esc(e.message)}</p>`;
  }
}

async function applyClaimDraftApp() {
  const text = document.getElementById('draftResultText')?.value;
  if (!text || !_selectedClaimId) return;
  try {
    await api('/patents/' + _patentId + '/claims/' + _selectedClaimId + '/text', {
      method: 'PATCH',
      body: JSON.stringify({ claim_text: text }),
    });
    const claim = _claims.find(c => c.claim_id === _selectedClaimId);
    if (claim) claim.claim_text = text;
    closeModal('claimDraftModal');
    // Refresh draft textarea if this claim is selected in the editor
    const ta = document.getElementById('draftTextarea');
    if (ta) ta.value = text;
  } catch (e) { alert(e.message); }
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
  const out = document.getElementById('composerDraftOutput');
  if (!_patentId) { alert('Open a project first.'); return; }

  btn.innerHTML = '<span class="spinner"></span> Generating…'; btn.disabled = true;
  out.innerHTML = '<p style="color:var(--text-muted)">Generating draft… Sections are ' +
    'written one by one by the LLM; this may take a few minutes depending on the model.</p>';

  try {
    // Backend takes the (editable) claims text, assembles a full English
    // patent draft section by section, and persists it as patent_draft.
    const res = await api('/patents/' + _patentId + '/draft/generate', {
      method: 'POST',
      body: JSON.stringify({
        claims_text: document.getElementById('composerClaimsInput').value,
      }),
    });
    _composerDraft = res.draft_html || '';
    out.innerHTML = _composerDraft ||
      '<p style="color:var(--text-muted)">The draft came back empty.</p>';
    if (res.warnings && res.warnings.length) {
      out.innerHTML += '<div style="margin-top:14px;padding:8px 11px;border:1px solid ' +
        'var(--border);border-radius:6px;color:var(--text-muted);font-size:12px">⚠ ' +
        res.warnings.map(esc).join('<br>') + '</div>';
    }
  } catch (e) {
    out.innerHTML = '<p style="color:#ff8a8a">Draft generation failed: ' + esc(e.message) + '</p>';
  } finally {
    btn.innerHTML = '⚡ Generate Draft'; btn.disabled = false;
  }
}
function backToEditor() { showPage('page-editor'); }

// ═══════════════════════════════════════════════════════════════
// Extract Pipeline
// ═══════════════════════════════════════════════════════════════
function openExtractModal() {
  document.getElementById('bbfFileInput').value = '';
  document.getElementById('reportFileInput').value = '';
  document.getElementById('inventorQaExtractFileInput').value = '';
  document.getElementById('bbfFileName').textContent = 'Click to select BBF file (auto-uploads on selection)';
  document.getElementById('reportFileName').textContent = 'Click to select Report file (auto-uploads on selection)';
  document.getElementById('inventorQaExtractFileName').textContent = 'Click to select Inventor_QA file (auto-uploads on selection)';
  document.getElementById('bbfExtractDocList').innerHTML = '';
  document.getElementById('reportExtractDocList').innerHTML = '';
  document.getElementById('inventorQaExtractDocList').innerHTML = '';
  const bs = document.getElementById('bbfExtractStatus'); if (bs) bs.textContent = '';
  const rs = document.getElementById('reportExtractStatus'); if (rs) rs.textContent = '';
  const qs = document.getElementById('inventorQaExtractStatus'); if (qs) qs.textContent = '';
  document.getElementById('extractStatus').innerHTML = '';
  document.getElementById('btnExtract').disabled = false;
  document.getElementById('btnExtract').innerHTML = '⚡ Extract Elements';
  document.getElementById('extractModal').classList.add('active');
  refreshBbfExtractDocs();
  refreshReportExtractDocs();
  refreshInventorQaExtractDocs();
}

async function onBbfExtractFileChange() {
  const input = document.getElementById('bbfFileInput');
  const label = document.getElementById('bbfFileName');
  const status = document.getElementById('bbfExtractStatus');
  const file = input.files[0];
  if (!file) {
    label.textContent = 'Click to select BBF file (auto-uploads on selection)';
    if (status) status.textContent = '';
    return;
  }
  label.textContent = file.name;
  if (!_patentId) {
    if (status) status.innerHTML = '<span style="color:var(--danger)">Open a project first.</span>';
    input.value = '';
    return;
  }
  if (status) status.innerHTML = '<span class="loading-text"><span class="spinner"></span> Uploading…</span>';
  try {
    const form = new FormData(); form.append('file', file);
    const res = await fetch('/api/patents/' + _patentId + '/invention-disclosure/documents', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || ('Upload failed (' + res.status + ')'));
    }
    if (status) status.innerHTML = '<span style="color:var(--success)">✓ Uploaded "' + esc(file.name) + '"</span>';
    input.value = '';
    label.textContent = 'Click to select BBF file (auto-uploads on selection)';
    await refreshBbfExtractDocs();
  } catch (e) {
    if (status) status.innerHTML = '<span style="color:var(--danger)">' + esc(e.message) + '</span>';
  }
}

async function refreshBbfExtractDocs() {
  const box = document.getElementById('bbfExtractDocList');
  if (!_patentId || !box) { if (box) box.innerHTML = ''; return; }
  try {
    const idf = await api('/patents/' + _patentId + '/invention-disclosure');
    const docs = idf.documents || [];
    if (!docs.length) {
      box.innerHTML = '<p class="ws-empty-msg" style="margin:4px 0;font-size:11px">No BBF documents uploaded yet.</p>';
      return;
    }
    box.innerHTML = '<div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">Existing BBF documents (latest is used for extraction):</div>' + docs.map(d => `
      <div class="patent-input-doc-row">
        <span class="patent-input-doc-name">📄 ${esc(d.original_filename)}</span>
        <span class="patent-input-doc-meta">${formatBytes(d.size_bytes)}</span>
      </div>`).join('');
  } catch (_) { box.innerHTML = ''; }
}

async function onReportExtractFileChange() {
  const input = document.getElementById('reportFileInput');
  const label = document.getElementById('reportFileName');
  const status = document.getElementById('reportExtractStatus');
  const file = input.files[0];
  if (!file) {
    label.textContent = 'Click to select Report file (auto-uploads on selection)';
    if (status) status.textContent = '';
    return;
  }
  label.textContent = file.name;
  if (!_patentId) {
    if (status) status.innerHTML = '<span style="color:var(--danger)">Open a project first.</span>';
    input.value = '';
    return;
  }
  if (status) status.innerHTML = '<span class="loading-text"><span class="spinner"></span> Uploading…</span>';
  try {
    const form = new FormData(); form.append('file', file);
    const res = await fetch('/api/patents/' + _patentId + '/research-report/documents', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || ('Upload failed (' + res.status + ')'));
    }
    if (status) status.innerHTML = '<span style="color:var(--success)">✓ Uploaded "' + esc(file.name) + '"</span>';
    input.value = '';
    label.textContent = 'Click to select Report file (auto-uploads on selection)';
    await refreshReportExtractDocs();
  } catch (e) {
    if (status) status.innerHTML = '<span style="color:var(--danger)">' + esc(e.message) + '</span>';
  }
}

async function refreshReportExtractDocs() {
  const box = document.getElementById('reportExtractDocList');
  if (!_patentId || !box) { if (box) box.innerHTML = ''; return; }
  try {
    const rr = await api('/patents/' + _patentId + '/research-report');
    const docs = rr.documents || [];
    if (!docs.length) {
      box.innerHTML = '<p class="ws-empty-msg" style="margin:4px 0;font-size:11px">No Research Report documents uploaded yet.</p>';
      return;
    }
    box.innerHTML = '<div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">Existing Research Report documents (latest is used for extraction):</div>' + docs.map(d => `
      <div class="patent-input-doc-row">
        <span class="patent-input-doc-name">📄 ${esc(d.original_filename)}</span>
        <span class="patent-input-doc-meta">${formatBytes(d.size_bytes)}</span>
      </div>`).join('');
  } catch (_) { box.innerHTML = ''; }
}

async function onInventorQaExtractFileChange() {
  const input = document.getElementById('inventorQaExtractFileInput');
  const label = document.getElementById('inventorQaExtractFileName');
  const status = document.getElementById('inventorQaExtractStatus');
  const file = input.files[0];
  if (!file) {
    label.textContent = 'Click to select Inventor_QA file (auto-uploads on selection)';
    if (status) status.textContent = '';
    return;
  }
  label.textContent = file.name;
  if (!_patentId) {
    if (status) status.innerHTML = '<span style="color:var(--danger)">Open a project first.</span>';
    input.value = '';
    return;
  }
  if (status) status.innerHTML = '<span class="loading-text"><span class="spinner"></span> Uploading…</span>';
  try {
    const form = new FormData(); form.append('file', file);
    const res = await fetch('/api/patents/' + _patentId + '/inventor-qa/documents', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || ('Upload failed (' + res.status + ')'));
    }
    if (status) status.innerHTML = '<span style="color:var(--success)">✓ Uploaded "' + esc(file.name) + '"</span>';
    input.value = '';
    label.textContent = 'Click to select Inventor_QA file (auto-uploads on selection)';
    await refreshInventorQaExtractDocs();
  } catch (e) {
    if (status) status.innerHTML = '<span style="color:var(--danger)">' + esc(e.message) + '</span>';
  }
}

async function refreshInventorQaExtractDocs() {
  const box = document.getElementById('inventorQaExtractDocList');
  if (!_patentId || !box) { if (box) box.innerHTML = ''; return; }
  try {
    const qa = await api('/patents/' + _patentId + '/inventor-qa');
    const docs = qa.documents || [];
    if (!docs.length) {
      box.innerHTML = '<p class="ws-empty-msg" style="margin:4px 0;font-size:11px">No Inventor_QA documents uploaded yet.</p>';
      return;
    }
    box.innerHTML = '<div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">Existing Inventor_QA documents:</div>' + docs.map(d => `
      <div class="patent-input-doc-row">
        <span class="patent-input-doc-name">📄 ${esc(d.original_filename)}</span>
        <span class="patent-input-doc-meta">${formatBytes(d.size_bytes)}</span>
      </div>`).join('');
  } catch (_) { box.innerHTML = ''; }
}

async function startExtraction() {
  if (!_patentId) { alert('Open a project first.'); return; }
  // Files now auto-upload on selection, so the inputs are normally empty.
  // The pipeline pulls the latest stored BBF/Report for the active patent.
  // Validate that both stored documents exist before running.
  let idf, rr;
  try {
    [idf, rr] = await Promise.all([
      api('/patents/' + _patentId + '/invention-disclosure'),
      api('/patents/' + _patentId + '/research-report'),
    ]);
  } catch (e) {
    alert('Could not load patent inputs: ' + e.message);
    return;
  }
  if (!(idf.documents || []).length) { alert('Upload a BBF document first.'); return; }
  if (!(rr.documents || []).length) { alert('Upload a Research Report document first.'); return; }

  const btn = document.getElementById('btnExtract');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Extracting…';
  document.getElementById('extractStatus').innerHTML = '<span class="loading-text"><span class="spinner"></span> Running pipeline…</span>';
  try {
    const form = new FormData();
    form.append('patent_id', String(_patentId));
    await fetch('/api/pipeline/extract-elements', { method: 'POST', body: form });
    const poll = setInterval(async () => {
      const s = await api('/pipeline/extract-elements-status?patent_id=' + _patentId);
      if (s.status === 'running' && s.stage) {
        document.getElementById('extractStatus').innerHTML =
          '<span class="loading-text"><span class="spinner"></span> ' + esc(s.stage) + '</span>';
      }
      if (s.status === 'done') {
        clearInterval(poll);
        document.getElementById('extractStatus').innerHTML = '<span style="color:var(--success)">✓ Extracted ' + s.elements.length + ' elements!</span>';
        btn.innerHTML = '⚡ Extract Elements'; btn.disabled = false;
        // Store BBF text for AI Suggest Definition (persisted server-side too)
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
          st.innerHTML = '<span style="color:var(--success)">✓ Loaded ' + (s.count || '') + ' docs. ChromaDB index ready.</span>';
          document.getElementById('statusBadge').textContent = 'Data Loaded';
          document.getElementById('statusBadge').classList.add('ws-status-badge--loaded');
        } else if (s.status === 'error') { clearInterval(poll); st.innerHTML = '<span style="color:var(--danger)">Error: ' + (s.error||'') + '</span>'; }
      } catch (_) {}
    }, 2000);
  } catch (e) { st.innerHTML = '<span style="color:var(--danger)">Failed: ' + e.message + '</span>'; }
}

async function openSettingsModal() {
  // Pull the latest stored values rather than relying on JS-only state.
  // This makes the modal show the current persisted truth even after a
  // page refresh.
  let context = _context;
  let bbfText = _bbfText;
  if (_patentId) {
    try {
      const [patent, idf] = await Promise.all([
        api('/patents/' + _patentId),
        api('/patents/' + _patentId + '/invention-disclosure'),
      ]);
      context = patent.invention_context || '';
      bbfText = idf.bbf_text || '';
      _context = context;
      _bbfText = bbfText;
    } catch (_) {}
  }
  document.getElementById('settingsContext').value = context;
  document.getElementById('settingsBBF').value = bbfText;
  api('/rag/llm-status').then(s => {
    document.getElementById('settingsLLMUrl').value = s.url || '';
  }).catch(() => {});
  document.getElementById('settingsModal').classList.add('active');
}

async function saveSettings() {
  const ctx = document.getElementById('settingsContext').value;
  const bbf = document.getElementById('settingsBBF').value;
  const llmUrl = document.getElementById('settingsLLMUrl').value.trim();
  _context = ctx;
  _bbfText = bbf;

  // Persist invention_context on the active patent, and bbf_text on
  // its invention_disclosure. Skipped silently when no project is open.
  if (_patentId) {
    try {
      await api('/patents/' + _patentId, {
        method: 'PATCH',
        body: JSON.stringify({ invention_context: ctx }),
      });
    } catch (e) { console.warn('save invention_context failed:', e.message); }
    try {
      await api('/patents/' + _patentId + '/invention-disclosure', {
        method: 'PUT',
        body: JSON.stringify({ bbf_text: bbf }),
      });
    } catch (e) { console.warn('save bbf_text failed:', e.message); }
  }

  // Always send the LLM URL — empty string clears it on the backend.
  try {
    await api('/rag/set-llm-url', { method: 'POST', body: JSON.stringify({ url: llmUrl }) });
  } catch (e) { console.warn('save llm url failed:', e.message); }

  closeModal('settingsModal');
}
async function openUploadModal() {
  document.getElementById('uploadModal').classList.add('active');
  const st = document.getElementById('uploadStatus');
  if (!st) return;
  st.innerHTML = '';
  try {
    const s = await api('/rag/data-status');
    if (s.loaded) {
      _dataLoaded = true;
      const badge = document.getElementById('statusBadge');
      if (badge) {
        badge.textContent = 'Data Loaded';
        badge.classList.add('ws-status-badge--loaded');
      }
      st.innerHTML =
        '<span style="color:var(--success)">✓ ' + (s.count || 0) +
        ' docs already indexed in ChromaDB. Upload a new Excel to rebuild.</span>';
    } else {
      st.innerHTML =
        '<span style="color:var(--text-muted);font-size:12px">No data indexed yet. Upload an Excel to build the ChromaDB vector index.</span>';
    }
  } catch (_) { /* leave status empty on transient errors */ }
}

// ═══════════════════════════════════════════════════════════════
// Patent Inputs — Inventor_QA (Buluşçu ile Yazışmalar)
// ═══════════════════════════════════════════════════════════════
let _inputsPatentId = null;

async function openPatentInputs(patentId) {
  _inputsPatentId = patentId;

  // Reset BBF card
  document.getElementById('idfPriorArt').value = '';
  document.getElementById('idfClosestPriorPatents').value = '';
  document.getElementById('idfNovelFeatures').value = '';
  document.getElementById('idfSaveStatus').textContent = '';

  // Reset Research Report card
  document.getElementById('rrExecutiveSummary').value = '';
  document.getElementById('rrSearchStrategy').value = '';
  document.getElementById('rrClassificationKeywords').value = '';
  document.getElementById('rrElementPatentAnalysis').value = '';
  document.getElementById('rrSaveStatus').textContent = '';

  // Reset Inventor_QA card
  document.getElementById('inventorQaText').value = '';
  document.getElementById('inventorQaFileInput').value = '';
  document.getElementById('inventorQaFileName').textContent = 'No file selected';
  document.getElementById('btnUploadInventorQaDoc').disabled = true;
  document.getElementById('inventorQaDocList').innerHTML =
    '<p class="ws-empty-msg" style="margin:6px 0">Loading…</p>';
  const qaStatus = document.getElementById('inventorQaSaveStatus');
  if (qaStatus) qaStatus.textContent = '';

  document.getElementById('patentInputsModal').classList.add('active');

  await Promise.all([
    loadInventionDisclosure(),
    loadResearchReport(),
    loadInventorQa(),
  ]);
}

async function loadInventionDisclosure() {
  if (!_inputsPatentId) return;
  try {
    const idf = await api('/patents/' + _inputsPatentId + '/invention-disclosure');
    document.getElementById('idfPriorArt').value = idf.prior_art_and_problems || '';
    document.getElementById('idfClosestPriorPatents').value = idf.closest_prior_patents || '';
    document.getElementById('idfNovelFeatures').value = idf.novel_features || '';
    document.getElementById('idfSaveStatus').textContent = '';
  } catch (e) {
    document.getElementById('idfSaveStatus').textContent = 'Load failed: ' + e.message;
  }
}

async function saveInventionDisclosure() {
  if (!_inputsPatentId) return;
  const status = document.getElementById('idfSaveStatus');
  status.textContent = 'Saving…';
  try {
    await api('/patents/' + _inputsPatentId + '/invention-disclosure', {
      method: 'PUT',
      body: JSON.stringify({
        prior_art_and_problems: document.getElementById('idfPriorArt').value || null,
        closest_prior_patents: document.getElementById('idfClosestPriorPatents').value || null,
        novel_features: document.getElementById('idfNovelFeatures').value || null,
      }),
    });
    status.textContent = 'Saved ✓';
  } catch (e) {
    status.textContent = 'Error: ' + e.message;
  }
}

async function loadResearchReport() {
  if (!_inputsPatentId) return;
  try {
    const rr = await api('/patents/' + _inputsPatentId + '/research-report');
    document.getElementById('rrExecutiveSummary').value = rr.executive_summary || '';
    document.getElementById('rrSearchStrategy').value = rr.search_strategy || '';
    document.getElementById('rrClassificationKeywords').value = rr.classification_and_keywords || '';
    document.getElementById('rrElementPatentAnalysis').value = rr.element_patent_analysis || '';
    document.getElementById('rrSaveStatus').textContent = '';
  } catch (e) {
    document.getElementById('rrSaveStatus').textContent = 'Load failed: ' + e.message;
  }
}

async function saveResearchReport() {
  if (!_inputsPatentId) return;
  const status = document.getElementById('rrSaveStatus');
  status.textContent = 'Saving…';
  try {
    await api('/patents/' + _inputsPatentId + '/research-report', {
      method: 'PUT',
      body: JSON.stringify({
        executive_summary: document.getElementById('rrExecutiveSummary').value || null,
        search_strategy: document.getElementById('rrSearchStrategy').value || null,
        classification_and_keywords: document.getElementById('rrClassificationKeywords').value || null,
        element_patent_analysis: document.getElementById('rrElementPatentAnalysis').value || null,
      }),
    });
    status.textContent = 'Saved ✓';
  } catch (e) {
    status.textContent = 'Error: ' + e.message;
  }
}

async function loadInventorQa() {
  if (!_inputsPatentId) return;
  try {
    const qa = await api('/patents/' + _inputsPatentId + '/inventor-qa');
    document.getElementById('inventorQaText').value = qa.questions_and_answers || '';
    renderInventorQaDocs(qa.documents || []);
  } catch (e) {
    document.getElementById('inventorQaDocList').innerHTML =
      '<p class="ws-empty-msg" style="margin:6px 0;color:var(--danger)">' + esc(e.message) + '</p>';
  }
}

function renderInventorQaDocs(docs) {
  const box = document.getElementById('inventorQaDocList');
  if (!docs.length) {
    box.innerHTML = '<p class="ws-empty-msg" style="margin:6px 0">No documents uploaded yet.</p>';
    return;
  }
  box.innerHTML = docs.map(d => `
    <div class="patent-input-doc-row">
      <span class="patent-input-doc-name">📄 ${esc(d.original_filename)}</span>
      <span class="patent-input-doc-meta">${formatBytes(d.size_bytes)}</span>
      <span class="patent-input-doc-actions">
        <a class="btn btn-sm btn-ghost" href="/api/patents/${_inputsPatentId}/inventor-qa/documents/${d.document_id}" target="_blank">Download</a>
        <button class="btn btn-sm btn-ghost" onclick="deleteInventorQaDocument(${d.document_id})">🗑</button>
      </span>
    </div>`).join('');
}

function formatBytes(n) {
  if (!n && n !== 0) return '';
  if (n < 1024) return n + ' B';
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
  return (n / (1024 * 1024)).toFixed(1) + ' MB';
}

function onInventorQaFileChange() {
  const input = document.getElementById('inventorQaFileInput');
  const label = document.getElementById('inventorQaFileName');
  const btn = document.getElementById('btnUploadInventorQaDoc');
  if (input.files.length) {
    label.textContent = input.files[0].name;
    btn.disabled = false;
  } else {
    label.textContent = 'No file selected';
    btn.disabled = true;
  }
}

async function uploadInventorQaDocument() {
  if (!_inputsPatentId) return;
  const input = document.getElementById('inventorQaFileInput');
  if (!input.files.length) return;
  const form = new FormData();
  form.append('file', input.files[0]);
  const btn = document.getElementById('btnUploadInventorQaDoc');
  btn.disabled = true;
  try {
    const res = await fetch('/api/patents/' + _inputsPatentId + '/inventor-qa/documents', {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || ('Upload failed (' + res.status + ')'));
    }
    const qa = await res.json();
    renderInventorQaDocs(qa.documents || []);
    input.value = '';
    document.getElementById('inventorQaFileName').textContent = 'No file selected';
  } catch (e) {
    alert(e.message);
  } finally {
    btn.disabled = !input.files.length;
  }
}

async function deleteInventorQaDocument(documentId) {
  if (!_inputsPatentId) return;
  if (!confirm('Delete this document?')) return;
  try {
    await api('/patents/' + _inputsPatentId + '/inventor-qa/documents/' + documentId, { method: 'DELETE' });
    await loadInventorQa();
  } catch (e) { alert(e.message); }
}

async function saveInventorQaText() {
  if (!_inputsPatentId) return;
  const text = document.getElementById('inventorQaText').value;
  const status = document.getElementById('inventorQaSaveStatus');
  if (status) status.textContent = 'Saving…';
  try {
    const qa = await api('/patents/' + _inputsPatentId + '/inventor-qa', {
      method: 'PUT',
      body: JSON.stringify({ questions_and_answers: text }),
    });
    renderInventorQaDocs(qa.documents || []);
    if (status) status.textContent = 'Saved ✓';
  } catch (e) {
    if (status) status.textContent = 'Error: ' + e.message;
    else alert(e.message);
  }
}

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

  // bbf_text is now per-patent; populated by openProject.
  try {
    const ls = await api('/rag/llm-status');
    if (ls.url) console.log('[LLM] Remote URL:', ls.url);
  } catch (_) {}

  showPage('page-dashboard');
});


// ═══════════════════════════════════════════════════════════════
// WORKSPACE DOCUMENT ASSISTANT (offline_qa_module)
// ═══════════════════════════════════════════════════════════════

let assistantMode = 'P1';
let assistantBusy = false;
// Per-mode cache of the rendered result HTML so switching between
// Core Problem / Claim Structure / Element Lookup keeps each tab's
// own answer (and shows blank for tabs that haven't been asked yet).
// Cleared by `_clearAssistantCache` when the active patent changes.
let _assistantResultByMode = { P1: '', P2: '', P3: '' };
let _assistantTermByMode = { P3: '' };

function _clearAssistantCache() {
  _assistantResultByMode = { P1: '', P2: '', P3: '' };
  _assistantTermByMode = { P3: '' };
  const root = document.getElementById('assistantResult');
  if (root) root.innerHTML = '';
  const term = document.getElementById('assistantTermInput');
  if (term) term.value = '';
}

function _assistantEsc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function toggleAssistantDrawer(open) {
  const drawer = document.getElementById('assistantDrawer');
  const overlay = document.getElementById('assistantOverlay');
  if (!drawer) return;
  const isOpen = open === undefined ? !drawer.classList.contains('open') : !!open;
  drawer.classList.toggle('open', isOpen);
  overlay.classList.toggle('open', isOpen);
  drawer.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
}

function selectAssistantMode(mode) {
  // Snapshot the term input for the outgoing mode (only P3 uses it)
  // so coming back to P3 restores the term that produced the cached
  // result. Other modes don't have an input to preserve.
  if (assistantMode === 'P3') {
    const term = document.getElementById('assistantTermInput');
    if (term) _assistantTermByMode.P3 = term.value || '';
  }

  assistantMode = mode;
  document.querySelectorAll('.assistant-mode-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });
  document.getElementById('assistantTermRow').style.display = (mode === 'P3') ? 'block' : 'none';

  // Show this mode's cached result (empty string = blank panel = unasked).
  document.getElementById('assistantResult').innerHTML = _assistantResultByMode[mode] || '';

  // Restore P3's last term so the user sees what produced the cached result.
  if (mode === 'P3') {
    const term = document.getElementById('assistantTermInput');
    if (term) term.value = _assistantTermByMode.P3 || '';
  }
}

async function askAssistant() {
  if (assistantBusy) return;

  if (!_patentId) {
    _renderAssistantError('No active patent project. Open a project first.');
    return;
  }

  const body = { pattern_id: assistantMode };
  if (assistantMode === 'P3') {
    const term = (document.getElementById('assistantTermInput').value || '').trim();
    if (!term) {
      _renderAssistantError('Please enter a term to look up.');
      return;
    }
    body.term = term;
  }

  _setAssistantBusy(true);
  try {
    const data = await api('/patents/' + _patentId + '/assistant/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    _renderAssistantResult(data);
  } catch (err) {
    _renderAssistantError(err && err.message ? err.message : 'Assistant call failed.');
  } finally {
    _setAssistantBusy(false);
  }
}

function _setAssistantBusy(busy) {
  assistantBusy = busy;
  const btn = document.getElementById('assistantAskBtn');
  const hint = document.getElementById('assistantAskHint');
  if (btn) btn.disabled = busy;
  if (hint) hint.textContent = busy ? 'Thinking…' : '';
  if (busy) {
    document.getElementById('assistantResult').innerHTML =
      '<p class="ws-empty-msg">Running model… this may take a few seconds.</p>';
  }
}

function _renderAssistantError(msg) {
  const html = '<div class="assistant-insufficient">' + _assistantEsc(msg) + '</div>';
  document.getElementById('assistantResult').innerHTML = html;
  _assistantResultByMode[assistantMode] = html;
}

function _supportBadge(level) {
  const label = level === 'explicit' ? 'Explicitly Stated'
              : level === 'inferred' ? 'Inferred'
              : 'Insufficient';
  return '<span class="assistant-support-badge support-' + _assistantEsc(level) + '">' + label + '</span>';
}

function _renderAssistantResult(data) {
  const root = document.getElementById('assistantResult');
  if (!data || !data.pattern_id) {
    root.innerHTML = '<div class="assistant-insufficient">Empty response.</div>';
    return;
  }

  const parts = [];
  const title = data.title || data.pattern_id;
  parts.push('<div class="assistant-result-header">');
  parts.push('<h4>' + _assistantEsc(title) + '</h4>');
  parts.push(_supportBadge(data.support_level));
  parts.push('</div>');

  if (data.support_level === 'insufficient') {
    parts.push('<div class="assistant-insufficient">' +
      _assistantEsc(data.insufficient_message || data.answer || 'Not enough information in the source documents.') +
      '</div>');
    root.innerHTML = parts.join('');
    return;
  }

  if (data.answer) {
    parts.push('<div class="assistant-answer-block">' + _assistantEsc(data.answer).replace(/\n/g, '<br>') + '</div>');
  }

  if (data.pattern_id === 'P2' && data.claim_structure) {
    parts.push(_renderClaimStructure(data.claim_structure));
  }

  if (Array.isArray(data.evidence) && data.evidence.length) {
    parts.push(_renderEvidence(data.evidence, data.pattern_id));
  }

  const html = parts.join('');
  root.innerHTML = html;
  // Cache against the response's own pattern_id so a slow request that
  // returns after the user switched tabs still lands in the right cache.
  const cacheKey = data.pattern_id in _assistantResultByMode ? data.pattern_id : assistantMode;
  _assistantResultByMode[cacheKey] = html;
}

function _renderClaimStructure(cs) {
  const out = ['<div class="assistant-cs-section">'];

  if (Array.isArray(cs.independent_candidates) && cs.independent_candidates.length) {
    out.push('<h5>Independent claim candidates</h5>');
    cs.independent_candidates.forEach(c => out.push(_renderCsCard(c)));
  }
  if (Array.isArray(cs.dependent_candidates) && cs.dependent_candidates.length) {
    out.push('<h5>Dependent claim candidates</h5>');
    cs.dependent_candidates.forEach(c => out.push(_renderCsCard(c, true)));
  }
  if (Array.isArray(cs.cautions) && cs.cautions.length) {
    out.push('<h5>Drafting cautions</h5>');
    out.push('<ul class="assistant-cs-cautions">');
    cs.cautions.forEach(c => out.push('<li>' + _assistantEsc(c) + '</li>'));
    out.push('</ul>');
  }

  out.push('</div>');
  return out.join('');
}

function _renderCsCard(c, isDependent) {
  const features = (c.features || []).map(f => '<li>' + _assistantEsc(f) + '</li>').join('');
  const dep = isDependent && c.depends_on
    ? '<div class="assistant-cs-dep">depends on: ' + _assistantEsc(c.depends_on) + '</div>' : '';
  const sup = c.support_level
    ? '<div class="assistant-cs-support">' + _supportBadge(c.support_level) +
      (c.support_note ? ' <span class="assistant-cs-note">' + _assistantEsc(c.support_note) + '</span>' : '') +
      '</div>' : '';
  return '<div class="assistant-cs-card">' +
    '<div class="assistant-cs-label">' + _assistantEsc(c.label || '') + '</div>' +
    dep +
    (features ? '<ul class="assistant-cs-features">' + features + '</ul>' : '') +
    (c.reason ? '<div class="assistant-cs-reason">' + _assistantEsc(c.reason) + '</div>' : '') +
    sup +
    '</div>';
}

function _renderEvidence(evidence, mode) {
  const out = ['<div class="assistant-evidence-section">',
              '<h5>Evidence</h5>'];
  evidence.forEach(ev => {
    const note = ev.usefulness_note
      ? '<div class="assistant-evidence-note">' + _assistantEsc(ev.usefulness_note) + '</div>' : '';
    const meta = '<div class="assistant-evidence-meta">' +
      _assistantEsc(ev.evidence_id || '') + ' · ' +
      _assistantEsc(ev.document_type || '') + ' · ' +
      _assistantEsc(ev.field || '') + '</div>';
    let excerpt = _assistantEsc(ev.excerpt || '').replace(/\n/g, '<br>');
    if (mode === 'P3' && ev.match_term) {
      excerpt = _highlightTerm(excerpt, ev.match_term);
    }
    out.push('<div class="assistant-evidence-card">' + meta + note +
             '<div class="assistant-evidence-excerpt">' + excerpt + '</div></div>');
  });
  out.push('</div>');
  return out.join('');
}

function _highlightTerm(escapedHtml, term) {
  if (!term) return escapedHtml;
  const safeTerm = _assistantEsc(term).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  if (!safeTerm) return escapedHtml;
  const re = new RegExp('(' + safeTerm + ')', 'gi');
  return escapedHtml.replace(re, '<span class="assistant-highlight">$1</span>');
}
