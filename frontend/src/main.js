import './styles.css';

const incidents = [
  { id: 'INC-2048', title: 'Core router saturation', device: 'R-core', type: 'Operational', severity: 'High', confidence: 96, age: '04 min', metric: 'CPU 95%', detail: 'Queue depth is rising across two downstream edges.', action: 'Reroute traffic', risk: 18 },
  { id: 'INC-2047', title: 'East ingress packet loss', device: 'E-14', type: 'Operational', severity: 'Medium', confidence: 89, age: '11 min', metric: 'Loss 6.8%', detail: 'Loss is sustained above baseline on the east ingress path.', action: 'Rate limit', risk: 27 },
  { id: 'INC-2045', title: 'Unexpected scan pattern', device: 'FW-02', type: 'Security', severity: 'Critical', confidence: 93, age: '18 min', metric: '12.4k req/s', detail: 'Sequential port access detected from multiple source ranges.', action: 'Block source IPs', risk: 61 }
];

const devices = [
  { name: 'R-core', role: 'Core router', state: 'Degraded', cpu: 95, latency: 182, tone: 'warn' },
  { name: 'E-14', role: 'Edge gateway', state: 'Watch', cpu: 71, latency: 84, tone: 'watch' },
  { name: 'E-19', role: 'Edge gateway', state: 'Healthy', cpu: 38, latency: 31, tone: 'good' },
  { name: 'FW-02', role: 'Security firewall', state: 'Investigate', cpu: 82, latency: 66, tone: 'critical' }
];

let currentView = 'Overview';
const ranges = ['24h', '7d', '30d'];
const analyticsSeries = {
  '24h': { cpu: [32, 45, 58, 71, 82, 95], label: 'Last 24 hours' },
  '7d': { cpu: [44, 52, 61, 58, 66, 71], label: 'Last 7 days' },
  '30d': { cpu: [38, 47, 52, 56, 64, 69], label: 'Last 30 days' }
};
let analyticsRange = '24h';
let selectedIncident = incidents[0];
let simulated = false;
let approved = false;
let actionBusy = false;
let actionError = '';
let lastUpdated = '12 sec ago';
let apiStatus = 'Connecting to control plane';
let analyst = null;
let profileOpen = false;
let explainerOpen = false;
let analystEvidence = '';
let authChecked = false;
let authenticatedUser = null;
let authMode = 'login';
let authError = '';
let inspectionOpen = false;
let cubeScrollHandler = null;
let activity = [
  ['09:42:18', 'Detector', 'Anomaly sustained on R-core', 'warn'],
  ['09:40:52', 'Diagnosis', 'Root cause isolated to core router', 'good'],
  ['09:39:11', 'Simulator', 'Reroute path passed safety checks', 'good'],
  ['09:37:44', 'Monitor', 'East ingress returned to baseline', 'muted']
];

const app = document.querySelector('#app');

function render() {
  if (!authChecked || !authenticatedUser) {
    app.innerHTML = authView();
    bindAuthEvents();
    return;
  }
  app.innerHTML = `
    <div class="shell">
      <canvas class="shader-layer" id="shader" aria-hidden="true"></canvas>
      <div class="scroll-cube" aria-hidden="true"><div class="cube"><i class="cube-face cube-front"></i><i class="cube-face cube-back"></i><i class="cube-face cube-right"></i><i class="cube-face cube-left"></i><i class="cube-face cube-top"></i><i class="cube-face cube-bottom"></i></div></div>
      ${sidebar()}
      <main class="main">
        ${topbar()}
        ${currentView === 'Overview' ? overviewView() : ''}
        ${currentView === 'Analytics' ? analyticsView() : ''}
        ${currentView === 'Topology' ? topologyView() : ''}
        ${currentView === 'Incidents' ? incidentsView() : ''}
        ${currentView === 'Change queue' ? queueView() : ''}
      </main>
      ${explainerOpen ? explainerModal() : ''}
      ${profileOpen ? profileModal() : ''}
      <div class="toast" id="toast" role="status"></div>
    </div>`;
  bindEvents();
  startShader();
  startCubeScroll();
  startScrollReveals();
}

