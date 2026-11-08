'use strict';
const $ = id => document.getElementById(id);
const state = {tab: 'propositions', offset: 0, selected: null, info: null, preview: null, form: null, listVersion: 0, detailVersion: 0};
const pageSize = 30;
function el(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
function button(text, action, className) { const node = el('button', text, className); node.type = 'button'; node.addEventListener('click', () => Promise.resolve().then(action).catch(showError)); return node; }
function badge(value) { return el('span', value.replaceAll('_', ' '), 'badge ' + value); }
function notice(message, error = false) { $('notice').hidden = !message; $('notice').textContent = message; $('notice').className = error ? 'error' : ''; }
function showError(error) { notice(error.message, true); }
async function api(path, body) {
  const options = body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Holon-Token': state.info.csrf_token}, body: JSON.stringify(body)};
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) { const error = new Error(data.error || 'Request failed'); error.status = response.status; throw error; }
  return data;
}
function pendingKey() { return 'holon-pending:' + state.info.database; }
function pending() { return JSON.parse(sessionStorage.getItem(pendingKey()) || 'null'); }
function pendingBanner() { $('pending').hidden = !pending(); }
async function command(operation, args, retry = false) {
  const old = pending();
  const proposed = {operation, arguments: args};
  if (old && !retry && JSON.stringify({operation: old.operation, arguments: old.arguments}) !== JSON.stringify(proposed)) {
    throw new Error('Retry the saved submission first so its outcome is known.');
  }
  const body = old || {request_id: crypto.randomUUID(), ...proposed};
  sessionStorage.setItem(pendingKey(), JSON.stringify(body)); pendingBanner();
  try {
    const result = await api('/api/commands', body);
    sessionStorage.removeItem(pendingKey()); pendingBanner();
    return result;
  } catch (error) {
    // A rejected transaction has no writes; transport/503 outcomes remain retryable.
    if (error.status && error.status < 500) { sessionStorage.removeItem(pendingKey()); pendingBanner(); }
    throw error;
  }
}
function rawDetails(title, data) { const details = el('details'); details.append(el('summary', title), el('pre', JSON.stringify(data, null, 2))); return details; }
async function loadList() {
  const version = ++state.listVersion;
  const query = new URLSearchParams({q: $('search').value, limit: pageSize, offset: state.offset});
  query.set(state.tab === 'propositions' ? 'status' : 'source', state.tab === 'propositions' ? $('status').value : $('source-filter').value);
  const data = await api('/api/' + state.tab + '?' + query);
  if (version !== state.listVersion) return;
  $('records').replaceChildren();
  for (const item of data.items) {
    const row = button('', () => select(item.id), 'record' + (state.selected === item.id ? ' active' : ''));
    row.append(el('strong', state.tab === 'propositions' ? item.claim : item.report.slice(0, 130)));
    row.append(el('small', state.tab === 'propositions' ? item.scope : item.source));
    row.append(state.tab === 'propositions' ? badge(item.status) : el('small', item.active_links + ' active evidence links'));
    $('records').append(row);
  }
  if (!data.items.length) $('records').append(el('p', 'No records match. Create one or adjust the filters.', 'muted'));
  $('prev').disabled = state.offset === 0;
  $('next').disabled = data.items.length < pageSize;
  $('page').textContent = 'Page ' + (state.offset / pageSize + 1);
}
async function select(id) {
  state.selected = id;
  const version = ++state.detailVersion;
  const tab = state.tab;
  const data = await api('/api/' + tab + '/' + encodeURIComponent(id));
  if (version !== state.detailVersion) return;
  if (tab === 'propositions') renderClaim(data); else renderObservation(data);
  const structurePanel = el('section', 'Loading dependency records…', 'panel');
  $('detail').append(structurePanel);
  try {
    const structure = await api(tab === 'propositions' ? '/api/derivations' : '/api/lineage');
    if (version !== state.detailVersion) return;
    structurePanel.replaceChildren(tab === 'propositions' ? derivationPanel(id, structure) : originPanel(id, structure));
  } catch (error) {
    if (version === state.detailVersion) structurePanel.replaceChildren(el('p', error.message, 'muted'), button('Retry loading', () => select(id)));
  }
  await loadList();
}
async function refresh() { await loadList(); if (state.selected) await select(state.selected); if ($('lineage-browser').open) await showLineage(); }
function fieldPair(label, value) { const block = el('div', undefined, 'review-field'); block.append(el('strong', label), el('p', value == null ? 'Unknown' : String(value))); return block; }
function renderClaim(data) {
  const main = $('detail'); main.replaceChildren();
  main.append(el('span', 'Scoped claim', 'eyebrow'), el('h1', data.proposition.claim), el('p', data.proposition.scope, 'muted'), badge(data.status));
  const actions = el('div', undefined, 'actions');
  actions.append(button('+ Add report', () => reportForm(data.proposition.id), 'primary'), button('Use an existing observation', async () => { await switchTab('observations'); notice('Choose an observation, then select “Link to a claim”.'); }));
  main.append(actions);
  const stats = el('div', undefined, 'stats');
  for (const [label, count] of [['Supporting', data.evidence.filter(e => e.active && e.relation === 'supports').length], ['Contradicting', data.evidence.filter(e => e.active && e.relation === 'contradicts').length], ['Withdrawn', data.evidence.filter(e => !e.active).length]]) {
    const stat = el('div', undefined, 'stat'); stat.append(el('strong', count), el('span', label)); stats.append(stat);
  }
  main.append(stats, el('h2', 'Evidence & reports'));
  if (!data.evidence.length) main.append(el('p', 'No evidence yet. Add a report or link an existing observation.', 'muted'));
  for (const evidence of data.evidence) {
    const card = el('article', undefined, 'evidence' + (evidence.active ? '' : ' inactive'));
    const head = el('div', undefined, 'evidence-head'); head.append(el('strong', evidence.source), badge(evidence.active ? evidence.relation : 'inactive'));
    card.append(head, el('p', evidence.report, 'report'), el('div', 'Observed: ' + (evidence.observed_at || 'unknown') + ' · Recorded: ' + evidence.recorded_at, 'meta'));
    if (evidence.model) card.append(el('p', 'Interpretation by ' + evidence.model + ': ' + evidence.reason, 'meta'));
    if (!evidence.active) card.append(el('p', 'Withdrawn by ' + evidence.withdrawal_actor + ': ' + evidence.withdrawal_reason + (evidence.replacement_evidence_id ? ' · Replacement retained in this history.' : ''), 'meta'));
    const controls = el('div', undefined, 'actions');
    controls.append(button('View observation', async () => { await switchTab('observations'); await select(evidence.observation_id); }));
    if (evidence.active) controls.append(button('Correct report', () => correctionForm(evidence)), button('Reinterpret', () => reinterpretForm(evidence)), button('Withdraw', () => withdrawalForm(evidence)));
    card.append(controls, rawDetails('Record IDs & provenance', evidence)); main.append(card);
  }
  const history = el('section', undefined, 'panel'); history.append(el('h2', 'Revision history'));
  if (!data.history.length) history.append(el('p', 'No evidence revisions yet.', 'muted'));
  else {
    const wrap = el('div', undefined, 'table-wrap'); const table = el('table'); const header = el('tr');
    for (const title of ['Revision', 'Status', 'Active links', 'Recorded']) header.append(el('th', title));
    const thead = el('thead'); thead.append(header); table.append(thead); const tbody = el('tbody');
    for (const revision of data.history) { const row = el('tr'); row.append(el('td', revision.sequence), el('td', revision.status.replaceAll('_', ' ')), el('td', revision.evidence_ids.length), el('td', revision.recorded_at)); tbody.append(row); }
    table.append(tbody); wrap.append(table); history.append(wrap, rawDetails('Revision policies & evidence IDs', data.history));
  }
  main.append(history);
  const projection = el('section', undefined, 'panel'); projection.append(el('h2', 'Experimental Beta projection'), el('p', 'A model of stipulated evidence impact—not calibrated truth confidence. Source clusters are assumptions about shared origin.', 'muted'));
  const p = data.projection;
  if (p.readout) {
    const r = p.readout;
    projection.append(fieldPair('Mean / variance', Number(r.mean).toFixed(4) + ' / ' + Number(r.variance).toFixed(4)), fieldPair('Effective support / contradiction', r.effective_support + ' / ' + r.effective_contradiction));
  } else projection.append(el('p', 'Projection unavailable: legacy impact metadata is incomplete. Qualitative evidence and history remain available.', 'muted'));
  projection.append(fieldPair('Replay coverage', p.replay_coverage), rawDetails('Clusters, contributions, exclusions & policy', p)); main.append(projection);
}
function renderObservation(data) {
  const main = $('detail'); main.replaceChildren(); const o = data.observation;
  main.append(el('span', 'Observation', 'eyebrow'), el('h1', o.source), el('p', o.report, 'report'), fieldPair('Observed at', o.observed_at), fieldPair('Recorded at', o.recorded_at));
  const actions = el('div', undefined, 'actions'); actions.append(button('Link to a claim', () => linkForm(o.id), 'primary')); main.append(actions, el('h2', 'Evidence links'));
  if (!data.links.length) main.append(el('p', 'This observation is not linked to a claim yet.', 'muted'));
  for (const link of data.links) { const card = el('article', undefined, 'evidence'); card.append(badge(link.active ? link.relation : 'inactive'), button('Inspect claim', async () => { await switchTab('propositions'); await select(link.proposition_id); }), rawDetails('Link provenance', link)); main.append(card); }
  main.append(rawDetails('Original observation record', o));
}
function inputSpec(name, label, options = {}) { return {name, label, ...options}; }
const sourceField = () => inputSpec('source', 'Source');
const reportField = () => inputSpec('report', 'Original report', {type: 'textarea'});
const timeField = () => inputSpec('observed_at', 'Observation time (optional)', {optional: true, placeholder: '2026-11-06T21:00:00-05:00 — leave unknown time blank'});
const relationField = () => inputSpec('relation', 'Manual relationship (Save only)', {choices: [['supports', 'Supports'], ['contradicts', 'Contradicts'] ]});
const actorFields = () => [inputSpec('actor', 'Your name / attribution'), inputSpec('reason', 'Reason for change', {type: 'textarea'})];
const massField = () => inputSpec('mass', 'Experimental impact mass (optional)', {type: 'number', optional: true, placeholder: 'Default: 1; reinterpretation retains the original'});
function openForm(title, help, specs, operation, fixed = {}, previewKind = null) {
  state.form = {operation, fixed, previewKind, specs, stale: false}; $('reload-form').hidden = true; $('save').disabled = false; $('editor-title').textContent = title; $('editor-help').textContent = help;
  $('form-fields').replaceChildren(); $('form-error').textContent = ''; $('preview-button').hidden = !previewKind; $('save').textContent = operation === 'withdraw' ? 'Withdraw evidence' : 'Save';
  for (const spec of specs) {
    const label = el('label', spec.label); let input;
    if (spec.choices) { input = el('select'); for (const [value, text] of spec.choices) { const option = el('option', text); option.value = value; input.append(option); } }
    else { input = el(spec.type === 'textarea' ? 'textarea' : 'input'); if (spec.type !== 'textarea') input.type = spec.type || 'text'; }
    input.name = spec.name; input.id = 'field-' + spec.name; input.required = !spec.optional;
    if (spec.placeholder) input.placeholder = spec.placeholder;
    if (spec.type === 'number') { input.min = '0'; input.step = 'any'; }
    if (spec.value != null) input.value = spec.value;
    label.append(input); $('form-fields').append(label);
  }
  if (previewKind) {
    const label = el('label', 'Ollama model'); const input = el('input'); input.name = 'model'; input.id = 'field-model'; input.value = state.info.model; label.append(input); $('form-fields').append(label);
    $('form-fields').append(el('p', 'Preview with model ignores the manual relationship above. It sends the claim, scope, and report to ' + state.info.ollama_host + '. Nothing is accepted automatically.', 'muted'));
  }
  $('editor').showModal();
}
function reportForm(pid) { openForm('Add report', 'Save a manually assigned relationship, or ask the model for a proposal to review.', [sourceField(), reportField(), timeField(), relationField(), massField()], 'report', {proposition_id: pid}, 'report'); }
function correctionForm(e) { openForm('Correct report', 'Preserves the original report and replaces only this evidence link. Other uses of the original observation remain unchanged.', [ ...actorFields(), {...sourceField(), value: e.source}, {...reportField(), value: e.report}, timeField(), {...relationField(), value: e.relation}, massField()], 'correct', {evidence_id: e.id}); }
function reinterpretForm(e) { openForm('Reinterpret evidence', 'Retains the observation and its lineage; replaces the relationship to this claim.', [...actorFields(), {...relationField(), value: e.relation}, massField()], 'reinterpret', {evidence_id: e.id}, 'reinterpret'); }
function withdrawalForm(e) { openForm('Withdraw evidence', 'Removes this link from active support. Its original report, attribution, and history remain inspectable.', actorFields(), 'withdraw', {evidence_id: e.id}); }
async function linkForm(oid) {
  openForm('Link observation', 'Find a claim, then assign a relationship or review a model proposal.', [inputSpec('claim_search', 'Find a claim', {optional: true}), inputSpec('proposition_id', 'Claim', {choices: []}), relationField(), massField()], 'link', {observation_id: oid}, 'observation');
  let version = 0;
  async function searchClaims() {
    const current = ++version; const data = await api('/api/propositions?' + new URLSearchParams({q: $('field-claim_search').value, limit: 100}));
    if (current !== version || !$('field-proposition_id')) return;
    const select = $('field-proposition_id'); select.replaceChildren(); const placeholder = el('option', 'Select a claim…'); placeholder.value = ''; select.append(placeholder);
    for (const p of data.items) { const option = el('option', p.claim + ' · ' + p.scope); option.value = p.id; select.append(option); }
  }
  $('field-claim_search').addEventListener('input', () => searchClaims().catch(showError)); await searchClaims();
}
function formArguments() {
  if (!$('editor-form').reportValidity()) return null;
  const args = {...state.form.fixed};
  for (const spec of state.form.specs) {
    if (spec.name === 'claim_search') continue;
    const value = $('field-' + spec.name).value;
    if (spec.optional && value === '') continue;
    args[spec.name] = spec.type === 'number' ? Number(value) : value;
  }
  return state.form.buildArguments ? state.form.buildArguments(args) : args;
}
function busy(value) { $('save').disabled = value || !!state.form?.stale; $('preview-button').disabled = value; $('close-editor').disabled = value; }
async function saved(result) {
  $('editor').close(); $('review').close(); state.preview = null;
  notice('Saved. Workspace records are up to date.');
  if (state.tab === 'propositions' && result.proposition_id) state.selected = result.proposition_id;
  if (state.tab === 'observations' && result.observation_id) state.selected = result.observation_id;
  await refresh();
}
$('editor-form').addEventListener('submit', async event => {
  event.preventDefault(); $('form-error').textContent = '';
  if (state.form.stale) return;
  try {
    const args = formArguments(); if (!args) return;
    busy(true);
    await saved(await command(state.form.operation, args));
  } catch (error) {
    $('form-error').textContent = error.message;
    if (error.status === 409 && state.form.reload) {
      state.form.stale = true; $('reload-form').hidden = false;
      $('form-error').textContent += ' Reload and review the current assignments before submitting again.';
    }
  } finally { busy(false); }
});
$('reload-form').addEventListener('click', async () => {
  const reload = state.form.reload;
  $('editor').close();
  try { await reload(); } catch (error) { showError(error); }
});
$('preview-button').addEventListener('click', async () => {
  const args = formArguments(); if (!args) return; delete args.relation;
  busy(true); $('form-error').textContent = '';
  try {
    state.preview = await api('/api/preview', {kind: state.form.previewKind, arguments: args, model: $('field-model').value});
    const p = state.preview.preview; $('preview-content').replaceChildren();
    for (const [label, value] of [['Claim', p.proposition.claim], ['Scope', p.proposition.scope], ['Source', p.source], ['Original report', p.report], ['Observed at', p.observed_at], ['Previous relation', p.previous_relation], ['Proposed relation', p.relation], ['Model rationale', p.reason], ['Model / prompt', p.model + ' / ' + p.prompt_version]]) {
      if (label === 'Previous relation' && value === undefined) continue;
      $('preview-content').append(fieldPair(label, value));
    }
    $('preview-content').append(rawDetails('Acceptance settings', args));
    $('accept').disabled = !state.preview.acceptable; $('review-error').textContent = state.preview.acceptable ? '' : 'This proposal is uncertain or unrelated and cannot be accepted.';
    $('editor').close(); $('review').showModal();
  } catch (error) { $('form-error').textContent = error.message; } finally { busy(false); }
});
$('accept').addEventListener('click', async () => {
  if (!state.preview) return; $('accept').disabled = true;
  $('discard').disabled = true; $('discard-x').disabled = true;
  try { await saved(await command('accept', {token: state.preview.token})); }
  catch (error) { $('review-error').textContent = error.message; $('accept').disabled = error.status === 409; }
  finally { $('discard').disabled = false; $('discard-x').disabled = false; }
});
async function discard() {
  if (state.preview) await api('/api/discard', {token: state.preview.token});
  state.preview = null; $('review').close(); $('editor').showModal();
}
$('discard').addEventListener('click', () => discard().catch(showError)); $('discard-x').addEventListener('click', () => discard().catch(showError));
$('review').addEventListener('cancel', event => { event.preventDefault(); if (!$('discard').disabled) discard().catch(showError); });
$('close-editor').addEventListener('click', () => $('editor').close());
$('editor').addEventListener('cancel', event => { if ($('save').disabled) event.preventDefault(); });
async function switchTab(tab) {
  state.tab = tab; state.offset = 0; state.selected = null; state.detailVersion++;
  $('claims-tab').classList.toggle('selected', tab === 'propositions'); $('observations-tab').classList.toggle('selected', tab === 'observations');
  $('search').value = ''; $('search').placeholder = tab === 'propositions' ? 'Find a claim or scope…' : 'Find a report or source…';
  $('status-label').hidden = tab !== 'propositions'; $('source-label').hidden = tab !== 'observations';
  $('create').textContent = tab === 'propositions' ? '+ New claim' : '+ New observation';
  $('detail').replaceChildren(el('p', tab === 'propositions' ? 'Select a claim to inspect its evidence and history.' : 'Select an observation to inspect its content and evidence links.', 'empty'));
  await loadList();
}
$('claims-tab').addEventListener('click', () => switchTab('propositions').catch(showError)); $('observations-tab').addEventListener('click', () => switchTab('observations').catch(showError));
$('create').addEventListener('click', () => state.tab === 'propositions'
  ? openForm('New scoped claim', 'State the claim and the circumstances or time it refers to.', [inputSpec('claim', 'Claim', {type: 'textarea'}), inputSpec('scope', 'Scope')], 'propose')
  : openForm('New observation', 'Record what was received. Saving an observation does not establish its truth or link it to a claim.', [sourceField(), reportField(), timeField()], 'observe'));
$('refresh').addEventListener('click', () => refresh().catch(showError));
for (const id of ['search', 'source-filter', 'status']) $(id).addEventListener(id === 'status' ? 'change' : 'input', () => { state.offset = 0; loadList().catch(showError); });
$('prev').addEventListener('click', () => { state.offset = Math.max(0, state.offset - pageSize); loadList().catch(showError); });
$('next').addEventListener('click', () => { state.offset += pageSize; loadList().catch(showError); });
$('retry').addEventListener('click', async () => { $('retry').disabled = true; try { await saved(await command(null, null, true)); } catch (error) { showError(error); } finally { $('retry').disabled = false; } });
$('origin-history').addEventListener('click', () => showLineage().catch(showError));
$('close-lineage').addEventListener('click', () => $('lineage-browser').close());
$('lineage-browser').addEventListener('close', () => { lineageViewVersion++; });
async function start() { state.info = await api('/api/workspace'); $('database').textContent = state.info.database; pendingBanner(); await loadList(); }
start().catch(showError);
