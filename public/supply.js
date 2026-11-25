(() => {
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const Cr = (v) => "₹" + (v / 1e7).toFixed(2) + " cr";
const L = (v) => "₹" + (v / 1e5).toFixed(1) + " L";
const pct = (v, n = 1) => (v * 100).toFixed(n) + "%";

function render(d) {
  const u = d.unfilled;
  const q = Object.entries(u.by_quarter).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${pct(v.fill)}</td><td>${Cr(v.unfilled_value)}</td></tr>`).join("");
  const c = Object.entries(u.by_cnf).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${Cr(v)}</td></tr>`).join("");
  let h = `<div class="card"><h2>Unfilled orders, last four quarters</h2><p><b>${Cr(u.total)}</b> (${Cr(u.conservative)} counting repeat orders once). Inside the scheme windows ${Cr(u.in_window)}; outside ${Cr(u.outside_window)}.</p>
    <table><thead><tr><th>Quarter</th><th>Fill</th><th>Unfilled</th></tr></thead><tbody>${q}</tbody></table>
    <table><thead><tr><th>C&amp;F</th><th>Unfilled</th></tr></thead><tbody>${c}</tbody></table></div>`;
  const s = d.shares, sr = Object.values(s.by_cnf).map((v) => `<tr><td>${esc(v.cnf)}</td><td>${pct(v.current)}</td><td>${pct(v.proposed)}</td><td>${(v.gap * 100).toFixed(1)} pts</td></tr>`).join("");
  h += `<div class="card"><h2>Allocation shares: FY25 share in use vs what stockists order</h2><p class="muted">${esc(s.basis)}. Review ${esc(s.review)}.</p>
    <table><thead><tr><th>C&amp;F</th><th>Current share</th><th>Proposed share</th><th>Gap</th></tr></thead><tbody>${sr}</tbody></table></div>`;
  const m = d.moves, mr = m.moves.map((x) => `<tr><td>${esc(x.sku)}</td><td>${esc(x.from_cnf)}</td><td>${esc(x.to_cnf)}</td><td>${x.packs}</td><td>${L(x.value)}</td></tr>`).join("");
  h += `<div class="card"><h2>Proposed moves through ${esc(m.moves[0]?.via || "the CDC")} (as of ${esc(m.as_of)})</h2><p>${L(m.covered_value)} of spare stock could cover part of ${L(m.unmet_value)} a month of unmet need. ${esc(m.note)}</p>
    <table><thead><tr><th>SKU</th><th>From</th><th>To</th><th>Packs</th><th>Value</th></tr></thead><tbody>${mr}</tbody></table></div>`;
  h += `<div class="card muted">${d.notes.map(esc).join("<br>")}</div>`;
  $("su_out").innerHTML = h;
}

$("su_go").addEventListener("click", async () => {
  $("su_out").textContent = "Working…";
  try {
    const r = await fetch("/api/supply-desk");
    if (!r.ok) throw new Error((await r.json()).error || r.statusText);
    render(await r.json());
  } catch (e) { $("su_out").innerHTML = `<div class="err">${esc(e.message)}</div>`; }
});
})();
