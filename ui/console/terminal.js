"use strict";
const screen = document.querySelector("#terminal-screen"), statusLine = document.querySelector("#terminal-status");
let terminal, fit, csrf = "", channel = null, cursor = 0, active = false, closing = false, inputQueue = Promise.resolve(), queued = 0;
const parameters = new URLSearchParams(location.search), sid = parameters.get("session"), mode = parameters.get("mode");
async function request(path, body, keepalive = false) {
  const options = { credentials:"same-origin", cache:"no-store", keepalive };
  if (body !== undefined) { options.method="POST"; options.headers={"Content-Type":"application/json","X-POC-CSRF":csrf}; options.body=JSON.stringify(body); }
  const response = await fetch(path, options), value = await response.json();
  if (!response.ok) throw new Error(value.error || "terminal_request_failed");
  return value;
}
function encode(bytes) { let text=""; for (const byte of bytes) text+=String.fromCharCode(byte); return btoa(text); }
function ended(reason) { active=false; statusLine.textContent=reason; if (terminal) terminal.options.disableStdin=true; }
function disconnect(reason = "Disconnected") {
  if (closing) return;
  closing=true; ended(typeof reason === "string" ? reason : "Disconnected");
  if (channel && csrf) request(`/api/terminals/${channel}/close`,{},true).catch(()=>{});
  if (terminal) terminal.dispose();
}
function input(bytes) {
  if (!active || closing || bytes.length===0) return;
  if (queued+bytes.length>65536) { disconnect("Input buffer full; reconnect to continue."); return; }
  queued+=bytes.length;
  for (let offset=0;offset<bytes.length;offset+=2048) {
    const part=bytes.slice(offset,offset+2048);
    inputQueue=inputQueue.then(async()=>{
      if (active && !closing) await request(`/api/terminals/${channel}/input`,{data:encode(part)});
    }).catch(error=>{ disconnect(error.message); }).finally(()=>{queued-=part.length;});
  }
}
async function poll() {
  while (active && !closing) {
    try {
      const value=await request(`/api/terminals/${channel}?cursor=${cursor}`);
      const bytes=Uint8Array.from(atob(value.data),ch=>ch.charCodeAt(0));
      if (bytes.length) await new Promise(resolve=>terminal.write(bytes,resolve));
      cursor=value.cursor;
      if (value.closed) { ended(`Terminal ended (${value.reason || "closed"}).`); break; }
    } catch(error) { disconnect(error.message); break; }
    await new Promise(resolve=>setTimeout(resolve,200));
  }
}
(async()=>{
  try {
    if (!/^[a-f0-9]{32}$/.test(sid || "") || !["login","attach"].includes(mode) || parameters.size!==2) throw new Error("Invalid terminal request");
    csrf=(await request("/api/bootstrap")).csrf;
    terminal=new Terminal({cursorBlink:true,fontSize:13,fontFamily:"Menlo, Consolas, monospace",scrollback:1000,allowProposedApi:false,
      theme:{background:"#111b2e",foreground:"#e7edf8"},linkHandler:{activate:()=>{}}});
    fit=new FitAddon.FitAddon();terminal.loadAddon(fit);terminal.open(screen);fit.fit();
    terminal.onData(text=>input(new TextEncoder().encode(text)));
    terminal.onBinary(text=>input(Uint8Array.from(text,ch=>ch.charCodeAt(0))));
    const ticket=await request(`/api/sessions/${sid}/terminal-ticket`,{mode});
    const result=await request("/api/terminals",{ticket:ticket.ticket,cols:Math.max(20,Math.min(300,terminal.cols)),rows:Math.max(5,Math.min(120,terminal.rows))});
    channel=result.id;active=true;statusLine.textContent="Connected · local sandbox";
    document.querySelector("#terminal-label").textContent=(mode==="login"?"Private Codex login":"Codex")+" · "+sid.slice(0,8);
    terminal.focus();poll();
  } catch(error) { ended(error.message); }
})();
let resizeTimer;
new ResizeObserver(()=>{
  clearTimeout(resizeTimer);
  resizeTimer=setTimeout(()=>{
    if (!terminal || !active || closing) return;
    fit.fit();request(`/api/terminals/${channel}/resize`,{cols:Math.max(20,Math.min(300,terminal.cols)),rows:Math.max(5,Math.min(120,terminal.rows))}).catch(error=>disconnect(error.message));
  },150);
}).observe(screen);
document.querySelector("#terminal-disconnect").addEventListener("click",disconnect);
window.addEventListener("pagehide",disconnect);
