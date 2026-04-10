/* ═══════════════════════════════════════════════════════════════
   Patent Drafting Tool — Home Page JS
   ═══════════════════════════════════════════════════════════════ */

// ── API helper ─────────────────────────────────────────────────

async function api(path, opts = {}) {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

// ── Utility ────────────────────────────────────────────────────

function esc(s) {
  if (!s) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

// ═══════════════════════════════════════════════════════════════
// Project List
// ═══════════════════════════════════════════════════════════════

async function loadProjects() {
  try {
    const projects = await api('/patents');
    renderProjectList(projects);
  } catch (e) {
    console.error('Failed to load projects:', e);
  }
}

function renderProjectList(projects) {
  const list = document.getElementById('projectList');
  if (!list) return;

  if (projects.length === 0) {
    list.innerHTML = '<p class="empty-list-msg">No projects yet. Click "+ New Project" to get started.</p>';
    return;
  }

  list.innerHTML = projects.map(p => `
    <div class="project-item" onclick="openProject(${p.patent_id})">
      <div>
        <div class="project-item-name">${esc(p.patent_name)}</div>
        <div class="project-item-sub">TUSAS Project Environment</div>
      </div>
      <span class="btn btn-sm btn-ghost">Open</span>
    </div>
  `).join('');
}

function openProject(patentId) {
  // Navigate to the project workspace.
  // For now, log the intent — workspace page will be implemented later.
  console.log('Open project:', patentId);
  alert('Project workspace will be implemented in the next step. Patent ID: ' + patentId);
}

// ═══════════════════════════════════════════════════════════════
// New Project Modal
// ═══════════════════════════════════════════════════════════════

function openNewProjectModal() {
  resetNewProjectForm();
  document.getElementById('newProjectModal').classList.add('active');
}

function closeNewProjectModal() {
  document.getElementById('newProjectModal').classList.remove('active');
}

function resetNewProjectForm() {
  document.getElementById('inputPatentName').value = '';
  document.getElementById('inputPatentOwner').value = '';

  // Uncheck all document type checkboxes and hide their sections
  ['chkDisclosure', 'chkResearch', 'chkQna'].forEach(id => {
    document.getElementById(id).checked = false;
  });
  ['sectionDisclosure', 'sectionResearch', 'sectionQna'].forEach(id => {
    document.getElementById(id).style.display = 'none';
  });

  // Clear all text inputs inside document sections
  document.querySelectorAll('.doc-section textarea').forEach(ta => {
    ta.value = '';
  });
}

// Toggle visibility of document-type sections based on checkbox state.
// Each checkbox maps to a specific section containing the fields
// defined in docs/home_page.md (e.g., disclosure has 3 fields,
// research report has 4, inventor Q&A has 1).
function toggleDocSection(type) {
  const map = {
    disclosure: { checkbox: 'chkDisclosure', section: 'sectionDisclosure' },
    research:   { checkbox: 'chkResearch',   section: 'sectionResearch' },
    qna:        { checkbox: 'chkQna',        section: 'sectionQna' },
  };
  const entry = map[type];
  if (!entry) return;

  const checked = document.getElementById(entry.checkbox).checked;
  document.getElementById(entry.section).style.display = checked ? 'block' : 'none';
}

// ═══════════════════════════════════════════════════════════════
// Project Submission
// ═══════════════════════════════════════════════════════════════

async function submitNewProject() {
  const patentName = document.getElementById('inputPatentName').value.trim();
  const patentOwner = document.getElementById('inputPatentOwner').value.trim();

  // Validate required fields (docs/home_page.md: patent_name + patent_owner required)
  if (!patentName) {
    alert('Patent / Project Name is required.');
    document.getElementById('inputPatentName').focus();
    return;
  }
  if (!patentOwner) {
    alert('Patent Owner is required.');
    document.getElementById('inputPatentOwner').focus();
    return;
  }

  // Build the request payload following the shape from docs/home_page.md.
  // Only include document sections that were selected via checkbox.
  const payload = {
    patent_name: patentName,
    patent_owner: patentOwner,
  };

  if (document.getElementById('chkDisclosure').checked) {
    payload.invention_disclosure = {
      prior_art_and_problems: document.getElementById('inputPriorArt').value.trim() || null,
      closest_prior_patents:  document.getElementById('inputClosestPatents').value.trim() || null,
      novel_features:         document.getElementById('inputNovelFeatures').value.trim() || null,
    };
  }

  if (document.getElementById('chkResearch').checked) {
    payload.research_report = {
      executive_summary:          document.getElementById('inputExecSummary').value.trim() || null,
      search_strategy:            document.getElementById('inputSearchStrategy').value.trim() || null,
      classification_and_keywords: document.getElementById('inputClassification').value.trim() || null,
      element_patent_analysis:    document.getElementById('inputElementAnalysis').value.trim() || null,
    };
  }

  if (document.getElementById('chkQna').checked) {
    payload.inventor_qna = {
      questions_and_answers: document.getElementById('inputQna').value.trim() || null,
    };
  }

  try {
    await api('/patents', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    closeNewProjectModal();
    // Reload the project list to show the newly created project
    await loadProjects();
  } catch (e) {
    alert('Failed to create project: ' + e.message);
  }
}

// ═══════════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  loadProjects();
});
