"use strict";
let csrf = "", busy = false, connected = false, createKey = null, commandToCopy = "", lastSessions = [];
const $ = (selector) => document.querySelector(selector);
const dialog = $("#details-dialog");
function toast(message) { $("#toast").textContent = message; $("#toast").classList.add("visible"); setTimeout(() => $("#toast").classList.remove("visible"), 3500); }
async function api(path, body, key, retried = false) {
  const headers = {};
  const options = { credentials: "same-origin", cache: "no-store", headers };
  if (body !== undefined) {
    options.method = "POST"; options.body = JSON.stringify(body);
    headers["Content-Type"] = "application/json"; headers["X-POC-CSRF"] = csrf;
    if (key) headers["Idempotency-Key"] = key;
  }
  const response = await fetch(path, options), data = await response.json();
  if (response.status === 401 && !retried && path !== "/api/bootstrap") {
    csrf = (await api("/api/bootstrap")).csrf;
    return api(path, body, key, true);
  }
  if (!response.ok) throw new Error(data.error || "request_failed");
  return data;
}
function notice(ok, title, text) {
  connected = ok; $("#notice-title").textContent = title; $("#notice-text").textContent = text;
  $("#connection-status").textContent = ok ? "Worker connected" : "Worker unavailable";
  $("#create-session").disabled = busy || !ok;
}
function details(title, description, content, command = "") {
  $("#dialog-title").textContent = title; $("#dialog-description").textContent = description;
  $("#dialog-content").textContent = content; commandToCopy = command;
  $("#copy-command").hidden = !command; dialog.showModal();
}
async function action(fn) {
  if (busy) return;
  busy = true; $("#create-session").disabled = true; $("#refresh-sessions").disabled = true;
  try { await fn(); } catch (error) { toast(error.message); }
  finally { busy = false; $("#refresh-sessions").disabled = false; $("#create-session").disabled = !connected; }
}
function button(text, callback, disabled = false) {
  const element = document.createElement("button"); element.className = "text-button";
  element.textContent = text; element.disabled = disabled; element.addEventListener("click", () => action(callback)); return element;
}
function render(sessions) {
  lastSessions = sessions;
  const filter = $("#session-state-filter").value;
  const visible = sessions.filter(s => filter === "all" || (filter === "active" ? ["ready", "provisioning", "stopping"].includes(s.state) : s.state === filter));
  $("#session-rows").replaceChildren();
  const active = sessions.filter((session) => session.state === "ready").length;
  $("#active-total").textContent = `${active} / 5`; $("#session-count").textContent = String(sessions.length);
  $("#empty-state").hidden = visible.length !== 0;
  $("#empty-state strong").textContent = "No sessions match this view";
  $("#empty-state span").textContent = sessions.length ? "Choose another state filter to view session history." : "Create your first session to get started.";
  for (const session of [...visible].reverse()) {
    const row = document.createElement("tr");
    const state = session.stop_reason === "expired" ? "Expired" : session.state === "ready" ? "Login-ready" : session.state;
    const expiry = session.expires ? new Date(session.expires * 1000).toLocaleString() : "No expiry (legacy)";
    for (const value of [`Codex · ${session.id.slice(0, 8)}`, state, session.runtime, expiry]) {
      const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
    }
    const actions = document.createElement("td");
    actions.append(button("Inspect", async () => {
      const [info, events] = await Promise.all([api(`/api/sessions/${session.id}`), api(`/api/sessions/${session.id}/events`)]);
      $("#event-output").textContent = events.map((e) => `${new Date(e.at * 1000).toLocaleString()} · ${e.action} · ${e.state}`).join("\n") || "No events.";
      details("Session details", "Current worker metadata. Login status is not inferred from the ready state.", JSON.stringify(info, null, 2));
    }));
    for (const kind of ["login", "attach"]) actions.append(button(kind === "login" ? "Login" : "Open Codex", async () => {
      const commands = await api(`/api/sessions/${session.id}/terminal`);
      details(kind === "login" ? "Private device login" : "Open Codex in Terminal", "Run this command in Mac Terminal. Keep login codes and credentials private. Browser terminal relay is not available in this pilot.", commands[kind], commands[kind]);
    }, session.state !== "ready"));
    actions.append(button("Stop", async () => {
      if (!window.confirm("Stop this session? Its temporary login home will be deleted. Your managed workspace will be kept.")) return;
      await api(`/api/sessions/${session.id}/stop`, {}); toast("Session stopped. Workspace retained."); await refresh();
    }, session.state === "stopped"));
    row.append(actions); $("#session-rows").append(row);
  }
}
async function refresh() {
  try {
    const result = await api("/api/sessions"); render(result.sessions);
    const cleanup = result.cleanup;
    const resident = result.resident_cleanup;
    const healthy = resident?.active && !resident.stale && resident.last_success && !resident.error;
    const fallback = cleanup?.last_success && !cleanup.error;
    const message = healthy
      ? "New sessions expire in one hour. The VM service checks every 30s, even with this backend closed. VM/Mac suspension pauses cleanup; legacy sessions need manual stop."
      : fallback
        ? "VM cleanup needs attention. The Mac backend is providing fallback cleanup while running. Legacy sessions need manual stop."
        : "Cleanup needs attention. Check the VM service and stop sessions manually if needed.";
    notice(true, healthy ? "Resident cleanup is healthy" : "Resident cleanup needs attention", message);
  } catch (error) {
    $("#session-rows").replaceChildren(); $("#active-total").textContent = "—"; $("#session-count").textContent = "—";
    $("#empty-state").hidden = true; notice(false, "Worker unavailable", `Actions are disabled until the connection returns (${error.message}).`);
  }
}
$("#create-session").addEventListener("click", () => action(async () => {
  createKey ||= crypto.randomUUID();
  const session = await api("/api/sessions", { policy_id: "codex-tls-pilot-v1" }, createKey);
  createKey = null; toast(session.state === "ready" ? `Session ${session.id.slice(0, 8)} is ready for private login.` : `Request resolved to session state: ${session.state}.`); await refresh();
}));
$("#refresh-sessions").addEventListener("click", () => action(async () => { await refresh(); await refreshMonitoring(); await refreshJournal(); }));
$("#close-dialog").addEventListener("click", () => dialog.close());
$("#copy-command").addEventListener("click", async () => { try { await navigator.clipboard.writeText(commandToCopy); toast("Command copied."); } catch { toast("Select the command and copy it manually."); } });
$("#date-label").textContent = new Intl.DateTimeFormat("en-IN", {dateStyle: "full", timeZone: "Asia/Kolkata"}).format(new Date()) + " · LOCAL PILOT";
(async () => {
  try { csrf = (await api("/api/bootstrap")).csrf; await refresh(); await refreshMonitoring(); await refreshJournal(); await loadHistory(true); }
  catch { notice(false, "Local backend unavailable", "Start scripts/serve_session_console.py and open its loopback URL."); }
})();
setInterval(() => { if (!busy && csrf) refresh(); }, 8000);

