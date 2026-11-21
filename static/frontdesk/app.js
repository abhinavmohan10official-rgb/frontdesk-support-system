let tickets = [];
let selectedId = null;
let currentFilter = 'all';
let composerMode = 'reply';
const agentName = document.querySelector('#agent-name').textContent.trim();
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[ch]));
const csrfToken = () => document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1] || '';
const fmt = (value) => new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
const statusLabel = (ticket) => ticket.is_late ? 'SLA at risk' : ({ open: 'Open', in_progress: 'In progress', waiting_customer: 'Waiting', resolved: 'Resolved', closed: 'Closed' }[ticket.status] || ticket.status);

function renderMetrics() {
  const active = tickets.filter((t) => !['resolved', 'closed'].includes(t.status)).length;
  const late = tickets.filter((t) => t.is_late).length;
  const waiting = tickets.filter((t) => t.status === 'waiting_customer').length;
  const unassigned = tickets.filter((t) => !t.assignee && !['resolved', 'closed'].includes(t.status)).length;
  $('#metrics').innerHTML = `<div class="metric"><span>Open tickets</span><strong>${active}</strong><small>Across the support queue</small></div><div class="metric"><span>SLA at risk</span><strong>${late}</strong><small>${late ? 'Needs attention now' : 'Everything on track'}</small></div><div class="metric"><span>Waiting on customer</span><strong>${waiting}</strong><small>Waiting time still counts</small></div><div class="metric"><span>Unassigned</span><strong>${unassigned}</strong><small>Ready to be claimed</small></div>`;
  $('#nav-count').textContent = active;
}

function renderList() {
  const query = $('#search').value.toLowerCase();
  const visible = tickets.filter((ticket) => !query || `${ticket.id} ${ticket.subject} ${ticket.customer}`.toLowerCase().includes(query));
  $('#ticket-list').innerHTML = visible.length ? visible.map((ticket) => `<div class="ticket-row ${ticket.id === selectedId ? 'selected' : ''}" data-id="${esc(ticket.id)}"><div><small>${esc(ticket.id)}</small><strong>${esc(ticket.subject)}</strong></div><span>${esc(ticket.customer)}</span><em class="badge ${esc(ticket.priority)}">${esc(ticket.priority)}</em><span class="status ${ticket.is_late ? 'late' : ''}">${esc(statusLabel(ticket))}</span><span>${ticket.assignee ? esc(ticket.assignee.name.split(' ')[0]) : '<i class="unassigned">Unassigned</i>'}</span></div>`).join('') : '<div class="empty-detail"><h3>No tickets found</h3></div>';
  document.querySelectorAll('.ticket-row').forEach((row) => row.onclick = () => selectTicket(row.dataset.id));
}

function detailHtml(ticket) {
  const notes = (ticket.notes || []).map((note) => `<div class="note"><b>Private note · ${esc(note.author)} · ${fmt(note.created_at)}</b><p>${esc(note.body)}</p></div>`).join('');
  const messages = ticket.messages.map((message) => `<div class="message ${message.kind === 'agent' ? 'agent' : ''}"><b>${esc(message.author)} · ${fmt(message.created_at)}</b><p>${esc(message.body)}</p></div>`).join('');
  const statusOptions = ['open', 'in_progress', 'waiting_customer', 'resolved', 'closed'].map((status) => `<option value="${status}" ${ticket.status === status ? 'selected' : ''}>${status.replace('_', ' ')}</option>`).join('');
  return `<div class="detail-head"><div class="detail-top"><div><small>${esc(ticket.id)} · Created ${fmt(ticket.created_at)}</small><h2>${esc(ticket.subject)}</h2><span class="badge ${esc(ticket.priority)}">${esc(ticket.priority)}</span> <span>${esc(statusLabel(ticket))}</span><div class="status-control"><label for="status-select">Status</label><select id="status-select">${statusOptions}</select></div></div><button id="take" ${ticket.assignee ? 'disabled' : ''}>${ticket.assignee ? esc(ticket.assignee.name) : 'Take ticket'}</button></div></div><div class="detail-section"><b class="section-label">SLA clock</b><div class="sla-grid"><div class="sla-card"><strong>${ticket.first_response_at ? 'Responded' : ticket.response_late ? 'Overdue' : 'Due ' + fmt(ticket.first_due_at)}</strong><span>First response</span></div><div class="sla-card"><strong>${['resolved', 'closed'].includes(ticket.status) ? 'Resolved' : ticket.resolution_late ? 'Overdue' : 'Due ' + fmt(ticket.resolution_due_at)}</strong><span>Resolution target</span></div></div></div><div class="detail-section"><b class="section-label">Conversation with ${esc(ticket.customer)}</b><div class="conversation">${messages}</div></div>${notes ? `<div class="detail-section"><b class="section-label">Internal notes · never shared with customer</b><div class="conversation">${notes}</div></div>` : ''}<div class="composer"><div class="tabs"><button class="tab ${composerMode === 'reply' ? 'active' : ''}" data-mode="reply">Reply to customer</button><button class="tab ${composerMode === 'note' ? 'active' : ''}" data-mode="note">Private team note</button></div><textarea id="composer" placeholder="${composerMode === 'reply' ? 'Write a reply to the customer…' : 'Add a note for the support team…'}"></textarea><div class="composer-actions"><small>${composerMode === 'reply' ? 'Visible to customer' : 'Private to support agents'}</small><button id="send">${composerMode === 'reply' ? 'Send reply' : 'Add note'}</button></div></div>`;
}

async function selectTicket(id) {
  selectedId = id;
  renderList();
  const ticket = tickets.find((item) => item.id === id);
  if (!ticket) return;
  $('#detail').innerHTML = detailHtml(ticket);
  bindDetail();
}

function bindDetail() {
  $('#take')?.addEventListener('click', () => mutate('claim', {}));
  $('#status-select')?.addEventListener('change', (event) => mutate('status', { status: event.target.value }));
  document.querySelectorAll('.tab').forEach((tab) => tab.onclick = () => {
    composerMode = tab.dataset.mode;
    $('#detail').innerHTML = detailHtml(tickets.find((ticket) => ticket.id === selectedId));
    bindDetail();
  });
  $('#send')?.addEventListener('click', () => {
    const body = $('#composer').value.trim();
    if (body) mutate(composerMode, { body });
  });
}

async function mutate(action, payload) {
  const response = await fetch(`/api/tickets/${selectedId}/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }, body: JSON.stringify({ ...payload, actor: agentName }) });
  const data = await response.json();
  if (!response.ok) { showToast(data.error); return; }
  showToast(action === 'claim' ? 'Ticket claimed' : action === 'note' ? 'Private note added' : action === 'status' ? 'Status updated' : 'Reply sent');
  await load();
  selectTicket(selectedId);
}

function showToast(message) { const toast = $('#toast'); toast.textContent = message; toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 2200); }
async function load() {
  const response = await fetch(`/api/tickets?filter=${currentFilter}`);
  tickets = await response.json();
  renderMetrics(); renderList();
  if (selectedId) { const selected = tickets.find((ticket) => ticket.id === selectedId); if (selected) { $('#detail').innerHTML = detailHtml(selected); bindDetail(); } }
}

document.querySelectorAll('.nav-item').forEach((item) => item.onclick = () => { currentFilter = item.dataset.filter; document.querySelectorAll('.nav-item').forEach((nav) => nav.classList.remove('active')); item.classList.add('active'); load(); });
$('#search').oninput = renderList;
$('#refresh').onclick = load;
load();