function sidebar() {
  const nav = ['Overview', 'Analytics', 'Topology', 'Incidents', 'Change queue'];
  return `<aside class="sidebar">
    <div class="brand"><span>NetOps</span></div>
    <div class="workspace"><span class="eyebrow">Workspace</span><strong>Northstar / Production</strong><span class="status-dot"><i></i> Connected</span></div>
    <nav class="nav" aria-label="Primary navigation">${nav.map((item, index) => `<button class="nav-item ${currentView === item ? 'active' : ''}" data-view="${item}"><span class="nav-index">0${index + 1}</span> ${item}${item === 'Incidents' ? '<b>3</b>' : ''}</button>`).join('')}</nav>
    <div class="sidebar-bottom">
      <div class="system-card"><span class="eyebrow">System health</span><strong>99.98%</strong><span>Last 30 days</span><div class="health-bar"><i></i></div></div>
      <button class="user-card" id="profile"><span class="avatar">${authenticatedUser.name.slice(0, 2).toUpperCase()}</span><span><strong>${authenticatedUser.name}</strong><small>Network lead</small></span><span class="chevron">Open</span></button>
    </div>
  </aside>`;
}

function topbar() {
  return `<header class="topbar"><div><span class="eyebrow">Saturday, September 12, 2026</span><h1>${currentView}</h1></div><div class="top-actions"><span class="live ${apiStatus.includes('Connected') ? '' : 'offline'}"><i></i> ${apiStatus}</span><button class="icon-button" id="explain-workflow">How it works</button><button class="icon-button" id="refresh">Refresh</button><button class="outline-button" id="export">Export report</button></div></header>`;
}

function overviewView() {
  return `<section class="overview-grid">
    <div class="metric-card intro-card"><span class="eyebrow">Network posture</span><strong>Stable, with attention</strong><p>One high-confidence diagnosis is ready for a controlled change.</p><div class="posture-line"><span><i class="pulse"></i> 47 devices monitored</span><span>Updated ${lastUpdated}</span></div></div>
    <div class="metric-card"><span class="eyebrow">Active incidents</span><strong class="big-number">03</strong><span class="metric-foot warn-text">1 high severity</span></div>
    <div class="metric-card"><span class="eyebrow">Auto-resolved today</span><strong class="big-number">18</strong><span class="metric-foot good-text">+12% vs yesterday</span></div>
    <div class="metric-card"><span class="eyebrow">Change risk</span><strong class="big-number">Low</strong><span class="metric-foot">0.18 average score</span></div>
  </section>
  <section class="integration-banner ${apiStatus.includes('Connected') ? '' : 'degraded'}"><div><span class="eyebrow">AI control room</span><strong>${apiStatus.includes('Connected') ? 'I am watching telemetry and preparing the next safe action.' : 'I need the backend connection before I can help with changes.'}</strong><p>${actionError || 'I explain the signal, check the change, and wait for your decision before anything moves forward.'}</p></div><span class="integration-state">${actionError ? 'Agent needs attention' : 'Agent ready'}</span></section>
  <section class="content-grid">
    <div class="primary-column">
      <div class="section-heading"><div><span class="eyebrow">Priority queue</span><h2>Needs your attention</h2></div><button class="text-button" data-view="Incidents">View all incidents</button></div>
      <div class="incident-list">${incidents.map(incidentCard).join('')}</div>
      ${analystPanel()}
      ${inspectionPanel()}
      ${activityPanel()}
    </div>
    ${diagnosisPanel()}
  </section>
  ${deviceSection()}`;
}

function authView() {
  return `<div class="auth-shell"><section class="auth-card"><div class="brand auth-brand"><span>NetOps</span></div><span class="eyebrow">AI network assistant</span><h1>${authMode === 'login' ? 'Sign in to continue' : 'Create operator account'}</h1><p class="auth-subtitle">Give the agent a secure workspace to observe signals, explain anomalies, and guide safe recovery.</p><form id="auth-form" class="auth-form">${authMode === 'signup' ? '<label>Display name<input name="name" autocomplete="name" required></label>' : ''}<label>Email address<input name="email" type="email" autocomplete="email" required></label><label>Password<input name="password" type="password" autocomplete="${authMode === 'login' ? 'current-password' : 'new-password'}" minlength="10" required></label>${authMode === 'signup' ? '<small>Use at least 10 characters.</small>' : ''}${authError ? `<div class="auth-error">${authError}</div>` : ''}<button class="auth-submit" type="submit">${authMode === 'login' ? 'Authenticate operator' : 'Create secure account'}</button></form><button class="auth-switch" id="auth-switch">${authMode === 'login' ? 'Need an account? Create one' : 'Already have an account? Sign in'}</button><div class="auth-session"><span class="status-dot"><i></i> Secure session ready</span><span>Session expires after 8 hours</span></div></section></div>`;
}

