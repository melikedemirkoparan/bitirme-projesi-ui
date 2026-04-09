/* ═══════════════════════════════════════════════════════════════
   Patent Drafting Tool — Frontend JS
   ═══════════════════════════════════════════════════════════════ */

// ── State ───────────────────────────────────────────────────────
const state = {
  dataLoaded: false,
  currentProject: null,
  projects: [],
  claims: [],          // [{name, elements:[{name,refNum,definition}]}]
  queueElements: [],   // [{name, status:'pending'|'done', definition}]
  draftText: '',
  composerClaims: '',
  composerDraft: '',
};

// ── Navigation ──────────────────────────────────────────────────
function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const page = document.getElementById(id);
  if (page) page.classList.add('active');
}

// ── API helpers ─────────────────────────────────────────────────
async function api(path, opts = {}) {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  return res.json();
}

// ── Data upload ─────────────────────────────────────────────────
async function uploadExcel(file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch('/api/upload-excel', { method: 'POST', body: form });
  return res.json();
}

// ═══════════════════════════════════════════════════════════════
// Dashboard
// ═══════════════════════════════════════════════════════════════

function renderProjectList() {
  const list = document.getElementById('projectList');
  if (!list) return;
  list.innerHTML = state.projects.map(p => `
    <div class="project-item ${state.currentProject?.id === p.id ? 'active' : ''}"
         onclick="openProject('${p.id}')">
      <div>
        <div class="project-item-name">${esc(p.name)}</div>
        <div class="project-item-sub">Patent Drafting Project</div>
      </div>
      <span class="btn btn-sm btn-ghost">Open</span>
    </div>
  `).join('');
}

