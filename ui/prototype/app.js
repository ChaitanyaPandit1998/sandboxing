const sessions = [
  { id: "codex-stable-01", cli: "Codex", runtime: "runsc-stable-20261109", workspace: "/workspace/api-refactor", status: "running", created: "12 min ago" },
  { id: "codex-runc-02", cli: "Codex", runtime: "runc", workspace: "/workspace/docs-review", status: "stopped", created: "Yesterday, 4:32 PM" },
];

const rows = document.querySelector("#session-rows");
const dialog = document.querySelector("#create-dialog");
const form = document.querySelector("#create-form");
const commandPreview = document.querySelector("#command-preview");
const toast = document.querySelector("#toast");
let toastTimer;

function runtimeLabel(runtime) {
  return {
    "runsc-stable-20261109": "runsc · stable",
    runsc: "runsc · pinned",
    "runsc-next": "runsc · nightly",
    runc: "runc · baseline",
  }[runtime] || runtime;
}

function safeSessionName(value) {
  return value.toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "codex-session";
}

function updateCounts() {
  const active = sessions.filter((session) => session.status === "running").length;
  document.querySelector("#active-total").innerHTML = `${active} <span class="metric-trend">Demo state</span>`;
  document.querySelector("#session-count").textContent = String(sessions.length);
  document.querySelector("#table-count").textContent = String(sessions.length).padStart(2, "0");
  document.querySelector("#shown-count").textContent = String(sessions.length);
  document.querySelector("#empty-state").hidden = sessions.length !== 0;
  document.querySelector("table").hidden = sessions.length === 0;
}

function makeCell(text, className = "") {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = text;
  return cell;
}

function renderSessions() {
  rows.replaceChildren();
  for (const session of sessions) {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const nameWrap = document.createElement("div");
    nameWrap.className = "session-main";
    const avatar = document.createElement("span");
    avatar.className = `session-avatar ${session.cli === "Codex" ? "codex" : "claude"}`;
    avatar.textContent = session.cli === "Codex" ? "C" : "✳";
    const label = document.createElement("span");
    label.className = "session-label";
    const title = document.createElement("strong");
    title.textContent = session.id;
    const subtitle = document.createElement("small");
    subtitle.textContent = `${session.cli} CLI · sample session`;
    label.append(title, subtitle);
    nameWrap.append(avatar, label);
    nameCell.append(nameWrap);
    row.append(nameCell);

    const statusCell = document.createElement("td");
    const status = document.createElement("span");
    status.className = `status-pill ${session.status}`;
    const statusDot = document.createElement("i");
    status.append(statusDot, document.createTextNode(session.status === "running" ? "Running" : "Stopped"));
    statusCell.append(status);
    row.append(statusCell);

    const runtimeCell = document.createElement("td");
    const runtime = document.createElement("span");
    runtime.className = "runtime-pill";
    const runtimeGlyph = document.createElement("b");
    runtimeGlyph.className = "runtime-glyph";
    runtimeGlyph.textContent = "◇";
    runtime.append(runtimeGlyph, document.createTextNode(runtimeLabel(session.runtime)));
    runtimeCell.append(runtime);
    row.append(runtimeCell);

    row.append(makeCell(session.workspace, "workspace-cell"));
    row.append(makeCell(session.created, "date-cell"));
    const actionCell = document.createElement("td");
    const action = document.createElement("button");
    action.className = "row-menu";
    action.type = "button";
    action.title = session.status === "running" ? "Stop demo session" : "Session stopped";
    action.setAttribute("aria-label", `${session.status === "running" ? "Stop" : "Stopped"} ${session.id}`);
    action.textContent = session.status === "running" ? "■" : "•••";
    action.disabled = session.status !== "running";
    action.addEventListener("click", () => stopSession(session.id));
    actionCell.append(action);
    row.append(actionCell);
    rows.append(row);
  }
  updateCounts();
}

function announce(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("visible"), 2800);
}

function addActivity(title, detail, iconClass = "created", icon = "＋") {
  const list = document.querySelector("#activity-list");
  const item = document.createElement("div");
  item.className = "activity-item";
  const symbol = document.createElement("span");
  symbol.className = `activity-symbol ${iconClass}`;
  symbol.textContent = icon;
  const content = document.createElement("span");
  content.className = "activity-content";
  const strong = document.createElement("strong");
  strong.textContent = title;
  const small = document.createElement("small");
  small.textContent = detail;
  content.append(strong, small);
  const time = document.createElement("time");
  time.textContent = "Just now";
  item.append(symbol, content, time);
  list.prepend(item);
}

function stopSession(id) {
  const session = sessions.find((item) => item.id === id);
  if (!session || session.status !== "running") return;
  session.status = "stopped";
  renderSessions();
  addActivity("Demo session stopped", `${id} · simulated in prototype`, "stopped", "✓");
  announce("Demo only — no container was stopped.");
}

function currentCommand() {
  const runtime = document.querySelector("#runtime-select").value;
  const cli = document.querySelector("#cli-select").value;
  return `limactl shell gvisor-poc -- bash -lc 'cd "$HOME/gvisor-poc" && bash scripts/run_agent_model_smoke.sh start ${runtime} ${cli}'`;
}

function renderCommand() {
  commandPreview.textContent = currentCommand();
}

document.querySelector("#open-create").addEventListener("click", () => {
  renderCommand();
  dialog.showModal();
});
document.querySelector("#empty-create").addEventListener("click", () => document.querySelector("#open-create").click());
document.querySelector("#runtime-select").addEventListener("change", renderCommand);
document.querySelector("#cli-select").addEventListener("change", renderCommand);
document.querySelector("#session-name").addEventListener("input", (event) => {
  event.target.value = event.target.value.replace(/[^a-zA-Z0-9-]/g, "-").slice(0, 40);
});

document.querySelector("#copy-command").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(currentCommand());
    announce("Command copied. Run it manually in your Lima VM.");
  } catch {
    announce("Clipboard unavailable here. Select and copy the command manually.");
  }
});

document.querySelector("#create-session").addEventListener("click", (event) => {
  event.preventDefault();
  const cli = document.querySelector("#cli-select").value;
  const runtime = document.querySelector("#runtime-select").value;
  const name = safeSessionName(document.querySelector("#session-name").value);
  const uniqueId = sessions.some((session) => session.id === name) ? `${name}-${String(sessions.length + 1).padStart(2, "0")}` : name;
  sessions.unshift({
    id: uniqueId,
    cli: cli === "codex" ? "Codex" : "Claude Code",
    runtime,
    workspace: "/workspace/new-session",
    status: "running",
    created: "Just now",
  });
  renderSessions();
  addActivity("Demo session created", `${uniqueId} · ${runtimeLabel(runtime)}`, "created", "＋");
  dialog.close();
  announce("Demo session added. Copy the generated command to start a real session.");
});

document.querySelector("#refresh-sessions").addEventListener("click", () => {
  renderSessions();
  announce("Sample session list refreshed.");
});
document.querySelector("#view-all").addEventListener("click", () => announce("You are viewing all sample sessions."));
document.querySelectorAll(".nav-item, .filter-button, .more-button").forEach((element) => {
  if (element.matches("a")) return;
  element.addEventListener("click", () => announce("This navigation control is illustrative in the prototype."));
});

renderSessions();