function inspectionPanel() {
  return `<section class="inspection-panel"><div class="analyst-head"><div><span class="eyebrow">AI inspection guide</span><h2>Windows 7 Task Manager evidence</h2></div><span class="agent-state"><i></i> Operator assist</span></div><p class="analyst-copy">Use this exact sequence during inspection. The AI agent can interpret the values you enter, but it cannot access the machine unless you provide the evidence.</p><button class="agent-button" id="toggle-inspection">${inspectionOpen ? 'Hide inspection steps' : 'Show exact inspection steps'}</button>${inspectionOpen ? '<ol class="inspection-steps"><li>Press <strong>Ctrl + Shift + Esc</strong> to open Task Manager.</li><li>Open the <strong>Processes</strong> tab and enable CPU, Memory, Network, and PID columns.</li><li>Sort CPU descending, wait 60 seconds, and record the top five process names and percentages.</li><li>Open <strong>Performance</strong> and record CPU usage, physical memory, and network activity.</li><li>Open <strong>Networking</strong>, select the active adapter, and record link speed and utilization.</li><li>Do not end a process. Capture screenshots or copy values, then return to NetOps for AI interpretation.</li></ol><div class="inspection-warning">Windows 7 is out of support. Do not collect passwords, tokens, or personal files in screenshots.</div>' : ''}</section>`;
}

function analystPanel() {
  return `<section class="analyst-panel"><div class="analyst-head"><div><span class="eyebrow">AI network assistant</span><h2>Evidence review</h2></div><span class="agent-state"><i></i> Ready to reason</span></div><p class="analyst-copy">${analyst ? analyst.answer : 'Tell me what you observed and I will connect it to the selected incident, explain the likely cause, and suggest the next safe step.'}</p><label class="agent-evidence-label" for="agent-evidence">What did you observe? <span>Optional</span></label><textarea id="agent-evidence" class="agent-evidence" rows="3" placeholder="Paste CPU, memory, network, process, or device output. Do not include passwords or tokens.">${analystEvidence}</textarea><div class="analyst-actions"><button class="agent-button" id="ask-analyst">${analyst ? 'Ask again' : 'Ask the AI agent'}</button><span>AI guidance · you stay in control</span></div></section>`;
}

function profileModal() {
  return `<div class="modal-backdrop" id="profile-backdrop"><section class="profile-modal" role="dialog" aria-modal="true" aria-labelledby="profile-title"><button class="modal-close" id="close-profile">Close</button><span class="eyebrow">Your AI workspace</span><h2 id="profile-title">${authenticatedUser.name}</h2><p>${authenticatedUser.email}</p><div class="profile-list"><div><span class="eyebrow">Workspace</span><strong>Northstar / Production</strong></div><div><span class="eyebrow">Session</span><strong>Verified · expires in 8 hours</strong></div><div><span class="eyebrow">Assistant</span><strong>Observes, explains, and guides</strong></div></div><button class="profile-action" id="profile-audit">View access history</button><button class="profile-action profile-logout" id="logout">Sign out securely</button></section></div>`;
}

