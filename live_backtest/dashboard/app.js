// Meridian desk. Plain JS, no build step. Everything shown is read from the
// backend's /api routes; the only writes are broker links, the execution
// mode and the scheduler start/stop (each behind an explicit confirm).
"use strict";

const REFRESH_MS = 30000;
const $ = (id) => document.getElementById(id);
const state = { tab: "desk", brokers: null, history: [], historyAt: -1 };

// ------------------------------------------------------------ helpers
async function api(path, options = {}) {
  const init = { ...options };
  if (init.body && typeof init.body !== "string") {
    init.body = JSON.stringify(init.body);
    init.headers = { "Content-Type": "application/json" };
  }
  const resp = await fetch(path, init);
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(body.detail || `${path} → ${resp.status}`);
  return body;
}
const safe = (promise) => promise.catch((error) => ({ __error: error.message }));

function n(value) { const x = Number(value); return value === null || value === undefined || value === "" || !Number.isFinite(x) ? null : x; }
function money(value, digits = 2) {
  const x = n(value); if (x === null) return "--";
  return x.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: digits, maximumFractionDigits: digits });
}
function signed(value, digits = 2) { const x = n(value); if (x === null) return "--"; return `${x > 0 ? "+" : x < 0 ? "−" : ""}${money(Math.abs(x), digits)}`; }
function pct(value, digits = 2, ratio = true) { const x = n(value); if (x === null) return "--"; const v = ratio ? x * 100 : x; return `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`; }
function fixed(value, digits = 2) { const x = n(value); return x === null ? "--" : x.toFixed(digits); }
function cls(value) { const x = n(value); return x === null || x === 0 ? "" : x > 0 ? "up" : "down"; }
function ago(seconds) {
  const x = n(seconds); if (x === null) return "--";
  if (x < 90) return `${Math.round(x)}s`; if (x < 5400) return `${Math.round(x / 60)}m`;
  if (x < 172800) return `${(x / 3600).toFixed(1)}h`; return `${(x / 86400).toFixed(1)}d`;
}
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([key, value]) => {
    if (value === null || value === undefined || value === false) return;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  });
  children.flat(Infinity).forEach((child) => node.append(child instanceof Node ? child : document.createTextNode(String(child ?? ""))));
  return node;
}
function kv(rows) {
  return el("dl", { class: "kv" }, rows.filter(Boolean).map(([k, v, c]) => [el("dt", {}, k), el("dd", { class: c || "" }, v)]));
}
function table(head, rows, empty = "nothing yet") {
  if (!rows.length) return el("div", { class: "empty" }, empty);
  return el("table", {}, el("thead", {}, el("tr", {}, head.map(([label, right]) => el("th", { class: right ? "r" : "" }, label)))),
    el("tbody", {}, rows.map((cells) => el("tr", {}, cells.map(([value, c]) => el("td", { class: c || "" }, value))))));
}
function put(id, ...nodes) { $(id).replaceChildren(...nodes); }
function meta(id, text) { $(id).textContent = text; }

// ------------------------------------------------------------ console
function log(text, kind = "") {
  const box = $("console-lines");
  box.append(el("div", { class: kind }, text));
  while (box.childElementCount > 80) box.firstChild.remove();
  $("console").scrollTop = $("console").scrollHeight;
}

// ------------------------------------------------------------ tabs
function show(tab) {
  if (!document.querySelector(`.page[data-page="${tab}"]`)) return;
  state.tab = tab;
  document.querySelectorAll(".page").forEach((page) => page.classList.toggle("active", page.dataset.page === tab));
  document.querySelectorAll(".fkey[data-tab]").forEach((key) => key.classList.toggle("active", key.dataset.tab === tab));
  try { localStorage.setItem("meridian-tab", tab); } catch (_) { /* private mode */ }
  refresh();
}

// ------------------------------------------------------------ desk
function renderStrip(status, stats, mode) {
  $("s-nav").textContent = money(stats.current_nav, 0);
  $("s-marked").textContent = money(stats.marked_nav, 0);
  $("s-ret").textContent = pct(stats.total_return_pct, 2, false);
  $("s-ret").className = cls(stats.total_return_pct);
  $("s-breaker").textContent = String(status.circuit_breaker_tier || "--").toUpperCase();
  $("s-kill").textContent = status.kill_switch_engaged ? "ENGAGED" : "CLEAR";
  $("s-kill").className = status.kill_switch_engaged ? "down" : "up";
  $("s-hb").textContent = ago(status.heartbeat_age_seconds);
  $("s-hb").className = status.heartbeat_stale ? "down" : "";
  const label = modeLabel(mode);
  $("s-exec").textContent = label;
  $("s-exec").className = mode.mode === "live" ? "down" : "";
  $("title-mode").textContent = label;
  $("sb-mode").textContent = label;
}

