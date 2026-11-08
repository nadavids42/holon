'use strict';
// The browser adapter records explicit structure; it never evaluates belief eligibility.
function signedLabel(reference, propositions) {
  const p = propositions.find(item => item.id === reference.proposition_id);
  return (reference.relation === 'supports' ? 'Support for: ' : 'Opposition to: ') +
    (p ? p.claim + ' · ' + p.scope : 'Unavailable claim');
}
function observationLabel(id, ledger) {
  const o = ledger.observations.find(item => item.id === id);
  return o ? o.source + ' · ' + o.report.slice(0, 160) + ' · observed ' + (o.observed_at || 'unknown') : 'Unavailable observation';
}
function originGroups(ledger) {
  const groups = new Map();
  for (const [id, group] of Object.entries(ledger.assignments)) {
    if (group === null) continue;
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(id);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}
function lineageEventState(event, ledger) {
  if (event.kind === 'reverse') return {reversible: false, label: 'Reversal recorded'};
  if (ledger.events.some(e => e.kind === 'reverse' && e.target_event_id === event.id)) return {reversible: false, label: 'Reversed'};
  if (!event.changes.every(c => ledger.heads[c.observation_id] === event.id)) return {reversible: false, label: 'Later dependent change — reverse it first'};
  return {reversible: true, label: 'Can be reversed'};
}
function claimLink(reference, propositions) {
  return button(signedLabel(reference, propositions), async () => {
    if ($('lineage-browser').open) $('lineage-browser').close();
    await switchTab('propositions'); await select(reference.proposition_id);
  }, 'claim-link');
}
function derivationPanel(pid, ledger) {
  const panel = el('div'); panel.append(el('h2', 'Recorded justifications'),
    el('p', 'These are supplied rules and dependencies. They do not change evidence status or the Beta projection; eligibility has not been evaluated.', 'muted'),
    button('+ Add justification', () => derivationForm(pid), 'primary'));
  const alternatives = ledger.justifications.filter(j => j.conclusion.proposition_id === pid);
  if (!alternatives.length) panel.append(el('p', 'No justifications recorded for this claim.', 'muted'));
  for (const j of alternatives) {
    const card = el('article', undefined, 'evidence');
    card.append(badge(j.conclusion.relation), el('h3', j.rule), el('p', 'All premises required (AND)', 'eyebrow'));
    const list = el('ul', undefined, 'premise-list');
    for (const premise of j.premises) { const item = el('li'); item.append(claimLink(premise, ledger.propositions)); list.append(item); }
    card.append(list, el('p', j.actor + ' · ' + j.recorded_at + ' · ' + j.reason, 'meta'), rawDetails('Justification record', j)); panel.append(card);
  }
  if (alternatives.length > 1) panel.append(el('p', 'Justifications with the same conclusion stance are alternatives (OR); they are not independent evidence counts.', 'muted'));
  const dependents = ledger.justifications.filter(j => j.premises.some(p => p.proposition_id === pid));
  if (dependents.length) {
    panel.append(el('h3', 'Used as a premise in'));
    for (const j of dependents) panel.append(claimLink(j.conclusion, ledger.propositions));
  }
  return panel;
}
function premiseRow(propositions, pid, rows, list) {
  const row = {node: el('fieldset', undefined, 'premise-editor')};
  row.node.append(el('legend', 'Required premise'));
  const searchLabel = el('label', 'Search claims'); const search = el('input'); search.type = 'search'; search.placeholder = 'Claim or scope'; searchLabel.append(search);
  const claimLabel = el('label', 'Premise claim'); row.claim = el('select'); row.claim.required = true; claimLabel.append(row.claim);
  const signLabel = el('label', 'Required stance'); row.sign = el('select');
  for (const [value, label] of [['supports', 'Support for claim'], ['contradicts', 'Opposition to claim']]) { const option = el('option', label); option.value = value; row.sign.append(option); }
  signLabel.append(row.sign);
  function update() {
    const chosen = row.claim.value; row.claim.replaceChildren();
    const placeholder = el('option', 'Select a scoped claim…'); placeholder.value = ''; row.claim.append(placeholder);
    const query = search.value.toLowerCase();
    for (const p of propositions) {
      if (p.id === pid || (p.id !== chosen && !(p.claim + ' ' + p.scope).toLowerCase().includes(query))) continue;
      const option = el('option', p.claim + ' · ' + p.scope); option.value = p.id; row.claim.append(option);
    }
    row.claim.value = chosen || '';
  }
  search.addEventListener('input', update); update();
  row.node.append(searchLabel, claimLabel, signLabel, button('Remove premise', () => { rows.splice(rows.indexOf(row), 1); row.node.remove(); }));
  rows.push(row); list.append(row.node); row.claim.focus();
}
function derivationArguments(args, pid, rows) {
  if (!rows.length) throw new Error('Add at least one premise.');
  const premises = rows.map(row => ({proposition_id: row.claim.value, relation: row.sign.value}));
  if (premises.some(p => !p.proposition_id || p.proposition_id === pid)) throw new Error('Select a different claim for every premise.');
  if (new Set(premises.map(p => JSON.stringify(p))).size !== premises.length) throw new Error('The same signed premise is listed more than once.');
  const {relation, ...rest} = args;
  return {...rest, conclusion: {proposition_id: pid, relation}, premises};
}
async function derivationForm(pid) {
  const ledger = await api('/api/derivations');
  const conclusion = ledger.propositions.find(p => p.id === pid);
  if (!conclusion) throw new Error('This claim is no longer available.');
  openForm('Add justification', 'Record why the selected premises jointly justify this conclusion. This saves dependency structure, not an evidence or belief update.',
    [inputSpec('relation', 'Conclusion stance', {choices: [['supports', 'Support for claim'], ['contradicts', 'Opposition to claim']]}),
     inputSpec('rule', 'Rule / why these premises suffice', {type: 'textarea'}), ...actorFields()],
    'derive', {justification_id: crypto.randomUUID()});
  $('form-fields').prepend(fieldPair('Conclusion', conclusion.claim + ' · ' + conclusion.scope));
  const rows = []; const list = el('div');
  $('form-fields').append(el('h3', 'All required premises (AND)'), list,
    button('+ Add premise', () => premiseRow(ledger.propositions, pid, rows, list)));
  premiseRow(ledger.propositions, pid, rows, list);
  state.form.buildArguments = args => derivationArguments(args, pid, rows);
  $('save').textContent = 'Record justification';
}
function originPanel(oid, ledger) {
  const panel = el('div'); const group = ledger.assignments[oid];
  panel.append(el('h2', 'Reported origin'), fieldPair('Current group', group === null ? 'Unknown — independence is not assumed' : group),
    el('p', 'Origin groups are assertions about shared source material. They are separate from evidence impact clusters and do not change the Beta projection.', 'muted'));
  const actions = el('div', undefined, 'actions'); actions.append(button('Assign / change origin', () => originForm(oid)), button('All origins & history', () => showLineage())); panel.append(actions);
  const events = ledger.events.filter(e => e.changes.some(c => c.observation_id === oid));
  if (!events.length) panel.append(el('p', 'No origin changes recorded for this observation.', 'muted'));
  for (const event of events.slice().reverse()) panel.append(lineageEventCard(event, ledger));
  return panel;
}
function changeSummary(changes, ledger) {
  const list = el('ul', undefined, 'change-list');
  for (const c of changes) {
    const item = el('li'); item.append(el('strong', observationLabel(c.observation_id, ledger)),
      el('div', (c.before === null ? 'Unknown' : c.before) + ' → ' + (c.after === null ? 'Unknown' : c.after), 'meta')); list.append(item);
  }
  return list;
}
function lineageEventCard(event, ledger) {
  const card = el('article', undefined, 'evidence'); const status = lineageEventState(event, ledger);
  card.append(el('h3', '#' + event.sequence + ' · ' + event.kind), badge(status.label),
    el('p', event.actor + ' · ' + event.recorded_at + ' · ' + event.reason, 'meta'), changeSummary(event.changes, ledger));
  if (status.reversible) card.append(button('Review reversal', () => reversalForm(event.id)));
  card.append(rawDetails('Origin event record', event)); return card;
}
async function originForm(oid) {
  const ledger = await api('/api/lineage');
  if (!Object.hasOwn(ledger.assignments, oid)) throw new Error('Observation is no longer available.');
  openForm('Assign observation origin', 'Use the same group name for reports known to share an origin. Leave the group blank to record unknown origin. Different names do not prove independence.',
    [inputSpec('group_id', 'Origin group (blank means unknown)', {optional: true, value: ledger.assignments[oid] || '', placeholder: 'For example: original-door-reading'}), ...actorFields()],
    'assign-origin', {event_id: crypto.randomUUID(), observation_id: oid, expected_revision: ledger.revision});
  $('form-fields').prepend(fieldPair('Observation', observationLabel(oid, ledger)), fieldPair('Current origin', ledger.assignments[oid]));
  const options = el('datalist'); options.id = 'origin-options';
  for (const [group] of originGroups(ledger)) { const option = el('option'); option.value = group; options.append(option); }
  $('field-group_id').setAttribute('list', options.id); $('form-fields').append(options);
  state.form.buildArguments = args => ({...args, group_id: args.group_id?.trim() || null});
  state.form.reload = () => originForm(oid);
  $('save').textContent = 'Record origin';
}
function mergeChanges(ledger, selected, target) {
  return Object.entries(ledger.assignments).filter(([,group]) => selected.includes(group))
    .map(([observation_id, before]) => ({observation_id, before, after: target}));
}
async function mergeForm() {
  const ledger = await api('/api/lineage'); const groups = originGroups(ledger);
  if (groups.length < 2) throw new Error('Assign observations to at least two origin groups before merging.');
  openForm('Merge shared origins', 'Select groups known to share an origin, then choose which name to keep. Review every affected observation below. This does not merge evidence or change belief status.',
    [inputSpec('target_group_id', 'Group name to keep', {choices: [['', 'Select groups first…']]}), ...actorFields()],
    'merge-origins', {event_id: crypto.randomUUID(), expected_revision: ledger.revision});
  const selection = el('fieldset', undefined, 'group-selection'); selection.append(el('legend', 'Groups to merge (choose at least two)'));
  const checks = groups.map(([group, ids]) => {
    const label = el('label'); const input = el('input'); input.type = 'checkbox'; input.value = group;
    label.append(input, el('span', group + ' · ' + ids.length + ' observations')); selection.append(label); return input;
  });
  const summary = el('div'); $('form-fields').prepend(selection); $('form-fields').append(el('h3', 'Affected observations'), summary);
  const selected = () => checks.filter(c => c.checked).map(c => c.value);
  function showChanges() {
    const target = $('field-target_group_id').value;
    summary.replaceChildren(target ? changeSummary(mergeChanges(ledger, selected(), target), ledger) : el('p', 'Choose the group name to keep.', 'muted'));
  }
  for (const check of checks) check.addEventListener('change', () => {
    const input = $('field-target_group_id'); const previous = input.value; input.replaceChildren();
    const placeholder = el('option', 'Choose a selected group…'); placeholder.value = ''; input.append(placeholder);
    for (const group of selected()) { const option = el('option', group); option.value = group; input.append(option); }
    input.value = selected().includes(previous) ? previous : ''; showChanges();
  });
  $('field-target_group_id').addEventListener('change', showChanges); showChanges();
  state.form.buildArguments = args => {
    const group_ids = selected();
    if (group_ids.length < 2 || !group_ids.includes(args.target_group_id)) throw new Error('Choose at least two groups and a selected target.');
    return {...args, group_ids};
  };
  state.form.reload = mergeForm; $('save').textContent = 'Record merge';
}
async function reversalForm(eventId) {
  const ledger = await api('/api/lineage'); const event = ledger.events.find(e => e.id === eventId);
  if (!event || !lineageEventState(event, ledger).reversible) throw new Error('This change cannot currently be reversed. Refresh history and reverse later dependent changes first.');
  openForm('Reverse origin change #' + event.sequence, 'Restore the assignments below. The original event and this reversal both remain in history. Evidence status and projection clusters are unchanged.',
    actorFields(), 'reverse-lineage', {event_id: crypto.randomUUID(), target_event_id: event.id, expected_revision: ledger.revision});
  $('form-fields').prepend(fieldPair('Original reason', event.reason), changeSummary(event.changes.map(c => ({...c, before: c.after, after: c.before})), ledger));
  state.form.reload = () => reversalForm(eventId); $('save').textContent = 'Record reversal';
}
let lineageViewVersion = 0;
async function showLineage() {
  const version = ++lineageViewVersion;
  const ledger = await api('/api/lineage'); if (version !== lineageViewVersion) return;
  const content = $('lineage-content'); content.replaceChildren(el('p', 'Explicit shared-origin assertions. Unassigned observations remain unknown, not independent. These groups do not update evidence impact clusters.', 'muted'));
  const actions = el('div', undefined, 'actions'); actions.append(button('Merge groups', mergeForm, 'primary'), button('Refresh history', showLineage)); content.append(actions);
  const groups = originGroups(ledger);
  if (!groups.length) content.append(el('p', 'No groups yet. Open an observation and choose “Assign / change origin”.', 'muted'));
  for (const [group, ids] of groups) {
    const section = el('details'); section.append(el('summary', group + ' · ' + ids.length + ' observations'));
    for (const oid of ids) section.append(button(observationLabel(oid, ledger), async () => { $('lineage-browser').close(); await switchTab('observations'); await select(oid); }, 'claim-link'));
    content.append(section);
  }
  content.append(el('h3', 'Change history'), el('p', 'Revision ' + ledger.revision + ' · Provenance completeness: unknown', 'meta'));
  for (const event of ledger.events.slice().reverse()) content.append(lineageEventCard(event, ledger));
  if (!ledger.events.length) content.append(el('p', 'No origin changes recorded.', 'muted'));
  if (!$('lineage-browser').open) $('lineage-browser').showModal();
}