function explainerModal() {
  return `<div class="modal-backdrop" id="explainer-backdrop"><section class="explainer-modal" role="dialog" aria-modal="true" aria-labelledby="explainer-title"><button class="modal-close" id="close-explainer">Close</button><span class="eyebrow">Anomaly response guide</span><h2 id="explainer-title">How the AI agent helps you fix a fault</h2><p class="explainer-lead">NetOps turns an unclear signal into a guided decision. It shows what happened, where it happened, and what still needs a human operator.</p><div class="explainer-list"><div><span class="explainer-index">01</span><div><strong>When does it react?</strong><p>When a device signal stays outside its normal baseline, detection creates an incident instead of reacting to a one-off spike.</p></div></div><div><span class="explainer-index">02</span><div><strong>Where did the anomaly happen?</strong><p>The incident identifies the affected device, role, signal, and location in the topology, such as CPU pressure on R-core or a scan pattern at FW-02.</p></div></div><div><span class="explainer-index">03</span><div><strong>Why this diagnosis?</strong><p>RCA compares the device, symptoms, history, and security context to explain the likely cause and show its confidence.</p></div></div><div><span class="explainer-index">04</span><div><strong>What if the AI cannot access or fix it?</strong><p>The agent does not pretend to control an unavailable machine. Open the inspection guide, collect the requested CPU, memory, network, or process evidence, and bring it back for interpretation.</p></div></div><div><span class="explainer-index">05</span><div><strong>How does the fix become safe?</strong><p>The planner ranks reversible actions, simulation checks the predicted result, and a human approves the change before it enters the queue or reaches an executor.</p></div></div></div></section></div>`;
}

function incidentCard(incident) {
  return `<button class="incident-card ${incident.id === selectedIncident.id ? 'selected' : ''}" data-incident="${incident.id}"><div class="incident-top"><span class="incident-id">${incident.id}</span><span class="severity ${incident.severity.toLowerCase()}">${incident.severity}</span></div><h3>${incident.title}</h3><p>${incident.device}<span>·</span>${incident.type}</p><div class="incident-bottom"><span>${incident.metric}</span><span>${incident.age} ago</span></div></button>`;
}

function diagnosisPanel() {
  return `<aside class="detail-panel"><div class="detail-header"><div><span class="eyebrow">Selected diagnosis</span><h2>${selectedIncident.id}</h2></div><span class="severity ${selectedIncident.severity.toLowerCase()}">${selectedIncident.severity}</span></div>
    <div class="diagnosis-title"><h3>${selectedIncident.title}</h3><p>${selectedIncident.detail}</p></div>
    <div class="diagnosis-meta"><div><span class="eyebrow">Root device</span><strong>${selectedIncident.device}</strong></div><div><span class="eyebrow">Confidence</span><strong>${selectedIncident.confidence}%</strong></div><div><span class="eyebrow">Detected</span><strong>${selectedIncident.age} ago</strong></div></div>
    <div class="signal-box"><div class="signal-top"><span class="eyebrow">Signal</span><strong>${selectedIncident.metric}</strong></div><div class="bars">${[35, 42, 44, 49, 47, 61, 55, 70, 74, 82, 91, 96].map((height, index) => `<i style="height:${height}%" class="${index > 8 ? 'hot' : ''}"></i>`).join('')}</div><div class="signal-labels"><span>30 min ago</span><span>Now</span></div></div>
    <div class="recommendation"><span class="recommendation-label">Recommended action</span><strong>${selectedIncident.action}</strong><div class="recommendation-row"><span>Predicted CPU after change</span><b>${selectedIncident.id === 'INC-2048' ? '62%' : '54%'}</b></div><div class="recommendation-row"><span>Risk score</span><b class="risk-score">${selectedIncident.risk}%</b></div></div>
    <button class="simulate-button" id="simulate" ${actionBusy || simulated ? 'disabled' : ''}>${actionBusy ? 'Requesting simulation' : simulated ? 'Simulation complete' : 'Run safety simulation'}<span>${simulated ? 'Passed' : 'Run'}</span></button>
    <button class="approve-button" id="approve" ${actionBusy || !simulated || approved ? 'disabled' : ''}>${approved ? 'Decision recorded' : simulated ? 'Record operator approval' : 'Simulation required before approval'}</button>
    <p class="panel-note">${approved ? 'I recorded your approval as a decision only. No device command was sent.' : 'I will wait for a passing simulation and your approval before recording a decision. No device command is sent.'}</p>
  </aside>`;
}