function modeLabel(mode) {
  if (!mode || mode.__error) return "--";
  if (mode.mode === "sim") return "SIM";
  return `${mode.mode.toUpperCase()} · ${(mode.broker_name || mode.broker || "").toUpperCase()}`;
}

function renderAccount(stats, linked, mode) {
  const nodes = [
    el("div", { class: "sub" }, mode.mode === "sim" || mode.mode === "readonly" ? "simulator ledger · cash basis" : `${mode.mode} ledger · ${mode.broker_name}`),
    el("div", { class: "big" }, money(stats.current_nav)),
    kv([
      ["Marked NAV", money(stats.marked_nav)],
      ["Unrealized", signed(stats.unrealized_pnl), cls(stats.unrealized_pnl)],
      ["Total return", pct(stats.total_return_pct, 2, false), cls(stats.total_return_pct)],
      ["Starting capital", money(stats.starting_capital, 0)],
      ["Win rate", n(stats.win_rate) === null ? "--" : `${(stats.win_rate * 100).toFixed(1)}%`],
      ["Sharpe (excess, daily)", stats.insufficient_data ? "n/a" : fixed(stats.sharpe_ratio)],
      ["Max drawdown", pct(stats.max_drawdown), "down"],
      ["Trades (closed)", `${stats.n_trades ?? "--"} (${stats.n_closed_trades ?? "--"})`],
      ["Stale marks", String(stats.stale_marks ?? 0), n(stats.stale_marks) > 100 ? "down" : "dim"],
    ]),
  ];
  if (n(stats.stale_marks) > 100) {
    nodes.push(el("div", { class: "msg err" }, "Many marks use old prices, so Sharpe and drawdown are unreliable until the price cache refreshes (runs every cycle)."));
  }
  if (linked && linked.available) {
    nodes.push(el("div", { class: "sub", style: "margin-top:10px" }, `${(linked.broker || "").toUpperCase()} ${linked.env} account · ${linked.currency}`),
      kv([["Equity", money(linked.equity)], ["Cash", money(linked.cash)], ["Buying power", money(linked.buying_power)],
        ["Positions", String((linked.positions || []).length)]]));
  } else if (linked && linked.error) {
    nodes.push(el("div", { class: "msg err" }, `broker: ${linked.error}`));
  }
  put("p-account", ...nodes);
  meta("m-account", stats.risk_free_through ? `RF thru ${stats.risk_free_through}` : "");
}

function renderSystem(status, sched) {
  const cycle = status.last_cycle || {};
  const jobs = (sched && sched.jobs) || {};
  const running = sched && sched.operation_state === "RUNNING";
  put("p-system",
    kv([
      ["Kill switch", status.kill_switch_engaged ? `ENGAGED ${status.kill_switch_reason || ""}` : "clear", status.kill_switch_engaged ? "down" : "up"],
      ["Circuit breaker", String(status.circuit_breaker_tier || "--")],
      ["Heartbeat", `${ago(status.heartbeat_age_seconds)} ago${status.heartbeat_stale ? " · STALE" : ""}`, status.heartbeat_stale ? "down" : ""],
      ["Last cycle", cycle.as_of_date || "--"],
      ["Session", cycle.session_open === undefined ? "--" : cycle.session_open ? "closed · traded" : "not closed yet"],
      ["Considered / placed", cycle.entries ? `${cycle.entries_considered ?? 0} / ${(cycle.entries || []).filter((e) => e.allowed).length}` : "--"],
      ["Errors", (cycle.errors || []).length ? String(cycle.errors.length) : "none", (cycle.errors || []).length ? "down" : ""],
      ["Scheduler", sched && !sched.__error ? (sched.operation_state || "--") : "unavailable"],
      ...Object.values(jobs).map((job) => [`  ${job.key}`, job.loaded ? job.state || "loaded" : "not loaded", job.loaded ? "" : "dim"]),
    ]),
    el("div", { class: "row" },
      el("button", { class: "btn", disabled: !sched || sched.__error || running, onclick: () => schedule("start") }, "Start schedule"),
      el("button", { class: "btn", disabled: !sched || sched.__error || !running, onclick: () => schedule("stop") }, "Stop schedule")),
  );
  meta("m-system", cycle.ts ? new Date(cycle.ts * 1000).toLocaleString() : "");
  $("sb-sched").textContent = `SCHED ${sched && !sched.__error ? sched.operation_state || "--" : "n/a"}`;
}

