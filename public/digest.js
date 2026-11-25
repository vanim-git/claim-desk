(() => {
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const names = { claim: "Claim desk", stock: "Expiry watch", schemes: "Scheme desk", supply: "Supply desk" };

function renderDigest(d) {
  $("dg_out").innerHTML = `<div class="card muted">As of ${esc(d.as_of)}. ${esc(d.note)}</div>` + d.sections.map((s) =>
    `<div class="card"><h2>${esc(s.owner)} <span class="muted">${esc(s.role)}</span></h2><ul>${s.items.map((i) =>
      `<li>${esc(i.text)} <a href="#${esc(i.tab === "claim" ? "" : i.tab)}">${esc(names[i.tab])}</a></li>`).join("")}</ul></div>`).join("");
}

function renderLog(d) {
  const rows = Object.entries(d.files).map(([f, v]) => {
    const { rows: n, exact_duplicate_rows_dropped: dup, ...fx } = v;
    return `<tr><td>${esc(f)}</td><td>${n}</td><td>${dup}</td><td>${esc(Object.entries(fx).map(([k, x]) => k.replace(/_/g, " ") + ": " + x).join("; ")) || "none"}</td></tr>`;
  }).join("");
  $("dg_out").innerHTML = `<div class="card"><h2>Data fixes, counted per file</h2><p class="muted">${esc(d.note)}</p>
    <table><thead><tr><th>File</th><th>Rows</th><th>Exact duplicates dropped</th><th>Other fixes (counts of cells)</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

async function load(url, fn) {
  $("dg_out").textContent = "Working…";
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error((await r.json()).error || r.statusText);
    fn(await r.json());
  } catch (e) { $("dg_out").innerHTML = `<div class="err">${esc(e.message)}</div>`; }
}
let STEPS = null;
function fillSteps() {
  $("ac_step").innerHTML = (STEPS[$("ac_desk").value] || []).map((x) => `<option>${esc(x)}</option>`).join("");
}
function renderActions(d) {
  STEPS = d.steps; fillSteps();
  const rows = d.entries.map((e) => `<tr><td>${e.seq}</td><td>${esc(e.at)}</td><td>${esc(e.desk)}</td><td>${esc(e.step)}</td><td>${esc(e.ref)}</td><td>${esc(e.by)}</td><td>${esc(e.note)}</td></tr>`).join("");
  $("dg_out").innerHTML = `<div class="card"><h2>Action log</h2><p class="muted">Chain check: ${d.chain.ok ? "unbroken, " + d.chain.entries + " entries" : "BROKEN at entry " + d.chain.broken_at}.
    ${d.durable ? "" : "On Vercel this log is lost on a cold start: it is not durable until a hosted store is agreed."}</p>
    ${rows ? `<table><thead><tr><th>#</th><th>When (UTC)</th><th>Desk</th><th>Step</th><th>About</th><th>By</th><th>Note</th></tr></thead><tbody>${rows}</tbody></table>` : "<p>No steps recorded yet.</p>"}</div>`;
}
async function loadActions() { await load("/api/actions", renderActions); }
$("ac_desk").addEventListener("change", () => STEPS && fillSteps());
$("dg_acts").addEventListener("click", loadActions);
$("ac_go").addEventListener("click", async () => {
  if (!STEPS) { const r = await fetch("/api/actions?limit=1"); STEPS = (await r.json()).steps; fillSteps(); }
  const body = { desk: $("ac_desk").value, step: $("ac_step").value, by: $("ac_by").value, ref: $("ac_ref").value, note: $("ac_note").value };
  const r = await fetch("/api/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json();
  $("ac_msg").textContent = r.ok ? `Recorded as step ${j.entry.seq}.${j.durable ? "" : " Not durable on Vercel."}` : j.error;
  if (r.ok) loadActions();
});
fetch("/api/actions?limit=1").then((r) => r.json()).then((d) => { STEPS = d.steps; fillSteps(); }).catch(() => {});
$("dg_go").addEventListener("click", () => load("/api/digest", renderDigest));
$("dg_log").addEventListener("click", () => load("/api/data-log", renderLog));
})();
