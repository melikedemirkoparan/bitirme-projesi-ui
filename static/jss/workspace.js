/* ═══════════════════════════════════════════════════════════════
   Patent Drafting Tool — Claim Workspace JS
   ═══════════════════════════════════════════════════════════════ */

// ── URL / context ───────────────────────────────────────────────

function getPatentId() {
  const params = new URLSearchParams(window.location.search);
  const id = parseInt(params.get('id'), 10);
  return isNaN(id) ? null : id;
}

// ── API helper ──────────────────────────────────────────────────

async function api(path, opts = {}) {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || 'Request failed');
  }
  if (res.status === 204) return null;
  return res.json();
}

function esc(s) {
  if (!s) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

// ── Navigation ──────────────────────────────────────────────────

function goHome() {
  window.location.href = '/';
}

function goUpload() {
  // Upload page will be implemented in a later phase.
  alert('Upload page coming soon.');
}

// ── Patent info ─────────────────────────────────────────────────

async function loadPatentInfo(patentId) {
  try {
    const patent = await api('/patents/' + patentId);
    document.getElementById('navPatentName').textContent = patent.patent_name;
    document.title = patent.patent_name + ' — Patent Drafting Tool';
  } catch (e) {
    document.getElementById('navPatentName').textContent = 'Patent #' + patentId;
    console.error('Failed to load patent info:', e);
  }
}

// ═══════════════════════════════════════════════════════════════
// Claims — Left Panel
// ═══════════════════════════════════════════════════════════════

// Currently selected claim (used by Phase 7 draft editor)
let _selectedClaimId = null;
// In-memory claim list (used to populate parent dropdown)
let _claims = [];
// Patent-level element pool (center panel)
let _elements = [];
// Linked elements per claim — { claim_id: [Element, ...] }
let _claimElements = {};
// Selected element within a claim tree — { claimId, elementId }
let _selectedElement = { claimId: null, elementId: null };
// Collapse state per claim — { claim_id: bool } — undefined = expanded
let _claimExpanded = {};
// Target claim for the Link Element modal
let _addElemTargetClaimId = null;
// Per-claim search query for the element tree — { claim_id: string }
let _elemTreeSearch = {};

async function loadClaims() {
  const patentId = getPatentId();
  if (!patentId) return;

  try {
    const claims = await api('/patents/' + patentId + '/claims');
    _claims = claims;

    // Preserve existing expand state; default new claims to expanded
    claims.forEach(c => {
      if (_claimExpanded[c.claim_id] === undefined) _claimExpanded[c.claim_id] = true;
    });

    // Fetch linked elements for all claims in parallel
    const results = await Promise.all(
      claims.map(c =>
        api('/patents/' + patentId + '/claims/' + c.claim_id + '/elements').catch(() => [])
      )
    );
    claims.forEach((c, i) => { _claimElements[c.claim_id] = results[i]; });

    renderClaimList(claims);
  } catch (e) {
    console.error('Failed to load claims:', e);
  }
}

function renderClaimList(claims) {
  const container = document.getElementById('claimList');
  if (!container) return;

  if (claims.length === 0) {
    container.innerHTML = '<p class="ws-empty-msg">No claims yet. Click "+ Add Claim" to get started.</p>';
    return;
  }

  container.innerHTML = claims.map(c => _renderClaimCard(c)).join('');
}

function _deriveClaimStatus(linkedElems) {
  if (linkedElems.length === 0) return null;
  return linkedElems.every(el => el.definition_text && el.definition_text.trim().length > 0)
    ? 'Ready'
    : 'Incomplete';
}

function _renderClaimCard(c) {
  const isIndependent = c.claim_dependency_type === 'independent';
  const accentMod  = isIndependent ? 'claim-card--independent' : 'claim-card--dependent';
  const isSelected = c.claim_id === _selectedClaimId;
  const expanded   = _claimExpanded[c.claim_id] !== false;
  const linkedElems = _claimElements[c.claim_id] || [];
  const status = _deriveClaimStatus(linkedElems);
  const parentClaim = c.parent_claim_id
    ? _claims.find(p => p.claim_id === c.parent_claim_id)
    : null;

  const statusBadge = status
    ? `<span class="claim-status-badge claim-status--${status.toLowerCase()}">
         <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="10" height="10">
           ${status === 'Ready'
             ? '<circle cx="12" cy="12" r="10"/><polyline points="9 12 11 14 15 10"/>'
             : '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>'}
         </svg>
         ${status}
       </span>`
    : '';

  const chevronPath = expanded
    ? '<polyline points="6 9 12 15 18 9"/>'
    : '<polyline points="9 18 15 12 9 6"/>';

  return `
    <div class="claim-card ${accentMod} ${isSelected ? 'claim-card--selected' : ''}"
         onclick="selectClaim(${c.claim_id})">

      <div class="claim-card-header">
        <div class="claim-header-left">
          <button class="claim-collapse-btn"
                  onclick="event.stopPropagation(); toggleClaimExpanded(${c.claim_id})"
                  title="${expanded ? 'Collapse' : 'Expand'}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
              ${chevronPath}
            </svg>
          </button>
          <svg class="claim-layers-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="15" height="15">
            <polygon points="12 2 2 7 12 12 22 7 12 2"/>
            <polyline points="2 17 12 22 22 17"/>
            <polyline points="2 12 12 17 22 12"/>
          </svg>
          <span class="claim-card-number">Claim ${c.claim_number}</span>
          ${statusBadge}
        </div>
        <div class="claim-header-right">
          <button class="btn btn-sm btn-primary claim-add-elem-btn"
                  onclick="event.stopPropagation(); openAddElementsModal(${c.claim_id})">
            + Add Elements
          </button>
          <button class="claim-delete-btn"
                  onclick="event.stopPropagation(); deleteClaim(${c.claim_id})"
                  title="Delete claim">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
              <path d="M10 11v6M14 11v6"/>
              <path d="M9 6V4h6v2"/>
            </svg>
          </button>
        </div>
      </div>

      ${parentClaim ? `
      <div class="claim-dep-hint">↳ depends on Claim ${parentClaim.claim_number}</div>` : ''}

      ${expanded ? _renderElemTree(c.claim_id, linkedElems) : ''}
    </div>
  `;
}

function _renderElemTree(claimId, linkedElems) {
  const rawQuery = _elemTreeSearch[claimId] || '';
  const query    = rawQuery.toLowerCase();
  const filtered = query
    ? linkedElems.filter(el => el.element_name.toLowerCase().includes(query))
    : linkedElems;

  const total   = linkedElems.length;
  const visible = filtered.length;

  // Up/down eligibility based on selected element position in the full (unfiltered) list
  const selInThis  = _selectedElement.claimId === claimId;
  const selIdx     = selInThis
    ? linkedElems.findIndex(el => el.element_id === _selectedElement.elementId)
    : -1;
  const canMoveUp   = selIdx > 0;
  const canMoveDown = selIdx >= 0 && selIdx < linkedElems.length - 1;
  const selId       = selInThis ? _selectedElement.elementId : null;

  const ctrlBtn = (enabled, onclick, title, pathD) => `
    <button class="elem-tree-ctrl-btn${enabled ? '' : ' elem-tree-ctrl-btn--disabled'}"
            ${enabled ? `onclick="event.stopPropagation(); ${onclick}"` : 'disabled'}
            title="${title}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
        ${pathD}
      </svg>
    </button>`;

  const rows = filtered.length === 0
    ? `<p class="ws-empty-msg" style="padding:12px 0 4px;">${
        query ? 'No elements match.' : 'No elements linked yet. Click "+ Add Elements".'
      }</p>`
    : `<div class="elem-tree-list">
         ${filtered.map(el => _renderTreeElemRow(claimId, el)).join('')}
       </div>`;

  return `
    <div class="claim-elem-tree">
      <div class="claim-elem-tree-hdr">
        <span class="elem-tree-label">ELEMENT TREE</span>
        <div class="elem-tree-controls">
          ${ctrlBtn(canMoveUp,   `reorderElement(${claimId},${selId},'up')`,   'Move up',   '<polyline points="18 15 12 9 6 15"/>')}
          ${ctrlBtn(canMoveDown, `reorderElement(${claimId},${selId},'down')`, 'Move down', '<polyline points="6 9 12 15 18 9"/>')}
          ${ctrlBtn(true, `refreshClaimElements(${claimId})`, 'Refresh',
            '<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/>')}
        </div>
      </div>

      <div class="elem-tree-search-row">
        <div class="elem-tree-search">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input type="text"
                 class="elem-tree-search-input"
                 data-search-claim="${claimId}"
                 placeholder="Search elements"
                 value="${esc(rawQuery)}"
                 oninput="event.stopPropagation(); filterElemTree(${claimId}, this.value)"
                 onclick="event.stopPropagation()">
        </div>
      </div>

      ${total > 0 ? `
      <div class="elem-tree-stats">
        <span>${visible} visible</span>
        <span>${total} linked</span>
      </div>` : ''}

      ${rows}
    </div>
  `;
}

function _renderTreeElemRow(claimId, el) {
  const isSelected = _selectedElement.claimId === claimId && _selectedElement.elementId === el.element_id;
  const hasDef = el.definition_text && el.definition_text.trim().length > 0;

  const defIcon = hasDef
    ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="14" height="14">
         <circle cx="12" cy="12" r="10"/><polyline points="9 12 11 14 15 10"/>
       </svg>`
    : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="14" height="14">
         <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
       </svg>`;

  return `
    <div class="tree-elem-row ${isSelected ? 'tree-elem-row--selected' : ''}"
         onclick="event.stopPropagation(); selectClaimElement(${claimId}, ${el.element_id})">
      <span class="tree-elem-bullet">·</span>
      <span class="tree-elem-name">${esc(el.element_name)}</span>
      ${isSelected ? '<span class="tree-elem-selected-badge">SELECTED</span>' : ''}
      <div class="tree-elem-actions">
        <span class="tree-elem-def-icon ${hasDef ? 'def-icon--ready' : 'def-icon--incomplete'}"
              title="${hasDef ? 'Definition complete' : 'Definition missing'}">
          ${defIcon}
        </span>
        <button class="tree-elem-unlink-btn"
                onclick="event.stopPropagation(); unlinkElementFromClaim(${claimId}, ${el.element_id})"
                title="Unlink from this claim">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
          </svg>
        </button>
      </div>
    </div>
  `;
}

function selectClaim(claimId) {
  _selectedClaimId = claimId;
  // Re-render claim list to update selection highlight
  renderClaimList(_claims);
  updateQueueHint();
  // Phase 7 will hook into this — stub for now
  onClaimSelected(claimId);
}

function onClaimSelected(claimId) {
  const claim = _claims.find(c => c.claim_id === claimId);
  if (!claim) return;

  // Update subtitle in right panel header
  const label = document.getElementById('draftClaimLabel');
  if (label) {
    label.textContent = `Claim ${claim.claim_number} — ${claim.claim_dependency_type}, ${claim.claim_category}`;
  }

  // Render the draft textarea
  const draftBody = document.getElementById('draftBody');
  if (draftBody) {
    draftBody.innerHTML = '<textarea class="draft-textarea" id="draftTextarea" oninput="onDraftInput()" placeholder="Enter or edit the draft text for this claim…"></textarea>';
    document.getElementById('draftTextarea').value = claim.claim_text || '';
  }

  // Enable Save button and show save status
  const btnSave = document.getElementById('btnSaveDraft');
  if (btnSave) btnSave.disabled = false;

  const statusEl = document.getElementById('draftSaveStatus');
  if (statusEl) {
    statusEl.style.visibility = 'visible';
    document.getElementById('draftSaveStatusText').textContent = 'Not saved yet';
  }
}

function onDraftInput() {
  const statusText = document.getElementById('draftSaveStatusText');
  if (statusText) statusText.textContent = 'Unsaved changes';
}

async function saveDraftText() {
  if (!_selectedClaimId) return;
  const patentId = getPatentId();
  const textarea = document.getElementById('draftTextarea');
  if (!textarea) return;

  const claimText = textarea.value;

  try {
    await api('/patents/' + patentId + '/claims/' + _selectedClaimId + '/text', {
      method: 'PATCH',
      body: JSON.stringify({ claim_text: claimText }),
    });
    // Update in-memory cache
    const cached = _claims.find(c => c.claim_id === _selectedClaimId);
    if (cached) cached.claim_text = claimText;

    const statusText = document.getElementById('draftSaveStatusText');
    if (statusText) statusText.textContent = 'Saved';
  } catch (e) {
    alert('Failed to save draft: ' + e.message);
  }
}

function rewriteWithReport() {
  alert('Rewrite with Report — coming soon.');
}

function goToAIDraft() {
  alert('AI Draft — coming soon.');
}

async function deleteClaim(claimId) {
  if (!confirm('Delete this claim? Dependent claims will also be removed.')) return;
  const patentId = getPatentId();
  try {
    await api('/patents/' + patentId + '/claims/' + claimId, { method: 'DELETE' });
    delete _claimElements[claimId];
    delete _claimExpanded[claimId];
    if (_selectedClaimId === claimId) {
      _selectedClaimId = null;
      const label = document.getElementById('draftClaimLabel');
      if (label) label.textContent = 'Select a claim to edit its draft text.';
      const draftBody = document.getElementById('draftBody');
      if (draftBody) draftBody.innerHTML = '<p class="ws-empty-msg">No claim selected.</p>';
      const btnSave = document.getElementById('btnSaveDraft');
      if (btnSave) btnSave.disabled = true;
      const statusEl = document.getElementById('draftSaveStatus');
      if (statusEl) statusEl.style.visibility = 'hidden';
      updateQueueHint();
    }
    if (_selectedElement.claimId === claimId) {
      _selectedElement = { claimId: null, elementId: null };
    }
    await loadClaims();
  } catch (e) {
    alert('Failed to delete claim: ' + e.message);
  }
}

// ═══════════════════════════════════════════════════════════════
// Add Claim Modal
// ═══════════════════════════════════════════════════════════════

function openAddClaimModal() {
  // Reset the form to defaults
  document.querySelectorAll('input[name="claimDependencyType"]').forEach(r => {
    r.checked = r.value === 'independent';
  });
  document.getElementById('selectClaimCategory').value = 'apparatus';
  document.getElementById('parentClaimSection').style.display = 'none';
  _populateParentClaimDropdown();
  document.getElementById('addClaimModal').classList.add('active');
}

function closeAddClaimModal() {
  document.getElementById('addClaimModal').classList.remove('active');
}

function onDependencyTypeChange() {
  const dep = document.querySelector('input[name="claimDependencyType"]:checked')?.value;
  document.getElementById('parentClaimSection').style.display =
    dep === 'dependent' ? 'block' : 'none';
}

function _populateParentClaimDropdown() {
  const sel = document.getElementById('selectParentClaim');
  sel.innerHTML = '<option value="">— select a parent claim —</option>';
  _claims.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.claim_id;
    opt.textContent = `Claim ${c.claim_number} (${c.claim_dependency_type}, ${c.claim_category})`;
    sel.appendChild(opt);
  });
}