let monitorBusy = false, signals = [], approvedHosts = [];
const controlNames = ["Runtime", "Non-root user", "Read-only root", "No new privileges", "Dropped capabilities", "Resource limits", "Internal agent network", "Workspace / CA mount boundary", "Gateway domain configuration"];
function textNode(tag, text, className = "") {
  const node = document.createElement(tag); node.textContent = text; if (className) node.className = className; return node;
}
function pill(text, status = "") { return textNode("span", text, `status-pill ${status}`); }
function renderMonitoring(data) {
  $("#sample-time").textContent = `Sampled ${new Date(data.sampled_at * 1000).toLocaleTimeString()} · refreshes every 30s`;
  const sessions = data.sessions, unavailable = sessions.filter(s => s.error).length;
  $("#monitor-status").textContent = sessions.length
    ? `${sessions.length} active session(s) sampled. ${unavailable} incomplete sample(s). Configuration checks do not replace behavior or bypass testing.`
    : "No active sessions to inspect. Policy checks and utilization are unmeasured until a session is running. Recorded validation results remain available below.";
  $("#policy-rows").replaceChildren();
  let passed = 0, failed = 0;
  for (const name of controlNames) {
    const checks = sessions.map(s => s.checks.find(c => c.name === name));
    const failures = checks.filter(c => c?.status === "fail").length;
    const good = checks.filter(c => c?.status === "pass").length;
    const complete = sessions.length > 0 && checks.every(Boolean);
    if (failures) failed++; else if (complete) passed++;
    const row = document.createElement("tr"); row.append(textNode("td", name));
    const cell = document.createElement("td"); cell.append(pill(failures ? `${failures} failed` : complete ? "Passing" : "Unmeasured", failures ? "fail" : complete ? "pass" : "muted-pill")); row.append(cell);
    row.append(textNode("td", sessions.length ? `${good}/${sessions.length} sessions verified` : "No active session")); $("#policy-rows").append(row);
  }
  $("#policy-total").textContent = `${passed}/9 passing · ${failed} failing · ${9 - passed - failed} unmeasured`;
  $("#telemetry-rows").replaceChildren();
  for (const session of sessions) {
    const row = document.createElement("tr"), stats = session.telemetry, egress = session.egress?.counts;
    const percent = value => Number.isFinite(value) ? `${value.toFixed(1)}%` : "Unavailable";
    for (const value of [session.id.slice(0, 8), percent(stats?.cpu_percent), percent(stats?.memory_percent), stats?.pids ?? "Unavailable", egress ? `${egress.allow} allowed · ${egress.deny} denied` : "Unavailable"]) row.append(textNode("td", String(value)));
    $("#telemetry-rows").append(row);
  }
  if (!sessions.length) { const row = document.createElement("tr"), cell = textNode("td", "No active agent containers to sample."); cell.colSpan = 5; row.append(cell); $("#telemetry-rows").append(row); }
  signals = data.signals; renderSignals();
  approvedHosts = data.allowed_hosts; $("#allowed-hosts").replaceChildren(...approvedHosts.map(host => textNode("li", host)));
  $("#timing-bars").replaceChildren();
  if (!data.recorded_timings.length) $("#timing-bars").textContent = "No recorded measurements available.";
  const max = Math.max(1, ...data.recorded_timings.map(v => v.seconds));
  for (const metric of data.recorded_timings) {
    const row = textNode("div", "", "timing-row"), progress = document.createElement("progress");
    progress.max = max; progress.value = metric.seconds; progress.setAttribute("aria-label", `${metric.label}: ${metric.seconds.toFixed(2)} seconds`);
    row.append(textNode("span", metric.label), progress, textNode("strong", `${metric.seconds.toFixed(2)}s`)); $("#timing-bars").append(row);
  }
}
function renderSignals() {
  const filter = $("#signal-filter").value, visible = signals.filter(s => filter === "all" || s.kind === filter);
  $("#signal-total").textContent = `${signals.length} review signals`;
  $("#signal-list").replaceChildren();
  const labels = { policy_drift: "Policy configuration drift", egress_denied: "Egress policy denial", lifecycle_failure: "Worker lifecycle failure" };
  for (const signal of visible) {
    const row = textNode("div", "", "signal-row"), copy = document.createElement("div");
    copy.append(textNode("strong", `${labels[signal.kind] || "Review signal"} · ${signal.session_id.slice(0, 8)}`), textNode("p", signal.detail));
    if (signal.at) copy.append(textNode("small", new Date(signal.at * 1000).toLocaleString()));
    row.append(pill(signal.severity === "high" ? "High" : "Review", signal.severity === "high" ? "fail" : "review"), copy); $("#signal-list").append(row);
  }
  if (!visible.length) $("#signal-list").append(textNode("div", "No matching signals in the sampled data. This does not establish that no suspicious activity occurred.", "signal-empty"));
}
async function refreshMonitoring() {
  if (monitorBusy) return; monitorBusy = true;
  try { renderMonitoring(await api("/api/monitor")); }
  catch { $("#monitor-status").textContent = "Monitoring unavailable. Any previous sample below is stale; no current policy or telemetry assurance is available."; $("#sample-time").textContent = "Sample unavailable / stale"; $("#policy-total").textContent = "Current checks unavailable"; }
  finally { monitorBusy = false; }
}
$("#signal-filter").addEventListener("change", renderSignals);
$("#domain-form").addEventListener("submit", event => {
  event.preventDefault(); const host = $("#domain-input").value.trim().toLowerCase().replace(/\.+$/, "");
  if (!approvedHosts.length) { $("#domain-result").textContent = "Load the policy before checking a hostname."; return; }
  const valid = host.length <= 253 && host.split(".").every(label => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label));
  $("#domain-result").textContent = !valid ? "Enter a hostname only, without a URL scheme, port or path." : approvedHosts.includes(host) ? `${host}: allowed by the HTTPS hostname policy (port 443). This does not guarantee endpoint access.` : `${host}: blocked by the default-deny policy. IP literals and unapproved subdomains are not allowed.`;
});
function updateNavigation() { const hash = location.hash || "#overview"; for (const link of document.querySelectorAll('nav a[href^="#"]')) link.classList.toggle("active", link.hash === hash); const titles = {"#overview":"Overview", "#sessions":"Sessions", "#activity":"Lifecycle events", "#policy":"Policy checks", "#telemetry":"Telemetry", "#security":"Suspicious activity", "#domains":"Blocked sites", "#alerts":"Alerts", "#history":"Event history"}; $(".breadcrumb strong").textContent = titles[hash] || "Overview"; }
window.addEventListener("hashchange", updateNavigation); updateNavigation();
setInterval(() => { if (csrf && !busy) refreshMonitoring(); }, 30000);