function activityPanel() {
  return `<div class="section-heading activity-heading"><div><span class="eyebrow">Decision log</span><h2>Recent activity</h2></div><span class="live muted-live"><i></i> Streaming</span></div><div class="activity-list">${activity.map((item) => `<div class="activity-row"><span class="activity-time">${item[0]}</span><span class="activity-marker ${item[3]}"></span><span class="activity-source">${item[1]}</span><span class="activity-message">${item[2]}</span></div>`).join('')}</div>`;
}

function deviceSection() {
  return `<section class="devices-section"><div class="section-heading"><div><span class="eyebrow">Fleet snapshot</span><h2>Device health</h2></div><button class="text-button" data-view="Topology">Open topology</button></div><div class="device-table"><div class="table-head"><span>Device</span><span>State</span><span>CPU</span><span>Latency</span><span>Last signal</span></div>${devices.map((device, index) => `<div class="device-row"><div class="device-name"><span class="device-icon">${index + 1}</span><span><strong>${device.name}</strong><small>${device.role}</small></span></div><span class="device-state ${device.tone}"><i></i>${device.state}</span><div class="cpu"><span>${device.cpu}%</span><div><i style="width:${device.cpu}%"></i></div></div><span class="latency">${device.latency} ms</span><span class="signal-time">${index === 0 ? '12 sec ago' : index === 1 ? '28 sec ago' : '41 sec ago'}</span></div>`).join('')}</div></section>`;
}

function topologyView() {
  return `<section class="page-grid"><div class="page-intro"><span class="eyebrow">Live network map</span><h2>Topology</h2><p>Trace service health from the core router through each edge and security boundary.</p></div><div class="topology-map"><div class="topology-line line-a"></div><div class="topology-line line-b"></div><div class="topology-line line-c"></div>${devices.map((device, index) => `<button class="topology-node node-${index + 1}" data-incident="${incidents[index % incidents.length].id}"><span class="node-ring ${device.tone}"></span><strong>${device.name}</strong><small>${device.role}</small><em>${device.latency} ms</em></button>`).join('')}<div class="topology-legend"><span><i class="legend-dot good"></i> Healthy</span><span><i class="legend-dot watch"></i> Attention</span><span><i class="legend-dot critical"></i> Critical</span></div></div>${deviceSection()}</section>`;
}

function incidentsView() {
  return `<section class="page-grid"><div class="page-intro"><span class="eyebrow">Incident management</span><h2>Active incidents</h2><p>Review signals, run a safety simulation, and record an operator decision. No device command is sent.</p></div><div class="incident-board">${incidents.map((incident) => `<article class="board-card">${incidentCard(incident)}<div class="board-footer"><span>Owner: Network automation</span><button class="small-action" data-incident="${incident.id}">Open diagnosis</button></div></article>`).join('')}</div>${activityPanel()}</section>`;
}

function queueView() {
  return `<section class="page-grid"><div class="page-intro"><span class="eyebrow">AI-guided changes</span><h2>Change queue</h2><p>I keep recommendations explainable and simulated. This queue records decisions; it does not send device commands.</p></div><div class="queue-card"><div class="queue-head"><span>Change</span><span>Risk</span><span>State</span><span>Owner</span></div><div class="queue-row"><strong>${selectedIncident.action}</strong><span class="risk-score">${selectedIncident.risk}%</span><span class="queue-state ${approved ? 'queued' : 'ready'}">${approved ? 'Decision recorded' : simulated ? 'Ready for approval' : 'Simulation required'}</span><span>Alex Kim</span></div><div class="queue-row"><strong>East ingress baseline review</strong><span class="risk-score">09%</span><span class="queue-state complete">Completed</span><span>Auto-remediation</span></div></div><div class="queue-note"><span class="eyebrow">Agent note</span><strong>I will not move a change forward until the simulation passes and you confirm it.</strong><button class="outline-button" data-view="Incidents">Review active incidents</button></div></section>`;
}