function renderExec(mode) {
  const live = mode.mode === "live";
  put("p-exec",
    el("div", { class: "big", style: `font-size:22px;${live ? "color:var(--down)" : ""}` }, modeLabel(mode)),
    kv([
      ["Ledger", mode.ledger || "--"],
      ["Capital (sizes orders)", mode.mode === "paper" || live ? money(mode.capital_usd, 0) : "$100,000 sim"],
      ["Environment", mode.mode === "sim" ? "--" : mode.env],
      ["Live allowed", mode.live_allowed ? "yes (.env)" : "no", mode.live_allowed ? "down" : "dim"],
      ["Live order cap", money(mode.live_max_order_usd, 0)],
      ["Armed", mode.armed_at ? new Date(mode.armed_at * 1000).toLocaleString() : "--", mode.armed_at ? "down" : "dim"],
    ]),
    el("div", { class: "row" }, el("button", { class: "btn primary", onclick: () => show("brokers") }, "Change mode / link broker  F2")));
  meta("m-exec", mode.mode === "sim" ? "no broker" : mode.env);
}

function renderEquity(curve) {
  const marked = curve && curve.marked && curve.marked.dates && curve.marked.dates.length ? curve.marked : null;
  const dates = marked ? marked.dates : (curve && curve.dates) || [];
  const values = marked ? (marked.nav || marked.marked_nav || marked.values || []) : (curve && curve.nav) || [];
  if (values.length < 2) { put("p-equity", el("div", { class: "empty" }, "No equity history yet. The curve starts after the first trading day.")); return; }
  const W = 1000, H = 240, P = 44;
  const lo = Math.min(...values), hi = Math.max(...values), span = Math.max(hi - lo, 1);
  const x = (i) => P + (i / (values.length - 1)) * (W - P - 8);
  const y = (v) => 10 + (1 - (v - lo) / span) * (H - 34);
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("preserveAspectRatio", "none");
  const add = (tag, attrs, text) => { const node = document.createElementNS(ns, tag); Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v)); if (text) node.textContent = text; svg.append(node); };
  [0, 0.5, 1].forEach((t) => {
    const v = lo + span * (1 - t), yy = y(v);
    add("line", { x1: P, x2: W, y1: yy, y2: yy, class: "grid" });
    add("text", { x: 2, y: yy + 4, class: "axis" }, `${(v / 1000).toFixed(1)}k`);
  });
  const start = values[0];
  if (start >= lo && start <= hi) add("line", { x1: P, x2: W, y1: y(start), y2: y(start), class: "base" });
  add("path", { d: values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" "), class: "line" });
  add("text", { x: P, y: H - 4, class: "axis" }, dates[0]);
  add("text", { x: W - 90, y: H - 4, class: "axis" }, dates[dates.length - 1]);
  put("p-equity", svg);
  const last = values[values.length - 1];
  meta("m-equity", `${money(last, 0)} · ${pct(last / start - 1)}`);
}

function renderPositions(rows) {
  const list = Array.isArray(rows) ? rows : [];
  const total = list.reduce((sum, p) => sum + (n(p.unrealized_pnl) || 0), 0);
  put("p-positions", table(
    [["TICKER"], ["DIR"], ["ENTRY", 1], ["LAST", 1], ["DAYS", 1], ["NOTIONAL", 1], ["UNREAL", 1]],
    list.map((p) => [[p.ticker, "t"], [p.direction === "long" ? "LONG" : "SHORT", p.direction === "long" ? "up" : "down"],
      [fixed(p.entry_price), "r"], [fixed(p.last_close), "r"], [String(p.days_held ?? "--"), "r"],
      [money(p.notional, 0), "r"], [signed(p.unrealized_pnl), `r ${cls(p.unrealized_pnl)}`]]),
    "No open positions."));
  meta("m-positions", `${list.length} open · ${signed(total)}`);
  $("s-open").textContent = String(list.length);
}

function renderSignals(rows) {
  const list = (Array.isArray(rows) ? rows : []).slice(0, 40);
  put("p-signals", table(
    [["TICKER"], ["SUE", 1], ["P(DRIFT)", 1], ["DIR"], ["DECISION"]],
    list.map((s) => [[s.ticker, "t"], [fixed(s.sue), "r"], [fixed(s.calibrated_proba, 3), "r"],
      [String(s.direction || "").toUpperCase(), s.direction === "long" ? "up" : "down"],
      [s.allowed ? `BUY ${(n(s.size_fraction) * 100).toFixed(1)}%` : String(s.reason || "skip").replace(/_/g, " "), s.allowed ? "up" : "dim"]]),
    "No scored reports yet."));
  meta("m-signals", list[0] ? `as of ${list[0].as_of_date}` : "");
}

