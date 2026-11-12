"use strict";
let csrf = "", busy = false, connected = false, createKey = null, commandToCopy = "";
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
  $("#session-rows").replaceChildren();
  const active = sessions.filter((session) => session.state === "ready").length;
  $("#active-total").textContent = `${active} / 5`; $("#session-count").textContent = String(sessions.length);
  $("#empty-state").hidden = sessions.length !== 0;
  for (const session of [...sessions].reverse()) {
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
$("#refresh-sessions").addEventListener("click", () => action(refresh));
$("#close-dialog").addEventListener("click", () => dialog.close());
$("#copy-command").addEventListener("click", async () => { try { await navigator.clipboard.writeText(commandToCopy); toast("Command copied."); } catch { toast("Select the command and copy it manually."); } });
$("#date-label").textContent = new Intl.DateTimeFormat("en-IN", {dateStyle: "full", timeZone: "Asia/Kolkata"}).format(new Date()) + " · LOCAL PILOT";
(async () => {
  try { csrf = (await api("/api/bootstrap")).csrf; await refresh(); }
  catch { notice(false, "Local backend unavailable", "Start scripts/serve_session_console.py and open its loopback URL."); }
})();
setInterval(() => { if (!busy && csrf) refresh(); }, 8000);