function analyticsView() {
  const series = analyticsSeries[analyticsRange];
  const avg = Math.round(series.cpu.reduce((sum, value) => sum + value, 0) / series.cpu.length);
  const peak = Math.max(...series.cpu);
  return `<section class="page-grid"><div class="page-intro analytics-intro"><div><span class="eyebrow">Telemetry trends</span><h2>Analytics dashboard</h2><p>Range-aware trends from the same signals that drive incidents and the change queue.</p></div><div class="range-tabs">${ranges.map((range) => `<button class="range-tab ${analyticsRange === range ? 'active' : ''}" data-range="${range}">${range}</button>`).join('')}</div></div><div class="analytics-kpis"><div class="metric-card"><span class="eyebrow">Average CPU</span><strong class="big-number">${avg}%</strong><span class="metric-foot">${series.label}</span></div><div class="metric-card"><span class="eyebrow">Peak CPU</span><strong class="big-number">${peak}%</strong><span class="metric-foot">Core router R-core</span></div></div><article class="analytics-card wide"><div class="section-heading"><div><span class="eyebrow">Core CPU utilization</span><h3>R-core · ${series.label}</h3></div></div><div class="bars analytics-bars">${series.cpu.map((value) => `<i style="height:${value}%" title="${value}%"></i>`).join('')}</div><div class="signal-labels"><span>Start</span><span>${series.label}</span></div></article>${deviceSection()}</section>`;
}

function bindEvents() {
  document.querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', () => { currentView = button.dataset.view; render(); }));
  document.querySelectorAll('[data-range]').forEach((button) => button.addEventListener('click', async () => { analyticsRange = button.dataset.range; await hydrateTelemetry(); render(); }));
  document.querySelectorAll('[data-incident]').forEach((card) => card.addEventListener('click', () => { selectedIncident = incidents.find((item) => item.id === card.dataset.incident); simulated = false; approved = false; currentView = 'Overview'; render(); }));
  document.querySelector('#simulate')?.addEventListener('click', runSimulation);
  document.querySelector('#approve')?.addEventListener('click', approveChange);
  document.querySelector('#refresh')?.addEventListener('click', () => { lastUpdated = 'just now'; addActivity('Monitor', 'Telemetry refreshed across 47 devices', 'good'); render(); toast('Telemetry refreshed'); });
  document.querySelector('#export')?.addEventListener('click', exportReport);
  document.querySelector('#profile')?.addEventListener('click', () => { profileOpen = true; render(); });
  document.querySelector('#close-profile')?.addEventListener('click', () => { profileOpen = false; render(); });
  document.querySelector('#profile-backdrop')?.addEventListener('click', (event) => { if (event.target.id === 'profile-backdrop') { profileOpen = false; render(); } });
  document.querySelector('#profile-audit')?.addEventListener('click', () => toast('Access audit is recorded in the control-plane log'));
  document.querySelector('#explain-workflow')?.addEventListener('click', () => { explainerOpen = true; render(); });
  document.querySelector('#close-explainer')?.addEventListener('click', () => { explainerOpen = false; render(); });
  document.querySelector('#explainer-backdrop')?.addEventListener('click', (event) => { if (event.target.id === 'explainer-backdrop') { explainerOpen = false; render(); } });
  document.querySelector('#ask-analyst')?.addEventListener('click', askAnalyst);
  document.querySelector('#toggle-inspection')?.addEventListener('click', () => { inspectionOpen = !inspectionOpen; render(); });
  document.querySelector('#logout')?.addEventListener('click', logout);
}

function bindAuthEvents() {
  document.querySelector('#auth-switch')?.addEventListener('click', () => { authMode = authMode === 'login' ? 'signup' : 'login'; authError = ''; render(); });
  document.querySelector('#auth-form')?.addEventListener('submit', submitAuth);
  startShader();
}

async function submitAuth(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const endpoint = authMode === 'login' ? '/api/login' : '/api/signup';
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: form.get('email'), password: form.get('password'), display_name: form.get('name') || form.get('email') }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Authentication failed');
    if (authMode === 'signup') {
      authMode = 'login';
      authError = 'Account created. Sign in with the matching credentials.';
      render();
      return;
    }
    localStorage.setItem('netops_session', result.token);
    authenticatedUser = result.user;
    authError = '';
    render();
    hydrateFromApi();
  } catch (error) {
    authError = error.message;
    render();
  }
}

async function logout() {
  const token = localStorage.getItem('netops_session');
  await apiFetch('/api/logout', { method: 'POST' }).catch(() => {});
  localStorage.removeItem('netops_session');
  authenticatedUser = null;
  authChecked = true;
  render();
}