function renderUpcoming(data) {
  const events = (data && data.events) || [];
  put("p-upcoming", table(
    [["TICKER"], ["DATE"], ["WHEN"], ["EPS EST", 1]],
    events.slice(0, 40).map((e) => [[e.ticker, "t"], [String(e.earnings_date || "").slice(0, 10)],
      [String(e.timing || "").replace(/_/g, " "), "dim"], [e.eps_estimate === null ? "--" : fixed(e.eps_estimate), "r"]]),
    "No upcoming reports in the watch list."));
  meta("m-upcoming", `${events.length} in ${data && data.horizon_days ? data.horizon_days : "--"}d`);
}

function renderTape(rows) {
  const list = Array.isArray(rows) ? rows : [];
  put("p-tape", ...(list.length ? list.map((e) => el("div", {},
    el("span", { class: "ts" }, new Date(e.ts * 1000).toLocaleString()), el("span", { class: "k" }, String(e.kind || e.source || "").toUpperCase()), e.summary))
    : [el("div", { class: "empty" }, "No events yet.")]));
  meta("m-tape", `${list.length} latest`);
}

async function loadDesk() {
  const [status, stats, positions, signals, upcoming, tape, curve, mode, linked, sched] = await Promise.all([
    safe(api("/api/status")), safe(api("/api/stats")), safe(api("/api/positions")), safe(api("/api/signals")),
    safe(api("/api/upcoming_earnings")), safe(api("/api/event_feed?limit=40")), safe(api("/api/equity_curve")),
    safe(api("/api/mode")), safe(api("/api/linked_account")), safe(api("/api/launchd_status")),
  ]);
  if (status.__error) throw new Error(status.__error);
  renderStrip(status, stats, mode);
  renderAccount(stats, linked, mode);
  renderSystem(status, sched);
  renderExec(mode);
  renderEquity(curve);
  renderPositions(positions);
  renderSignals(signals);
  renderUpcoming(upcoming);
  renderTape(tape);
}

// ------------------------------------------------------------ brokers
const MODE_INFO = {
  sim: ["SIMULATOR", "Real prices, simulated fills. No broker needed."],
  readonly: ["READ-ONLY", "Simulator trades; your broker account is shown alongside."],
  paper: ["BROKER PAPER", "Orders go to the broker's paper / sandbox / demo account."],
  live: ["LIVE", "Real orders, real money. Needs MERIDIAN_ALLOW_LIVE=yes, live keys and the arm phrase."],
};

function renderMode(data) {
  const mode = data.mode;
  let pick = state.pickMode || mode.mode;
  const brokers = Object.values(data.brokers);
  const eligible = (m) => brokers.filter((b) => m === "readonly" ? Object.values(b.linked).some(Boolean)
    : m === "paper" ? b.can_trade.includes("paper") && b.linked.paper
      : m === "live" ? b.can_trade.includes("live") && b.linked.live : false);
  const brokerSelect = el("select", { class: "in", id: "mode-broker" },
    eligible(pick).map((b) => el("option", { value: b.id, selected: b.id === mode.broker }, b.name)));
  const envSelect = el("select", { class: "in", id: "mode-env" }, ["paper", "live"].map((env) => el("option", { value: env, selected: env === mode.env }, env)));
  const capital = el("input", { class: "in", id: "mode-capital", type: "number", min: "1", step: "100", value: String(mode.capital_usd || 100000) });
  const confirm = el("input", { class: "in", id: "mode-confirm", placeholder: mode.arm_phrase || "LIVE <BROKER>", spellcheck: "false" });
  const msg = el("div", { class: "msg", id: "mode-msg" });
  const fields = [];
  if (pick !== "sim") {
    if (!eligible(pick).length) fields.push(el("div", { class: "msg err" }, pick === "readonly" ? "Link a broker below first." : `Link a broker's ${pick} credentials below first.`));
    else fields.push(el("label", { class: "f" }, "Broker", brokerSelect));
    if (pick === "readonly") fields.push(el("label", { class: "f" }, "Read with", envSelect));
    if (pick === "paper" || pick === "live") fields.push(el("label", { class: "f" }, "Capital that sizes orders (USD)", capital));
    if (pick === "live") fields.push(el("label", { class: "f" }, `Type the arm phrase (${eligible("live")[0] ? `LIVE ${eligible("live")[0].id.toUpperCase()}` : "LIVE <BROKER>"})`, confirm));
  }
  put("p-mode",
    el("div", { class: "modes" }, Object.entries(MODE_INFO).map(([key, [title, text]]) =>
      el("button", { class: `mode${key === pick ? " on" : ""}`, "data-mode": key, type: "button", onclick: () => { state.pickMode = key; renderMode(data); } },
        el("b", {}, `${key === mode.mode ? "● " : ""}${title}`), el("span", {}, text)))),
    el("div", { class: "row" }, fields,
      el("button", { class: `btn ${pick === "live" ? "danger" : "primary"}`, disabled: pick !== "sim" && !eligible(pick).length, onclick: applyMode }, pick === "live" ? "Arm live" : "Apply")),
    pick === "live" && !mode.live_allowed ? el("div", { class: "msg err" }, `Live is off: ${mode.live_blocked_reason}.`) : "",
    msg);
  meta("m-mode", `current: ${modeLabel(mode)}`);
}

