const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const LABEL = { APPROVE: "Approve", REJECT: "Reject", NEEDS_PERSON: "Needs a person", ALREADY_LOGGED: "Already logged" };
let last = null;

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const j = await r.json().catch(() => ({ error: "Unreadable response (" + r.status + ")" }));
  if (!r.ok) throw new Error(j.error || j.detail?.[0]?.msg || "Error " + r.status);
  return j;
}

// tabs
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("on", x === t));
  document.querySelectorAll(".pane").forEach((p) => (p.hidden = p.id !== t.dataset.tab));
}));

async function run(payload) {
  $("out").innerHTML = '<div class="card">Checking…</div>';
  try { last = await api("/api/claim", payload); render(last); }
  catch (e) { $("out").innerHTML = `<div class="card err">${esc(e.message)}</div>`; }
}

$("t-reg").addEventListener("submit", (e) => { e.preventDefault(); run({ claim_no: $("claim_no").value.trim() }); });
document.querySelectorAll("[data-claim]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); $("claim_no").value = a.dataset.claim; run({ claim_no: a.dataset.claim }); }));
$("t-new").addEventListener("submit", (e) => {
  e.preventDefault();
  run({ claim: { stockist_code: $("n_stockist").value.trim(), batch_no: $("n_batch").value.trim(), qty: Number($("n_qty").value),
    claim_type: $("n_type").value || null, invoice_ref: $("n_inv").value.trim() || null, claim_date: $("n_date").value || null, am_approval: $("n_appr").value.trim() || null, resubmission_of: $("n_resub").value.trim() || null } });
});
$("t-mail").addEventListener("submit", (e) => {
  e.preventDefault();
  if ($("m_sample").value) return run({ email_id: $("m_sample").value });
  run({ email_text: $("m_text").value, sender: $("m_sender").value.trim() || null, received: $("m_recv").value || null });
});
$("m_sample").addEventListener("change", () => { if ($("m_sample").value) $("m_text").value = ""; });
for (let i = 1; i <= 30; i++) { const id = "EML-" + String(i).padStart(3, "0"); $("m_sample").add(new Option(id, id)); }

function evText(ev) { return (ev || []).map((x) => `${x.file}${x.row ? " row " + x.row : ""}${x.claim_no ? " " + x.claim_no : ""}`).join("; "); }

function lineHtml(r, i) {
  const l = r.line || {};
  const rows = (r.checks || []).map((c) => `<tr><td>${esc(c.rule)}</td><td>${esc(c.clause)}</td><td class="s-${c.status}">${esc(c.status)}</td><td>${esc(c.detail)}<div class="ev">${esc(evText(c.evidence))}</div></td></tr>`).join("");
  const flags = (r.flags || []).map((f) => `<span class="flag">${esc(f)}</span>`).join("");
  const notes = [...(r.notes || []), ...(r.hints || [])].map((n) => `<li>${esc(n)}</li>`).join("");
  const credit = r.recommended_credit_inr != null ? `<p>Recommended credit: <b>₹${Number(r.recommended_credit_inr).toLocaleString("en-IN")}</b></p>` : "";
  const allow = r.allowable_qty != null && r.outcome !== "APPROVE" ? `<p>Allowable quantity: <b>${esc(r.allowable_qty)}</b> packs</p>` : "";
  const linked = r.linked_claim ? `<p>Already logged as <b>${esc(r.linked_claim.claim_no)}</b> (${esc(r.linked_claim.status)}${r.linked_claim.cn_no ? ", " + esc(r.linked_claim.cn_no) : ""}). Do not log it again.</p>` : "";
  return `<div class="card" data-i="${i}"><span class="badge ${r.outcome}">${LABEL[r.outcome] || r.outcome}</span>
    <span class="muted"> line ${r.line_no}: ${esc(l.stockist)} · batch ${esc(l.batch)} · qty ${esc(l.qty)} · ${esc(l.claim_type)}</span>
    <div>${flags}</div>${linked}${credit}${allow}
    ${rows ? `<table class="rules"><thead><tr><th>Rule</th><th>Clause</th><th>Result</th><th>Detail and evidence</th></tr></thead><tbody>${rows}</tbody></table>` : ""}
    ${notes ? `<ul>${notes}</ul>` : ""}
    <div class="act"><button data-a="accept">Accept recommendation</button><input placeholder="Reason (needed to override)"><button class="ghost" data-a="override">Override</button><span class="done"></span></div></div>`;
}

function render(d) {
  let h = "";
  if (d.error) h += `<div class="card err">${esc(d.error)}</div>`;
  if (d.status_reply) {
    const s = d.status_reply;
    h += `<div class="card"><span class="badge status">Status query</span><pre>${esc(JSON.stringify(s, null, 2))}</pre>${s.found ? `<p class="muted">Draft reply for your team to send (the tool never sends):</p><pre>Dear stockist, your claim ${esc(s.claim_no)} is ${esc(s.status)}${s.credit_note ? ", credit note " + esc(s.credit_note) : ""}. Lodged ${esc(s.lodged)}.</pre>` : ""}</div>`;
  } else if (d.forward_to) {
    h += `<div class="card"><span class="badge forward">Forward</span><p>Not a claim. Forward to <b>${esc(d.forward_to)}</b>.</p></div>`;
  }
  if (d.explanation) h += `<div class="card"><b>Summary.</b> ${esc(d.explanation)}<div class="muted">Read by: ${esc(d.parsed_by || "n/a")} · model calls: ${esc(d.model_calls)}</div></div>`;
  (d.results || []).forEach((r, i) => (h += lineHtml(r, i)));
  $("out").innerHTML = h || '<div class="card">Nothing to show.</div>';
}

$("out").addEventListener("click", async (e) => {
  const b = e.target.closest("button[data-a]"); if (!b) return;
  const card = b.closest(".card"), r = last.results[card.dataset.i], reason = card.querySelector("input").value.trim();
  try {
    await api("/api/decision", { claim_ref: r.line.claim_no || last.audit?.email_id || "new-claim", line_no: r.line_no, recommended: r.outcome, action: b.dataset.a, reason });
    card.querySelector(".done").textContent = b.dataset.a === "accept" ? "Accepted, logged." : "Override logged.";
    card.querySelectorAll("button").forEach((x) => (x.disabled = true));
  } catch (err) { card.querySelector(".done").textContent = err.message; }
});

$("audit").addEventListener("click", async () => {
  $("audit_out").textContent = "Running…";
  try {
    const a = await api("/api/audit");
    $("audit_out").innerHTML = `<pre>${esc(JSON.stringify({ ...a, sample: undefined }, null, 2))}</pre>`;
  } catch (e) { $("audit_out").innerHTML = `<div class="err">${esc(e.message)}</div>`; }
});

api("/api/health").then((h) => ($("health").textContent = h.model_key_set ? "model key set" : "no model key: rules only")).catch(() => ($("health").textContent = "API not reachable"));