async function askAnalyst() {
  const button = document.querySelector('#ask-analyst');
  analystEvidence = document.querySelector('#agent-evidence')?.value.trim() || '';
  if (button) { button.disabled = true; button.textContent = 'Reviewing evidence'; }
  try {
    const response = await apiFetch('/api/analyst', { method: 'POST', body: JSON.stringify({ incident_id: selectedIncident.id, evidence: analystEvidence }) });
    if (!response.ok) throw new Error('Analyst service returned an error');
    analyst = await response.json();
    addActivity('AI analyst', `Assessment recorded for ${selectedIncident.id}`, 'good');
    render();
  } catch (error) {
    if (button) { button.disabled = false; button.textContent = 'Retry evidence assessment'; }
    toast('AI analyst unavailable: start the NetOps API on port 8000');
  }
}

async function runSimulation() {
  if (actionBusy || simulated) return;
  actionBusy = true;
  actionError = '';
  render();
  try {
    const response = await apiFetch('/api/simulate', {
      method: 'POST',
      body: JSON.stringify({ incident_id: selectedIncident.id, action: selectedIncident.action })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Simulation endpoint is unavailable');
    simulated = result.passed === true;
    selectedIncident.risk = result.risk;
    selectedIncident.decision = result.decision;
    if (!simulated) throw new Error(result.reason || 'Simulation rejected the action');
    addActivity('Simulator', `${selectedIncident.action}: predicted CPU ${result.predicted_cpu}% -> ${result.decision}`, result.decision === 'rejected' ? 'critical' : 'good');
  } catch (error) {
    actionError = `Simulation blocked: ${error.message}.`;
    toast('Simulation was not confirmed by the backend');
  } finally {
    actionBusy = false;
    render();
  }
}

async function approveChange() {
  if (actionBusy || !simulated || approved) return;
  actionBusy = true;
  actionError = '';
  render();
  try {
    const response = await apiFetch('/api/decide', {
      method: 'POST',
      body: JSON.stringify({ incident_id: selectedIncident.id, action: selectedIncident.action, risk: selectedIncident.risk, simulated_passed: simulated, category: selectedIncident.type })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Decision endpoint is unavailable');
    approved = result.decision !== 'rejected';
    if (!approved) throw new Error('The safety check did not confirm this change');
    addActivity('AI decision', `${selectedIncident.action} -> ${result.decision} after safety review`, 'good');
    currentView = 'Change queue';
  } catch (error) {
    actionError = `Approval blocked: ${error.message}.`;
    toast('Approval was not confirmed by the backend');
  } finally {
    actionBusy = false;
    render();
  }
}

function exportReport() {
  const report = `NetOps Control Room\nGenerated: ${new Date().toISOString()}\nActive incidents: ${incidents.length}\nSelected diagnosis: ${selectedIncident.id} - ${selectedIncident.title}\nRecommended action: ${selectedIncident.action}\nRisk score: ${selectedIncident.risk}%\n`;
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([report], { type: 'text/plain' }));
  link.download = 'netops-report.txt';
  link.click();
  URL.revokeObjectURL(link.href);
  toast('Report downloaded');
}

function addActivity(source, message, tone) {
  activity = [[new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }), source, message, tone], ...activity.slice(0, 3)];
}

function toast(message) {
  const item = document.querySelector('#toast');
  if (!item) return;
  item.textContent = message;
  item.classList.add('show');
  window.clearTimeout(window.toastTimer);
  window.toastTimer = window.setTimeout(() => item.classList.remove('show'), 2600);
}

function startShader() {
  const canvas = document.querySelector('#shader');
  if (!canvas) return;
  const context = canvas.getContext('2d');
  let running = true;
  const resize = () => { canvas.width = window.innerWidth * devicePixelRatio; canvas.height = window.innerHeight * devicePixelRatio; context.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0); };
  const draw = (time) => {
    if (!document.body.contains(canvas)) { running = false; return; }
    const width = window.innerWidth;
    const height = window.innerHeight;
    context.clearRect(0, 0, width, height);
    context.strokeStyle = 'rgba(148, 178, 174, 0.05)';
    context.lineWidth = 1;
    const drift = (time * 0.004) % 64;
    for (let x = -64 + drift; x < width; x += 64) { context.beginPath(); context.moveTo(x, 0); context.lineTo(x, height); context.stroke(); }
    for (let y = -64 + drift; y < height; y += 64) { context.beginPath(); context.moveTo(0, y); context.lineTo(width, y); context.stroke(); }
    if (running) requestAnimationFrame(draw);
  };
  resize();
  window.addEventListener('resize', resize);
  requestAnimationFrame(draw);
}