$("#session-state-filter").addEventListener("change", () => render(lastSessions));

let storedAlerts = [], journalBusy = false, historyBusy = false, historyBefore = null, storedHistory = [];
const kindLabels = {lifecycle:"Lifecycle", lifecycle_failure:"Worker failure", egress_denied:"Egress denied", policy_drift:"Policy drift"};
function renderAlerts() {
  const filter = $("#alert-state").value;
  const visible = storedAlerts.filter(a => filter === "all" || (filter === "active" ? a.status !== "resolved" : a.status === filter));
  $("#alert-list").replaceChildren();
  for (const alert of visible) {
    const row = textNode("div", "", "signal-row"), copy = textNode("div", "", "alert-copy");
    copy.append(textNode("strong", `${kindLabels[alert.kind]} · ${alert.session_id.slice(0, 8)}`), textNode("p", alert.detail));
    copy.append(textNode("small", `${alert.event_count} distinct event(s) · last seen ${new Date(alert.last_seen*1000).toLocaleString()}`));
    const actions = textNode("div", "", "alert-buttons");
    for (const operation of ["acknowledge", "resolve"]) actions.append(button(operation === "acknowledge" ? "Acknowledge" : "Resolve", async () => {
      await api(`/api/alerts/${alert.id}/${operation}`, {});
      toast(operation === "acknowledge" ? "Alert acknowledged." : "Alert resolved. New evidence may reopen it."); await refreshJournal();
    }, alert.status === "resolved" || (operation === "acknowledge" && alert.status === "acknowledged")));
    copy.append(actions); row.append(pill(alert.status, alert.status === "resolved" ? "muted-pill" : alert.severity === "high" ? "fail" : "review"), copy);
    $("#alert-list").append(row);
  }
  if (!visible.length) $("#alert-list").append(textNode("div", "No alerts match this view. This does not establish that no suspicious activity occurred.", "signal-empty"));
}
async function refreshJournal() {
  if (journalBusy) return; journalBusy = true;
  try {
    const data = await api("/api/alerts"); storedAlerts = data.alerts; renderAlerts();
    $("#alert-counts").textContent = `${data.counts.open} open · ${data.counts.acknowledged} acknowledged · ${data.counts.resolved} resolved`;
    const recent = data.last_collection && Date.now()/1000 - data.last_collection < 90;
    $("#collector-status").textContent = data.last_collection
      ? `Last resident collection: ${new Date(data.last_collection*1000).toLocaleString()}. ${recent ? "Recent" : "Stale; check the VM service"}. ${data.collection_errors} incomplete session sample(s). Latest 100 alerts shown; counts cover all retained alerts.`
      : "No resident collection recorded yet. Local history collection requires the VM service; this browser does not collect events.";
    $("#alert-audit").replaceChildren();
    for (const entry of data.audit) $("#alert-audit").append(textNode("div", `${new Date(entry.at*1000).toLocaleString()} · ${entry.action} · ${entry.actor} · alert ${entry.alert_id.slice(0,8)}`, "audit-row"));
    if (!data.audit.length) $("#alert-audit").append(textNode("div", "No alert actions recorded.", "signal-empty"));
  } catch { $("#collector-status").textContent = "Alert service unavailable. Any displayed alerts are stale."; }
  finally { journalBusy = false; }
}
async function loadHistory(reset = true) {
  if (historyBusy) return; historyBusy = true;
  $("#history-kind").disabled = true; $("#history-load").disabled = true; $("#history-refresh").disabled = true;
  try {
    const query = new URLSearchParams(), kind = $("#history-kind").value;
    if (kind) query.set("kind",kind);
    if (!reset && historyBefore) query.set("before",String(historyBefore));
    const data = await api(`/api/security-events${query.size ? "?"+query : ""}`);
    storedHistory = reset ? data.events : [...storedHistory,...data.events]; historyBefore = data.next_before;
    $("#history-rows").replaceChildren();
    for (const entry of storedHistory) {
      const row = document.createElement("tr");
      for (const value of [new Date(entry.observed_at*1000).toLocaleString(), kindLabels[entry.kind], entry.session_id.slice(0,8),entry.detail]) row.append(textNode("td",value));
      $("#history-rows").append(row);
    }
    if (!storedHistory.length) { const row = document.createElement("tr"), cell = textNode("td","No retained events match this filter."); cell.colSpan = 4; row.append(cell); $("#history-rows").append(row); }
    $("#history-count").textContent = `${storedHistory.length} records shown${storedHistory.length >= 500 ? "; reload newest or narrow the filter" : ""}`;
    $("#history-load").hidden = !historyBefore || storedHistory.length >= 500;
  } catch { $("#history-count").textContent = "History unavailable; previous records may be stale."; }
  finally { historyBusy = false; $("#history-kind").disabled = false; $("#history-load").disabled = false; $("#history-refresh").disabled = false; }
}
$("#alert-state").addEventListener("change",renderAlerts);
$("#refresh-alerts").addEventListener("click",()=>action(refreshJournal));
$("#history-kind").addEventListener("change",()=>loadHistory(true));
$("#history-load").addEventListener("click",()=>loadHistory(false));
$("#history-refresh").addEventListener("click",()=>loadHistory(true));
setInterval(()=>{ if(csrf && !busy) refreshJournal(); },30000);
