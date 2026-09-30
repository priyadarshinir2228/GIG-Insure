// GigInsure admin dashboard: polls the platform API and updates every panel in place.
const $ = (s, el = document) => el.querySelector(s);
const inr = (v, d = 0) => v == null ? "–" : "₹" + Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
const f = (v, d = 3) => v == null ? "–" : Number(v).toFixed(d);
const pct = (v, d = 1) => v == null ? "–" : (v * 100).toFixed(d) + "%";
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const tokenStore = { get: () => { try { return localStorage.getItem("gi_admin_token") || ""; } catch { return ""; } },
                     set: v => { try { localStorage.setItem("gi_admin_token", v); } catch {} } };
let adminToken = tokenStore.get();
// GETs are public (read-only dashboards); POSTs are admin actions and carry the token when the server is locked.
async function api(p, body) {
  if (body === undefined) return fetch(p).then(r => r.json());
  const send = () => fetch(p, { method: "POST", headers: { "Content-Type": "application/json", "X-Admin-Token": adminToken }, body: JSON.stringify(body) });
  let r = await send();
  if (r.status === 401) {
    const t = window.prompt("This action needs the admin token (set as GIGINSURE_ADMIN_TOKEN on the server):");
    if (!t) return { error: "admin token required" };
    adminToken = t.trim(); tokenStore.set(adminToken);
    r = await send();
    if (r.status === 401) { alert("Wrong admin token."); adminToken = ""; tokenStore.set(""); return { error: "admin token required" }; }
  }
  return r.json();
}

const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const COL = { accent: () => css("--accent"), teal: () => css("--accent-2"), bad: () => css("--bad"), warn: () => css("--warn"), good: () => css("--good"), muted: () => css("--muted"), line: () => css("--line"), ink: () => css("--ink") };
Chart.defaults.font.family = "system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.animation = false;
const charts = {};
function chart(id, cfg) {
  Chart.defaults.color = COL.muted(); Chart.defaults.borderColor = COL.line();
  if (charts[id]) { charts[id].data = cfg.data; if (cfg.options) charts[id].options = cfg.options; charts[id].update("none"); return charts[id]; }
  cfg.options = Object.assign({ responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { boxWidth: 10 } } } }, cfg.options || {});
  return charts[id] = new Chart($("#" + id), cfg);
}

// ---------------------------------------------------------------- tabs
document.querySelectorAll("button.tab").forEach(b => b.onclick = () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  document.querySelectorAll(".tabpane").forEach(x => x.classList.remove("active"));
  b.classList.add("active"); $("#tab-" + b.dataset.tab).classList.add("active");
  if (b.dataset.tab === "ml") loadML(true);
});

// ---------------------------------------------------------------- controls
let zonesLoaded = false;
async function initZones() {
  const zs = await api("/api/zones");
  $("#sim-zones").innerHTML = zs.map(z => `<option value="${z.id}" ${z.id === 0 ? "selected" : ""}>${esc(z.name)} (flood ${z.flood_score})</option>`).join("");
  zonesLoaded = true;
}
$("#sim-go").onclick = async () => {
  const ids = [...$("#sim-zones").selectedOptions].map(o => +o.value);
  if (!ids.length) return alert("Pick at least one zone");
  await api("/api/admin/simulate", { zone_ids: ids, scenario: $("#sim-kind").value, hours: +$("#sim-hours").value, fraud_ring: $("#sim-fraud").checked });
  refresh();
};
document.querySelectorAll("[data-ff]").forEach(b => b.onclick = async () => { b.disabled = true; await api("/api/admin/fast_forward", { hours: +b.dataset.ff }); b.disabled = false; refresh(); });
$("#speed").oninput = e => $("#speed-v").textContent = e.target.value + "s";
$("#speed").onchange = e => api("/api/admin/speed", { tick_seconds: +e.target.value });
$("#retrain").onclick = async () => { await api("/api/admin/retrain", { fast: true }); refresh(); };
window.review = async (id, approve) => { await api(`/api/admin/review/${id}`, { approve }); refresh(); };
window.replay = async (eid) => { const r = await api(`/api/admin/replay/${eid}`, {}); if (r.error) return; alert(`Replayed ${r.replayed} claims of ${eid}\nDecisions: ${JSON.stringify(r.decisions)}\nLedger: ${r.ledger_before[0]} txns → ${r.ledger_after[0]} txns (unchanged)`); refresh(); };