async function applyMode() {
  const pick = state.pickMode || state.brokers.mode.mode;
  const body = { mode: pick };
  if (pick !== "sim") body.broker = $("mode-broker") ? $("mode-broker").value : null;
  if (pick === "readonly") body.env = $("mode-env").value;
  if (pick === "paper" || pick === "live") body.capital_usd = Number($("mode-capital").value);
  if (pick === "live") body.confirm = $("mode-confirm").value;
  try {
    const mode = await api("/api/mode", { method: "POST", body });
    state.pickMode = null;
    log(`mode → ${modeLabel(mode)}`);
    await loadBrokers();
  } catch (error) {
    $("mode-msg").className = "msg err"; $("mode-msg").textContent = error.message;
  }
}

function brokerCard(b) {
  const caps = el("div", { class: "caps" },
    el("span", { class: "tag ok" }, "READ-ONLY"),
    el("span", { class: `tag ${b.can_trade.includes("paper") ? "ok" : "dim"}` }, b.can_trade.includes("paper") ? "PAPER" : "NO PAPER"),
    el("span", { class: `tag ${b.can_trade.includes("live") ? "warn" : "dim"}` }, b.can_trade.includes("live") ? "LIVE" : "NO LIVE ORDERS"),
    b.supports_short ? "" : el("span", { class: "tag dim" }, "LONG ONLY"));
  const envBlocks = b.envs.map((env) => {
    const linked = b.linked[env];
    const acct = el("div", { class: "acct", id: `acct-${b.id}-${env}` });
    if (linked) {
      acct.append(el("div", { class: "sub" }, `${env.toUpperCase()} · linked`), el("div", { class: "wait" }, "reading account…"));
      api(`/api/brokers/${b.id}/account?env=${env}`).then((a) => {
        acct.replaceChildren(el("div", { class: "sub" }, `${env.toUpperCase()} · ${a.account_id || ""} · ${a.currency} · ${a.latency_ms} ms`),
          kv([["Equity", money(a.equity)], ["Cash", money(a.cash)], ["Buying power", money(a.buying_power)],
            ["Positions", String((a.positions || []).length)]]),
          el("div", { class: "row" }, el("button", { class: "btn", onclick: () => unlink(b, env) }, `Unlink ${env}`)));
      }).catch((error) => {
        acct.replaceChildren(el("div", { class: "sub" }, `${env.toUpperCase()} · linked`), el("div", { class: "msg err" }, error.message),
          el("div", { class: "row" }, el("button", { class: "btn", onclick: () => unlink(b, env) }, `Unlink ${env}`)));
      });
      return acct;
    }
    const msg = el("div", { class: "msg" });
    const form = el("form", { onsubmit: (event) => link(event, b, env, msg) },
      el("div", { class: "sub" }, `${env.toUpperCase()} · not linked`),
      b.fields.map((f) => el("label", { class: "f" }, `${f.label}${f.optional ? " (optional)" : ""}`,
        el("input", { class: "in", name: f.name, type: f.secret ? "password" : "text", placeholder: f.placeholder || "", autocomplete: "off", spellcheck: "false" }))),
      el("div", { class: "row" }, el("button", { class: "btn primary", type: "submit" }, `Link ${env}`)), msg);
    return form;
  });
  return el("article", { class: "pane broker" },
    el("header", {}, b.name, el("span", { class: "meta" }, b.regions.map((r) => r.toUpperCase()).join(" · "))),
    el("div", { class: "body" }, caps, el("div", { class: "note" }, b.note, " ", el("a", { href: b.docs_url, target: "_blank", rel: "noopener noreferrer" }, "docs")), envBlocks));
}