function startCubeScroll() {
  const cube = document.querySelector('.cube');
  if (!cube) return;
  if (cubeScrollHandler) window.removeEventListener('scroll', cubeScrollHandler);
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reducedMotion) return;
  let frame = 0;
  cubeScrollHandler = () => {
    if (frame) return;
    frame = window.requestAnimationFrame(() => {
      const scrollAmount = window.scrollY;
      cube.style.transform = `rotateX(${scrollAmount * 0.16}deg) rotateY(${scrollAmount * 0.22}deg) rotateZ(${scrollAmount * 0.04}deg)`;
      frame = 0;
    });
  };
  window.addEventListener('scroll', cubeScrollHandler, { passive: true });
  cubeScrollHandler();
}

function startScrollReveals() {
  const elements = document.querySelectorAll('.page-intro, .topology-map, .devices-section, .content-grid, .incident-board, .queue-card, .queue-note, .analytics-card, .analytics-kpis');
  if (!elements.length) return;
  elements.forEach((element) => element.classList.add('scroll-reveal'));
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) {
    elements.forEach((element) => element.classList.add('is-visible'));
    return;
  }
  const observer = new IntersectionObserver((entries, currentObserver) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      currentObserver.unobserve(entry.target);
    });
  }, { threshold: 0.14 });
  elements.forEach((element) => observer.observe(element));
}

render();

async function hydrateFromApi() {
  try {
    const response = await apiFetch('/api/state');
    if (response.status === 401) {
      authenticatedUser = null;
      authChecked = true;
      render();
      return;
    }
    if (!response.ok) throw new Error('Control plane unavailable');
    const state = await response.json();
    apiStatus = state.connected ? 'Connected to control plane' : 'Control plane degraded';
    if (Array.isArray(state.incidents) && state.incidents.length) {
      incidents.splice(0, incidents.length, ...state.incidents);
      selectedIncident = incidents[0];
    }
    if (Array.isArray(state.events) && state.events.length) {
      activity = state.events.map((event) => [new Date(event.created_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }), event.source, event.message, event.tone]);
    }
    if (Array.isArray(state.devices) && state.devices.length) {
      devices.splice(0, devices.length, ...state.devices);
    }
    await hydrateTelemetry();
    render();
  } catch (error) {
    apiStatus = 'Offline control plane';
    render();
  }
}

async function hydrateTelemetry() {
  try {
    const response = await apiFetch(`/api/telemetry?range=${analyticsRange}`);
    if (!response.ok) return;
    const series = await response.json();
    if (Array.isArray(series.cpu) && series.cpu.length) {
      analyticsSeries[analyticsRange] = { cpu: series.cpu, label: series.label || analyticsRange };
    }
    if (Array.isArray(series.devices) && series.devices.length) {
      devices.splice(0, devices.length, ...series.devices);
    }
  } catch (error) {
    return;
  }
}

const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) || 'http://127.0.0.1:8000';

async function apiFetch(path, options = {}) {
  const token = localStorage.getItem('netops_session');
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  return fetch(url, { ...options, headers });
}

async function restoreSession() {
  const token = localStorage.getItem('netops_session');
  if (!token) {
    authChecked = true;
    render();
    return;
  }
  try {
    const response = await apiFetch('/api/profile');
    if (!response.ok) throw new Error('Session expired');
    const profile = await response.json();
    authenticatedUser = { name: profile.name, email: profile.email };
  } catch (error) {
    localStorage.removeItem('netops_session');
  }
  authChecked = true;
  render();
  if (authenticatedUser) hydrateFromApi();
}

restoreSession();