// ---------------------------------------------------------------- live ops
const DEC = { PAID: "good", PAID_AFTER_REVIEW: "good", HOLD_REVIEW: "warn", REJECTED_FRAUD: "bad", REJECT_DUPLICATE: "bad", REJECT_ZERO: "", MONITORING: "info" };
const seenClaims = new Set();
let lastGenerated = null, firstLoad = true;

function kpi(l, v, s = "") { return `<div class="kpi"><div class="l">${l}</div><div class="v">${v}</div><div class="s">${s}</div></div>`; }
function meter(label, v, thr, max, unit) {
  const w = Math.min(100, (v / max) * 100), t = (thr / max) * 100;
  return `<div class="meter"><span>${label}</span><div class="bar"><i class="${v > thr ? "over" : ""}" style="width:${w}%"></i><b style="left:${t}%"></b></div><span class="r">${f(v, label === "AQI" ? 0 : 1)}${unit}</span></div>`;
}

function renderSummary(S) {
  const k = S.kpis, c = S.clock, d = k.decisions || {};
  $("#clock").innerHTML = `${esc(c.city)} · policy week <b>${c.week_no}</b> · <b>${c.day} ${String(c.hour).padStart(2, "0")}:00</b> · week-of-year ${c.week_of_year} · weather: ${c.weather}`;
  $("#kpis").innerHTML = [
    kpi("Delivery partners", k.workers, `${k.active_policies} active weekly policies`),
    kpi("Premiums collected", inr(k.premiums), `this week ${inr(k.week_premiums)} · avg ${inr(k.avg_premium, 2)}/wk`),
    kpi("Payouts (UPI)", inr(k.payouts), `this week ${inr(k.week_payouts)}`),
    kpi("Loss ratio", pct(k.loss_ratio), "payouts ÷ premiums"),
    kpi("Disruption events", k.events_total, `${k.events_open} open now`),
    kpi("Claims auto-initiated", k.claims_total, `${(d.PAID || 0) + (d.PAID_AFTER_REVIEW || 0)} paid · ${d.HOLD_REVIEW || 0} held · ${k.duplicates_blocked} dup blocked`),
    kpi("Decision latency", k.decision_ms_p95 == null ? "–" : f(k.decision_ms_p95, 1) + " ms", "p95 trigger→fraud→payout"),
  ].join("");
  $("#lr-note").textContent = `loss ratio ${pct(k.loss_ratio)}`;

  $("#zones").innerHTML = S.zones.map(z => {
    const hit = z.fired && z.fired.length;
    return `<div class="zone ${hit ? "hit" : ""}"><div class="zn"><span>${esc(z.name)}</span>${hit ? `<span class="chip bad">${z.fired.join(", ")}</span>` : `<span class="chip good">normal</span>`}</div>
      <div class="meta">flood ${z.flood_score} · ${z.workers} workers · LR ${pct(z.loss_ratio, 0)}${z.scenario ? ` · <b>sim: ${z.scenario}</b>` : ""}${z.event_id ? ` · ${z.event_id} (${z.event_hours}h)` : ""}</div>
      ${z.rain == null ? "" : meter("Rain", z.rain, 50, 100, "mm") + meter("AQI", z.aqi, 400, 500, "") + meter("Temp", z.temp, 42, 50, "°")}
      ${z.curfew ? `<div class="chip bad">curfew in force</div>` : ""}</div>`;
  }).join("");

  const m = S.models;
  $("#models").innerHTML = `Pricing GBDT <b>v${m.pricing_version}</b> (MAE ₹${f(m.pricing_mae, 2)})<br>Fraud IsolationForest <b>v${m.fraud_version}</b><br>
    <span class="muted">results: ${esc(m.results_generated_at)}${m.fast_mode ? " (fast mode)" : ""} · loaded ${esc(m.loaded_at)}</span><br>
    ${m.pipeline_running ? `<span class="chip warn">retraining pipeline running…</span>` : ""}`;
  $("#retrain").disabled = m.pipeline_running;
  if (lastGenerated && lastGenerated !== m.results_generated_at) loadML(true);
  lastGenerated = m.results_generated_at;

  const s = S.series;
  chart("c-money", { type: "line", data: { labels: s.map(x => x.label), datasets: [
    { label: "Premiums", data: s.map(x => x.premiums), borderColor: COL.accent(), pointRadius: 0, borderWidth: 2 },
    { label: "Payouts", data: s.map(x => x.payouts), borderColor: COL.bad(), backgroundColor: COL.bad() + "22", fill: true, pointRadius: 0, borderWidth: 2 }] },
    options: { scales: { x: { ticks: { maxTicksLimit: 8 } } } } });
  chart("c-env", { type: "line", data: { labels: s.map(x => x.label), datasets: [
    { label: "max rain mm/hr (thr 50)", data: s.map(x => x.max_rain), borderColor: COL.accent(), pointRadius: 0, borderWidth: 1.5, yAxisID: "y" },
    { label: "max temp °C (thr 42)", data: s.map(x => x.max_temp), borderColor: COL.warn(), pointRadius: 0, borderWidth: 1.5, yAxisID: "y" },
    { label: "max AQI (thr 400)", data: s.map(x => x.max_aqi), borderColor: COL.muted(), pointRadius: 0, borderWidth: 1.5, yAxisID: "y2" },
    { label: "zones disrupted", data: s.map(x => x.zones_disrupted), type: "bar", backgroundColor: COL.bad() + "55", yAxisID: "y3" }] },
    options: { scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { position: "left", suggestedMax: 60 }, y2: { position: "right", suggestedMax: 450, grid: { display: false } }, y3: { display: false, max: 10 } } } });

  $("#claims tbody").innerHTML = S.claims.map(cl => {
    const isNew = !firstLoad && !seenClaims.has(cl.claim_id + cl.decision); seenClaims.add(cl.claim_id + cl.decision);
    const sc = cl.fraud_score, thr = cl.threshold, w = sc == null ? 0 : Math.min(100, sc / 0.8 * 100);
    return `<tr class="${isNew ? "new" : ""}"><td>${cl.claim_id}</td><td>${esc(cl.worker_id)}</td><td>${esc(cl.zone)}</td><td class="muted">${esc(cl.event_id)}</td>
      <td class="r">${f(cl.lost_hours, 1)}</td>
      <td><div class="score"><div class="bar"><i class="${sc >= thr ? "over" : ""}" style="width:${w}%"></i><b style="left:${thr / 0.8 * 100}%"></b></div>${f(sc, 3)}</div></td>
      <td class="small">${esc(cl.reasons) || '<span class="muted">clean</span>'}${cl.true_kind && cl.true_kind !== "genuine" ? ` <span class="chip">sim: ${cl.true_kind}</span>` : ""}</td>
      <td><span class="chip ${DEC[cl.decision] || ""}">${cl.decision}</span></td><td class="r">${inr(cl.amount, 2)}</td><td class="muted">${esc(cl.txn_id || "")}</td></tr>`;
  }).join("") || `<tr><td colspan="10" class="muted">No claims yet — trigger a disruption with the simulator.</td></tr>`;

  const lf = S.live_fraud;
  $("#livefraud").innerHTML = [["claims scored", lf.scored], ["injected fraud", lf.injected], ["caught", lf.caught], ["live recall", pct(lf.live_recall)],
    ["false alarms", lf.false_alarms], ["live FPR", pct(lf.live_fpr)]].map(([l, v]) => `<div class="stat"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
  $("#held").innerHTML = S.held.length ? S.held.map(h => `<div class="list"><div class="it"><span>#${h.claim_id} ${esc(h.worker_id)} · ${esc(h.zone)} · score ${f(h.fraud_score)}<br><span class="muted">${esc(h.reasons) || "multivariate anomaly"}</span></span>
      <span><button class="btn sm" onclick="review(${h.claim_id}, true)">Approve ${inr(h.amount)}</button> <button class="btn sm" onclick="review(${h.claim_id}, false)">Reject</button></span></div></div>`).join("")
    : `<span class="muted">No claims awaiting review.</span>`;
  const ld = S.live_drift || {};
  $("#livedrift").innerHTML = Object.keys(ld).length ? Object.entries(ld).map(([k, v]) => `<div class="stat"><div class="v">${f(v.psi)}</div><div class="l">${k} · <span class="chip ${v.status === "significant" ? "bad" : v.status === "moderate" ? "warn" : "good"}">${v.status}</span></div></div>`).join("")
    : `<span class="muted">collecting readings (needs ~12 simulated hours)…</span>`;

  $("#events tbody").innerHTML = S.events.map(e => `<tr><td>${e.event_id}</td><td>${esc(e.zone)}</td><td>${esc(e.triggers)}</td><td class="r">${e.hours}</td><td class="r">${f(e.severity, 2)}</td>
    <td class="r">${e.claims}</td><td class="r">${inr(e.paid)}</td><td><span class="chip ${e.status === "OPEN" ? "bad" : ""}">${e.status}</span></td>
    <td>${e.status === "CLOSED" ? `<button class="btn sm" onclick="replay('${e.event_id}')">Replay</button>` : ""}</td></tr>`).join("") || `<tr><td colspan="9" class="muted">No events yet.</td></tr>`;

  chart("c-lr", { type: "bar", data: { labels: S.zones.map(z => z.name), datasets: [{ label: "loss ratio", data: S.zones.map(z => z.loss_ratio), backgroundColor: S.zones.map(z => z.loss_ratio > 1 ? COL.bad() : z.loss_ratio > 0.6 ? COL.warn() : COL.accent()) }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: v => (v * 100) + "%" } } } } });

  const term = $("#log"), atBottom = term.scrollHeight - term.scrollTop - term.clientHeight < 30;
  term.innerHTML = S.log.map(l => `<span class="dim">${l.t.slice(11)} ${esc(l.sim).padEnd(14)}</span> <span class="t-${l.tag}">[${l.tag}]</span> ${esc(l.msg)}`).join("\n");
  if (atBottom || firstLoad) term.scrollTop = term.scrollHeight;
  firstLoad = false;
}

function renderForecast(F) {
  $("#fc-note").textContent = `week-of-year ${F.week_of_year} · expected claims ${inr(F.total_expected_claims)} vs premium ${inr(F.total_expected_premium)} · projected LR ${pct(F.total_expected_premium ? F.total_expected_claims / F.total_expected_premium : 0)}`;
  chart("c-forecast", { type: "bar", data: { labels: F.zones.map(z => z.name), datasets: [
    { label: "expected claims ₹ (ML)", data: F.zones.map(z => z.expected_claims_inr), backgroundColor: COL.bad() + "cc" },
    { label: "expected premium ₹", data: F.zones.map(z => z.expected_premium_inr), backgroundColor: COL.accent() + "cc" }] } });
  $("#forecast tbody").innerHTML = F.zones.map(z => `<tr><td>${esc(z.name)}</td><td>${z.flood_score}</td><td class="r">${z.workers}</td>
    <td class="r">${inr(z.premiums.food, 2)}</td><td class="r">${inr(z.premiums.qcom, 2)}</td><td class="r">${inr(z.premiums.ecom, 2)}</td>
    <td class="r">${f(z.expected_hours, 2)}</td><td class="r">${inr(z.expected_claims_inr)}</td><td><span class="chip ${z.risk === "high" ? "bad" : z.risk === "medium" ? "warn" : "good"}">${z.risk}</span></td></tr>`).join("");
}

// ---------------------------------------------------------------- ML tab
let mlLoadedFor = null;
async function loadML(force) {
  const R = await api("/api/admin/ml");
  if (!force && mlLoadedFor === R.generated_at) return;
  mlLoadedFor = R.generated_at;
  const ch = R.pricing.gbdt_champion.test, lin = R.pricing.ridge_linear.test;
  const gatePass = R.gate.filter(g => g.result === "PASS").length;
  $("#ml-banner").innerHTML = [["pipeline run", esc(R.generated_at) + (R.fast_mode ? " (fast)" : "")], ["dataset", `${R.data.rows.toLocaleString()} rows · ${R.data.weeks} wks × ${R.data.zones} zones`],
    ["champion", `${R.best_family.toUpperCase()} lr ${R.best_params.learning_rate} · depth ${R.best_params.max_depth} · ${R.best_params.n_estimators} trees`],
    ["test MAE / R²", `₹${f(ch.mae, 3)} / ${f(ch.r2, 3)}`], ["vs linear", `−${f((1 - ch.mae / lin.mae) * 100, 1)}% MAE`],
    ["fraud ROC-AUC", f(R.fraud.iforest.roc_auc)], ["gate", `${gatePass}/${R.gate.length} PASS`], ["tracked runs", `${R.n_runs} (${R.tracking_backend})`], ["runtime", f(R.runtime_s, 0) + " s"]]
    .map(([l, v]) => `<div class="stat"><div class="l">${l}</div><div class="v">${v}</div></div>`).join("");

  $("#gate tbody").innerHTML = R.gate.map(g => `<tr><td>${esc(g.check)}</td><td>${esc(g.threshold)}</td><td class="r">${f(g.measured)}</td><td><span class="chip ${g.result === "PASS" ? "good" : "bad"}">${g.result}</span></td></tr>`).join("");
  const regRows = [];
  for (const [name, vs] of Object.entries(R.registry)) for (const v of vs) regRows.push(`<tr><td>${esc(name)}</td><td>v${v.version}</td><td><span class="chip ${v.stage === "Production" ? "good" : v.stage === "Archived" ? "" : "info"}">${v.stage}</span></td>
    <td>${v.metrics.mae != null ? "MAE ₹" + f(v.metrics.mae) : "ROC-AUC " + f(v.metrics.roc_auc)}</td><td class="muted">${esc(v.created)}</td></tr>`);
  $("#registry tbody").innerHTML = regRows.join("");
  const p = R.performance;
  $("#perf").innerHTML = [["quote p50", f(p.price_latency_ms_p50, 2) + " ms"], ["quote p95", f(p.price_latency_ms_p95, 2) + " ms"], ["batch pricing", Math.round(p.price_batch_rows_per_s).toLocaleString() + "/s"],
    ["fraud scoring", Math.round(p.fraud_score_rows_per_s).toLocaleString() + "/s"], ["triggers", f(p.trigger_hours_per_s / 1e6, 1) + " M zone-h/s"], ["claim path p95", f(p.e2e_claim_ms_p95, 2) + " ms"]]
    .map(([l, v]) => `<div class="stat"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");

  const names = Object.keys(R.pricing);
  chart("c-models", { type: "bar", data: { labels: names, datasets: [
    { label: "CV MAE (weeks 0–103)", data: names.map(n => R.pricing[n].cv.cv_mae_mean), backgroundColor: COL.muted() + "aa" },
    { label: "Test MAE (weeks 104–129)", data: names.map(n => R.pricing[n].test.mae), backgroundColor: names.map(n => n === "gbdt_champion" ? COL.good() : COL.accent()) }] } });
  $("#pricing tbody").innerHTML = names.map(n => { const t = R.pricing[n].test, c = R.pricing[n].cv; return `<tr><td>${n === "gbdt_champion" ? "<b>" + n + "</b>" : n}</td><td class="r">${f(c.cv_mae_mean, 2)} ± ${f(c.cv_mae_std, 2)}</td>
    <td class="r">${f(t.mae)}</td><td class="r">${f(t.rmse)}</td><td class="r">${f(t.r2)}</td><td class="r">${f(t.mape, 1)}</td><td class="r">${f(t.within_2rs, 1)}</td></tr>`; }).join("");
  chart("c-scatter", { type: "scatter", data: { datasets: [
    { label: "test weeks", data: R.test_pred.y.map((y, i) => ({ x: y, y: R.test_pred.p[i] })), backgroundColor: COL.accent() + "66", pointRadius: 2 },
    { label: "perfect", type: "line", data: [{ x: 15, y: 15 }, { x: 40, y: 40 }], borderColor: COL.bad(), borderDash: [4, 4], pointRadius: 0 }] },
    options: { scales: { x: { title: { display: true, text: "actual ₹" }, min: 14, max: 41 }, y: { title: { display: true, text: "predicted ₹" }, min: 14, max: 41 } } } });
  $("#persona tbody").innerHTML = Object.entries(R.persona_metrics).map(([k, m]) => `<tr><td>${k}</td><td class="r">${f(m.mae)}</td><td class="r">${f(m.rmse)}</td><td class="r">${f(m.r2)}</td><td class="r">${f(m.within_2rs, 1)}</td></tr>`).join("");
  chart("c-tuning", { type: "bar", data: { labels: R.tuning.map(t => t.run.replace("gbdt_", "")), datasets: [{ label: "CV MAE ₹", data: R.tuning.map(t => t.cv_mae_mean), backgroundColor: R.tuning.map((t, i) => i === 0 ? COL.good() : COL.accent() + "99") }] },
    options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { min: Math.floor(Math.min(...R.tuning.map(t => t.cv_mae_mean)) * 10) / 10 - 0.1 } } } });
  chart("c-imp", { type: "bar", data: { labels: R.importance.map(x => x[0]), datasets: [{ label: "MAE increase when shuffled (₹)", data: R.importance.map(x => x[1]), backgroundColor: COL.teal() }] },
    options: { indexAxis: "y", plugins: { legend: { display: false } } } });

  const fr = R.fraud;
  chart("c-roc", { type: "line", data: { datasets: [{ label: `Isolation Forest (AUC ${f(fr.iforest.roc_auc)})`, data: fr.roc[0].map((x, i) => ({ x, y: fr.roc[1][i] })), borderColor: COL.accent(), pointRadius: 0 },
    { label: "chance", data: [{ x: 0, y: 0 }, { x: 1, y: 1 }], borderColor: COL.muted(), borderDash: [4, 4], pointRadius: 0 }] },
    options: { parsing: false, scales: { x: { type: "linear", min: 0, max: 1, title: { display: true, text: "FPR" } }, y: { min: 0, max: 1, title: { display: true, text: "TPR" } } } } });
  chart("c-pr", { type: "line", data: { datasets: [{ label: `PR (AUC ${f(fr.iforest.pr_auc)})`, data: fr.pr[0].map((x, i) => ({ x, y: fr.pr[1][i] })), borderColor: COL.teal(), pointRadius: 0 }] },
    options: { parsing: false, scales: { x: { type: "linear", min: 0, max: 1, title: { display: true, text: "recall" } }, y: { min: 0, max: 1, title: { display: true, text: "precision" } } } } });
  const it = fr.iforest;
  $("#cm").innerHTML = `<div class="cm"><div class="h"></div><div class="h">pred genuine</div><div class="h">pred fraud</div>
    <div class="h">genuine</div><div class="tn">TN ${it.tn}</div><div class="fp">FP ${it.fp}</div><div class="h">fraud</div><div class="fn">FN ${it.fn}</div><div class="tp">TP ${it.tp}</div></div>
    <div class="small">threshold ${f(fr.threshold, 4)} (2% FPR budget) · test ${fr.n_test.toLocaleString()} claims, ${fr.n_fraud_test} fraud</div>
    <div class="list">${Object.entries(fr.by_kind).map(([k, v]) => `<div class="it"><span>${k === "spoof" ? "GPS spoofing" : k === "presence" ? "Fake presence" : "Claim farming"} (n=${v.n})</span><b>${pct(v.recall)}</b></div>`).join("")}</div>`;
  $("#fraudtbl tbody").innerHTML = [["Isolation Forest (" + fr.selected + ")", fr.iforest], ["Rule baseline (5 hard rules)", fr.rules], ["Local Outlier Factor", fr.lof]]
    .map(([n, m]) => `<tr><td>${n}</td><td class="r">${f(m.precision)}</td><td class="r">${f(m.recall)}</td><td class="r">${f(m.f1)}</td><td class="r">${f(m.roc_auc)}</td><td class="r">${f(m.pr_auc)}</td><td class="r">${f(m.fpr)}</td></tr>`).join("");

  const tn = Object.keys(R.triggers);
  chart("c-trig", { type: "bar", data: { labels: tn.map(n => `${n} (${R.triggers[n].events} h)`), datasets: ["precision", "recall", "f1"].map((k, i) => ({ label: k, data: tn.map(n => R.triggers[n][k]), backgroundColor: [COL.accent(), COL.teal(), COL.good()][i] })) },
    options: { scales: { y: { min: 0, max: 1 } } } });
  const cc = R.concept, wk = cc.weekly;
  chart("c-concept", { type: "line", data: { labels: wk.map(w => w.week), datasets: [
    { label: "static model (never retrained)", data: wk.map(w => w.mae_static), borderColor: COL.muted(), pointRadius: 0, borderWidth: 1.5 },
    { label: "monitored + retrained", data: wk.map(w => w.mae_adaptive), borderColor: COL.accent(), pointRadius: 0, borderWidth: 2 },
    { label: `alarm threshold ₹${f(cc.threshold, 2)}`, data: wk.map(() => cc.threshold), borderColor: COL.bad(), borderDash: [5, 4], pointRadius: 0, borderWidth: 1 }] },
    options: { scales: { x: { title: { display: true, text: "week" }, ticks: { maxTicksLimit: 12 } }, y: { title: { display: true, text: "weekly MAE ₹" } } } } });
  $("#concept-note").innerHTML = `data shift from week ${cc.data_start}, concept shift from week ${cc.concept_start}. ` + (cc.events.map(e => `Alarm week ${e.week}: challenger ₹${f(e.holdout_new, 2)} vs serving ₹${f(e.holdout_old, 2)} → gate <b>${e.gate ? "PASS" : "FAIL"}</b>${e.version ? ` (v${e.version} promoted)` : ""}`).join("; ") || "no alarm")
    + `. Mean MAE weeks 130–155: ₹${f(cc.adaptive_mae_weeks_130_155, 2)} monitored vs ₹${f(cc.static_mae_weeks_130_155, 2)} static.`;
  const win = Object.keys(R.data_drift), feats = R.data_drift[win[0]].map(r => r.feature);
  $("#psi").innerHTML = `<thead><tr><th>Feature</th>${win.map(w => `<th class="r">${esc(w)}</th>`).join("")}</tr></thead><tbody>` + feats.map(ft => `<tr><td>${ft}</td>${win.map(w => { const r = R.data_drift[w].find(x => x.feature === ft); return `<td class="r ${r.drifted ? "psi-yes" : "psi-no"}">${f(r.psi)} ${r.drifted ? "DRIFT" : ""}</td>`; }).join("")}</tr>`).join("") + "</tbody>";
}

// ---------------------------------------------------------------- loop
async function refresh() {
  try { renderSummary(await api("/api/admin/summary")); } catch (e) { console.error(e); }
}
let fcTick = 0;
async function loop() {
  if (!zonesLoaded) await initZones();
  await refresh();
  if (fcTick++ % 5 === 0) api("/api/admin/forecast").then(renderForecast).catch(console.error);
  setTimeout(loop, 2000);
}
loop();