async function link(event, b, env, msg) {
  event.preventDefault();
  const fields = Object.fromEntries(new FormData(event.target).entries());
  msg.className = "msg"; msg.textContent = "linking…";
  try {
    const result = await api(`/api/brokers/${b.id}/link`, { method: "POST", body: { env, fields } });
    log(`${b.name} ${env} linked${result.account && result.account.error ? ` (first read failed: ${result.account.error})` : ""}`);
    await loadBrokers();
  } catch (error) { msg.className = "msg err"; msg.textContent = error.message; }
}

async function unlink(b, env) {
  if (!(await ask(`Unlink ${b.name} (${env})?`, "This deletes the stored credentials for this environment. If it is the active mode, Meridian falls back to the simulator."))) return;
  await api(`/api/brokers/${b.id}/unlink`, { method: "POST", body: { env } });
  log(`${b.name} ${env} unlinked`);
  await loadBrokers();
}

async function loadBrokers() {
  const data = await api("/api/brokers");
  state.brokers = data;
  renderMode(data);
  put("p-regions", ...data.regions.map((region) => el("section", { class: "region" },
    el("h3", {}, region.name.toUpperCase(), el("small", {}, region.no_public_api.length ? `no public trading API: ${region.no_public_api.join(", ")}` : "")),
    el("div", { class: "broker-grid" }, region.brokers.map((id) => brokerCard(data.brokers[id]))))));
  renderStripMode(data.mode);
}
function renderStripMode(mode) { const label = modeLabel(mode); $("s-exec").textContent = label; $("title-mode").textContent = label; $("sb-mode").textContent = label; }

// ------------------------------------------------------------ research
async function loadResearch() {
  const [stats, replay, tests, mc] = await Promise.all([safe(api("/api/stats")), safe(api("/api/live_backtest_metrics")),
    safe(api("/api/research_tests")), safe(api("/api/monte_carlo"))]);
  put("p-forward", stats.__error ? el("div", { class: "empty" }, stats.__error) : kv([
    ["Closed trades", String(stats.n_closed_trades ?? "--")], ["Win rate", n(stats.win_rate) === null ? "--" : `${(stats.win_rate * 100).toFixed(1)}%`],
    ["Sharpe (excess)", stats.insufficient_data ? "n/a" : fixed(stats.sharpe_ratio)], ["Sortino", fixed(stats.sortino_ratio)],
    ["Max drawdown", pct(stats.max_drawdown), "down"], ["Total return", pct(stats.total_return_pct, 2, false), cls(stats.total_return_pct)],
    ["Risk-free", n(stats.risk_free_rate) === null ? "--" : `${(stats.risk_free_rate * 100).toFixed(2)}% (thru ${stats.risk_free_through})`],
    ["Backfilled trades", String(stats.n_backfilled_trades ?? 0)]]));
  meta("m-forward", "marked daily vs T-bills");
  put("p-replay", replay.__error || replay.available === false ? el("div", { class: "empty" }, "No replay metrics in reports/.") : kv([
    ["Window", `${replay.start_date} → ${replay.end_date}`], ["Trades", String(replay.n_trades)],
    ["Annual return", pct(replay.annualized_return)], ["Annual vol", pct(replay.annualized_std)],
    ["Sharpe", fixed(replay.sharpe_ratio)], ["Max drawdown", pct(replay.max_drawdown), "down"],
    ["Win rate", pct(replay.win_rate)], ["Total return", pct(replay.total_return), cls(replay.total_return)]]));
  meta("m-replay", replay.n_days_replayed ? `${replay.n_days_replayed} days` : "");
  const list = (tests && tests.tests) || [];
  put("p-tests", table([["TEST"], ["WINDOW"], ["SHARPE", 1], ["CAGR", 1], ["T", 1], ["RESULT"]],
    list.map((t) => [[t.name, "t"], [(t.window || []).map((d) => String(d).slice(0, 4)).join("–")], [fixed(t.result && t.result.sharpe), "r"],
      [pct(t.result && t.result.cagr, 1), "r"], [fixed(t.result && t.result.t_stat), "r"], [t.passed ? "PASS" : "FAIL", t.passed ? "up" : "down"]]),
    "No pre-registered tests found."));
  meta("m-tests", list.length ? `${list.filter((t) => t.passed).length}/${list.length} passed` : "");
  const boot = mc && mc.bootstrap;
  put("p-mc", !boot ? el("div", { class: "empty" }, "No Monte Carlo report.") : kv([
    ["Draws", String(mc.n_bootstrap_draws)], ["Ending return p5", pct(boot.ending_return_pct.p5)], ["Ending return p50", pct(boot.ending_return_pct.p50)],
    ["Ending return p95", pct(boot.ending_return_pct.p95)], ["Max DD p50", pct(boot.max_drawdown_pct.p50), "down"],
    ["Draws ending < 0", pct(boot.pct_draws_ending_negative, 1)]]));
  meta("m-mc", mc && mc.n_trades ? `${mc.n_trades} trades resampled` : "");
}