async function submitAddClaim() {
  const patentId = getPatentId();
  const depType  = document.querySelector('input[name="claimDependencyType"]:checked')?.value;
  const category = document.getElementById('selectClaimCategory').value;

  let parentClaimId = null;
  if (depType === 'dependent') {
    const raw = document.getElementById('selectParentClaim').value;
    if (!raw) {
      alert('Please select a parent claim for a dependent claim.');
      return;
    }
    parentClaimId = parseInt(raw, 10);
  }

  const payload = {
    claim_dependency_type: depType,
    claim_category: category,
    parent_claim_id: parentClaimId,
  };

  try {
    await api('/patents/' + patentId + '/claims', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    closeAddClaimModal();
    await loadClaims();
  } catch (e) {
    alert('Failed to add claim: ' + e.message);
  }
}

// ═══════════════════════════════════════════════════════════════
// Claim-local element management — Phase 6B.1
// ═══════════════════════════════════════════════════════════════

function toggleClaimExpanded(claimId) {
  _claimExpanded[claimId] = !(_claimExpanded[claimId] !== false);
  renderClaimList(_claims);
}

function selectClaimElement(claimId, elementId) {
  _selectedElement = { claimId, elementId };
  renderClaimList(_claims);
  // Open the richer Element Definition modal in edit mode
  openElementEditModal(elementId);
}

function openAddElementsModal(claimId) {
  _addElemTargetClaimId = claimId;
  const claim = _claims.find(c => c.claim_id === claimId);

  const title = document.getElementById('addElemsModalTitle');
  if (title) title.textContent = claim ? `Add Elements to Claim ${claim.claim_number}` : 'Add Elements';

  const alreadyLinked = new Set((_claimElements[claimId] || []).map(e => e.element_id));
  const available = _elements.filter(e => !alreadyLinked.has(e.element_id));

  const sel = document.getElementById('selectElemToLink');
  if (sel) {
    if (available.length === 0) {
      sel.innerHTML = '<option value="">All elements are already linked to this claim</option>';
    } else {
      sel.innerHTML = '<option value="">— select an element —</option>' +
        available.map(e =>
          `<option value="${e.element_id}">${esc(e.element_name)}${e.reference_number !== null && e.reference_number !== undefined ? ` (Ref ${e.reference_number})` : ''}</option>`
        ).join('');
    }
  }

  const btn = document.getElementById('btnConfirmLinkElem');
  if (btn) btn.disabled = available.length === 0;

  document.getElementById('addElementsModal').classList.add('active');
}

function closeAddElementsModal() {
  document.getElementById('addElementsModal').classList.remove('active');
  _addElemTargetClaimId = null;
}

async function submitLinkElement() {
  const claimId = _addElemTargetClaimId;
  if (!claimId) return;

  const raw = document.getElementById('selectElemToLink').value;
  if (!raw) {
    alert('Please select an element to link.');
    return;
  }

  const elementId = parseInt(raw, 10);
  const patentId  = getPatentId();

  try {
    await api('/patents/' + patentId + '/claims/' + claimId + '/elements', {
      method: 'POST',
      body: JSON.stringify({ element_id: elementId }),
    });
    // Reload linked elements for just this claim
    _claimElements[claimId] = await api(
      '/patents/' + patentId + '/claims/' + claimId + '/elements'
    );
    closeAddElementsModal();
    renderClaimList(_claims);
  } catch (e) {
    alert('Failed to link element: ' + e.message);
  }
}

async function unlinkElementFromClaim(claimId, elementId) {
  const patentId = getPatentId();
  try {
    await api('/patents/' + patentId + '/claims/' + claimId + '/elements/' + elementId, {
      method: 'DELETE',
    });
    if (_selectedElement.claimId === claimId && _selectedElement.elementId === elementId) {
      _selectedElement = { claimId: null, elementId: null };
    }
    _claimElements[claimId] = await api(
      '/patents/' + patentId + '/claims/' + claimId + '/elements'
    );
    renderClaimList(_claims);
  } catch (e) {
    alert('Failed to unlink element: ' + e.message);
  }
}

function filterElemTree(claimId, query) {
  _elemTreeSearch[claimId] = query;
  renderClaimList(_claims);
  // Restore focus to the search input after re-render
  const input = document.querySelector(`[data-search-claim="${claimId}"]`);
  if (input) {
    input.focus();
    const len = input.value.length;
    input.setSelectionRange(len, len);
  }
}

async function refreshClaimElements(claimId) {
  const patentId = getPatentId();
  try {
    _claimElements[claimId] = await api(
      '/patents/' + patentId + '/claims/' + claimId + '/elements'
    );
    renderClaimList(_claims);
  } catch (e) {
    console.error('Failed to refresh claim elements:', e);
  }
}

async function reorderElement(claimId, elementId, direction) {
  const patentId = getPatentId();
  try {
    await api('/patents/' + patentId + '/claims/' + claimId + '/elements/' + elementId, {
      method: 'PATCH',
      body: JSON.stringify({ direction }),
    });
    _claimElements[claimId] = await api(
      '/patents/' + patentId + '/claims/' + claimId + '/elements'
    );
    renderClaimList(_claims);
  } catch (e) {
    alert('Failed to reorder element: ' + e.message);
  }
}

// ═══════════════════════════════════════════════════════════════
// Element Queue — Phase 6A.1 / 6A.2
// ═══════════════════════════════════════════════════════════════

async function loadElements() {
  const patentId = getPatentId();
  if (!patentId) return;

  try {
    const elements = await api('/patents/' + patentId + '/elements');
    _elements = elements;
    renderElementQueue(elements);
  } catch (e) {
    console.error('Failed to load elements:', e);
  }
}

function renderElementQueue(elements) {
  const container = document.getElementById('elementQueue');
  if (!container) return;

  if (elements.length === 0) {
    container.innerHTML = '<p class="ws-empty-msg">No elements yet. Add an element to start building the patent-level pool.</p>';
    return;
  }

  container.innerHTML = elements.map(el => `
    <div class="element-card">
      <div class="element-drag-handle" aria-hidden="true">
        <svg viewBox="0 0 10 16" fill="currentColor" width="10" height="16">
          <circle cx="3" cy="2" r="1.5"/><circle cx="7" cy="2" r="1.5"/>
          <circle cx="3" cy="7" r="1.5"/><circle cx="7" cy="7" r="1.5"/>
          <circle cx="3" cy="12" r="1.5"/><circle cx="7" cy="12" r="1.5"/>
        </svg>
      </div>
      <div class="element-card-main">
        <div class="element-card-name">${esc(el.element_name)}</div>
        <div class="element-card-meta">
          ${el.reference_number !== null && el.reference_number !== undefined
            ? `<span class="element-ref">Ref ${el.reference_number}</span>`
            : `<span class="element-ref element-ref--muted">No ref</span>`}
        </div>
      </div>
      <div class="element-card-actions">
        <span class="element-drag-label">Drag</span>
        <button class="btn btn-sm btn-ghost element-edit-btn"
                onclick="openElementEditModal(${el.element_id})"
                title="Edit element">Edit</button>
        <button class="btn btn-sm btn-ghost element-delete-btn"
                onclick="deleteElement(${el.element_id})"
                title="Delete element">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
          </svg>
        </button>
      </div>
    </div>
  `).join('');
}

function updateQueueHint() {
  const hint = document.getElementById('queueHint');
  if (!hint) return;

  if (!_selectedClaimId) {
    hint.textContent = 'No claim selected.';
    hint.classList.remove('ws-queue-hint--active');
    return;
  }

  const claim = _claims.find(c => c.claim_id === _selectedClaimId);
  if (!claim) {
    hint.textContent = 'No claim selected.';
    hint.classList.remove('ws-queue-hint--active');
    return;
  }

  hint.textContent = `Selected: Claim ${claim.claim_number}`;
  hint.classList.add('ws-queue-hint--active');
}

async function deleteElement(elementId) {
  if (!confirm('Delete this element from the patent-level pool?')) return;

  const patentId = getPatentId();
  try {
    await api('/patents/' + patentId + '/elements/' + elementId, { method: 'DELETE' });
    await loadElements();
  } catch (e) {
    alert('Failed to delete element: ' + e.message);
  }
}

// ═══════════════════════════════════════════════════════════════
// Element Definition Modal — Phase 6A.2
// ═══════════════════════════════════════════════════════════════

let _elemDefMode = 'create';   // 'create' | 'edit'
let _elemDefId   = null;       // element_id when editing

// Called by "+ Add Element" button — opens in create mode
function openAddElementModal() {
  _elemDefMode = 'create';
  _elemDefId   = null;

  // Reset form
  document.getElementById('defElementName').value    = '';
  document.getElementById('defReferenceNumber').value = '';
  document.getElementById('defDefinitionText').value  = '';
  document.getElementById('elemDefStatus').innerHTML  = _defStatusHtml('Not saved yet');

  // Hide edit-only UI
  document.getElementById('elemContextRow').style.display  = 'none';
  document.getElementById('elemSavedBadge').style.display  = 'none';
  document.getElementById('elemSlotInfo').style.display    = 'none';

  // Linked claims: show empty state in create mode
  document.getElementById('linkedClaimsList').innerHTML =
    '<p class="elem-no-links">No linked claims yet.</p>';

  document.getElementById('elementDefModal').classList.add('active');
  document.getElementById('defElementName').focus();
}

// Called by Edit button on an element card — opens in edit mode
async function openElementEditModal(elementId) {
  const patentId = getPatentId();
  const el = _elements.find(e => e.element_id === elementId);
  if (!el) return;

  _elemDefMode = 'edit';
  _elemDefId   = elementId;

  // Populate fields
  document.getElementById('defElementName').value    = el.element_name;
  document.getElementById('defReferenceNumber').value = el.reference_number ?? '';
  document.getElementById('defDefinitionText').value  = el.definition_text  ?? '';
  document.getElementById('elemDefStatus').innerHTML  = _defStatusHtml('Not saved yet');

  // Show edit-only UI
  document.getElementById('elemContextRow').style.display = 'flex';
  document.getElementById('elemBreadcrumbName').textContent = el.element_name;
  document.getElementById('elemIdBadge').textContent = 'ID: ' + el.element_id;
  document.getElementById('elemSavedBadge').style.display = 'inline-flex';

  // Fetch and render linked claims (slot context)
  try {
    const links = await api('/patents/' + patentId + '/elements/' + elementId + '/links');
    _renderLinkedClaims(links);
  } catch (_) {
    document.getElementById('linkedClaimsList').innerHTML =
      '<p class="elem-no-links">Could not load linked claims.</p>';
    document.getElementById('elemSlotInfo').style.display = 'none';
  }

  document.getElementById('elementDefModal').classList.add('active');
  document.getElementById('defElementName').focus();
}

function _renderLinkedClaims(links) {
  const list = document.getElementById('linkedClaimsList');
  const slotEl = document.getElementById('elemSlotInfo');

  if (links.length === 0) {
    list.innerHTML = '<p class="elem-no-links">No linked claims yet.</p>';
    slotEl.style.display = 'none';
    return;
  }

  list.innerHTML = links.map(l => `
    <div class="linked-claim-item">
      <span class="linked-claim-number">Claim ${l.claim_number}</span>
      <span class="linked-claim-slot">Slot ${l.order_index}</span>
    </div>
  `).join('');

  // Show slot info under the element name (first linked claim's slot)
  slotEl.textContent = `Main Definition (Slot ${links[0].order_index})`;
  slotEl.style.display = 'block';
}

function _defStatusHtml(text) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
  </svg> ${text}`;
}

function closeElementDefModal() {
  document.getElementById('elementDefModal').classList.remove('active');
  _elemDefMode = 'create';
  _elemDefId   = null;
}

// Marks definition as having unsaved changes when the user types
function onDefinitionInput() {
  document.getElementById('elemDefStatus').innerHTML = _defStatusHtml('Unsaved changes');
}

function aiSuggestDefinition() {
  alert('AI Suggest Definition — coming soon.');
}

function copyDefinition() {
  const text = document.getElementById('defDefinitionText').value;
  if (text) {
    navigator.clipboard.writeText(text).catch(() => {});
  }
}

function clearDefinition() {
  document.getElementById('defDefinitionText').value = '';
  document.getElementById('elemDefStatus').innerHTML = _defStatusHtml('Not saved yet');
}

async function submitElementDef() {
  const patentId = getPatentId();
  const name     = document.getElementById('defElementName').value.trim();
  const refRaw   = document.getElementById('defReferenceNumber').value.trim();
  const defText  = document.getElementById('defDefinitionText').value.trim();

  if (!name) {
    alert('Element Name is required.');
    document.getElementById('defElementName').focus();
    return;
  }

  let referenceNumber = null;
  if (refRaw) {
    referenceNumber = parseInt(refRaw, 10);
    if (Number.isNaN(referenceNumber) || referenceNumber < 0) {
      alert('Reference Number must be a non-negative integer.');
      document.getElementById('defReferenceNumber').focus();
      return;
    }
  }

  const payload = {
    element_name:     name,
    reference_number: referenceNumber,
    definition_text:  defText || null,
  };

  try {
    if (_elemDefMode === 'create') {
      await api('/patents/' + patentId + '/elements', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    } else {
      await api('/patents/' + patentId + '/elements/' + _elemDefId, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
    }
    closeElementDefModal();
    // Reload elements; in edit mode also reload claims so status badges update
    if (_elemDefMode === 'edit') {
      await Promise.all([loadElements(), loadClaims()]);
    } else {
      await loadElements();
    }
  } catch (e) {
    alert('Failed to save element: ' + e.message);
  }
}

// ═══════════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  const patentId = getPatentId();

  if (!patentId) {
    document.getElementById('navPatentName').textContent = 'No project selected';
    return;
  }

  loadPatentInfo(patentId);
  loadClaims();
  loadElements();
  updateQueueHint();
});
