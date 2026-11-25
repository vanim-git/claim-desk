(() => {
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const L = (v) => "₹" + (v / 1e5).toFixed(1) + " L";
const pct = (v, n = 2) => (v * 100).toFixed(n) + "%";

function render(d) {
  const t = d.sku_table;
  const rows = t.rows.map((r) => `<tr><td>${esc(r.sku)} ${esc(r.product)}</td><td>${esc(r.shelf_months)}</td><td>${L(r.sales)}</td><td>${L(r.scheme_stock_value)}</td><td>${L(r.claims)}</td><td>${pct(r.claim_rate)}</td><td>${L(r.extra_cost)}</td></tr>`).join("");
  let h = `<div class="card"><h2>Scheme SKUs: stock sold on scheme vs expiry claims (last four quarters)</h2>
    <p>Claim rate on SKUs that never carry a scheme: <b>${pct(t.baseline_rate)}</b>. Extra cost of schemes: <b>${L(t.total_extra_per_year)}</b> a year. ${esc(t.note)}</p>
    <table><thead><tr><th>SKU</th><th>Shelf life (months)</th><th>Sales</th><th>Scheme stock at PTS</th><th>Expiry claims</th><th>Claim rate</th><th>Extra cost</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  const foc = d.foc.map((q) => `<tr><td>${esc(q.quarter)}</td><td>${L(q.sales)}</td><td>${L(q.free_value)}</td><td>${pct(q.share)}</td><td>${q.over_cap ? "over the 3% cap: CFO approval (§4.4)" : "within"}</td></tr>`).join("");
  h += `<div class="card"><h2>Free goods vs the 3% cap (§4.4)</h2><table><thead><tr><th>Quarter</th><th>Primary sales</th><th>Free goods at PTS</th><th>Share</th><th>Cap</th></tr></thead><tbody>${foc}</tbody></table></div>`;
  const w = d.warnings.slice(0, 60).map((x) => `<tr><td>${esc(x.cnf)}</td><td>${esc(x.stockist)} ${esc(x.stockist_name)}</td><td>${esc(x.sku)}</td><td>${x.est_stock_months == null ? "n/a" : x.est_stock_months.toFixed(1)}</td><td>${x.bought_90d}</td><td>${esc(x.warnings.join("; "))}</td></tr>`).join("");
  h += `<div class="card"><h2>Stockists to check before the next scheme (as of ${esc(d.as_of)})</h2>
    <p>${d.warnings.length} stockist-SKU pairs with estimated stock above 2.5 months (§4.5). By C&amp;F: ${esc(JSON.stringify(d.by_cnf))}. Showing 60.</p>
    <table><thead><tr><th>C&amp;F</th><th>Stockist</th><th>SKU</th><th>Est. months of stock</th><th>Bought, last 90 days</th><th>Warning</th></tr></thead><tbody>${w}</tbody></table>
    <div class="muted">${d.notes.map(esc).join(" · ")}</div></div>`;
  $("sc_out").innerHTML = h;
}

$("sc_go").addEventListener("click", async () => {
  $("sc_out").textContent = "Working…";
  try {
    const r = await fetch("/api/scheme-desk");
    if (!r.ok) throw new Error((await r.json()).error || r.statusText);
    render(await r.json());
  } catch (e) { $("sc_out").innerHTML = `<div class="err">${esc(e.message)}</div>`; }
});
})();