// ------------------------------------------------------------ setup
async function loadSetup() {
  const data = await api("/api/setup");
  const required = data.checks.filter((c) => !c.optional);
  const done = required.filter((c) => c.ok).length;
  put("p-ready",
    el("div", { class: `ready-banner ${data.ready ? "ok" : "no"}` },
      data.ready ? "READY · the bot will trade on schedule in the mode you picked" : `${done}/${required.length} required steps done`),
    el("div", { class: "checks" }, data.checks.map((c) => el("div", { class: `check ${c.ok ? "ok" : c.optional ? "opt" : "no"}` },
      el("span", { class: "mark" }, c.ok ? "✓" : c.optional ? "–" : "✗"),
      el("span", { class: "lbl" }, `${c.label}${c.optional ? " (optional)" : ""}`),
      el("span", { class: "det" }, c.detail),
      c.fix ? el("span", { class: "fix" }, `→ ${c.fix}`) : ""))));
  meta("m-ready", `${data.platform} · port ${data.port}`);

  const mode = data.mode;
  const live = data.checks.find((c) => c.id === "live");
  const brokers = data.checks.find((c) => c.id === "broker");
  const steps = [
    ["Link the broker's live keys in F2 Brokers", brokers.ok && /live/.test(brokers.detail)],
    ["Set MERIDIAN_ALLOW_LIVE=yes in .env, then restart the desk", live.ok],
    [`Pick LIVE in F2 and type the arm phrase${mode.broker ? ` (${mode.arm_phrase})` : ""}`, mode.mode === "live"],
  ];
  put("p-live",
    el("div", { class: "checks" }, steps.map(([text, ok], i) => el("div", { class: `check ${ok ? "ok" : "opt"}` },
      el("span", { class: "mark" }, ok ? "✓" : String(i + 1)), el("span", { class: "lbl" }, text), el("span", { class: "det" }, "")))),
    el("p", { class: "sub" }, `Each live order is clipped to ${money(mode.live_max_order_usd, 0)}. Try the broker's paper mode first: same code path, no real money.`),
    el("div", { class: "row" }, el("button", { class: "btn primary", onclick: () => show("brokers") }, "Open brokers  F2")));
  meta("m-live", mode.mode === "live" ? "ARMED" : "not armed");
}

// ------------------------------------------------------------ actions
function ask(title, text, phrase) {
  return new Promise((resolve) => {
    const dialog = $("dialog");
    const input = phrase ? el("input", { class: "in", placeholder: phrase, spellcheck: "false" }) : null;
    const done = (value) => { dialog.hidden = true; resolve(value); };
    $("dialog-title").textContent = title;
    put("dialog-body", el("div", {}, text), input || "",
      el("div", { class: "row" },
        el("button", { class: "btn primary", onclick: () => done(phrase ? input.value.trim().toUpperCase() === phrase : true) }, "OK"),
        el("button", { class: "btn", onclick: () => done(false) }, "Cancel")));
    $("dialog-close").onclick = () => done(false);
    dialog.hidden = false;
    (input || dialog.querySelector(".btn")).focus();
  });
}

async function schedule(action) {
  const ok = await ask(action === "start" ? "Start the schedule?" : "Stop the schedule?",
    action === "start" ? "Loads the launchd jobs. Loading runs one cycle right away; it only trades after a completed session."
      : "Unloads the launchd jobs. Open positions stay open and are not exited until the schedule runs again.");
  if (!ok) return;
  try { await api(`/api/control/${action}`, { method: "POST", body: { confirm: true } }); log(`schedule ${action} sent`); }
  catch (error) { log(error.message, "err"); }
  refresh();
}

