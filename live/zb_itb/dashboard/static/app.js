/* ═══════════════════════════════════════════════════════════════════
   gapup — terminal desk
   plain JS · canvas charts · draggable tmux panes · command prompt
   ═══════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  /* ───────────────────────────── helpers ─────────────────────────── */
  const $  = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

  const num = (x, d) => (x == null || Number.isNaN(x)) ? "—" : Number(x).toLocaleString("en-US", { minimumFractionDigits: d == null ? 0 : d, maximumFractionDigits: d == null ? 0 : d });
  const money = (x) => (x == null || Number.isNaN(x)) ? "—" : "$" + Number(x).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const money0 = (x) => (x == null || Number.isNaN(x)) ? "—" : "$" + Math.round(Number(x)).toLocaleString("en-US");
  const pct = (x, d = 1) => (x == null || Number.isNaN(x)) ? "—" : (x >= 0 ? "+" : "−") + Math.abs(x * 100).toFixed(d) + "%";
  const bp = (x, d = 1) => (x == null || Number.isNaN(x)) ? "—" : (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(d) + " bp";
  const sgn = (x) => x > 0 ? "pos" : x < 0 ? "neg" : "dim";
  const dstr = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso.length <= 10 ? iso + "T12:00:00Z" : iso);
    return d.toLocaleDateString("en-US", { timeZone: "America/New_York", month: "short", day: "2-digit", year: "numeric" });
  };
  const tstr = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleTimeString("en-US", { timeZone: "America/New_York", hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
  };
  const isoShort = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso.length <= 10 ? iso + "T12:00:00Z" : iso);
    return d.toLocaleDateString("en-US", { timeZone: "America/New_York", month: "short", day: "2-digit" });
  };
  const hms = (secs) => {
    secs = Math.max(0, Math.floor(secs));
    const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60;
    return (h ? h + "h " : "") + String(m).padStart(2, "0") + "m " + String(s).padStart(2, "0") + "s";
  };
  const asciiBar = (frac, width) => {
    width = width || 24;
    const n = clamp(Math.round(frac * width), 0, width);
    return '<span class="ascii-bar">' + "█".repeat(n) + '<span class="rest">' + "░".repeat(width - n) + "</span></span>";
  };

  const font = (n, w) => (w || 400) + " " + n + 'px "IBM Plex Mono", "SFMono-Regular", "SF Mono", Menlo, Monaco, monospace';

  const cssVar = (name, fallback, el) => {
    const v = getComputedStyle(el || document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  };

  function withAlpha(hex, a) {
    const h = String(hex || "").replace("#", "").trim();
    if (h.length === 3) {
      return "rgba(" + parseInt(h[0] + h[0], 16) + "," + parseInt(h[1] + h[1], 16) + "," + parseInt(h[2] + h[2], 16) + "," + a + ")";
    }
    if (h.length === 6) {
      return "rgba(" + parseInt(h.slice(0, 2), 16) + "," + parseInt(h.slice(2, 4), 16) + "," + parseInt(h.slice(4, 6), 16) + "," + a + ")";
    }
    return hex;
  }

  function chartColors(el) {
    return {
      accent: cssVar("--accent", "#e6a2b5", el),
      red: cssVar("--red", "#d77e79", el),
      amber: cssVar("--amber", "#d8ad77", el),
      text: cssVar("--text", "#dcc9bd", el),
      bright: cssVar("--bright", "#f6e9df", el),
      dim: cssVar("--dim", "#9d8779", el),
      faint: cssVar("--faint", "#6c584d", el),
      grid: cssVar("--grid", "#241915", el),
      grid2: cssVar("--grid-2", "#32221c", el),
      bg: cssVar("--panel", "#1a1311", el),
      tip: cssVar("--screen", "#171110", el),
    };
  }

  function accentColor() { return chartColors().accent; }

  /* ───────────────────────────── state ───────────────────────────── */
  const S = {
    tab: "desk",
    cost: 2,
    theme: "glint",
    cfg: null, now: null, sig: null, journal: [], equity: [], kill: null,
    btAll: null, btLo: null, edge: null, fwd: null, mc: null, account: null, bg: null,
    cmp: null,
    accounts: null, accountsAt: 0, nailMode: "live",
    acctView: "ITB",
    leg: "ITB", costNail: 5,
    view: "long-only",
    journalFilter: "",
    lastSignalAt: 0,
    history: [], histIdx: -1,
  };

  const KEY = {
    tab: "zb-term-tab-v3",
    order: "zb-term-order-v3",
    panes: "zb-term-panes-v3",
    paneThemes: "zb-term-pane-themes-v1",
    theme: "zb-term-theme-v4",
    cost: "zb-term-cost-v1",
    view: "zb-term-view-v1",
    acct: "zb-term-acct-v1",
    leg: "zb-term-leg-v1",
    costNail: "zb-term-cost-nail-v1",
  };

  const TABS = ["desk", "research", "background", "nail"];
  const THEMES = ["glint", "mummy", "flash"];
  const THEME_LABEL = { glint: "glint", mummy: "mummy", flash: "flash" };
  const THEME_GLYPH = { glint: "✦", mummy: "☠", flash: "◐" };

  function save(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* ignore */ } }
  function load(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }

  /* ───────────────────────────── api ─────────────────────────────── */
  let lastOk = 0;

  function setConn(live) {
    const cls = live ? "live" : "dead";
    const txt = live ? "LIVE" : "OFFLINE";
    const c = $("#conn"), sb = $("#sb-conn");
    if (c) { c.classList.toggle("live", live); c.classList.toggle("dead", !live); c.querySelector("span").textContent = txt; }
    if (sb) { sb.classList.toggle("live", live); sb.classList.toggle("dead", !live); sb.lastChild.textContent = txt; }
    if (live) lastOk = Date.now();
  }

  async function api(path) {
    try {
      const r = await fetch(path, { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const j = await r.json();
      setConn(true);
      return j;
    } catch (e) {
      setConn(false);
      throw e;
    }
  }

  /* ───────────────────────────── chrome ──────────────────────────── */
  function bindChrome() {
    $$(".light").forEach((b, i) => b.addEventListener("click", () => {
      if (i === 0) resetLayout();
      if (i === 1) cycleTheme();
      if (i === 2) {
        if (!document.fullscreenElement) document.documentElement.requestFullscreen && document.documentElement.requestFullscreen();
        else document.exitFullscreen && document.exitFullscreen();
      }
    }));
  }

  function cycleTheme() {
    const i = THEMES.indexOf(S.theme);
    setTheme(THEMES[(i + 1) % THEMES.length]);
    echo("theme → " + S.theme + " (" + THEMES.join(" · ") + ")", "ok");
  }

  function setTheme(name) {
    if (THEMES.indexOf(name) < 0) return false;
    S.theme = name;
    document.documentElement.dataset.theme = name;
    save(KEY.theme, name);
    const label = $("#theme-name");
    if (label) label.textContent = THEME_LABEL[name] || name;
    const glyph = $(".scene-brand .glyph");
    if (glyph) glyph.textContent = THEME_GLYPH[name] || "❀";
    $$("[data-theme-choice]").forEach((b) => b.classList.toggle("active", b.dataset.themeChoice === name));
    $$(".pane").forEach(paneThemeHint);
    startAtmos();
    renderTab(S.tab);
    return true;
  }

  function bindThemePicker() {
    $$("[data-theme-choice]").forEach((b) => b.addEventListener("click", () => {
      setTheme(b.dataset.themeChoice);
    }));
  }

  /* atmosphere: a handful of themed particles, never a screensaver */
  function startAtmos() {
    const host = $("#atmos");
    if (!host) return;
    host.innerHTML = ""; return;   /* the grain-gradient shader (grain.js) is the only atmosphere now */
    host.innerHTML = "";
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;

    const rnd = (a, b) => a + Math.random() * (b - a);
    const add = (kind) => {
      const p = document.createElement("span");
      p.className = "particle " + kind;
      p.style.left = rnd(1, 98).toFixed(2) + "vw";
      host.appendChild(p);
      return p;
    };
    const life = (p, a, b) => {
      const d = rnd(a, b);
      p.style.animationDuration = d.toFixed(2) + "s";
      p.style.animationDelay = (-rnd(0, d)).toFixed(2) + "s";
    };
    const drift = (p, span) => {
      p.style.setProperty("--dx", rnd(-span, span).toFixed(0) + "px");
    };

    const theme = S.theme;

    if (theme === "sakura") {
      for (let i = 0; i < 7; i++) {
        const p = add("petal");
        life(p, 22, 40);
        const size = rnd(4, 9);
        p.style.width = size.toFixed(1) + "px";
        p.style.height = (size * 1.15).toFixed(1) + "px";
        drift(p, 90);
        p.style.setProperty("--rot", rnd(180, 600).toFixed(0) + "deg");
      }
    } else if (theme === "matcha") {
      for (let i = 0; i < 9; i++) {
        const p = add("leaf");
        life(p, 18, 32);
        const size = rnd(3.5, 7);
        p.style.width = size.toFixed(1) + "px";
        p.style.height = (size * 1.5).toFixed(1) + "px";
        drift(p, 80);
        p.style.setProperty("--rot", rnd(260, 620).toFixed(0) + "deg");
      }
      for (let i = 0; i < 4; i++) {
        const p = add("firefly");
        p.style.top = rnd(24, 88).toFixed(1) + "vh";
        life(p, 9, 17);
        drift(p, 50);
      }
    } else if (theme === "meteor") {
      for (let i = 0; i < 3; i++) {
        const p = add("shoot");
        p.style.top = rnd(2, 24).toFixed(1) + "vh";
        p.style.left = rnd(-28, -8).toFixed(1) + "vw";
        p.style.width = rnd(100, 230).toFixed(0) + "px";
        life(p, 9, 17);
      }
    } else if (theme === "snow") {
      for (let i = 0; i < 24; i++) {
        const p = add("flake");
        const size = rnd(2, 5);
        p.style.width = size.toFixed(1) + "px";
        p.style.height = size.toFixed(1) + "px";
        life(p, 14, 28);
        drift(p, 55);
      }
    } else if (theme === "ember") {
      for (let i = 0; i < 16; i++) {
        const p = add("spark");
        const size = rnd(1.4, 3.2);
        p.style.width = size.toFixed(1) + "px";
        p.style.height = size.toFixed(1) + "px";
        life(p, 7, 15);
        drift(p, 40);
      }
    }
  }

  function setTab(tab, push) {
    if (TABS.indexOf(tab) < 0) return;
    S.tab = tab;
    $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    $$(".sb-win").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    $$(".page").forEach((p) => p.classList.toggle("active", p.dataset.page === tab));
    save(KEY.tab, tab);
    renderTab(tab);
    if (push !== false) { const sc = $("#screen"); if (sc) sc.scrollTop = 0; }
  }

  function bindTabs() {
    $$("[data-tab]").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
  }

  function renderChrome() {
    if (S.cfg) {
      const mode = S.cfg.mode || "PAPER";
      $("#mode-badge").textContent = mode;
      $("#sb-broker").textContent = S.cfg.label || "—";
    }
    const killOn = !!(S.kill && S.kill.kill);
    const k = $("#sb-kill");
    k.textContent = killOn ? "KILL ON" : "KILL OFF";
    k.classList.toggle("on", killOn);
    if (S.now) {
      $("#win-title").textContent = "gapup — -zsh — 142×41";
    }
  }

  /* ───────────────────────────── clock ───────────────────────────── */
  const ET_FMT = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York", hourCycle: "h23",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });

  function etNow() {
    const p = {};
    ET_FMT.formatToParts(new Date()).forEach((x) => { p[x.type] = x.value; });
    return {
      y: +p.year, mo: +p.month, d: +p.day,
      h: +p.hour, mi: +p.minute, s: +p.second,
      secs: +p.hour * 3600 + +p.minute * 60 + +p.second,
      iso: p.year + "-" + p.month + "-" + p.day,
      label: p.hour + ":" + p.minute + ":" + p.second,
    };
  }

  function startClock() {
    const tick = () => {
      const t = etNow();
      $("#sb-clock").textContent = t.label + " ET";
      $$(".countdown[data-target]").forEach((el) => {
        const target = +el.dataset.target;
        const left = target - t.secs;
        if (left >= 0) { el.textContent = "in " + hms(left); el.classList.toggle("soon", left < 900); }
        else el.textContent = "passed";
      });
      if (S.tab === "desk") updateTimelineLive();
    };
    tick();
    setInterval(tick, 1000);
  }

  /* ───────────────────────────── schedule ────────────────────────── */
  const STEPS = [
    { t: "09:15:00", secs: 33300, label: "signal ready", note: "ZB 09:00 print" },
    { t: "09:27:00", secs: 34020, label: "OPG deadline", note: "order must be in" },
    { t: "09:30:00", secs: 34200, label: "entry", note: "ITB + NAIL open" },
    { t: "09:31:30", secs: 34290, label: "fill check", note: "confirm / retry" },
    { t: "09:35:00", secs: 34500, label: "late cutoff", note: "no entries after" },
    { t: "10:30:00", secs: 37800, label: "exit", note: "flatten" },
    { t: "15:50:00", secs: 57000, label: "failsafe", note: "force flat" },
  ];

  function stepState(secs, nowSecs, open) {
    if (!open) return "off";
    if (nowSecs > secs + 30) return "done";
    return "next";
  }

  function nextStep(nowSecs, open) {
    if (!open) return null;
    return STEPS.find((s) => s.secs > nowSecs) || null;
  }

  function fmtCountdown(target, nowSecs) {
    const left = target - nowSecs;
    if (left < 0) return "passed";
    return "in " + hms(left);
  }

  /* ───────────────────────────── drag / panes ────────────────────── */
  let drag = null;

  function paneThemeHint(pane) {
    const btn = $('[data-act="theme"]', pane);
    if (!btn) return;
    const cur = pane.dataset.theme
      ? (THEME_LABEL[pane.dataset.theme] || pane.dataset.theme)
      : ("inherit global (" + (THEME_LABEL[S.theme] || S.theme) + ")");
    btn.title = "pane theme: " + cur + " · click to cycle · ⌥ click to collapse";
    btn.setAttribute("aria-label", "pane theme: " + cur + " · click to cycle");
  }

  function applyPaneThemes() {
    const st = load(KEY.paneThemes, null);
    if (st && typeof st === "object") {
      $$(".pane").forEach((p) => {
        const v = st[p.dataset.pane];
        if (THEMES.indexOf(v) >= 0) p.dataset.theme = v;
      });
    }
    $$(".pane").forEach(paneThemeHint);
  }

  function savePaneThemes() {
    const out = {};
    $$(".pane").forEach((p) => { if (p.dataset.theme) out[p.dataset.pane] = p.dataset.theme; });
    save(KEY.paneThemes, out);
  }

  function clearPaneThemes() {
    $$(".pane").forEach((p) => { delete p.dataset.theme; paneThemeHint(p); });
    try { localStorage.removeItem(KEY.paneThemes); } catch (e) { /* ignore */ }
  }

  function rerenderAfterTheme() {
    const screen = $("#screen");
    const y = screen ? screen.scrollTop : 0;
    const scrolls = {};
    $$(".pane").forEach((p) => { const b = $(".pane-body", p); if (b) scrolls[p.dataset.pane] = b.scrollTop; });
    renderTab(S.tab);
    $$(".pane").forEach((p) => { const b = $(".pane-body", p); if (b && scrolls[p.dataset.pane] != null) b.scrollTop = scrolls[p.dataset.pane]; });
    if (screen) screen.scrollTop = y;
  }

  function cyclePaneTheme(pane) {
    const pool = THEMES;
    if (!pane.dataset.theme) {
      pane.dataset.theme = pool[(pool.indexOf(S.theme) + 1) % pool.length];
    } else {
      const cur = pane.dataset.theme;
      const next = pool[(pool.indexOf(cur) + 1) % pool.length];
      if (next === S.theme) delete pane.dataset.theme; else pane.dataset.theme = next;
    }
    paneThemeHint(pane);
    savePaneThemes();
    rerenderAfterTheme();
  }

  function bindPaneControls() {
    $$(".pane").forEach((pane) => {
      $$(".pctl button", pane).forEach((b) => b.addEventListener("click", (e) => {
        e.stopPropagation();
        const act = b.dataset.act;
        if (act === "theme") {
          if (e.altKey) pane.classList.toggle("min");
          else cyclePaneTheme(pane);
        }
        if (act === "max") { pane.classList.toggle("max"); pane.parentElement.classList.toggle("is-max", !!$(".pane.max", pane.parentElement)); }
        if (act === "close") pane.classList.add("closed");
        savePaneState();
      }));
    });

    document.addEventListener("pointerdown", (e) => {
      const head = e.target.closest && e.target.closest(".pane-head");
      if (!head || e.target.closest("button")) return;
      drag = { pane: head.closest(".pane"), x: e.clientX, y: e.clientY, moved: false, over: null };
    });

    document.addEventListener("pointermove", (e) => {
      if (!drag) return;
      if (!drag.moved && Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) < 6) return;
      drag.moved = true;
      drag.pane.classList.add("dragging");
      const el = document.elementFromPoint(e.clientX, e.clientY);
      const over = el && el.closest ? el.closest(".pane") : null;
      if (drag.over && drag.over !== over) drag.over.classList.remove("drop-target");
      drag.over = over && over !== drag.pane ? over : null;
      if (drag.over) drag.over.classList.add("drop-target");
    });

    document.addEventListener("pointerup", () => {
      if (!drag) return;
      const { pane, over, moved } = drag;
      pane.classList.remove("dragging");
      if (over) {
        over.classList.remove("drop-target");
        if (moved) {
          const from = Array.prototype.indexOf.call(pane.parentElement.children, pane);
          const to = Array.prototype.indexOf.call(pane.parentElement.children, over);
          if (from < to) over.after(pane); else over.before(pane);
          saveOrder();
        }
      }
      drag = null;
    });
  }

  function saveOrder() {
    const out = {};
    $$(".page").forEach((p) => { out[p.dataset.page] = $$(".pane", p).map((x) => x.dataset.pane); });
    save(KEY.order, out);
  }

  function applyOrder() {
    const ord = load(KEY.order, null);
    if (!ord) return;
    $$(".page").forEach((p) => {
      const ids = ord[p.dataset.page];
      if (!Array.isArray(ids)) return;
      const map = {};
      $$(".pane", p).forEach((x) => { map[x.dataset.pane] = x; });
      ids.forEach((id) => { if (map[id]) p.appendChild(map[id]); });
    });
  }

  function savePaneState() {
    const out = {};
    $$(".pane").forEach((p) => { out[p.dataset.pane] = p.classList.contains("closed") ? "closed" : p.classList.contains("min") ? "min" : "open"; });
    save(KEY.panes, out);
  }

  function applyPaneState() {
    const st = load(KEY.panes, null);
    if (!st) return;
    $$(".pane").forEach((p) => {
      const v = st[p.dataset.pane];
      if (v === "closed") p.classList.add("closed");
      if (v === "min") p.classList.add("min");
    });
  }

  function resetLayout() {
    $$(".pane").forEach((p) => { p.classList.remove("closed", "min", "max"); });
    $$(".page").forEach((p) => p.classList.remove("is-max"));
    clearPaneThemes();
    try { localStorage.removeItem(KEY.order); localStorage.removeItem(KEY.panes); } catch (e) { /* ignore */ }
    renderTab(S.tab);
    echo("layout reset — panes restored, pane themes cleared", "ok");
  }

  /* ───────────────────────────── modal ───────────────────────────── */
  function openModal(title, body) {
    $("#modal-title").textContent = title;
    $("#modal-body").textContent = typeof body === "string" ? body : JSON.stringify(body, null, 2);
    $("#modal").classList.add("on");
  }
  function closeModal() { $("#modal").classList.remove("on"); }

  /* ───────────────────────────── prompt ──────────────────────────── */
  const COMMANDS = ["help", "desk", "research", "background", "h2h", "leg", "tab", "refresh", "acct", "sig", "theme", "cost", "layout", "clear", "date", "whoami", "ls", "exit"];

  function bindPrompt() {
    const cmd = $("#cmd"), ghost = $("#ghost"), block = $("#block");

    const sync = () => {
      ghost.textContent = cmd.value;
      block.style.left = ghost.offsetWidth + "px";
      block.classList.toggle("idle", document.activeElement !== cmd);
    };

    cmd.addEventListener("input", sync);
    cmd.addEventListener("focus", sync);
    cmd.addEventListener("blur", sync);

    cmd.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const v = cmd.value.trim();
        cmd.value = "";
        sync();
        if (v) runCommand(v);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (!S.history.length) return;
        S.histIdx = S.histIdx < 0 ? S.history.length - 1 : Math.max(0, S.histIdx - 1);
        cmd.value = S.history[S.histIdx]; sync();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        if (S.histIdx < 0) return;
        S.histIdx++;
        if (S.histIdx >= S.history.length) { S.histIdx = -1; cmd.value = ""; }
        else cmd.value = S.history[S.histIdx];
        sync();
      } else if (e.key === "Tab") {
        e.preventDefault();
        const v = cmd.value.trim();
        if (!v) return;
        const hits = COMMANDS.filter((c) => c.startsWith(v));
        if (hits.length === 1) { cmd.value = hits[0] + " "; sync(); }
        else if (hits.length > 1) echo(hits.join("  "), "dm");
      } else if (e.key === "l" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault(); clearConsole();
      } else if (e.key === "Escape") {
        cmd.blur();
      }
    });

    $("#prompt").addEventListener("click", () => cmd.focus());
    $("#modal-close").addEventListener("click", closeModal);
    $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });

    document.addEventListener("keydown", (e) => {
      const typing = document.activeElement === cmd || /INPUT|TEXTAREA/.test((document.activeElement || {}).tagName || "");
      if (e.key === "Escape") { closeModal(); return; }
      if (typing) return;
      if (e.key >= "1" && e.key <= "4") { setTab(TABS[+e.key - 1]); e.preventDefault(); }
      else if (e.key === "r" || e.key === "R") { refreshAll(true); }
      else if (e.key === "/" || e.key === ":") { e.preventDefault(); cmd.focus(); }
      else if (e.key === "?" || (e.key === "/" && e.shiftKey)) { e.preventDefault(); cmd.focus(); runCommand("help"); }
    });
    sync();
  }

  function echo(line, cls) {
    const box = $("#console"), inner = $("#console-inner");
    if (!inner) return;
    const d = document.createElement("div");
    d.className = "cline" + (cls ? " " + cls : "");
    d.innerHTML = line;
    inner.appendChild(d);
    while (inner.children.length > 120) inner.removeChild(inner.firstChild);
    box.classList.add("on");
    box.scrollTop = box.scrollHeight;
  }

  function clearConsole() {
    $("#console-inner").innerHTML = "";
    $("#console").classList.remove("on");
  }

  function runCommand(raw) {
    const line = esc(raw);
    echo('<span class="pr">rytty@slimebook</span> <span class="pr">gapup</span> <span class="dm">%</span> ' + line);
    S.history.push(raw);
    S.histIdx = -1;
    const parts = raw.trim().split(/\s+/);
    const cmd = (parts[0] || "").toLowerCase();
    const arg = (parts[1] || "").toLowerCase();

    switch (cmd) {
      case "help":
        echo([
          "desk · research · background · h2h      switch tab (h2h = head to head, ITB vs NAIL)",
          "tab <1-4|name>                          switch tab",
          "refresh | r                             reload all feeds",
          "acct                                    query both paper accounts",
          "sig                                     recompute today's signal",
          "leg itb|nail                            research tab: ITB or NAIL (3×)",
          "cost <bp>                               set cost per side (current leg)",
          "theme <name>                            glint · mummy · flash",
          "layout reset                            re-open every pane",
          "clear                                   clear this console",
          "date · whoami · ls · exit               the classics",
        ].join("\n"), "dm");
        break;
      case "desk": case "research": case "background":
        setTab(cmd); echo("→ " + cmd, "ok");
        break;
      case "h2h": case "head": case "nail": case "headtohead":
        setTab("nail"); echo("→ head to head · ITB vs NAIL", "ok");
        break;
      case "model": case "backtest": case "log": case "rules":
        setTab("research"); echo("→ research (formerly " + cmd + ")", "ok");
        break;
      case "tab": {
        const t = /^\d$/.test(arg) ? TABS[+arg - 1] : (["h2h", "head", "headtohead"].indexOf(arg) >= 0 ? "nail" : arg);
        if (TABS.indexOf(t) >= 0) { setTab(t); echo("→ " + t, "ok"); }
        else echo("tab: unknown tab " + esc(arg || ""), "er");
        break;
      }
      case "refresh": case "r":
        refreshAll(true);
        break;
      case "acct": case "account":
        echo("accounts: refreshing ITB + NAIL", "dm");
        loadAccounts(true);
        break;
      case "sig": case "signal":
        fetchSignal(true);
        break;
      case "theme":
        if (arg) {
          if (setTheme(arg)) echo("theme → " + S.theme, "ok");
          else echo("theme: choose " + THEMES.join(" · "), "er");
        } else cycleTheme();
        break;
      case "cost": {
        const v = parseFloat(arg);
        if (!Number.isFinite(v) || v < 0 || v > 50) { echo("cost: need 0–50 bp", "er"); break; }
        if (S.leg === "NAIL") { S.costNail = v; save(KEY.costNail, v); } else { S.cost = v; save(KEY.cost, v); }
        echo("cost → " + v + " bp/side (" + legName() + ")", "ok");
        loadResearch();
        break;
      }
      case "leg":
        if (arg === "itb" || arg === "nail") { setLeg(arg); if (S.tab !== "research") setTab("research"); }
        else echo("leg: choose itb · nail (current " + legName() + ")", "er");
        break;
      case "layout":
        if (arg === "reset") resetLayout(); else echo("layout: try `layout reset`", "er");
        break;
      case "clear":
        clearConsole();
        break;
      case "date":
        echo(new Date().toString() + "  ·  " + etNow().label + " ET", "dm");
        break;
      case "whoami":
        echo("rytty — paper desk, no live orders", "dm");
        break;
      case "ls":
        echo("desk  research  background", "dm");
        break;
      case "exit":
        echo("there is no exit. only 10:30.", "dm");
        break;
      default:
        echo("zsh: command not found: " + esc(cmd), "er");
    }
  }

  /* ───────────────────────────── data ────────────────────────────── */
  async function loadConfig() {
    try { S.cfg = await api("/api/config"); } catch (e) { /* offline */ }
  }
  async function loadNow() {
    try { S.now = await api("/api/now"); } catch (e) { /* offline */ }
  }
  async function loadRegime() {
    try { S.regime = await api("/api/regime"); } catch (e) { /* offline */ }
  }
  async function loadKill() {
    try { S.kill = await api("/api/kill"); } catch (e) { /* offline */ }
  }
  async function loadJournal() {
    try { const j = await api("/api/journal?limit=500"); S.journal = j.rows || []; } catch (e) { /* offline */ }
  }
  async function loadEquity() {
    try { const j = await api("/api/equity"); S.equity = j.rows || []; } catch (e) { /* offline */ }
  }
  let accountsPromise = null;
  async function loadAccounts(force) {
    if (!force && S.accounts && Date.now() - S.accountsAt < 12000) return;
    if (accountsPromise) return accountsPromise;
    accountsPromise = (async () => {
      try { S.accounts = await api("/api/accounts"); S.accountsAt = Date.now(); }
      catch (e) { S.accounts = { ok: false, error: String(e) }; }
      if (S.tab === "nail") renderNail();
      else if (S.tab === "desk") renderTab("desk");
    })();
    try { await accountsPromise; } finally { accountsPromise = null; }
  }
  async function loadBackground() {
    try { S.bg = await api("/api/background"); }
    catch (e) { if (!S.bg) S.bg = { ok: false, error: String(e) }; }
  }

  async function fetchSignal(announce) {
    const t0 = performance.now();
    try {
      const j = await api("/api/signal");
      S.sig = j;
      S.lastSignalAt = Date.now();
      if (announce) echo("signal recomputed in " + Math.round(performance.now() - t0) + "ms · d=" + ((j.signal || {}).d ?? "—"), "ok");
      renderTab(S.tab);
    } catch (e) {
      S.sig = { ok: false, error: String(e) };
      if (announce) echo("signal: " + esc(String(e)), "er");
      renderTab(S.tab);
    }
  }

  async function fetchAccount(announce) {
    const el = $("#p-account");
    if (el) el.innerHTML = '<div class="skeleton">querying broker…</div>';
    try {
      const j = await api("/api/account");
      S.account = j;
      const eq = j.ok && j.account ? Number(j.account.equity) : null;
      const shortMin = (S.cfg && S.cfg.config && S.cfg.config.short_min_equity_usd) || 2000;
      if (Number.isFinite(eq) && eq >= shortMin && S.view === "long-only") {
        S.view = "all";
        save(KEY.view, S.view);
        if (announce !== false) echo("auto mode: equity ≥ " + money(shortMin) + " — research view set to long + short", "dim");
        if (S.tab === "research") renderTab("research");
      }
      if (announce !== false) echo(j.ok ? "account: " + money((j.account || {}).equity) + " equity · " + esc(j.broker || "") : "account: " + esc(j.error || "failed"), j.ok ? "ok" : "er");
    } catch (e) {
      S.account = { ok: false, error: String(e) };
      if (announce !== false) echo("account: " + esc(String(e)), "er");
    }
    renderTab(S.tab);
  }

  async function loadLive() {
    await Promise.allSettled([loadNow(), loadKill(), loadRegime(), loadJournal(), loadEquity(), loadBackground(), loadAccounts(false)]);
    renderChrome();
    renderTab(S.tab);
    fetchSignal(false);
    if (S.equity.length) drawSparkInMilestone();
  }

  async function loadResearch() {
    let any = false;
    const q = (leg, view) => api("/api/backtest?cost_bp=" + (leg === "NAIL" ? S.costNail : S.cost) +
      "&view=" + view + "&start_cap=1000&sym=" + leg);
    const cmp = { ITB: {}, NAIL: {} };
    let cmpOk = false;
    const grab = (leg, view, slot) => q(leg, view).then((j) => {
      if (j && j.ok && !j.empty) { cmp[leg][slot] = j; cmpOk = true; }
    });
    await Promise.allSettled([
      q(S.leg, "all").then((j) => { S.btAll = j; any = true; }),
      q(S.leg, "Long-only").then((j) => { S.btLo = j; any = true; }),
      api("/api/edge?cost_bp=" + rcost() + "&sym=" + S.leg).then((j) => { S.edge = j; any = true; }),
      api("/api/forward").then((j) => { S.fwd = j; any = true; }),
      api("/api/mc?sym=" + S.leg).then((j) => { S.mc = j; any = true; }),
      grab("ITB", "all", "all"),
      grab("ITB", "Long-only", "lo"),
      grab("NAIL", "all", "all"),
      grab("NAIL", "Long-only", "lo"),
    ]);
    if (cmpOk) S.cmp = cmp;
    if (any) renderTab(S.tab);
    renderChrome();
  }

  async function refreshAll(announce) {
    const t0 = performance.now();
    if (announce) echo("refresh · pulling feeds…", "dm");
    await Promise.allSettled([loadConfig(), loadNow(), loadKill(), loadRegime(), loadJournal(), loadEquity(), loadBackground()]);
    await fetchSignal(false);
    if (S.tab === "research") loadResearch();
    if (S.tab === "desk") await loadAccounts(true);
    if (S.tab === "nail") await Promise.allSettled([loadAccounts(true), loadNail(false)]);
    renderChrome();
    renderTab(S.tab);
    if (announce) echo("refresh done in " + Math.round(performance.now() - t0) + "ms", "ok");
  }

  /* ───────────────────────────── renderers ───────────────────────── */
  const META = (id, text) => { const el = $('[data-meta="' + id + '"]'); if (el) el.textContent = text; };
  const nowStamp = () => "UPDATED " + etNow().label;
  const bt = () => (S.view === "long-only" ? S.btLo : S.btAll);
  const rcost = () => (S.leg === "NAIL" ? S.costNail : S.cost);
  const legName = () => (S.leg === "NAIL" ? "NAIL (3×)" : "ITB");
  function legBar() {
    return '<div class="view-toggle leg-toggle">' +
      '<button class="btn ' + (S.leg === "ITB" ? "on" : "") + '" data-leg="ITB">ITB</button>' +
      '<button class="btn ' + (S.leg === "NAIL" ? "on" : "") + '" data-leg="NAIL">NAIL (3×)</button>' +
      '<span class="faint small">research leg · same ZB signal · ' + rcost() + ' bp/side</span></div>';
  }
  function bindLegBar(el) {
    $$("[data-leg]", el).forEach((b) => b.addEventListener("click", () => setLeg(b.dataset.leg)));
  }
  function setLeg(v) {
    v = String(v || "").toUpperCase() === "NAIL" ? "NAIL" : "ITB";
    if (v === S.leg) return;
    S.leg = v; save(KEY.leg, v);
    S.btAll = S.btLo = S.edge = S.mc = null;
    renderTab(S.tab);
    loadResearch();
    echo("research leg → " + legName(), "ok");
  }

  function dayLabel() {
    if (!S.now) return "—";
    const d = new Date(S.now.date + "T12:00:00Z");
    return d.toLocaleDateString("en-US", { timeZone: "UTC", weekday: "short", day: "2-digit", month: "short", year: "numeric" }).toUpperCase();
  }

  function marketOpenToday() { return !!(S.now && S.now.market_open_today); }

  /* signal */
  function regimeLine() {
    const r = S.regime;
    if (!r || !r.ok || !r.enabled) return "";
    if (r.corr == null) return '<div class="sig-foot"><span class="kappa">REGIME</span><span class="amber">correlation unavailable · trading without the switch</span></div>';
    const on = r.on;
    return '<div class="sig-foot"><span class="kappa">REGIME</span><span class="' + (on ? "pos" : "neg") + '">' + (on ? "ON" : "OFF · trades skipped") + '</span>' +
      '<span class="faint">builders vs bonds, ' + r.window_days + 'd corr ' + (r.corr >= 0 ? "+" : "") + r.corr.toFixed(2) + ' · needs &gt; ' + Number(r.threshold).toFixed(1) + '</span></div>';
  }

  function renderSignal() {
    const el = $("#p-signal");
    if (!el) return;
    const t = etNow();
    const open = marketOpenToday();

    if (!open && S.now) {
      el.innerHTML =
        '<div class="eyebrow">SESSION · <b>' + esc(dayLabel()) + '</b></div>' +
        '<div class="sig-verdict"><span class="sig-arrow dim">·</span><span class="big dim">CLOSED</span></div>' +
        '<div class="sig-sub">no NYSE session today · next ' + esc(dstr(S.now.next_session)) + '</div>' +
        '<div class="sig-foot"><span class="kappa">RULE</span><span>ZB overnight → ITB + NAIL (3×) 09:30→10:30 ET</span></div>';
      META("signal", "MARKET CLOSED");
      return;
    }

    if (!S.sig) {
      el.innerHTML = '<div class="skeleton">reading ZB=F 60m bars…</div>';
      return;
    }
    if (!S.sig.ok) {
      el.innerHTML = '<div class="eyebrow">SESSION · <b>' + esc(dayLabel()) + '</b></div>' +
        '<div class="sig-verdict"><span class="sig-arrow neg">!</span><span class="big neg">NO DATA</span></div>' +
        '<div class="sig-sub">' + esc(S.sig.error || "signal unavailable") + '</div>' +
        '<div class="sig-foot"><button class="btn" id="sig-retry">retry signal</button><span class="faint">yfinance · 60m bars</span></div>';
      const rb = $("#sig-retry"); if (rb) rb.addEventListener("click", () => fetchSignal(true));
      META("signal", "SIGNAL ERROR");
      return;
    }

    const s = S.sig.signal || {};
    const d = s.d;
    const p0 = s.zb_p0_prev1600, p1 = s.zb_p1_0900;
    const move = (p0 && p1) ? Math.log(p1 / p0) * 1e4 : null;

    if (p0 == null || p1 == null) {
      const ns0 = nextStep(t.secs, open);
      el.innerHTML =
        '<div class="eyebrow">SESSION · <b>' + esc(dayLabel()) + '</b></div>' +
        '<div class="sig-verdict"><span class="sig-arrow amber">◷</span><span class="big amber">AWAITING 09:00</span></div>' +
        '<div class="sig-sub">ZB 09:00 print not in yet — the frozen rule computes at 09:15 ET</div>' +
        '<div class="sig-foot">' +
        (ns0 ? '<span class="kappa">NEXT</span><span>' + esc(ns0.t.slice(0, 5)) + " " + esc(ns0.label) + '</span><span class="countdown" data-target="' + ns0.secs + '">in ' + hms(ns0.secs - t.secs) + "</span>" : '<span class="kappa">NEXT</span><span>session complete</span>') +
        '<span style="margin-left:auto" class="faint">prev close ' + (p0 == null ? "—" : Number(p0).toFixed(4)) + "</span></div>";
      META("signal", "AWAITING 09:00 PRINT");
      return;
    }

    const long = d > 0, short = d < 0;
    const cls = long ? "pos" : short ? "neg" : "amber";
    const word = long ? "LONG ITB + NAIL" : short ? "SHORT ITB + NAIL" : "NO TRADE";
    const arrow = long ? "↑" : short ? "↓" : "·";
    const sub = d === 0
      ? "ZB print missing or flat — the rule stands down"
      : "d = " + (d > 0 ? "+1" : "−1") + " · both accounts hold 09:30 → 10:30 ET · ITB " + S.cost + " · NAIL " + S.costNail + " bp/side";

    const ns = nextStep(t.secs, open);
    const foot = ns
      ? '<span class="kappa">NEXT</span><span>' + esc(ns.t.slice(0, 5)) + " " + esc(ns.label) + '</span><span class="countdown" data-target="' + ns.secs + '">in ' + hms(ns.secs - t.secs) + "</span>"
      : '<span class="kappa">NEXT</span><span>session complete</span>';

    el.innerHTML =
      '<div class="sig-top">' +
        '<div><div class="eyebrow">SESSION · <b>' + esc(dayLabel()) + '</b></div>' +
          '<div class="sig-verdict"><span class="sig-arrow ' + cls + '">' + arrow + '</span>' +
          '<span class="big ' + cls + '">' + word + "</span></div>" +
          '<div class="sig-sub">' + esc(sub) + "</div></div>" +
        '<div class="sig-price">' +
          '<div class="kv"><span class="k">ZB 16:00 prev</span><span class="v">' + (p0 == null ? "—" : Number(p0).toFixed(4)) + "</span></div>" +
          '<div class="kv"><span class="k">ZB 09:00</span><span class="v">' + (p1 == null ? "—" : Number(p1).toFixed(4)) + "</span></div>" +
          '<div class="kv"><span class="k">overnight</span><span class="v ' + sgn(move == null ? 0 : move) + '">' + bp(move) + "</span></div>" +
        "</div>" +
      "</div>" +
      '<div class="sig-foot">' + foot + '<span style="margin-left:auto" class="faint">as of ' + t.label + " ET</span></div>" + regimeLine();
    META("signal", d === 0 ? "STANDS DOWN" : (long ? "LONG BIAS" : "SHORT BIAS") + " · " + nowStamp());
  }

  /* account + milestone, one pane, shared by both paper accounts */
  function accountMilestone(eq) {
    const known = Number.isFinite(eq);
    const shortMin = (S.cfg && S.cfg.config && S.cfg.config.short_min_equity_usd) || 2000;
    const target = 25000;
    const f1 = known ? clamp(eq / shortMin, 0, 1) : 0;
    const f2 = known ? clamp(eq / target, 0, 1) : 0;
    const eqTxt = known ? money0(eq) : "$—";
    return '<div class="acct-ms">' +
      '<div class="minihead">shorts unlock · ' + money0(shortMin) + ' <span class="' + (f1 >= 1 ? "pos" : "dim") + '">' + (known ? Math.round(f1 * 100) + "%" : "—") + "</span></div>" +
      '<div class="fwd-progress">' + asciiBar(f1, 22) + '<span class="fwd-pct">' + eqTxt + "</span></div>" +
      '<div class="minihead" style="margin-top:5px">milestone · $25,000 <span class="dim">' + (known ? Math.round(f2 * 100) + "%" : "—") + "</span></div>" +
      '<div class="fwd-progress">' + asciiBar(f2, 22) + '<span class="fwd-pct">' + (known ? (eq >= target ? "target cleared" : money0(target - eq) + " to go") : "account unavailable") + "</span></div>" +
      "</div>";
  }

  function accountModeBar() {
    const live = !!(S.accounts && S.accounts.ok);
    return '<div class="sig-foot acct-switch" style="margin-bottom:8px">' +
      '<span class="kappa">ACCOUNT</span>' +
      '<button class="btn' + (S.acctView === "ITB" ? " active" : "") + '" data-av="ITB">ITB</button>' +
      '<button class="btn' + (S.acctView === "NAIL" ? " active" : "") + '" data-av="NAIL">NAIL (3×)</button>' +
      '<span class="faint" style="margin-left:auto">' + (live ? "live paper" : "reading…") + "</span></div>";
  }

  function bindAccountModes(el) {
    $$("[data-av]", el).forEach((b) => b.addEventListener("click", () => {
      const v = b.dataset.av === "NAIL" ? "NAIL" : "ITB";
      if (v === S.acctView) return;
      S.acctView = v;
      save(KEY.acct, v);
      renderAccount();
    }));
  }

  function accountMeta(n) {
    const val = (name) => {
      const a = n && n.ok && n.accounts ? n.accounts[name] : null;
      return name + " " + (a && a.ok ? money0(a.equity) : "—");
    };
    return val("ITB") + " · " + val("NAIL");
  }

  function renderAccount() {
    const el = $("#p-account");
    if (!el) return;
    if (!S.accounts) {
      el.innerHTML = accountModeBar() + '<div class="skeleton">reading accounts…</div>';
      bindAccountModes(el);
      META("account", "LOADING");
      loadAccounts(false);
      return;
    }
    if (!S.accounts.ok) {
      el.innerHTML = accountModeBar() +
        '<div class="mid neg">unavailable</div>' +
        '<div class="faint small">' + esc((S.accounts.error || "").slice(0, 120)) + "</div>" +
        '<div style="margin-top:8px"><button class="btn" id="acct-btn">retry</button></div>' +
        accountMilestone(null);
      bindAccountModes(el);
      const b = $("#acct-btn"); if (b) b.addEventListener("click", () => loadAccounts(true));
      META("account", "ACCOUNTS ERROR");
      return;
    }

    const n = S.accounts;
    const name = S.acctView === "NAIL" ? "NAIL" : "ITB";
    const a = (n.accounts || {})[name];
    const broker = (n.broker && n.broker.label) || "ALPACA · PAPER · 2 ACCTS";
    if (!a || !a.ok) {
      el.innerHTML = accountModeBar() +
        '<div class="eyebrow">BROKER · <b>' + esc(broker) + "</b></div>" +
        '<div class="mid neg">unavailable</div>' +
        '<div class="faint small">' + esc(((a && a.error) || "account missing").slice(0, 120)) + "</div>" +
        '<div style="margin-top:8px"><button class="btn" id="acct-btn">retry</button></div>' +
        accountMilestone(null);
      bindAccountModes(el);
      const b = $("#acct-btn"); if (b) b.addEventListener("click", () => loadAccounts(true));
      META("account", accountMeta(n));
      return;
    }

    const eq = Number(a.equity), cash = Number(a.cash), bpw = Number(a.buying_power);
    const chg = Number.isFinite(Number(a.day_pnl)) ? Number(a.day_pnl) : null;
    const statusCls = a.status === "ACTIVE" && !a.trading_blocked ? "pos" : "amber";
    const statusTxt = a.trading_blocked ? "BLOCKED" : (a.status || "—");
    el.innerHTML = accountModeBar() +
      '<div class="eyebrow">BROKER · <b>' + esc(broker) + "</b></div>" +
      '<div class="mid bright num">' + money(eq) + "</div>" +
      '<div class="faint small">equity' + (chg == null ? "" : ' · <span class="' + sgn(chg) + '">' + (chg >= 0 ? "+" : "−") + money(Math.abs(chg)) + " today</span>") + "</div>" +
      simNote(a) +
      '<hr class="hr-dot">' +
      '<div class="kv"><span class="k">cash</span><span class="v">' + money(cash) + "</span></div>" +
      '<div class="kv"><span class="k">status</span><span class="v ' + statusCls + '">' + esc(statusTxt) + " · BP " + money0(bpw) + "</span></div>" +
      '<div class="kv"><span class="k">shorting</span><span class="v ' + (a.shorting_enabled ? "pos" : "dim") + '">' + (a.shorting_enabled ? "enabled" : "disabled") + "</span></div>" +
      '<div style="display:flex;align-items:center;gap:8px;margin-top:7px;flex-wrap:wrap"><button class="btn" id="acct-btn">refresh</button>' +
      '<span class="faint" style="font-size:9px">' + esc(tstr(a.as_of || n.fetched_et)) + " ET</span>" +
      '<span class="faint" style="font-size:9px;margin-left:auto">…' + esc(a.account_last4 || "—") + "</span></div>" +
      accountMilestone(eq);
    bindAccountModes(el);
    const b = $("#acct-btn");
    if (b) b.addEventListener("click", async () => {
      b.disabled = true;
      b.textContent = "refreshing…";
      await loadAccounts(true);
    });
    META("account", accountMeta(n));
  }

  /* total return: live accounts since day 1, plus the 2024–26 backtest (long-only and long + short) */
  async function loadReturns(force) {
    if (S.ret && !force && Date.now() - S.ret.at < 30 * 60 * 1000) return;
    if (S.retLoading) return;
    S.retLoading = true;
    try {
      const [lo, ls] = await Promise.all([api("/api/nail?view=long-only&start_cap=2000"), api("/api/nail?view=long%2Bshort&start_cap=2000")]);
      S.ret = { lo, ls, at: Date.now() };
    } catch (e) { S.ret = { error: String(e), at: Date.now() }; }
    S.retLoading = false;
    if (S.tab === "desk") renderReturns();
  }
  function renderReturns() {
    const el = $("#p-returns");
    if (!el) return;
    if (!S.ret) loadReturns(false);
    const signed = (v) => v == null || !Number.isFinite(Number(v)) ? "—" : '<span class="' + sgn(v) + '">' + (v >= 0 ? "+" : "−") + money(Math.abs(v)) + "</span>";
    const spct = (v, d) => v == null || !Number.isFinite(Number(v)) ? "—" : '<span class="' + sgn(v) + '">' + pct(v, d == null ? 2 : d) + "</span>";
    // live
    const acc = (S.accounts && S.accounts.ok && S.accounts.accounts) || {};
    const live = ["ITB", "NAIL"].map((k) => acc[k]).filter((a) => a && a.ok);
    let liveRows = "";
    if (live.length) {
      const tot = live.reduce((o, a) => ({ base: o.base + Number(a.baseline), eq: o.eq + Number(a.equity), sim: o.sim + Number(a.simulated_pnl || 0) }), { base: 0, eq: 0, sim: 0 });
      const row = (name, base, eq, sim, cls) => "<tr" + (cls ? ' class="' + cls + '"' : "") + "><td class=\"l\">" + name + "</td><td>" + money(base) + "</td><td>" + money(eq) + "</td><td>" + signed(eq - base) + "</td><td>" + spct(base ? eq / base - 1 : null) + "</td><td>" + (sim ? signed(sim) : '<span class="dim">—</span>') + "</td></tr>";
      liveRows = live.map((a) => row(a.name === "NAIL" ? "NAIL (3×)" : a.name, Number(a.baseline), Number(a.equity), Number(a.simulated_pnl || 0))).join("") +
        row("BOTH", tot.base, tot.eq, tot.sim, "hl");
    }
    // backtest
    const bt = (v) => (S.ret && S.ret[v] && S.ret[v].ok) ? S.ret[v] : null;
    const lo = bt("lo"), ls = bt("ls");
    const legRow = (k, label) => {
      const a = lo && lo.legs[k], b = ls && ls.legs[k];
      const tr = (x) => x ? x.final_equity / 2000 - 1 : null;
      return "<tr><td class=\"l\">" + label + "</td>" +
        "<td>" + spct(tr(a), 0) + "</td><td>" + (a ? pct(a.cagr, 0) : "—") + "</td><td>" + (a ? Number(a.sharpe).toFixed(2) : "—") + "</td><td class=\"neg\">" + (a ? pct(a.max_drawdown, 0) : "—") + "</td><td>" + (a ? (a.win * 100).toFixed(0) + "%" : "—") + "</td><td>" + (a ? a.n_trades : "—") + "</td>" +
        "<td class=\"sep\">" + spct(tr(b), 0) + "</td><td>" + (b ? pct(b.cagr, 0) : "—") + "</td><td>" + (b ? Number(b.sharpe).toFixed(2) : "—") + "</td><td class=\"neg\">" + (b ? pct(b.max_drawdown, 0) : "—") + "</td></tr>";
    };
    const first = lo && lo.legs.ITB && lo.legs.ITB.curve.length ? lo.legs.ITB.curve[0].date : "—";
    el.innerHTML = '<div class="ret-grid">' +
      '<section><div class="minihead">live paper accounts · since day 1</div>' +
        (liveRows ? '<table class="tbl"><thead><tr><th></th><th>start</th><th>equity</th><th>total $</th><th>total %</th><th>simulated</th></tr></thead><tbody>' + liveRows + "</tbody></table>"
                  : '<div class="skeleton">reading accounts…</div>') +
      "</section>" +
      '<section><div class="minihead">backtest · $2,000 · ' + esc(first) + " → " + esc((lo && lo.last_date) || "—") + " · ITB 2 / NAIL 5 bp per side</div>" +
        (lo || ls ? '<table class="tbl ret-bt"><thead><tr><th></th><th colspan="6">LONG-ONLY</th><th colspan="4" class="sep">LONG + SHORT</th></tr>' +
          "<tr><th></th><th>total</th><th>CAGR</th><th>Sharpe</th><th>max DD</th><th>win</th><th>trades</th><th class=\"sep\">total</th><th>CAGR</th><th>Sharpe</th><th>max DD</th></tr></thead><tbody>" +
          legRow("ITB", "ITB") + legRow("NAIL", "NAIL (3×)") + "</tbody></table>"
          : (S.ret && S.ret.error ? '<div class="no-data">' + esc(S.ret.error) + "</div>" : '<div class="skeleton">loading backtest…</div>')) +
        '<div class="faint small" style="margin-top:6px">backtest fills at the official 09:30 open, compounding; live expectation is about half.</div>' +
      "</section></div>";
    const nl = lo && lo.legs.NAIL;
    META("returns", live.length ? "LIVE " + live.map((a) => a.name + " " + pct(Number(a.equity) / Number(a.baseline) - 1, 2)).join(" · ") + (nl ? " · NAIL LONG-ONLY BT " + pct(nl.final_equity / 2000 - 1, 0) : "") : "LOADING");
  }

  /* sessions the desk missed (Mac off) are rebuilt from market data and added on top of broker equity */
  function simNote(a) {
    if (!a || !Number(a.simulated_pnl)) return "";
    const v = Number(a.simulated_pnl);
    return '<div class="faint small sim-note">incl. <span class="' + sgn(v) + '">' + (v >= 0 ? "+" : "−") + money(Math.abs(v)) +
      "</span> simulated · " + esc((a.simulated_days || []).join(", ")) + " · Mac was off · broker " + money(a.broker_equity) + "</div>";
  }

  /* milestone */
  function renderMilestone() {
    const el = $("#p-milestone");
    if (!el) return;
    const a = S.account && S.account.account;
    const eq = a ? Number(a.equity) : null;
    const known = Number.isFinite(eq);
    const shortMin = (S.cfg && S.cfg.config && S.cfg.config.short_min_equity_usd) || 2000;
    const pdt = 25000;
    const f1 = known ? clamp(eq / shortMin, 0, 1) : 0;
    const f2 = known ? clamp(eq / pdt, 0, 1) : 0;
    const eqTxt = known ? money0(eq) : "$—";

    el.innerHTML =
      '<div class="eyebrow">SHORTS UNLOCK AT <b>' + money0(shortMin) + "</b></div>" +
      '<div class="mid ' + (f1 >= 1 ? "pos" : "bright") + '">' + (known ? Math.round(f1 * 100) + "%" : "—") + "</div>" +
      '<div class="fwd-progress">' + asciiBar(f1, 26) + '<span class="fwd-pct">' + eqTxt + "</span></div>" +
      '<div class="faint small">' + (known ? (f1 >= 1 ? "unlocked · auto mode can short" : money0(shortMin - eq) + " to go") : "query the broker to size this") + "</div>" +
      '<hr class="hr-dot">' +
      '<div class="eyebrow">NEXT · <b>$25,000</b></div>' +
      '<div class="fwd-progress">' + asciiBar(f2, 26) + '<span class="fwd-pct">' + Math.round(f2 * 100) + "%</span></div>" +
      '<div class="faint small">no pattern-day-trader cap · RKT sleeve unlocks</div>';
    META("milestone", known ? "EQUITY " + eqTxt : "EQUITY UNKNOWN");
  }

  /* timeline */
  function renderTimeline() {
    const el = $("#p-timeline");
    if (!el) return;
    const t = etNow();
    const open = marketOpenToday();
    const ns = nextStep(t.secs, open);

    let head;
    if (open) {
      head = '<div class="eyebrow">' + esc(dayLabel()) + ' · <b>NYSE OPEN</b></div>' +
        (ns ? '<div class="small" style="margin-bottom:6px">next <span class="amber">' + esc(ns.t.slice(0, 5)) + " " + esc(ns.label) + '</span> · <span class="countdown" data-target="' + ns.secs + '">in ' + hms(ns.secs - t.secs) + "</span></div>"
            : '<div class="small dim" style="margin-bottom:6px">all steps complete</div>');
    } else {
      head = '<div class="eyebrow">' + esc(dayLabel()) + ' · <b>MARKET CLOSED</b></div>' +
        '<div class="small" style="margin-bottom:6px">next session <span class="cyan">' + esc(dstr(S.now && S.now.next_session)) + "</span></div>";
    }

    const rows = STEPS.map((s) => {
      let mark = "·", cls = "";
      if (open) {
        if (t.secs > s.secs + 30) { mark = "✓"; cls = "done"; }
        else if (ns && ns.t === s.t) { mark = "→"; cls = "next"; }
      }
      const note = cls === "next" ? '<span class="countdown" data-target="' + s.secs + '">in ' + hms(s.secs - t.secs) + "</span>" : esc(s.note);
      return '<div class="tl-row ' + cls + '"><span class="tl-t">' + s.t.slice(0, 5) + '</span><span class="tl-mark">' + mark +
        '</span><span class="tl-label">' + esc(s.label) + '</span><span class="tl-note">' + note + "</span></div>";
    }).join("");

    el.innerHTML = head + '<div class="tl">' + rows + "</div>";
    META("timeline", open ? (ns ? "NEXT " + ns.t.slice(0, 5) + " ET" : "COMPLETE") : "CLOSED");
  }

  function updateTimelineLive() {
    const t = { secs: etNow().secs };
    $$(".countdown[data-target]").forEach((el) => {
      const left = +el.dataset.target - t.secs;
      if (left >= 0) { el.textContent = "in " + hms(left); el.classList.toggle("soon", left < 900); }
      else el.textContent = "passed";
    });
  }

  /* live equity */
  function renderLiveEq() {
    const el = $("#p-liveeq");
    if (!el) return;
    const rows = S.equity || [];
    if (rows.length >= 1) {
      const pts = rows.map((r) => ({ x: r.day || r.ts_et, y: Number(r.equity) }));
      lineChart(el, pts, {
        note: "ITB · live journal",
        holdoutStart: null,
        fmtY: (v) => money0(v),
        fmtX: (v) => isoShort(v),
        tooltip: (p) => esc(p.x) + "  " + money(p.y),
      });
      const last = pts[pts.length - 1].y;
      META("liveeq", "LAST " + money(last) + " · " + nowStamp());
    } else {
      el.innerHTML = '<div class="no-data tall"><div class="flat">───────────────<b>◆</b>───────────────</div>' +
        "<b>no day_end_equity rows yet</b>" +
        "<span>the chart wakes up after the first 10:30 exit.</span>" +
        '<span>source · live/zb_itb/journal.jsonl</span></div>';
      META("liveeq", "AWAITING FIRST CLOSE");
    }
  }

  /* NAIL live account, same curve as the nail tab */
  function renderDeskNailEq() {
    const el = $("#p-naileq-desk");
    if (!el) return;
    const acct = S.accounts && S.accounts.ok ? (S.accounts.accounts || {}).NAIL : null;
    if (!acct) {
      if (S.accounts && !S.accounts.ok) {
        el.innerHTML = '<div class="no-data">' + esc(S.accounts.error || "accounts unavailable") + "</div>";
        META("naileq-desk", "ACCOUNT ERROR");
      } else {
        el.innerHTML = '<div class="skeleton">reading NAIL account…</div>';
        META("naileq-desk", "LOADING");
        loadAccounts(false);
      }
      return;
    }
    if (!acct.ok) {
      el.innerHTML = '<div class="no-data">' + esc(acct.error || "NAIL unavailable") + "</div>";
      META("naileq-desk", "ACCOUNT ERROR");
      return;
    }
    const pts = (acct.curve || []).map((p) => ({ x: p.date, y: Number(p.equity) }));
    if (!pts.length) {
      el.innerHTML = '<div class="chart-empty"><b>no account history</b></div>';
      META("naileq-desk", "AWAITING FIRST CLOSE");
      return;
    }
    lineChart(el, pts, {
      note: "NAIL · live account",
      holdoutStart: null,
      fmtY: (v) => money0(v),
      fmtX: (v) => isoShort(v),
      tooltip: (p) => esc(dstr(p.x)) + "  " + money(p.y) + "  " + (p.y - acct.baseline >= 0 ? "+" : "−") + money(Math.abs(p.y - acct.baseline)),
    });
    META("naileq-desk", money(acct.equity) + " · " + (acct.total_pnl >= 0 ? "+" : "−") + money(Math.abs(acct.total_pnl)));
  }

  /* tape */
  function renderTape() {
    const el = $("#p-tape");
    if (!el) return;
    const rows = (S.journal || []).slice(0, 80);
    if (!rows.length) {
      el.innerHTML = '<div class="tape-empty">journal is empty · no live events recorded yet</div>';
      META("tape", "EMPTY");
      return;
    }
    el.innerHTML = '<div class="tape">' + rows.map((r) => {
      const ev = String(r.event || "event");
      const sev = /fallback|warn|skip|sim_/i.test(ev) ? "warn" : /error|kill|fail|exception/i.test(ev) ? "err" : /enter|exit|equity|fill/i.test(ev) ? "ok" : "info";
      let who = "";
      if (r.from_broker || r.to_broker) who = (r.from_broker || "?") + " → " + (r.to_broker || "?");
      else if (r.symbol) who = r.symbol + (r.qty != null ? " × " + r.qty : "");
      else if (r.reason) who = "—";
      else who = Object.keys(r).filter((k) => !["ts_et", "day", "event"].includes(k)).slice(0, 2).join(" · ") || "—";
      const msg = r.reason || r.detail || r.error || r.note ||
        Object.entries(r).filter(([k]) => !["ts_et", "day", "event", "from_broker", "to_broker"].includes(k))
          .map(([k, v]) => k + "=" + (typeof v === "object" ? JSON.stringify(v) : v)).join("  ");
      return '<div class="tape-row sev-' + sev + '" data-json="' + encodeURIComponent(JSON.stringify(r)) + '">' +
        '<span class="tape-t">' + tstr(r.ts_et) + '</span><span class="tape-ev">' + esc(ev) + "</span>" +
        '<span class="tape-who">' + esc(who) + '</span><span class="tape-msg">' + esc(String(msg).slice(0, 300)) + "</span></div>";
    }).join("") + "</div>";
    $$(".tape-row", el).forEach((r) => r.addEventListener("click", () => {
      try { openModal("JOURNAL EVENT", JSON.parse(decodeURIComponent(r.dataset.json))); } catch (e) { /* ignore */ }
    }));
    META("tape", rows.length + " EVENTS · " + nowStamp());
  }

  /* research tl;dr — the whole page before the detail */
  function renderResearchTldr() {
    const el = $("#p-tldr");
    if (!el) return;
    const e = S.edge;
    if (!e || e.empty) { el.innerHTML = legBar() + '<div class="skeleton">reading the evidence…</div>'; bindLegBar(el); META("tldr", "LOADING"); return; }

    const hold = e.holdout || {};
    const erasAll = e.eras_all || {};
    const c13 = (e.costs || []).find((c) => Number(c.bp) === 13) || {};
    const drop = e.drop10 || {};
    const f = ((S.fwd && S.fwd.strategies) || []).find((s) => s.name === (S.leg === "NAIL" ? "zb_nail" : "zb_itb")) || {};
    const n = Number(f.n || 0), final = Number(f.final_n || 250);
    const t2 = (v) => (v == null || Number.isNaN(Number(v))) ? "—" : Number(v).toFixed(2);
    const pct = (v) => (v == null || Number.isNaN(Number(v))) ? "—" : (v >= 0 ? "+" : "−") + Math.abs(Number(v) * 100).toFixed(1) + "%";
    const grade = (t, m) => (m == null ? "pending" : Number(m) <= 0 ? "fail" : Number(t) >= 2 ? "pass" : "warn");
    const chip = (label, value, cls) => '<span class="tldr-chip ' + cls + '"><span>' + esc(label) + "</span><b>" + esc(value) + "</b></span>";
    const book = (S.btLo && Number.isFinite(Number(S.btLo.cagr)) && Number.isFinite(Number(S.btLo.sharpe)) && Number.isFinite(Number(S.btLo.max_drawdown)))
      ? " The long-only book runs " + pct(S.btLo.cagr) + " CAGR, Sharpe " + Number(S.btLo.sharpe).toFixed(2) + ", " + pct(S.btLo.max_drawdown) + " max drawdown."
      : "";

    const headline = n === 0
      ? "The sample is strong. The proof is empty."
      : Number(f.cum_net_pct) < 0
        ? "The forward tape is underwater. The kill line is the only question."
        : "The forward tape is collecting. Nothing has been proven yet.";

    const body = (S.leg === "NAIL" ? "NAIL is the 3× version of the same trade. " : "") +
      "The canonical 2024–26 " + legName() + " panel is " + bp(e.mean_bp) + " per trade net of " + rcost() + " bp/side, t " + t2(e.t) +
      " (n " + Number(e.n || 0) + ")." + book +
      " The long-history replication is " + bp(erasAll.mean_bp) +
      ", the holdout is " + bp(hold.mean_bp) + " at t " + t2(hold.t) +
      ", and at 13 bp/side the mean falls to " + bp(c13.mean_bp) +
      ". The forward record is the only clean arbiter.";

    const posture = n === 0
      ? "Trade the frozen size. Log the first outcome. Do not promote the model on backtest evidence."
      : Number(f.cum_net_pct) <= -8
        ? "The kill line is reached. Stand down; do not keep collecting."
        : "Let the 250-trade record decide. No re-tuning, no size increase.";

    el.innerHTML = legBar() +
      '<div class="tldr">' +
        '<div class="tldr-main">' +
          '<div class="tldr-head">' + esc(headline) + "</div>" +
          '<p class="tldr-copy">' + esc(body) + "</p>" +
        "</div>" +
        '<div class="tldr-side">' +
          '<div class="tldr-chips">' +
            chip("edge", bp(e.mean_bp), grade(e.t, e.mean_bp)) +
            chip("holdout", bp(hold.mean_bp), grade(hold.t, hold.mean_bp)) +
            chip("drop 10 best", bp(drop.mean_bp), grade(drop.t, drop.mean_bp)) +
            chip("long history", bp(erasAll.mean_bp), grade(erasAll.t, erasAll.mean_bp)) +
            chip("13 bp / side", bp(c13.mean_bp), "fail") +
            chip("forward", n + " / " + final, n === 0 ? "pending" : "info") +
          "</div>" +
          '<div class="tldr-call"><span>desk posture</span>' + esc(posture) + "</div>" +
        "</div>" +
      "</div>";
    bindLegBar(el);
    META("tldr", legName() + " · EDGE " + bp(e.mean_bp) + " · FORWARD " + n + " / " + final);
  }

  /* forward */
  function renderForward() {
    const el = $("#p-forward");
    if (!el) return;
    if (!S.fwd) { el.innerHTML = '<div class="skeleton">loading registry…</div>'; return; }
    if (!S.fwd.ok) { el.innerHTML = '<div class="no-data">forward registry unavailable · ' + esc(S.fwd.error || "") + "</div>"; return; }

    el.innerHTML = '<div class="fwd-grid">' + (S.fwd.strategies || []).map((s) => {
      const tag = s.kind === "live" ? '<span class="tag a">LIVE PAPER</span>'
        : !s.registered ? '<span class="tag r">NO SPEC</span>'
        : s.verdict === "passed" ? '<span class="tag g">PASSED</span>'
        : s.verdict === "failed" ? '<span class="tag r">FAILED</span>'
        : s.verdict === "killed" ? '<span class="tag r">KILLED</span>'
        : '<span class="tag a">PENDING</span>';
      const gate = s.gate || {};
      const cum = s.cum_net_pct == null ? "—" : (s.cum_net_pct >= 0 ? "+" : "−") + Math.abs(s.cum_net_pct).toFixed(2) + "%";
      const t = s.t == null ? "—" : Number(s.t).toFixed(2);
      const hit = s.hit == null ? "—" : (s.hit * 100).toFixed(1) + "%";
      return '<div>' +
        '<div class="fwd-head"><span class="fwd-id">' + esc(s.id) + '</span><span class="fwd-name">' + esc(s.label) + "</span>" + tag + "</div>" +
        '<div class="fwd-big"><span class="n num">' + s.n + '</span><span class="dim">/ ' + s.final_n + " trades</span></div>" +
        '<div class="fwd-progress">' + asciiBar(s.progress || 0, 30) + '<span class="fwd-pct">' + ((s.progress || 0) * 100).toFixed(1) + "%</span></div>" +
        '<div class="kv"><span class="k">cum net @ ' + s.cost_bp + 'bp</span><span class="v ' + (s.cum_net_pct > 0 ? "pos" : s.cum_net_pct < 0 ? "neg" : "dim") + '">' + cum + "</span></div>" +
        '<div class="kv"><span class="k">gross t-stat</span><span class="v">' + t + "</span></div>" +
        '<div class="kv"><span class="k">hit rate</span><span class="v">' + hit + "</span></div>" +
        '<div class="kv"><span class="k">kill switch</span><span class="v dim">' + esc(gate.kill || "—") + "</span></div>" +
        '<div class="fwd-gate" style="margin-top:7px">PASS · ' + esc(gate.pass || "—") + "</div>" +
        (s.first_decision ? '<div class="fwd-gate" style="color:var(--amber)">first decision · ' + esc(s.first_decision) + " 09:15 ET</div>" : "") +
        (s.registered_at ? '<div class="fwd-gate" style="margin-top:4px">registered ' + esc(String(s.registered_at).slice(0, 10)) + " · seq " + esc(s.seq) + "</div>" : "") +
        "</div>";
    }).join("") + "</div>";
    META("forward", "ITB + NAIL + RKT · PAPER ONLY");
  }

  /* costs */
  function renderCosts() {
    const el = $("#p-costs");
    if (!el) return;
    if (!S.edge) { el.innerHTML = '<div class="skeleton">computing sensitivity…</div>'; return; }
    if (!S.edge.ok) { el.innerHTML = '<div class="no-data">' + esc(S.edge.error || "unavailable") + "</div>"; return; }
    const e = S.edge;
    el.innerHTML =
      '<div class="minihead">net edge vs cost · bp/side</div>' +
      '<table class="tbl"><thead><tr><th>cost</th><th>mean</th><th>t</th><th>verdict</th></tr></thead><tbody>' +
      (e.costs || []).map((c) => {
        const hl = c.bp === rcost() ? "hl" : "";
        const ok = c.mean_bp > 0 && (c.t || 0) >= 1.65;
        return '<tr class="' + hl + '"><td class="l">' + c.bp + " bp</td><td>" + (c.mean_bp >= 0 ? "+" : "−") + Math.abs(c.mean_bp).toFixed(1) +
          ' bp</td><td>' + (c.t == null ? "—" : Number(c.t).toFixed(2)) + '</td><td class="' + (ok ? "pos" : c.mean_bp > 0 ? "amber" : "neg") + '">' + (ok ? "holds" : c.mean_bp > 0 ? "weak" : "gone") + "</td></tr>";
      }).join("") + "</tbody></table>" +
      '<div class="minihead">exit construction</div>' +
      '<table class="tbl"><thead><tr><th>entry print</th><th>mean</th><th>t</th></tr></thead><tbody>' +
      (e.exits || []).map((x) => '<tr><td class="l">' + esc(x.label) + "</td><td>" + (x.mean_bp >= 0 ? "+" : "−") + Math.abs(x.mean_bp).toFixed(1) + " bp</td><td>" + (x.t == null ? "—" : Number(x.t).toFixed(2)) + "</td></tr>").join("") +
      "</tbody></table>" +
      '<div class="minihead">tail dependence</div>' +
      '<div class="kv"><span class="k">drop the 10 best trades</span><span class="v">' + (e.drop10.mean_bp >= 0 ? "+" : "−") + Math.abs(e.drop10.mean_bp).toFixed(1) + " bp · t " + (e.drop10.t == null ? "—" : Number(e.drop10.t).toFixed(2)) + "</span></div>" +
      '<div class="kv"><span class="k">median trade</span><span class="v">' + (e.median_bp >= 0 ? "+" : "−") + Math.abs(e.median_bp).toFixed(1) + " bp</span></div>" +
      '<div class="minihead">sealed holdout · ' + esc(e.holdout.start) + " →</div>" +
      '<div class="kv"><span class="k">n</span><span class="v">' + e.holdout.n + "</span></div>" +
      '<div class="kv"><span class="k">mean</span><span class="v ' + (e.holdout.mean_bp > 0 ? "pos" : "neg") + '">' + (e.holdout.mean_bp >= 0 ? "+" : "−") + Math.abs(e.holdout.mean_bp).toFixed(1) + " bp</span></div>" +
      '<div class="kv"><span class="k">t-stat</span><span class="v">' + (e.holdout.t == null ? "—" : Number(e.holdout.t).toFixed(2)) + "</span></div>" +
      '<div class="faint small" style="margin-top:3px">positive, not significant — the forward record is the evidence that counts.</div>';
    META("costs", "COST " + rcost() + "BP · " + nowStamp());
  }

  /* robustness */
  function renderRobust() {
    const el = $("#p-robust");
    if (!el) return;
    if (!S.edge) { el.innerHTML = '<div class="skeleton">slicing 570 trades…</div>'; return; }
    if (!S.edge.ok) { el.innerHTML = '<div class="no-data">' + esc(S.edge.error || "unavailable") + "</div>"; return; }
    const e = S.edge;
    const sideRows = ["long", "short"].map((k) => {
      const s = e.sides[k];
      return '<tr><td class="l ' + (k === "long" ? "pos" : "neg") + '">' + s.label + "</td><td>" + s.n + "</td><td>" + (s.mean_bp >= 0 ? "+" : "−") + Math.abs(s.mean_bp).toFixed(1) + " bp</td><td>" + (s.t == null ? "—" : Number(s.t).toFixed(2)) + "</td></tr>";
    }).join("");

    const wdMax = Math.max.apply(null, e.weekdays.map((w) => Math.abs(w.mean_bp))) || 1;
    const wdRows = e.weekdays.map((w) => {
      const frac = Math.abs(w.mean_bp) / wdMax;
      return '<div style="display:grid;grid-template-columns:34px 1fr 62px 34px;gap:7px;align-items:center;padding:2px 0;font-size:10.5px">' +
        '<span class="dim">' + w.label + '</span><span class="bar tall">' + Array.from({ length: 22 }, (_, i) => '<i class="' + (i < Math.round(frac * 22) ? "on" : "") + '"></i>').join("") + "</span>" +
        '<span class="num ' + (w.mean_bp >= 0 ? "pos" : "neg") + '" style="text-align:right">' + (w.mean_bp >= 0 ? "+" : "−") + Math.abs(w.mean_bp).toFixed(1) + ' bp</span><span class="faint num" style="text-align:right">' + (w.t == null ? "—" : Number(w.t).toFixed(1)) + "</span></div>";
    }).join("");

    const qMax = Math.max.apply(null, e.quintiles.map((q) => Math.abs(q.mean_bp))) || 1;
    const qRows = e.quintiles.map((q) => {
      const frac = Math.abs(q.mean_bp) / qMax;
      return '<div style="display:grid;grid-template-columns:34px 1fr 62px;gap:7px;align-items:center;padding:2px 0;font-size:10.5px">' +
        '<span class="dim">' + q.label + '</span><span class="bar tall amber">' + Array.from({ length: 22 }, (_, i) => '<i class="' + (i < Math.round(frac * 22) ? "on" : "") + '"></i>').join("") + "</span>" +
        '<span class="num ' + (q.mean_bp >= 0 ? "pos" : "neg") + '" style="text-align:right">' + (q.mean_bp >= 0 ? "+" : "−") + Math.abs(q.mean_bp).toFixed(1) + " bp</span></div>";
    }).join("");

    const halves = (e.halves || []).slice(-8).reverse().map((h) =>
      '<tr><td class="l dim">' + h.label + "</td><td>" + h.n + "</td><td class='" + (h.mean_bp >= 0 ? "pos" : "neg") + "'>" + (h.mean_bp >= 0 ? "+" : "−") + Math.abs(h.mean_bp).toFixed(1) + " bp</td><td>" + (h.t == null ? "—" : Number(h.t).toFixed(2)) + "</td></tr>").join("");

    el.innerHTML =
      '<div class="minihead">direction</div>' +
      '<table class="tbl"><thead><tr><th>side</th><th>n</th><th>mean</th><th>t</th></tr></thead><tbody>' + sideRows + "</tbody></table>" +
      '<div class="minihead">weekday</div>' + wdRows +
      '<div class="minihead">signal magnitude · |m| quintiles</div>' + qRows +
      '<div class="minihead">half-year stability</div>' +
      '<table class="tbl"><thead><tr><th>period</th><th>n</th><th>mean</th><th>t</th></tr></thead><tbody>' + halves + "</tbody></table>";
    META("robust", "NET @ " + rcost() + "BP · " + nowStamp());
  }

  /* long history */
  function renderEras() {
    const el = $("#p-eras");
    if (!el) return;
    if (!S.edge) { el.innerHTML = '<div class="skeleton">reading long-history panel…</div>'; return; }
    if (!S.edge.ok || !S.edge.eras) { el.innerHTML = '<div class="no-data">long history unavailable</div>'; return; }
    const e = S.edge;
    el.innerHTML =
      (S.leg === "NAIL"
        ? '<div class="eyebrow">TLT PRE-MARKET → NAIL · 09:30→10:29</div>' +
          '<div class="faint small" style="margin-bottom:8px">' + esc(e.eras_note || "") + ' · Alpaca SIP 1m · pre-2020 NAIL bars are thin</div>'
        : '<div class="eyebrow">TLT GAP → BUILDER BASKET · 09:35→10:30</div>' +
          '<div class="faint small" style="margin-bottom:8px">independent vault bars · 3 bp/side · 2010 → 2026</div>') +
      '<table class="tbl"><thead><tr><th>era</th><th>n</th><th>mean</th><th>t</th></tr></thead><tbody>' +
      (e.eras || []).map((x) => '<tr><td class="l">' + esc(x.label) + "</td><td>" + x.n + "</td><td class='" + (x.mean_bp >= 0 ? "pos" : "neg") + "'>" + (x.mean_bp >= 0 ? "+" : "−") + Math.abs(x.mean_bp).toFixed(1) + " bp</td><td>" + (x.t == null ? "—" : Number(x.t).toFixed(2)) + "</td></tr>").join("") +
      (e.eras_all && e.eras_all.n ? '<tr class="hl"><td class="l">ALL</td><td>' + e.eras_all.n + "</td><td>" + (e.eras_all.mean_bp >= 0 ? "+" : "−") + Math.abs(e.eras_all.mean_bp).toFixed(1) + " bp</td><td>" + (e.eras_all.t == null ? "—" : Number(e.eras_all.t).toFixed(2)) + "</td></tr>" : "") +
      "</tbody></table>" +
      '<hr class="hr-dot">' +
      '<div class="kv"><span class="k">placebo · XLU / KRE / SPY</span><span class="v dim">≈ 0</span></div>' +
      '<div class="kv"><span class="k">cross-source · DHI LEN PHM TOL</span><span class="v pos">+20.5 to +22.6 bp</span></div>' +
      '<div class="kv"><span class="k">contract rolls</span><span class="v dim">no artifact</span></div>' +
      '<div class="faint small" style="margin-top:7px">The mechanism is older than the 2024–26 backtest. That is the prior; the forward record is the proof.</div>';
    META("eras", S.leg === "NAIL" ? "NAIL · 2017–2026 · REGIME SWITCH ON" : "2010–2026 · INDEPENDENT BARS");
  }

  /* risk */
  function renderRisk() {
    const el = $("#p-risk");
    if (!el) return;
    if (!S.edge) { el.innerHTML = '<div class="skeleton">computing risk…</div>'; return; }
    if (!S.edge.ok) { el.innerHTML = '<div class="no-data">' + esc(S.edge.error || "unavailable") + "</div>"; return; }
    const r = (S.edge.risk || {}).all || {};
    const lo = (S.edge.risk || {}).long_only || {};
    const cells = [
      ["cagr", pct(r.cagr), r.cagr >= 0 ? "pos" : "neg"],
      ["ann vol", pct(r.vol), "dim"],
      ["sharpe", r.sharpe == null ? "—" : Number(r.sharpe).toFixed(2), "bright"],
      ["sortino", r.sortino == null ? "—" : Number(r.sortino).toFixed(2), "bright"],
      ["max dd", pct(r.max_drawdown), "neg"],
      ["calmar", r.calmar == null ? "—" : Number(r.calmar).toFixed(1), "bright"],
      ["win rate", pct(r.win_rate), "dim"],
      ["profit factor", r.profit_factor == null ? "—" : Number(r.profit_factor).toFixed(2), "bright"],
      ["avg win", bp(r.avg_win_bp), "pos"],
      ["avg loss", bp(r.avg_loss_bp), "neg"],
      ["worst day", bp(r.worst_day_bp), "neg"],
      ["var 95", bp(r.var95_bp), "amber"],
      ["loss streak", (r.loss_streak || 0) + " trades", "dim"],
      ["dd duration", (r.dd_days || 0) + " days", "dim"],
      ["final $1k", money0(r.final_equity), "pos"],
    ];
    el.innerHTML =
      '<div class="stat-grid">' + cells.map(([k, v, cls]) =>
        '<div class="stat"><div class="sk">' + k + '</div><div class="sv ' + cls + '">' + esc(v) + "</div></div>").join("") + "</div>" +
      '<div class="minihead">long-only book · shorts disabled</div>' +
      '<div class="kv"><span class="k">CAGR</span><span class="v ' + (lo.cagr >= 0 ? "pos" : "neg") + '">' + pct(lo.cagr) + "</span></div>" +
      '<div class="kv"><span class="k">Sharpe</span><span class="v">' + (lo.sharpe == null ? "—" : Number(lo.sharpe).toFixed(2)) + "</span></div>" +
      '<div class="kv"><span class="k">max drawdown</span><span class="v neg">' + pct(lo.max_drawdown) + "</span></div>" +
      '<div class="faint small" style="margin-top:6px">calendar-filled · no-trade days = 0 · net @ ' + rcost() + "bp/side</div>";
    META("risk", "NET @ " + rcost() + "BP");
  }

  /* backtest equity */
  function renderBtEquity() {
    const el = $("#p-equity");
    if (!el) return;
    const b = bt();
    if (!b) { el.innerHTML = '<div class="skeleton">loading canonical trades…</div>'; return; }
    if (!b.ok) { el.innerHTML = '<div class="no-data">' + esc(b.error || "unavailable") + "</div>"; return; }
    const pts = (b.curve || []).map((p) => ({ x: p.date, y: p.equity }));
    if (!pts.length) { el.innerHTML = '<div class="no-data">no trades</div>'; return; }
    lineChart(el, pts, {
      note: legName() + " · NET @ " + rcost() + "BP/SIDE · " + (S.view === "long-only" ? "LONG-ONLY" : "LONG + SHORT") + " · $1,000",
      holdoutStart: "2026-08-11",
      fmtY: (v) => money0(v),
      fmtX: (v) => isoShort(v),
      tooltip: (p) => esc(dstr(p.x)) + "  " + money(p.y),
      kpis: "<span>CAGR <b class='" + (b.cagr >= 0 ? "pos" : "neg") + "'>" + pct(b.cagr) + "</b></span>" +
            "<span>SHARPE <b>" + Number(b.sharpe).toFixed(2) + "</b></span>" +
            "<span>MAXDD <b class='neg'>" + pct(b.max_drawdown) + "</b></span>" +
            "<span>END <b>" + money(b.final_equity) + "</b></span>",
    });
    META("equity", b.n_trades + " TRADES · " + b.start + " → " + b.end);
  }

  /* monthly */
  function renderMonthly() {
    const el = $("#p-monthly");
    if (!el) return;
    const b = bt();
    if (!b) { el.innerHTML = '<div class="skeleton">loading monthly…</div>'; return; }
    if (!b.ok) { el.innerHTML = '<div class="no-data">' + esc(b.error || "unavailable") + "</div>"; return; }
    const data = (b.monthly || []).map((m) => ({ label: m.month, value: m.pct / 100 }));
    if (!data.length) { el.innerHTML = '<div class="no-data">no monthly rows</div>'; return; }
    const pos = data.filter((d) => d.value > 0).length;
    const best = data.reduce((a, d) => d.value > a.value ? d : a, data[0]);
    const worst = data.reduce((a, d) => d.value < a.value ? d : a, data[0]);
    barChart(el, data, {
      note: "LOG RETURN PER MONTH · NET",
      fmtY: (v) => (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(0) + "%",
      tooltip: (d) => d.label + "  " + pct(d.value),
      kpis: "<span>POSITIVE <b>" + pos + "/" + data.length + "</b></span><span>BEST <b class='pos'>" + pct(best.value) + "</b></span><span>WORST <b class='neg'>" + pct(worst.value) + "</b></span>",
    });
    META("monthly", pos + "/" + data.length + " POSITIVE");
  }

  /* KPI */
  function renderKpi() {
    const el = $("#p-kpi");
    if (!el) return;
    const b = bt();
    if (!b) { el.innerHTML = '<div class="skeleton">loading stats…</div>'; return; }
    if (!b.ok) { el.innerHTML = '<div class="no-data">' + esc(b.error || "unavailable") + "</div>"; return; }
    const cells = [
      ["CAGR", pct(b.cagr), b.cagr >= 0 ? "pos" : "neg"],
      ["Sharpe", Number(b.sharpe).toFixed(2), "bright"],
      ["max DD", pct(b.max_drawdown), "neg"],
      ["win rate", pct(b.win_rate), "dim"],
      ["avg win", bp(b.avg_win_bp), "pos"],
      ["avg loss", bp(b.avg_loss_bp), "neg"],
      ["per trade", bp(b.per_trade_bp), "bright"],
      ["trades", String(b.n_trades), "dim"],
      ["final", money0(b.final_equity), "pos"],
    ];
    el.innerHTML =
      '<div class="view-toggle leg-toggle">' +
        '<button class="btn ' + (S.leg === "ITB" ? "on" : "") + '" data-leg="ITB">ITB</button>' +
        '<button class="btn ' + (S.leg === "NAIL" ? "on" : "") + '" data-leg="NAIL">NAIL (3×)</button>' +
      "</div>" +
      '<div class="view-toggle">' +
        '<button class="btn ' + (S.view === "long-only" ? "on" : "") + '" data-view="long-only">long-only</button>' +
        '<button class="btn ' + (S.view === "all" ? "on" : "") + '" data-view="all">long + short</button>' +
      "</div>" +
      '<div class="stat-grid">' + cells.map(([k, v, cls]) =>
      '<div class="stat"><div class="sk">' + k + '</div><div class="sv ' + cls + '">' + esc(v) + "</div></div>").join("") + "</div>" +
      '<div class="minihead">book</div>' +
      '<div class="kv"><span class="k">view</span><span class="v">' + (S.view === "long-only" ? "long-only" : "long + short") + "</span></div>" +
      '<div class="kv"><span class="k">period</span><span class="v">' + esc(b.start) + " → " + esc(b.end) + "</span></div>" +
      '<div class="kv"><span class="k">cost</span><span class="v">' + rcost() + " bp/side</span></div>" +
      '<div class="kv"><span class="k">start capital</span><span class="v">$1,000</span></div>' +
      '<div class="faint small" style="margin-top:7px">canonical f3 trades · ' + legName() + ' · official daily open · 10:30 exit</div>';

    $$("[data-view]", el).forEach((btn) => btn.addEventListener("click", () => {
      S.view = btn.dataset.view;
      save(KEY.view, S.view);
      renderTab("research");
    }));
    bindLegBar(el);
    META("kpi", legName() + " · " + b.n_trades + " TRADES · " + S.view.toUpperCase());
  }

  /* leg compare: ITB vs NAIL, long + short vs long-only, side by side */
  function renderLegCompare() {
    const el = $("#p-cmp");
    if (!el) return;
    const c = S.cmp || {};
    const pick = (leg, view) => (c[leg] && c[leg][view]) || null;
    const cols = [
      { b: pick("ITB", "all"), name: "ITB", sub: "long + short" },
      { b: pick("ITB", "lo"), name: "ITB", sub: "long-only" },
      { b: pick("NAIL", "all"), name: "NAIL (3×)", sub: "long + short" },
      { b: pick("NAIL", "lo"), name: "NAIL (3×)", sub: "long-only" },
    ];
    if (cols.some((x) => !x.b)) {
      el.innerHTML = '<div class="skeleton">loading leg comparison…</div>';
      return;
    }
    const tone = (v) => (v > 0 ? "pos" : v < 0 ? "neg" : "dim");
    const row = (label, fn, cls) =>
      "<tr><td>" + label + "</td>" + cols.map((x) => {
        const r = fn(x.b);
        return "<td class='" + (cls ? (typeof cls === "function" ? cls(r.v) : cls) : tone(r.v)) + "'>" + esc(r.s) + "</td>";
      }).join("") + "</tr>";
    const num = (s, v) => ({ s: s, v: v });
    const html =
      '<table class="tbl cmp-tbl"><thead><tr><th></th>' +
        cols.map((x) => "<th>" + esc(x.name) + '<span class="mini"> · ' + esc(x.sub) + "</span></th>").join("") +
      "</tr></thead><tbody>" +
      row("CAGR", (b) => num(pct(b.cagr), b.cagr)) +
      row("sharpe", (b) => num(Number(b.sharpe).toFixed(2), b.sharpe), "bright") +
      row("max DD", (b) => num(pct(b.max_drawdown), b.max_drawdown), "neg") +
      row("win rate", (b) => num(pct(b.win_rate), b.win_rate), "dim") +
      row("avg win", (b) => num(bp(b.avg_win_bp), b.avg_win_bp), "pos") +
      row("avg loss", (b) => num(bp(b.avg_loss_bp), b.avg_loss_bp), "neg") +
      row("per trade", (b) => num(bp(b.per_trade_bp), b.per_trade_bp), "bright") +
      row("trades", (b) => num(String(b.n_trades), b.n_trades), "dim") +
      row("final", (b) => num(money0(b.final_equity), b.final_equity), "pos") +
      "</tbody></table>" +
      '<div class="faint small" style="margin-top:7px">canonical f3 trades · official daily open · 10:30 exit · ' +
        esc(cols[0].b.start) + " → " + esc(cols[0].b.end) + " · ITB " + S.cost + " bp/side · NAIL " + S.costNail + " bp/side</div>";
    el.innerHTML = html;
    META("cmp", "ITB · NAIL · LONG + SHORT · LONG-ONLY · " + cols[0].b.n_trades + " TRADES EACH");
  }

  /* journal */
  function renderJournal() {
    const el = $("#p-journal");
    if (!el) return;
    el.innerHTML =
      '<div class="j-filter"><span>filter</span><input id="j-filter" placeholder="event, broker, reason…" value="' + esc(S.journalFilter) + '"><span class="faint" id="j-count"></span></div>' +
      '<div id="j-rows"></div>';
    $("#j-filter").addEventListener("input", (e) => { S.journalFilter = e.target.value; renderJournalRows(); });
    renderJournalRows();
    META("journal", (S.journal || []).length + " EVENTS · " + nowStamp());
  }

  function renderJournalRows() {
    const host = $("#j-rows");
    if (!host) return;
    const q = S.journalFilter.toLowerCase();
    const rows = (S.journal || []).filter((r) => !q || JSON.stringify(r).toLowerCase().includes(q));
    const count = $("#j-count");
    if (count) count.textContent = rows.length + " / " + (S.journal || []).length + " rows";
    host.innerHTML = rows.length
      ? '<table class="tbl log-tbl"><thead><tr><th>time et</th><th>event</th><th>detail</th></tr></thead><tbody>' +
        rows.map((r) => {
          const detail = r.reason || r.error || r.note || JSON.stringify(r).slice(0, 400);
          const sev = /fallback|warn|skip/i.test(r.event || "") ? "amber" : /error|kill|fail/i.test(r.event || "") ? "neg" : /enter|exit|equity/i.test(r.event || "") ? "pos" : "dim";
          return '<tr data-json="' + encodeURIComponent(JSON.stringify(r)) + '"><td class="d">' + tstr(r.ts_et) + '</td><td class="' + sev + '">' + esc(r.event || "—") + '</td><td class="l dim">' + esc(String(detail).slice(0, 260)) + "</td></tr>";
        }).join("") + "</tbody></table>"
      : '<div class="no-data"><b>no matching rows</b><span>journal.jsonl is written by the trader on every decision and fill.</span></div>';

    $$("tbody tr", host).forEach((tr) => tr.addEventListener("click", () => {
      try { openModal("JOURNAL EVENT", JSON.parse(decodeURIComponent(tr.dataset.json))); } catch (e) { /* ignore */ }
    }));
  }

  /* config */
  function renderConfig() {
    const el = $("#p-config");
    if (!el) return;
    if (!S.cfg || !S.cfg.ok) { el.innerHTML = '<div class="skeleton">loading config…</div>'; return; }
    const cfg = S.cfg.config || {};
    const order = ["symbol", "side_mode", "max_fraction_of_equity", "max_notional_usd", "protective_stop_pct",
      "max_drawdown_pct", "signal_ready_et", "opg_deadline_et", "fill_check_et", "late_entry_cutoff_et",
      "exit_et", "failsafe_et", "short_min_equity_usd"];
    const rows = order.filter((k) => k in cfg).map((k) => {
      let v = cfg[k];
      if (k === "max_notional_usd" || k === "short_min_equity_usd") v = money0(v);
      if (k === "max_fraction_of_equity") v = (Number(v) * 100).toFixed(0) + "%";
      if (k === "protective_stop_pct" || k === "max_drawdown_pct") v = v + "%";
      return '<div class="kv"><span class="k">' + k + '</span><span class="v">' + esc(v) + "</span></div>";
    }).join("");
    el.innerHTML =
      '<div class="eyebrow">live/zb_itb/config.json</div>' + rows + '<hr class="hr-dot">' +
      '<div class="kv"><span class="k">broker</span><span class="v">' + esc(S.cfg.label || "—") + "</span></div>" +
      '<div class="kv"><span class="k">kill file</span><span class="v ' + (S.kill && S.kill.kill ? "neg" : "pos") + '">' + (S.kill && S.kill.kill ? "present" : "absent") + "</span></div>" +
      '<div class="kv"><span class="k">orders placed</span><span class="v dim">never — read-only ui</span></div>';
    META("config", (S.cfg.mode || "") + " · " + nowStamp());
  }

  /* clock */
  function renderClock() {
    const el = $("#p-clock");
    if (!el) return;
    const t = etNow();
    const open = marketOpenToday();
    const desc = {
      "09:15:00": "frozen rule computes ZB 09:00 close",
      "09:27:00": "market-on-open order must be in",
      "09:30:00": "ITB + NAIL open · positions live",
      "09:31:30": "confirm fill · retry if needed",
      "09:35:00": "no entries after this",
      "10:30:00": "flatten · write day_end_equity",
      "15:50:00": "failsafe force-flat before close",
    };
    el.innerHTML =
      '<div class="eyebrow">ALL TIMES <b>AMERICA/NEW_YORK</b></div>' +
      '<p class="faint small" style="margin-bottom:7px">now ' + t.label + " ET · " + (open ? "NYSE session" : "market closed") + "</p>" +
      STEPS.map((s) => {
        const done = open && t.secs > s.secs + 30;
        const next = open && !done && STEPS.find((x) => x.secs > t.secs) === s;
        return '<div class="tl-row ' + (done ? "done" : next ? "next" : "") + '" style="grid-template-columns:50px 15px 1fr">' +
          '<span class="tl-t">' + s.t.slice(0, 5) + '</span><span class="tl-mark">' + (done ? "✓" : next ? "→" : "·") + "</span>" +
          '<span class="tl-label">' + esc(desc[s.t] || s.label) + "</span></div>";
      }).join("") +
      '<div class="faint small" style="margin-top:7px">launchd runs `run` at 09:05 and `evaluate` after 10:35.</div>';
    META("clock", t.label + " ET");
  }

  /* spec */
  function renderSpec() {
    const el = $("#p-spec");
    if (!el) return;
    if (!S.fwd) { el.innerHTML = '<div class="skeleton">loading frozen spec…</div>'; return; }
    if (!S.fwd.ok) { el.innerHTML = '<div class="no-data">' + esc(S.fwd.error || "unavailable") + "</div>"; return; }
    el.innerHTML = '<div class="fwd-grid">' + (S.fwd.strategies || []).map((s) =>
      '<div><div class="fwd-head"><span class="fwd-id">' + esc(s.id) + '</span><span class="fwd-name">' + esc(s.label) + "</span></div>" +
      '<div class="spec-row"><span class="sk">rule</span><span class="sv">' + esc(s.rule || "—") + "</span></div>" +
      '<div class="spec-row"><span class="sk">pass gate</span><span class="sv">' + esc((s.gate || {}).pass || "—") + "</span></div>" +
      '<div class="spec-row"><span class="sk">kill</span><span class="sv red">' + esc((s.gate || {}).kill || "—") + "</span></div>" +
      '<div class="kv"><span class="k">final n</span><span class="v">' + (s.final_n || "—") + "</span></div>" +
      '<div class="kv"><span class="k">spec hash</span><span class="v" style="font-size:9.5px">' + esc((s.spec_hash || "—").slice(0, 18)) + "…</span></div>" +
      '<div class="kv"><span class="k">registered</span><span class="v dim">' + esc(String(s.registered_at || "—").slice(0, 19).replace("T", " ")) + "Z</span></div>" +
      "</div>").join("") + "</div>" +
      '<hr class="hr-dot">' +
      '<div class="minihead">files</div>' +
      '<div class="kv"><span class="k">journal</span><span class="v dim">live/zb_itb/journal.jsonl</span></div>' +
      '<div class="kv"><span class="k">signals</span><span class="v dim">live/zb_itb/signals.log</span></div>' +
      '<div class="kv"><span class="k">forward eval</span><span class="v dim">reports/forward/zb_itb_eval.json</span></div>' +
      '<div class="kv"><span class="k">backtest</span><span class="v dim">research/zb_itb/verify/f3_trades_canonical.csv</span></div>';
    META("spec", "REGISTRY + GATES");
  }

  /* ───────────────────────────── background ────────────────────── */
  function renderBackground() {
    const el = $("#p-background");
    if (!el) return;
    const b = S.bg;
    if (!b) { el.innerHTML = '<div class="skeleton">reading the model\u2019s working memory…</div>'; return; }
    if (!b.ok) {
      el.innerHTML = '<div class="no-data" style="margin:22px">background unavailable · ' + esc(b.error || "unknown error") + "</div>";
      META("background", "ERROR");
      return;
    }

    const t = b.today || {};
    const state = ["awaiting", "long", "short", "flat"].indexOf(t.phase) >= 0 ? t.phase : "flat";
    const stateWord = { awaiting: "WAITING", long: "LONG", short: "SHORT", flat: "FLAT" }[state];
    const px = (v) => (v == null || Number.isNaN(Number(v))) ? "—" : Number(v).toFixed(4);
    const mv = (v) => (v == null || Number.isNaN(Number(v))) ? "—" : (Number(v) >= 0 ? "+" : "−") + Math.abs(Number(v)).toFixed(1) + " bp";
    const gen = tstr(b.generated_et);

    const facts = [
      ["prev 16:00", px(t.p0)],
      ["09:00 print", px(t.p1)],
      ["overnight", mv(t.move_bp), t.move_bp == null ? "" : "amber"],
      ["next", t.next || "—"],
    ].map(([k, v, cls]) => '<div class="bg-fact"><span>' + esc(k) + '</span><b class="' + (cls || "") + '">' + esc(v) + "</b></div>").join("");

    const thesis = (b.thesis || []).map((p) => "<p>" + esc(p) + "</p>").join("");
    const research = (b.research || []).map((p) => "<p>" + esc(p) + "</p>").join("");
    const trace = (b.stream || []).map((s) =>
      '<div class="trace-row ' + esc(s.state || "") + '"><span class="trace-t">' + esc(s.t) + '</span><span class="trace-tag">' + esc(s.tag) +
      '</span><span class="trace-text">' + esc(s.text) + "</span></div>").join("");

    const actions = (b.actions || []).length
      ? '<div class="actions">' + b.actions.map((a) =>
          '<div class="action" data-json="' + encodeURIComponent(JSON.stringify(a.raw || a)) + '">' +
          '<span class="action-t">' + esc(a.t) + '</span><span class="action-ev">' + esc(a.event) + '</span>' +
          '<span class="action-text">' + esc(a.text) + "</span></div>").join("") + "</div>" +
        '<div class="actions-note">click a row for the raw journal record</div>'
      : '<div class="action-empty">No journal actions yet. The first decision window is today at 09:15 ET; until then the tape is intentionally empty.</div>';

    const math = (b.math || []).map((m) =>
      '<div class="math-row"><div class="math-k">' + esc(m.label) + '</div><div class="math-e">' + esc(m.expr) + "</div></div>").join("");

    const evidence = (b.evidence || []).map((e) =>
      '<div class="ledger-row ' + esc(e.grade || "info") + '"><span class="ledger-dot"></span><span class="ledger-label">' + esc(e.label) +
      '<span class="ledger-note">' + esc(e.note || "") + '</span></span><span class="ledger-value">' + esc(e.value) + "</span></div>").join("");

    const constraints = (b.constraints || []).map((c) =>
      '<div class="kv"><span class="k">' + esc(c.k) + '</span><span class="v">' + esc(c.v) + "</span></div>").join("");

    const risks = (b.risks || []).map((r) =>
      '<div class="risk ' + esc(r.grade || "info") + '"><div class="risk-head"><span class="risk-dot"></span><span class="risk-title">' + esc(r.title) +
      '</span></div><div class="risk-text">' + esc(r.text) + "</div></div>").join("");

    const questions = (b.questions || []).map((q) => "<li>" + esc(q) + "</li>").join("");
    const spec = b.spec || {};

    el.innerHTML =
      '<div class="bg-wrap">' +
        '<header class="bg-hero">' +
          '<div class="bg-kicker">model memory · generated <b>' + esc(gen) + " ET</b> · " + esc(t.date || "") + " · " + esc(t.weekday || "") + "</div>" +
          '<div class="bg-title"><span class="bg-state ' + state + '">' + stateWord + "</span><span>" + esc(t.headline || "—") + "</span></div>" +
          '<p class="bg-dek">' + esc(t.detail || "") + "</p>" +
          '<div class="bg-facts">' + facts + "</div>" +
        "</header>" +
        '<div class="bg-grid">' +
          '<div class="bg-main">' +
            '<section class="bg-sec"><h2>thesis</h2>' + thesis + "</section>" +
            '<section class="bg-sec"><h2>today\'s trace</h2><div class="trace">' + trace + "</div></section>" +
            '<section class="bg-sec"><h2>what it did</h2>' + actions + "</section>" +
          "</div>" +
          '<aside class="bg-rail">' +
            '<section class="bg-sec"><h2>the math</h2><div class="math-list">' + math + "</div></section>" +
            '<section class="bg-sec"><h2>evidence ledger</h2><div class="ledger">' + evidence + "</div></section>" +
            '<section class="bg-sec"><h2>research notes</h2>' + research + "</section>" +
          "</aside>" +
        "</div>" +
        '<div class="bg-bottom">' +
          '<section class="bg-sec bg-risks"><h2>what could break it</h2>' + risks + "</section>" +
          '<section class="bg-sec bg-questions"><h2>open questions</h2><ul class="qs">' + questions + "</ul></section>" +
          '<div class="bg-foot-col">' +
            '<section class="bg-sec bg-constraints"><h2>constraints</h2>' + constraints + "</section>" +
            '<section class="bg-sec bg-spec"><h2>frozen spec</h2>' +
              '<div class="kv"><span class="k">id</span><span class="v">' + esc(spec.id || "—") + " · seq " + esc(spec.seq == null ? "—" : spec.seq) + "</span></div>" +
              '<div class="kv"><span class="k">forward</span><span class="v ' + (spec.verdict === "passed" ? "pos" : "amber") + '">' + esc(spec.forward || "—") + " · " + esc(spec.verdict || "") + "</span></div>" +
              '<div class="kv"><span class="k">NAIL forward</span><span class="v amber">' + esc(spec.nail_forward || "—") + " · live paper</span></div>" +
              '<div class="spec-block"><div class="rule">' + esc(spec.rule || "—") + "</div>" +
                '<div class="gate">PASS <span class="a">' + esc(spec.pass_gate || "—") + '</span><br>KILL <span class="r">' + esc(spec.kill || "—") + "</span></div>" +
                '<div class="hash">' + esc(spec.hash || "—") + " · registered " + esc(String(spec.registered_at || "—").slice(0, 19)) + "Z</div>" +
              "</div>" +
            "</section>" +
          "</div>" +
        "</div>" +
      "</div>";

    $$(".action", el).forEach((row) => row.addEventListener("click", () => {
      try { openModal("JOURNAL EVENT", JSON.parse(decodeURIComponent(row.dataset.json))); } catch (e) { /* ignore */ }
    }));
    META("background", stateWord + " · " + gen + " ET");
  }

  /* ───────────────────────────── tab render ─────────────────────── */
  function renderTab(tab) {
    if (tab === "desk") {
      renderSignal(); renderAccount(); renderTimeline(); renderLiveEq(); renderDeskNailEq(); renderTape(); renderReturns();
    } else if (tab === "research") {
      renderResearchTldr(); renderForward(); renderCosts(); renderRobust(); renderEras(); renderBtEquity(); renderMonthly(); renderKpi(); renderLegCompare();
    } else if (tab === "nail") {
      renderNail();
    } else if (tab === "background") {
      renderBackground();
    }
  }

  /* ───────────────────────────── charts ─────────────────────────── */
  function chartShell(el, note, kpis) {
    el.innerHTML = "";
    if (note) { const n = document.createElement("div"); n.className = "chart-note"; n.textContent = note; el.appendChild(n); }
    if (kpis) { const k = document.createElement("div"); k.className = "chart-kpis"; k.innerHTML = kpis; el.appendChild(k); }
    const wrap = document.createElement("div");
    wrap.className = "chart-wrap";
    wrap.style.position = "absolute";
    wrap.style.inset = "0";
    const cv = document.createElement("canvas");
    wrap.appendChild(cv);
    el.appendChild(wrap);
    return { wrap, cv };
  }

  function drawFrame(ctx, w, h, pad, el) {
    const C = chartColors(el);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = withAlpha(C.bg, .16);
    ctx.fillRect(0, 0, w, h);
    ctx.font = font(10);
    ctx.textBaseline = "middle";
  }

  /* ITB vs NAIL: live Alpaca paper accounts, plus the research backtest view */
  async function loadNail(force) {
    if (S.nail && !force && S.nail.view === S.nailView) return;
    try { S.nail = await api("/api/nail?view=" + encodeURIComponent(S.nailView) + "&start_cap=2000"); S.nail.view = S.nailView; }
    catch (e) { S.nail = { ok: false, error: String(e) }; }
    if (S.tab === "nail") renderNail();
  }
  function nailModeBar() {
    return '<div class="sig-foot" style="margin-bottom:8px"><span class="kappa">MODE</span>' +
      '<button class="btn' + (S.nailMode === "live" ? " active" : "") + '" data-nm="live">live accounts</button>' +
      '<button class="btn' + (S.nailMode === "research" ? " active" : "") + '" data-nm="research">research</button>' +
      '<span class="faint">same ZB signal · independent ITB and NAIL paper accounts</span></div>';
  }
  function bindNailModes(ctl) {
    $$("[data-nm]", ctl).forEach((b) => b.addEventListener("click", () => {
      S.nailMode = b.dataset.nm;
      if (S.nailMode === "live" && !S.accounts) loadAccounts(true);
      renderNail();
    }));
  }
  function renderNail() {
    if (!S.nailMode) S.nailMode = "live";
    if (S.nailMode === "live") renderNailLive();
    else renderNailResearch();
  }
  function renderNailLive() {
    const ctl = $("#p-nailctl"); if (!ctl) return;
    const n = S.accounts;
    if (!n) {
      ctl.innerHTML = nailModeBar() + '<div class="skeleton">reading ITB + NAIL accounts…</div>';
      bindNailModes(ctl); loadAccounts(true); return;
    }
    if (!n.ok) { ctl.innerHTML = nailModeBar() + '<div class="no-data">' + esc(n.error || "accounts unavailable") + "</div>"; bindNailModes(ctl); return; }
    const A = n.accounts.ITB || { ok: false, error: "ITB missing" };
    const B = n.accounts.NAIL || { ok: false, error: "NAIL missing" };
    const val = (x, f) => (x && x.ok) ? f(x) : '<span class="neg">' + esc((x && x.error) || "unavailable") + "</span>";
    const signedMoney = (v) => v == null ? "—" : '<span class="' + sgn(v) + '">' + (v >= 0 ? "+" : "−") + money(Math.abs(v)) + "</span>";
    const signedPct = (v) => v == null ? "—" : '<span class="' + sgn(v) + '">' + (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(2) + "%</span>";
    const row = (k, f) => "<tr><td>" + k + "</td><td>" + val(A, f) + "</td><td>" + val(B, f) + "</td></tr>";
    const position = (x) => x.positions && x.positions.length
      ? x.positions.map((p) => (p.side || "") + " " + p.qty + " " + p.symbol).join("<br>")
      : '<span class="dim">flat</span>';
    const key = (x) => "ALPACA · PAPER · …" + (x.account_last4 || "—");
    ctl.innerHTML = nailModeBar() +
      '<table class="tbl"><thead><tr><th></th><th>ITB</th><th>NAIL (3×)</th></tr></thead><tbody>' +
      row("key", key) +
      row("equity", (x) => '<b>' + money(x.equity) + "</b>") +
      row("P&L", (x) => signedMoney(x.total_pnl) + " · " + signedPct(x.total_pnl_pct)) +
      row("today", (x) => signedMoney(x.day_pnl) + " · " + signedPct(x.day_pnl_pct)) +
      row("position", position) +
      row("open orders", (x) => x.open_orders) +
      row("status", (x) => '<span class="' + (x.status === "ACTIVE" && !x.trading_blocked ? "pos" : "neg") + '">' + esc(x.status || "—") + "</span>") +
      row("start", (x) => money(x.baseline)) +
      row("simulated", (x) => Number(x.simulated_pnl) ? signedMoney(x.simulated_pnl) + ' <span class="faint">' + esc((x.simulated_days || []).join(", ")) + " · Mac off</span>" : '<span class="dim">—</span>') +
      "</tbody></table>";
    bindNailModes(ctl);
    META("nailctl", "LIVE · ITB + NAIL · " + esc((n.broker && n.broker.label) || "ALPACA · PAPER"));
    const chart = (id, a, name) => {
      const el = $(id); if (!el) return;
      if (!a.ok) { el.innerHTML = '<div class="no-data">' + esc(a.error || "unavailable") + "</div>"; return; }
      const pts = (a.curve || []).map((p) => ({ x: p.date, y: p.equity }));
      lineChart(el, pts, { note: name + " · live · " + money(a.baseline), fmtY: (v) => money0(v), fmtX: (v) => isoShort(v),
        tooltip: (p) => esc(dstr(p.x)) + "  " + money(p.y) + "  " + (p.y - a.baseline >= 0 ? "+" : "−") + money(Math.abs(p.y - a.baseline)),
        kpis: "<span>EQUITY <b>" + money(a.equity) + "</b></span><span>P&L <b class='" + sgn(a.total_pnl) + "'>" + signedMoney(a.total_pnl) + "</b></span><span>TODAY <b class='" + sgn(a.day_pnl) + "'>" + signedMoney(a.day_pnl) + "</b></span>" });
    };
    chart("#p-itbeq", A, "ITB"); chart("#p-naileq", B, "NAIL");
    META("itbeq", A.ok ? money(A.equity) + " · " + ((A.total_pnl >= 0 ? "+" : "−") + money(Math.abs(A.total_pnl))) : "ERROR");
    META("naileq", B.ok ? money(B.equity) + " · " + ((B.total_pnl >= 0 ? "+" : "−") + money(Math.abs(B.total_pnl))) : "ERROR");
    const d = $("#p-naildaily");
    if (d) {
      const cell = (v) => v == null ? "—" : '<span class="' + sgn(v) + '">' + (v >= 0 ? "+" : "−") + "$" + Math.abs(v).toFixed(2) + "</span>";
      d.innerHTML = '<table class="tbl"><thead><tr><th>date</th><th>ITB equity</th><th>ITB P&L</th><th>NAIL equity</th><th>NAIL P&L</th><th>NAIL − ITB</th></tr></thead><tbody>' +
        (n.daily || []).map((r) => "<tr><td>" + esc(dstr(r.date)) + "</td><td>" + (r.ITB == null ? "—" : money(r.ITB)) + "</td><td>" +
          cell(r.ITB_pnl) + "</td><td>" + (r.NAIL == null ? "—" : money(r.NAIL)) + "</td><td>" + cell(r.NAIL_pnl) + "</td><td>" +
          cell((r.NAIL_pnl != null && r.ITB_pnl != null) ? r.NAIL_pnl - r.ITB_pnl : null) + "</td></tr>").join("") + "</tbody></table>";
      META("naildaily", "LIVE · LAST " + (n.daily || []).length + " SESSIONS · ITB + NAIL");
    }
  }
  function renderNailResearch() {
    if (!S.nailView) S.nailView = "long+short";
    const ctl = $("#p-nailctl");
    if (!S.nail || S.nail.view !== S.nailView) { loadNail(true); }
    const n = S.nail;
    if (!ctl) return;
    if (!n) { ctl.innerHTML = nailModeBar() + '<div class="skeleton">loading ITB vs NAIL…</div>'; bindNailModes(ctl); return; }
    if (!n.ok) { ctl.innerHTML = nailModeBar() + '<div class="no-data">' + esc(n.error || "unavailable") + "</div>"; bindNailModes(ctl); return; }
    const A = n.legs.ITB, B = n.legs.NAIL;
    const row = (k, f) => "<tr><td>" + k + "</td><td>" + f(A) + "</td><td>" + f(B) + "</td></tr>";
    const sgnp = (v) => '<span class="' + (v >= 0 ? "pos" : "neg") + '">' + pct(v) + "</span>";
    ctl.innerHTML = nailModeBar() +
      '<div class="sig-foot" style="margin-bottom:8px"><span class="kappa">VIEW</span>' +
      '<button class="btn' + (S.nailView === "long+short" ? " active" : "") + '" data-nv="long+short">long + short</button>' +
      '<button class="btn' + (S.nailView === "long-only" ? " active" : "") + '" data-nv="long-only">long-only</button>' +
      '<span class="faint">backtest-style fills at the official 09:30 open · ITB 2 bp/side, NAIL 5 bp/side · $2,000 start</span></div>' +
      '<table class="tbl"><thead><tr><th></th><th>ITB</th><th>NAIL (3×)</th></tr></thead><tbody>' +
      row("trades", (x) => x.n_trades) +
      row("avg per trade", (x) => (x.avg_bp >= 0 ? "+" : "") + x.avg_bp.toFixed(1) + " bp") +
      row("win rate", (x) => (x.win * 100).toFixed(1) + "%") +
      row("avg win / loss", (x) => "+" + x.avg_win_bp.toFixed(0) + " / " + x.avg_loss_bp.toFixed(0) + " bp") +
      row("yearly (CAGR)", (x) => sgnp(x.cagr)) +
      row("sharpe", (x) => x.sharpe.toFixed(2)) +
      row("max drawdown", (x) => '<span class="neg">' + pct(x.max_drawdown) + "</span>") +
      row("worst day", (x) => '<span class="neg">' + pct(x.worst_day) + "</span>") +
      row("$2,000 became", (x) => money(x.final_equity)) +
      "</tbody></table>";
    bindNailModes(ctl);
    $$("[data-nv]", ctl).forEach((b) => b.addEventListener("click", () => { S.nailView = b.dataset.nv; renderNail(); }));
    META("nailctl", (S.nailView === "long-only" ? "LONG-ONLY" : "LONG + SHORT") + " · THROUGH " + esc(n.last_date || "—"));
    const chart = (id, leg, name) => {
      const el = $(id); if (!el) return;
      const pts = (leg.curve || []).map((p) => ({ x: p.date, y: p.equity }));
      lineChart(el, pts, { note: name + " · $2,000", holdoutStart: "2026-08-11", fmtY: (v) => money0(v), fmtX: (v) => isoShort(v),
        tooltip: (p) => esc(dstr(p.x)) + "  " + money(p.y),
        kpis: "<span>CAGR <b class='" + (leg.cagr >= 0 ? "pos" : "neg") + "'>" + pct(leg.cagr) + "</b></span><span>SHARPE <b>" + leg.sharpe.toFixed(2) + "</b></span><span>MAXDD <b class='neg'>" + pct(leg.max_drawdown) + "</b></span>" });
    };
    chart("#p-itbeq", A, "ITB"); chart("#p-naileq", B, "NAIL");
    META("itbeq", money(A.final_equity)); META("naileq", money(B.final_equity));
    const d = $("#p-naildaily");
    if (d) {
      const cell = (v, isUsd) => v == null ? "—" : '<span class="' + (v > 0 ? "pos" : v < 0 ? "neg" : "dim") + '">' + (v > 0 ? "+" : v < 0 ? "−" : "") + (isUsd ? "$" + Math.abs(v).toFixed(2) : Math.abs(v).toFixed(2) + "%") + "</span>";
      d.innerHTML = '<table class="tbl"><thead><tr><th>date</th><th>bonds overnight</th><th>signal</th><th>ITB</th><th>ITB $</th><th>NAIL</th><th>NAIL $</th><th>NAIL − ITB</th></tr></thead><tbody>' +
        (n.daily || []).map((r) => "<tr><td>" + esc(dstr(r.date)) + "</td><td>" + (r.m_bp >= 0 ? "+" : "") + Number(r.m_bp).toFixed(0) + " bp</td><td>" +
          (r.d > 0 ? '<span class="pos">LONG</span>' : r.d < 0 ? '<span class="neg">SHORT</span>' : '<span class="dim">skip</span>') + "</td><td>" +
          cell(r.ITB_pct) + "</td><td>" + cell(r.ITB_usd, true) + "</td><td>" + cell(r.NAIL_pct) + "</td><td>" + cell(r.NAIL_usd, true) + "</td><td>" +
          cell((r.NAIL_usd != null && r.ITB_usd != null) ? r.NAIL_usd - r.ITB_usd : null, true) + "</td></tr>").join("") + "</tbody></table>";
      META("naildaily", "LAST " + (n.daily || []).length + " SESSIONS · $ ON A $2,000 ACCOUNT, NO COMPOUNDING");
    }
  }

  function lineChart(el, pts, opt) {
    opt = opt || {};
    if (!pts.length) { el.innerHTML = '<div class="chart-empty"><b>no data</b></div>'; return; }
    const { wrap, cv } = chartShell(el, opt.note, opt.kpis);
    let hover = -1;

    function draw() {
      const r = wrap.getBoundingClientRect();
      const w = Math.max(2, r.width), h = Math.max(2, r.height);
      const dpr = window.devicePixelRatio || 1;
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
      const ctx = cv.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawFrame(ctx, w, h, null, el);

      const pad = { l: 50, r: 12, t: 38, b: 20 };
      const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;
      const vals = pts.map((p) => p.y);
      let lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
      if (lo === hi) { lo -= 1; hi += 1; }
      const span = hi - lo;
      lo -= span * 0.06; hi += span * 0.06;
      const X = (i) => pad.l + (pts.length === 1 ? pw / 2 : (i / (pts.length - 1)) * pw);
      const Y = (v) => pad.t + (1 - (v - lo) / (hi - lo)) * ph;
      const C = chartColors(el);
      const accent = C.accent;

      // holdout shade
      if (opt.holdoutStart) {
        const i0 = pts.findIndex((p) => p.x >= opt.holdoutStart);
        if (i0 > 0 && i0 < pts.length) {
          const x0 = X(i0);
          ctx.fillStyle = withAlpha(C.amber, .055);
          ctx.fillRect(x0, pad.t, pad.l + pw - x0, ph);
          ctx.strokeStyle = withAlpha(C.amber, .38);
          ctx.setLineDash([3, 4]); ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(x0, pad.t); ctx.lineTo(x0, pad.t + ph); ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = withAlpha(C.amber, .9);
          ctx.font = font(9.5);
          ctx.textAlign = "right";
          ctx.fillText("SEALED HOLDOUT", pad.l + pw - 4, pad.t - 9);
        }
      }

      // grid
      ctx.strokeStyle = C.grid; ctx.lineWidth = 1;
      ctx.fillStyle = C.dim; ctx.font = font(10); ctx.textAlign = "right";
      for (let g = 0; g <= 4; g++) {
        const v = lo + (hi - lo) * (g / 4);
        const y = Y(v);
        ctx.beginPath(); ctx.setLineDash([2, 4]); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + pw, y); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillText(opt.fmtY ? opt.fmtY(v) : String(Math.round(v)), pad.l - 7, y);
      }

      // x labels
      ctx.textAlign = "center"; ctx.fillStyle = C.faint;
      const nlab = Math.min(5, pts.length);
      const seen = new Set();
      for (let i = 0; i < nlab; i++) {
        const idx = Math.round((i / Math.max(1, nlab - 1)) * (pts.length - 1));
        if (seen.has(idx)) continue;
        seen.add(idx);
        const x = X(idx);
        ctx.fillText(opt.fmtX ? opt.fmtX(pts[idx].x) : String(pts[idx].x), clamp(x, pad.l + 22, pad.l + pw - 22), h - 9);
      }

      // area
      const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + ph);
      grad.addColorStop(0, withAlpha(accent, .17));
      grad.addColorStop(1, withAlpha(accent, 0));
      ctx.beginPath();
      pts.forEach((p, i) => { const x = X(i), y = Y(p.y); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      ctx.lineTo(X(pts.length - 1), pad.t + ph); ctx.lineTo(X(0), pad.t + ph); ctx.closePath();
      ctx.fillStyle = grad; ctx.fill();

      // line
      ctx.beginPath();
      pts.forEach((p, i) => { const x = X(i), y = Y(p.y); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      ctx.strokeStyle = accent; ctx.lineWidth = 1.6;
      ctx.shadowColor = withAlpha(accent, .38); ctx.shadowBlur = 7;
      ctx.stroke(); ctx.shadowBlur = 0;

      // last point
      const lx = X(pts.length - 1), ly = Y(pts[pts.length - 1].y);
      ctx.beginPath(); ctx.arc(lx, ly, 3.2, 0, Math.PI * 2); ctx.fillStyle = accent; ctx.fill();
      ctx.beginPath(); ctx.arc(lx, ly, 6.5, 0, Math.PI * 2); ctx.strokeStyle = withAlpha(accent, .26); ctx.lineWidth = 1; ctx.stroke();

      // hover
      if (hover >= 0 && hover < pts.length) {
        const p = pts[hover], x = X(hover), y = Y(p.y);
        ctx.strokeStyle = withAlpha(C.bright, .18);
        ctx.setLineDash([2, 3]); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + ph); ctx.stroke(); ctx.setLineDash([]);
        ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fillStyle = C.bright; ctx.fill();
        const label = opt.tooltip ? opt.tooltip(p) : String(p.y);
        ctx.font = font(9.5);
        const tw = ctx.measureText(label).width + 14;
        const bx = clamp(x - tw / 2, pad.l, pad.l + pw - tw);
        const by = clamp(y - 28, pad.t, pad.t + ph - 20);
        ctx.fillStyle = withAlpha(C.tip, .97);
        ctx.strokeStyle = C.grid2; ctx.lineWidth = 1;
        ctx.fillRect(bx, by, tw, 18); ctx.strokeRect(bx, by, tw, 18);
        ctx.fillStyle = C.text; ctx.textAlign = "left"; ctx.textBaseline = "middle";
        ctx.fillText(label, bx + 7, by + 9);
        ctx.textBaseline = "middle";
      }
    }

    cv.addEventListener("mousemove", (e) => {
      const r = cv.getBoundingClientRect();
      const pad = { l: 50, r: 12 };
      const pw = r.width - pad.l - pad.r;
      const x = e.clientX - r.left;
      const idx = Math.round(((x - pad.l) / pw) * (pts.length - 1));
      hover = clamp(idx, 0, pts.length - 1);
      draw();
    });
    cv.addEventListener("mouseleave", () => { hover = -1; draw(); });
    if (window.ResizeObserver) new ResizeObserver(() => draw()).observe(wrap);
    draw();
  }

  function barChart(el, data, opt) {
    opt = opt || {};
    if (!data.length) { el.innerHTML = '<div class="chart-empty"><b>no data</b></div>'; return; }
    const { wrap, cv } = chartShell(el, opt.note, opt.kpis);
    let hover = -1;

    function draw() {
      const r = wrap.getBoundingClientRect();
      const w = Math.max(2, r.width), h = Math.max(2, r.height);
      const dpr = window.devicePixelRatio || 1;
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
      const ctx = cv.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawFrame(ctx, w, h, null, el);

      const pad = { l: 44, r: 12, t: 38, b: 20 };
      const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;
      const vals = data.map((d) => d.value);
      let lo = Math.min(0, Math.min.apply(null, vals));
      let hi = Math.max(0, Math.max.apply(null, vals));
      const span = (hi - lo) || 1;
      lo -= span * 0.06; hi += span * 0.06;
      const Y = (v) => pad.t + (1 - (v - lo) / (hi - lo)) * ph;
      const y0 = Y(0);
      const bw = Math.max(1, (pw / data.length) * 0.68);
      const C = chartColors(el);

      // grid
      ctx.strokeStyle = C.grid; ctx.fillStyle = C.dim; ctx.font = font(10); ctx.textAlign = "right";
      for (let g = 0; g <= 4; g++) {
        const v = lo + (hi - lo) * (g / 4);
        const y = Y(v);
        ctx.beginPath(); ctx.setLineDash([2, 4]); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + pw, y); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillText(opt.fmtY ? opt.fmtY(v) : String(Math.round(v)), pad.l - 6, y);
      }

      // zero line
      ctx.strokeStyle = C.grid2; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(pad.l, y0); ctx.lineTo(pad.l + pw, y0); ctx.stroke();

      data.forEach((d, i) => {
        const cx = pad.l + (i + 0.5) * (pw / data.length);
        const y = Y(d.value);
        const top = Math.min(y, y0), hgt = Math.max(1, Math.abs(y - y0));
        const col = d.value >= 0 ? C.accent : C.red;
        ctx.fillStyle = hover === i ? C.bright : col;
        ctx.globalAlpha = hover >= 0 && hover !== i ? 0.45 : 0.9;
        ctx.fillRect(cx - bw / 2, top, bw, hgt);
        ctx.globalAlpha = 1;
      });

      // x labels
      ctx.fillStyle = C.faint; ctx.textAlign = "center";
      const step = Math.ceil(data.length / 7);
      data.forEach((d, i) => {
        if (i % step) return;
        ctx.fillText(d.label, pad.l + (i + 0.5) * (pw / data.length), h - 9);
      });

      // hover
      if (hover >= 0 && hover < data.length) {
        const d = data[hover];
        const label = opt.tooltip ? opt.tooltip(d) : String(d.value);
        ctx.font = font(9.5);
        const tw = ctx.measureText(label).width + 14;
        const cx = pad.l + (hover + 0.5) * (pw / data.length);
        const bx = clamp(cx - tw / 2, pad.l, pad.l + pw - tw);
        const by = clamp(Y(d.value) - 26, pad.t, pad.t + ph - 20);
        ctx.fillStyle = withAlpha(C.tip, .97); ctx.strokeStyle = C.grid2; ctx.lineWidth = 1;
        ctx.fillRect(bx, by, tw, 18); ctx.strokeRect(bx, by, tw, 18);
        ctx.fillStyle = C.text; ctx.textAlign = "left"; ctx.textBaseline = "middle";
        ctx.fillText(label, bx + 7, by + 9);
      }
      // baseline reset
      ctx.textBaseline = "middle";
    }

    cv.addEventListener("mousemove", (e) => {
      const r = cv.getBoundingClientRect();
      const padL = 44, padR = 12;
      const pw = r.width - padL - padR;
      const rel = (e.clientX - r.left - padL) / pw;
      hover = clamp(Math.floor(rel * data.length), 0, data.length - 1);
      draw();
    });
    cv.addEventListener("mouseleave", () => { hover = -1; draw(); });
    if (window.ResizeObserver) new ResizeObserver(() => draw()).observe(wrap);
    draw();
  }

  /* legacy hook used by loadLive */
  function drawSparkInMilestone() { /* milestone uses bars, no-op */ }

  /* ───────────────────────────── boot ───────────────────────────── */
  function boot() {
    const savedTheme = load(KEY.theme, "glint");
    S.theme = THEMES.indexOf(savedTheme) >= 0 ? savedTheme : "glint";
    S.cost = load(KEY.cost, 2) || 2;
    S.leg = load(KEY.leg, "ITB") === "NAIL" ? "NAIL" : "ITB";
    S.costNail = load(KEY.costNail, 5) || 5;
    S.view = load(KEY.view, "long-only") === "all" ? "all" : "long-only";
    S.acctView = load(KEY.acct, "ITB") === "NAIL" ? "NAIL" : "ITB";
    S.tab = load(KEY.tab, "desk");
    if (TABS.indexOf(S.tab) < 0) S.tab = "desk";

    applyPaneThemes();
    setTheme(S.theme);
    applyOrder();
    applyPaneState();
    bindChrome();
    bindTabs();
    bindThemePicker();
    bindPaneControls();
    bindPrompt();
    startClock();

    // config first so chrome labels are right
    (async () => {
      await Promise.allSettled([loadConfig(), loadNow(), loadKill()]);
      renderChrome();
      setTab(S.tab, false);
      loadLive();
      loadResearch();
    })();

    setInterval(() => {
      loadJournal(); loadEquity(); loadKill();
      if (S.tab === "desk") renderTab("desk");
      else if (S.tab === "background") renderBackground();
    }, 30000);
    setInterval(() => { if (S.tab === "research") loadResearch(); }, 120000);
    setInterval(() => { loadBackground(); }, 300000);
    setInterval(() => { if (marketOpenToday()) fetchSignal(false); }, 300000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