async function createNewProject() {
  const name = prompt('Project name:');
  if (!name) return;
  const p = await api('/projects', {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
  state.projects.push(p);
  renderProjectList();
}

async function openProject(id) {
  const p = state.projects.find(x => x.id === id);
  if (!p) return;
  state.currentProject = p;

  // Restore project state
  state.claims = p.claims || [];
  state.queueElements = p.elements || [];
  state.draftText = p.draft || '';

  if (state.claims.length === 0) {
    state.claims = [
      { name: 'Claim 1', elements: [] },
    ];
  }

  renderProjectList();
  showPage('page-editor');
  renderClaims();
  renderQueue();
  renderDraft();
  document.getElementById('projectNameDisplay').textContent = p.name;
}

// ═══════════════════════════════════════════════════════════════
// Claims Panel
// ═══════════════════════════════════════════════════════════════

function renderClaims() {
  const container = document.getElementById('claimsContainer');
  container.innerHTML = state.claims.map((claim, ci) => `
    <div class="claim-block">
      <div class="claim-block-header">
        <span class="claim-name">
          <span class="tag tag-blue">●</span>
          ${esc(claim.name)}
        </span>
        <div style="display:flex;gap:4px;">
          <button class="btn btn-sm tag-green" onclick="promptAddElement(${ci})">+ Add Element</button>
        </div>
      </div>
      <div class="element-tree">
        <div class="element-tree-title">
          ELEMENT TREE
          <span style="font-size:10px;color:var(--text-muted)">${claim.elements.length}</span>
        </div>
        <div class="search-box">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input type="search" placeholder="Search elements…" oninput="filterElements(${ci}, this.value)">
        </div>
        <div id="elementList-${ci}">
          ${claim.elements.map((el, ei) => `
            <div class="element-item" onclick="openElementDef(${ci}, ${ei})">
              <span>${esc(el.name)} ${el.refNum ? '('+el.refNum+')' : ''}</span>
              <div class="element-item-actions">
                <button onclick="event.stopPropagation();sendToQueue(${ci},${ei})" title="Send to queue">⚡</button>
                <button class="del" onclick="event.stopPropagation();removeElement(${ci},${ei})" title="Remove">×</button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `).join('');
}

function promptAddElement(claimIdx) {
  const name = prompt('Element name:');
  if (!name) return;
  const refNum = prompt('Reference number (optional):') || '';
  state.claims[claimIdx].elements.push({ name, refNum, definition: '' });
  renderClaims();

  // Also add to queue
  if (!state.queueElements.find(q => q.name === name)) {
    state.queueElements.push({ name, refNum, status: 'pending', definition: '' });
    renderQueue();
  }
}

function removeElement(ci, ei) {
  state.claims[ci].elements.splice(ei, 1);
  renderClaims();
}

function filterElements(ci, query) {
  const list = document.getElementById(`elementList-${ci}`);
  if (!list) return;
  const items = list.querySelectorAll('.element-item');
  items.forEach(item => {
    const match = item.textContent.toLowerCase().includes(query.toLowerCase());
    item.style.display = match ? '' : 'none';
  });
}

function addClaim() {
  const num = state.claims.length + 1;
  state.claims.push({ name: `Claim ${num}`, elements: [] });
  renderClaims();
}

function sendToQueue(ci, ei) {
  const el = state.claims[ci].elements[ei];
  if (!state.queueElements.find(q => q.name === el.name)) {
    state.queueElements.push({ name: el.name, refNum: el.refNum, status: 'pending', definition: '' });
    renderQueue();
  }
}

// ═══════════════════════════════════════════════════════════════
// Extraction Queue
// ═══════════════════════════════════════════════════════════════

function renderQueue() {
  const container = document.getElementById('queueContainer');
  container.innerHTML = state.queueElements.map((el, i) => `
    <div class="queue-item" onclick="openElementDef(-1, -1, '${esc(el.name)}')">
      <div class="queue-item-left">
        <div class="queue-item-check ${el.status === 'done' ? 'done' : ''}"></div>
        <span class="queue-item-name">${esc(el.name)}</span>
      </div>
      <span class="queue-item-status">${el.status === 'done' ? 'Done' : 'Pending'}</span>
    </div>
  `).join('');
}

// ═══════════════════════════════════════════════════════════════
// Element Definition Modal
// ═══════════════════════════════════════════════════════════════

let currentDefElement = null;

function openElementDef(ci, ei, queueName) {
  let elName, refNum, definition;

  if (queueName) {
    const qEl = state.queueElements.find(q => q.name === queueName);
    elName = qEl.name;
    refNum = qEl.refNum || '';
    definition = qEl.definition || '';
  } else {
    const el = state.claims[ci].elements[ei];
    elName = el.name;
    refNum = el.refNum || '';
    definition = el.definition || '';
  }

  currentDefElement = { ci, ei, name: elName, refNum, queueName };

  document.getElementById('defElementName').textContent = elName;
  document.getElementById('defRefNum').textContent = refNum || '-';
  document.getElementById('defTextarea').value = definition;
  document.getElementById('defModal').classList.add('active');
}

function closeDefModal() {
  document.getElementById('defModal').classList.remove('active');
}

function saveDefinition() {
  const text = document.getElementById('defTextarea').value;
  if (!currentDefElement) return;

  // Save to claim element
  if (currentDefElement.ci >= 0 && currentDefElement.ei >= 0) {
    state.claims[currentDefElement.ci].elements[currentDefElement.ei].definition = text;
  }

  // Save to queue element
  const qEl = state.queueElements.find(q => q.name === currentDefElement.name);
  if (qEl) {
    qEl.definition = text;
    if (text.trim()) qEl.status = 'done';
  }

  // Also update all claim elements with same name
  state.claims.forEach(c => {
    c.elements.forEach(el => {
      if (el.name === currentDefElement.name) el.definition = text;
    });
  });

  renderQueue();
  closeDefModal();
}

async function aiSuggestDefinition() {
  if (!state.dataLoaded) {
    alert('Please upload the Excel data file first (from Dashboard).');
    return;
  }

  const elName = currentDefElement.name;
  const context = state.currentProject?.context || '';
  const bbfText = state.currentProject?.bbf_text || '';

  const btn = document.getElementById('btnAiSuggest');
  btn.innerHTML = '<span class="spinner"></span> Generating…';
  btn.disabled = true;

  try {
    const result = await api('/generate-definition', {
      method: 'POST',
      body: JSON.stringify({
        element_name: elName,
        context: context,
        bbf_text: bbfText,
        top_k: 5,
      }),
    });

    document.getElementById('defTextarea').value = result.final_definition || '';

    // Show suggestions modal
    showAiSuggestions(result);
  } catch (e) {
    alert('Error: ' + e.message);
  } finally {
    btn.innerHTML = '⚡ AI Suggested Definition';
    btn.disabled = false;
  }
}

function showAiSuggestions(result) {
  const container = document.getElementById('suggestionsContent');

  const retrieved = result.retrieved_examples || [];
  const ragFrag = result.rag_fragment || '';
  const bbfFrag = result.bbf_fragment || '';
  const finalDef = result.final_definition || '';

  container.innerHTML = `
    <div class="suggestions-grid">
      <div class="suggestion-col">
        <h5>RAG Fragment</h5>
        <p style="font-size:12px;color:var(--text-secondary);margin-bottom:12px">${esc(ragFrag)}</p>
        <h5 style="margin-top:12px">Retrieved Examples</h5>
        <ul>
          ${retrieved.map(r => `
            <li onclick="selectSuggestion(this, '${escAttr(r.definition_en)}')"
                title="${esc(r.title_en)}">
              <strong>${esc(r.element_name_en)}</strong><br>
              <span style="font-size:11px;color:var(--text-muted)">${esc(r.definition_en.substring(0, 120))}…</span>
            </li>
          `).join('')}
        </ul>
      </div>
      <div class="suggestion-col">
        <h5>BBF Fragment</h5>
        <p style="font-size:12px;color:var(--text-secondary)">${esc(bbfFrag) || '<em>No BBF text provided</em>'}</p>
      </div>
      <div class="suggestion-col">
        <h5>Final Definition</h5>
        <p style="font-size:13px;color:var(--text-primary);font-weight:500">${esc(finalDef)}</p>
      </div>
    </div>
  `;

  document.getElementById('suggestionsModal').classList.add('active');
}

function selectSuggestion(li, text) {
  document.querySelectorAll('.suggestion-col li').forEach(l => l.classList.remove('selected'));
  li.classList.add('selected');
  document.getElementById('defTextarea').value = text;
}

function useSelectedSuggestion() {
  document.getElementById('suggestionsModal').classList.remove('active');
}

function closeSuggestionsModal() {
  document.getElementById('suggestionsModal').classList.remove('active');
}

function copyDefinition() {
  const text = document.getElementById('defTextarea').value;
  navigator.clipboard.writeText(text);
}

// ═══════════════════════════════════════════════════════════════
// Draft Editor
// ═══════════════════════════════════════════════════════════════

function renderDraft() {
  const ta = document.getElementById('draftTextarea');
  if (ta) ta.value = state.draftText;
}

function goToAiDraft() {
  // Build draft text from definitions
  let text = '';
  state.claims.forEach(claim => {
    text += claim.name + ':\n';
    claim.elements.forEach(el => {
      if (el.definition) {
        text += `  ${el.name} ${el.refNum ? '(' + el.refNum + ')' : ''}: ${el.definition}\n`;
      }
    });
    text += '\n';
  });
  state.draftText = text;
  renderDraft();
}

function insertDraftReport() {
  const defs = [];
  state.claims.forEach(claim => {
    claim.elements.forEach(el => {
      if (el.definition) {
        defs.push(`${el.name} ${el.refNum ? '(' + el.refNum + ')' : ''}: ${el.definition}`);
      }
    });
  });
  const report = 'ELEMENT DEFINITIONS REPORT\n' +
    '═'.repeat(40) + '\n\n' +
    defs.join('\n\n') + '\n';
  const ta = document.getElementById('draftTextarea');
  ta.value = report;
  state.draftText = report;
}

// ═══════════════════════════════════════════════════════════════
// Draft Composer Page
// ═══════════════════════════════════════════════════════════════

function openComposer() {
  // Pre-fill claims input from current state
  let claimText = '';
  state.claims.forEach(claim => {
    claimText += claim.name + ':\n';
    claim.elements.forEach(el => {
      claimText += `  - ${el.name} ${el.refNum ? '(' + el.refNum + ')' : ''}`;
      if (el.definition) claimText += ` — ${el.definition}`;
      claimText += '\n';
    });
    claimText += '\n';
  });
  state.composerClaims = claimText;

  document.getElementById('composerClaimsInput').value = claimText;
  document.getElementById('composerDraftOutput').innerHTML = state.composerDraft || '<p style="color:var(--text-muted)">Click "Generate Draft" to create patent description…</p>';
  showPage('page-composer');
}

async function generateDraft() {
  const claimsText = document.getElementById('composerClaimsInput').value;
  const btn = document.getElementById('btnGenerateDraft');
  btn.innerHTML = '<span class="spinner"></span> Generating…';
  btn.disabled = true;

  // Build a structured draft from available definitions
  let draft = '';
  draft += '<h4>1. Title</h4><p>' + (state.currentProject?.name || 'Patent Application') + '</p>';
  draft += '<h4>2. Technical Field</h4><p>The present invention relates to ' + (state.currentProject?.context || 'the described technical field') + '.</p>';
  draft += '<h4>3. Element Definitions</h4>';

  state.claims.forEach(claim => {
    claim.elements.forEach(el => {
      if (el.definition) {
        draft += `<p><strong>${el.name} ${el.refNum ? '(' + el.refNum + ')' : ''}</strong>: ${el.definition}</p>`;
      }
    });
  });

  draft += '<h4>4. Claims</h4>';
  draft += '<pre style="white-space:pre-wrap;color:var(--text-secondary)">' + esc(claimsText) + '</pre>';

  // Simulate a bit of delay for UX
  await new Promise(r => setTimeout(r, 500));

  state.composerDraft = draft;
  document.getElementById('composerDraftOutput').innerHTML = draft;

  btn.innerHTML = '⚡ Generate Draft';
  btn.disabled = false;
}

function backToEditor() {
  showPage('page-editor');
}

// ═══════════════════════════════════════════════════════════════
// Upload / Settings Modal
// ═══════════════════════════════════════════════════════════════

function openUploadModal() {
  document.getElementById('uploadModal').classList.add('active');
}
function closeUploadModal() {
  document.getElementById('uploadModal').classList.remove('active');
}

async function handleFileUpload(input) {
  const file = input.files[0];
  if (!file) return;

  const statusEl = document.getElementById('uploadStatus');
  statusEl.innerHTML = '<span class="loading-text"><span class="spinner"></span> Loading & building embeddings… This may take a few minutes.</span>';

  try {
    const result = await uploadExcel(file);
    if (result.error) {
      statusEl.innerHTML = `<span style="color:var(--danger)">Error: ${result.error}</span>`;
      return;
    }
    // Poll for completion
    statusEl.innerHTML = '<span class="loading-text"><span class="spinner"></span> Building embeddings… This takes a few minutes the first time. (Subsequent loads will be instant from cache.)</span>';
    const poll = setInterval(async () => {
      const s = await api('/data-status');
      if (s.status === 'done') {
        clearInterval(poll);
        state.dataLoaded = true;
        statusEl.innerHTML = `<span style="color:var(--success)">✓ Loaded ${s.count} documents. FAISS index ready.</span>`;
        document.getElementById('dataStatusBadge').textContent = '● Data Loaded';
        document.getElementById('dataStatusBadge').className = 'tag tag-green';
      } else if (s.status === 'error') {
        clearInterval(poll);
        statusEl.innerHTML = `<span style="color:var(--danger)">Error: ${s.error}</span>`;
      }
    }, 3000);
  } catch (e) {
    statusEl.innerHTML = `<span style="color:var(--danger)">Upload failed: ${e.message}</span>`;
  }
}

function openSettingsModal() {
  document.getElementById('settingsModal').classList.add('active');
}
function closeSettingsModal() {
  document.getElementById('settingsModal').classList.remove('active');
}
function saveSettings() {
  const context = document.getElementById('settingsContext').value;
  const bbf = document.getElementById('settingsBBF').value;
  if (state.currentProject) {
    state.currentProject.context = context;
    state.currentProject.bbf_text = bbf;
  }
  closeSettingsModal();
}

// ═══════════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════════

function esc(s) {
  if (!s) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function escAttr(s) {
  return (s || '').replace(/'/g, "\\'").replace(/\n/g, ' ').substring(0, 200);
}

// ── Init ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Check data status
  const status = await api('/data-status');
  state.dataLoaded = status.loaded;
  if (status.loaded) {
    document.getElementById('dataStatusBadge').textContent = '● Data Loaded';
    document.getElementById('dataStatusBadge').className = 'tag tag-green';
  }

  // Load projects
  state.projects = await api('/projects');
  renderProjectList();

  showPage('page-dashboard');
});