// ------------------------------------------------------------ commands
const COMMANDS = {
  help: () => log("desk | brokers | research | setup | refresh | mode | positions | signals | nav | art | clear | date"),
  desk: () => show("desk"), brokers: () => show("brokers"), research: () => show("research"), setup: () => show("setup"),
  1: () => show("desk"), 2: () => show("brokers"), 3: () => show("research"), 4: () => show("setup"),
  refresh: () => refresh(), r: () => refresh(),
  mode: async () => { const m = await api("/api/mode"); log(`mode ${modeLabel(m)} · ledger ${m.ledger} · live ${m.live_allowed ? "allowed" : "off"}`); },
  nav: async () => { const s = await api("/api/stats"); log(`nav ${money(s.current_nav)} · marked ${money(s.marked_nav)} · return ${pct(s.total_return_pct, 2, false)}`); },
  positions: async () => { const rows = await api("/api/positions"); rows.forEach((p) => log(`${p.ticker.padEnd(6)} ${p.direction.padEnd(5)} ${fixed(p.entry_price).padStart(9)} → ${fixed(p.last_close).padStart(9)} ${signed(p.unrealized_pnl)}`)); if (!rows.length) log("no open positions"); },
  signals: async () => { const rows = (await api("/api/signals")).slice(0, 10); rows.forEach((s) => log(`${s.ticker.padEnd(6)} sue ${fixed(s.sue).padStart(7)} p ${fixed(s.calibrated_proba, 3)} ${s.allowed ? "BUY" : s.reason}`)); },
  art: () => document.body.classList.toggle("no-art"),
  clear: () => $("console-lines").replaceChildren(),
  date: () => log(new Date().toString()),
};

$("prompt").addEventListener("submit", async (event) => {
  event.preventDefault();
  const raw = $("cmd").value.trim();
  $("cmd").value = "";
  if (!raw) return;
  state.history.push(raw); state.historyAt = state.history.length;
  log(`> ${raw}`, "in");
  const command = COMMANDS[raw.toLowerCase().split(/\s+/)[0]];
  if (!command) { log(`unknown command: ${raw} (type help)`, "err"); return; }
  try { await command(raw); } catch (error) { log(error.message, "err"); }
});
$("cmd").addEventListener("keydown", (event) => {
  if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
  event.preventDefault();
  state.historyAt = Math.max(0, Math.min(state.history.length, state.historyAt + (event.key === "ArrowUp" ? -1 : 1)));
  $("cmd").value = state.history[state.historyAt] || "";
});

// ------------------------------------------------------------ chrome
document.querySelectorAll(".fkey[data-tab]").forEach((key) => key.addEventListener("click", () => show(key.dataset.tab)));
$("btn-refresh").addEventListener("click", () => refresh());
$("btn-compact").addEventListener("click", () => document.body.classList.toggle("no-art"));
$("btn-full").addEventListener("click", () => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen()).catch(() => {}));
$("btn-reset").addEventListener("click", () => { try { localStorage.removeItem("meridian-tab"); } catch (_) { /* ignore */ } document.body.classList.remove("no-art"); show("desk"); });
document.addEventListener("keydown", (event) => {
  const keys = { F1: "desk", F2: "brokers", F3: "research", F4: "setup" };
  if (keys[event.key]) { event.preventDefault(); show(keys[event.key]); }
  else if (event.key === "F9") { event.preventDefault(); refresh(); }
  else if (event.key === "/" && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") { event.preventDefault(); $("cmd").focus(); }
});

function tick() {
  $("sb-clock").textContent = `${new Date().toLocaleTimeString("en-US", { timeZone: "America/New_York", hour12: false })} ET`;
}

async function loadArt() {
  try {
    const [big, small] = await Promise.all([fetch("art/fallen_angel.txt").then((r) => r.text()), fetch("art/fallen_angel_small.txt").then((r) => r.text())]);
    $("backdrop").textContent = window.innerWidth < 720 ? small : big;
  } catch (_) { /* art is decoration */ }
}

let refreshing = false;
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    if (state.tab === "desk") await loadDesk();
    else {
      const [status, stats, mode, positions] = await Promise.all([api("/api/status"), safe(api("/api/stats")),
        safe(api("/api/mode")), safe(api("/api/positions"))]);
      renderStrip(status, stats, mode);
      $("s-open").textContent = Array.isArray(positions) ? String(positions.length) : "--";
      if (state.tab === "brokers") await loadBrokers();
      else if (state.tab === "research") await loadResearch();
      else if (state.tab === "setup") await loadSetup();
    }
    $("sb-conn").textContent = "● ONLINE"; $("sb-conn").className = "sb-conn on";
    $("sb-updated").textContent = `updated ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    $("sb-conn").textContent = "● OFFLINE"; $("sb-conn").className = "sb-conn";
    log(`refresh failed: ${error.message}`, "err");
  } finally { refreshing = false; }
}

tick(); setInterval(tick, 1000);
loadArt();
let saved = "desk";
try { saved = localStorage.getItem("meridian-tab") || "desk"; if (saved === "background") saved = "setup"; } catch (_) { /* ignore */ }
show(saved);
setInterval(refresh, REFRESH_MS);
