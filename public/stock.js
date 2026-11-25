(() => {
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const L = (v) => "₹" + (v / 1e5).toFixed(1) + " L";
const pct = (v) => (v * 100).toFixed(0) + "%";

function batchTable(bs) {
  const rows = bs.map((b) => `<tr><td>${esc(b.sku)} ${esc(b.product)}</td><td>${esc(b.batch)}</td><td>${esc(b.expiry)}</td><td>${pct(b.rsl)}</td>
    <td>${esc(b.band)}</td><td>${b.qty}</td><td>${b.can_sell}</td><td>${b.excess}</td><td>${esc(b.action)}${b.over_buffer ? " (over 2 months cover)" : ""}</td></tr>`).join("");
  return `<table><thead><tr><th>SKU</th><th>Batch</th><th>Expiry</th><th>RSL</th><th>Band</th><th>Packs</th><th>Can sell in region</th><th>Excess</th><th>Action</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function render(d) {
  let h = `<div class="card"><b>As of ${esc(d.as_of)}.</b><ul>${d.brief.map((x) => `<li>${esc(x)}</li>`).join("")}</ul><div class="muted">${esc(d.note)}</div></div>`;
  d.cnfs.forEach((c) => {
    h += `<div class="card"><h2>${esc(c.cnf)} ${esc(c.summary?.city)}</h2>${c.batches.length ? batchTable(c.batches) : "<p>Nothing at or under 70% RSL.</p>"}</div>`;
  });
  Object.values(d.picklists).forEach((p) => {
    const rows = p.lines.map((l) => `<tr><td>${esc(l.sku)} ${esc(l.product)}</td><td>${l.pick_order}</td><td>${esc(l.batch)}</td><td>${esc(l.expiry)}</td><td>${pct(l.rsl)}</td><td>${l.qty}</td></tr>`).join("");
    h += `<div class="card"><h2>Pick list ${esc(p.cnf)}: oldest batch first</h2><p>To ${esc(p.to)}, copy ${esc(p.cc)}. Confirm within ${esc(p.confirm_within_days)} days. ${esc(p.instruction)}</p>
      <table><thead><tr><th>SKU</th><th>Pick order</th><th>Batch</th><th>Expiry</th><th>RSL</th><th>Packs</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  });
  const b = d.breaches, by = Object.values(b.by_cnf).map((e) => `<li>${esc(e.cnf)}: ${e.lines} lines, ${L(e.value)}</li>`).join("");
  const last = b.lines.slice(-15).reverse().map((r) => `<tr><td>${esc(r.date)}</td><td>${esc(r.invoice)}</td><td>${esc(r.cnf)}</td><td>${esc(r.stockist)}</td><td>${esc(r.batch)}</td><td>${r.packs}</td><td>${pct(r.rsl)}</td><td>${L(r.value)}</td></tr>`).join("");
  h += `<div class="card"><h2>Dispatches under 60% RSL, last 12 months (${esc(b.clause)})</h2><p>Total ${L(b.total_value)}, ${b.lines.length} lines.</p><ul>${by}</ul>
    <table><thead><tr><th>Date</th><th>Invoice</th><th>C&amp;F</th><th>Stockist</th><th>Batch</th><th>Packs</th><th>RSL</th><th>Value</th></tr></thead><tbody>${last}</tbody></table><div class="muted">Latest 15 shown.</div></div>`;
  $("st_out").innerHTML = h;
}

$("st_go").addEventListener("click", async () => {
  $("st_out").textContent = "Working…";
  try {
    const r = await fetch("/api/expiry-watch?viewer=" + encodeURIComponent($("st_viewer").value));
    if (!r.ok) throw new Error((await r.json()).error || r.statusText);
    render(await r.json());
  } catch (e) { $("st_out").innerHTML = `<div class="err">${esc(e.message)}</div>`; }
});
})();
