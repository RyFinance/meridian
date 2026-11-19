"""ZB → ITB trading desk dashboard (Streamlit).
    cd quant_v7 && PYTHONPATH=. .venv/bin/streamlit run live/zb_itb/dashboard/app.py
Reads only local files (journal, signal log, forward-test scoreboards, backtest trades). The broker is queried
only when you press "Refresh account"; nothing here places orders."""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
LIVE = ROOT / "live" / "zb_itb"
ET, PT = ZoneInfo("America/New_York"), ZoneInfo("America/Los_Angeles")
CFG = json.loads((LIVE / "config.json").read_text())

st.set_page_config(page_title="gapup Desk", page_icon="◐", layout="wide", initial_sidebar_state="expanded")

# ---------------------------------------------------------------- settings (sidebar) ----------------------------
ACCENTS = {"Harbor blue": "#2563c9", "Pine": "#1f7a5c", "Plum": "#7a3fb8", "Ember": "#c2410c", "Graphite": "#3f4756"}
with st.sidebar:
    st.markdown("### Desk settings")
    accent_name = st.selectbox("Accent", list(ACCENTS), index=0, key="accent")
    dark = st.toggle("Dark canvas", value=False, key="dark")
    compact = st.toggle("Compact cards", value=False, key="compact")
    st.markdown("#### Sections")
    show = {k: st.checkbox(k, value=True, key=f"sec_{k}") for k in
            ["Today", "Live P&L", "Model health", "Backtest reference", "Trade log", "Schedule"]}
    st.markdown("#### Backtest view")
    cost_bp = st.slider("Cost per side (bp)", 0.0, 10.0, 2.0, 0.5, key="cost")
    start_cap = st.number_input("Starting capital ($)", 100, 1_000_000, 1_000, 100, key="cap")
    view = st.radio("Strategy view", ["Long/short", "Long-only"], index=1, horizontal=True, key="view")
    st.caption("Settings are per-browser and change only this view, not the trader.")

A = ACCENTS[accent_name]
BG, PANEL, INK, MUTED, RULE = (("#0e1117", "#161b24", "#e7ebf2", "#97a1b2", "#262e3b") if dark else
                              ("#f5f6f8", "#ffffff", "#141a23", "#5d6878", "#e3e7ee"))
UP, DOWN, WARN = ("#3fbf86", "#ef7a63", "#e0b04c") if dark else ("#17804f", "#c0432c", "#a26b0f")
PAD = "14px 16px" if compact else "20px 22px"

st.markdown(f"""
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  .stApp {{ background: {BG}; color: {INK}; font-family: Manrope, -apple-system, Segoe UI, sans-serif; }}
  section[data-testid="stSidebar"] {{ background: {PANEL}; border-right: 1px solid {RULE}; }}
  h1, h2, h3, h4, p, label, span, div {{ color: {INK}; }}
  .block-container {{ padding-top: 1.6rem; max-width: 1280px; }}
  header[data-testid="stHeader"] {{ background: transparent; }}
  [data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton {{ display: none; }}
  section[data-testid="stSidebar"] * {{ color: {INK}; }}
  div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, input {{ background: {BG} !important; color: {INK} !important; border-color: {RULE} !important; }}
  .stCheckbox [data-testid="stCheckbox"] span, [role="checkbox"] {{ accent-color: {A}; }}
  .card {{ background: {PANEL}; border: 1px solid {RULE}; border-radius: 14px; padding: {PAD}; height: 100%; }}
  .kicker {{ font-family: 'JetBrains Mono', monospace; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: {MUTED}; }}
  .big {{ font-size: 1.9rem; font-weight: 800; letter-spacing: -.02em; font-variant-numeric: tabular-nums; margin-top: 2px; }}
  .sub {{ color: {MUTED}; font-size: .86rem; margin-top: 2px; }}
  .pill {{ display:inline-block; font-family:'JetBrains Mono',monospace; font-size:.72rem; padding:3px 10px; border-radius:999px; border:1px solid currentColor; }}
  .up {{ color: {UP}; }} .down {{ color: {DOWN}; }} .warn {{ color: {WARN}; }} .acc {{ color: {A}; }}
  .hero {{ display:flex; flex-wrap:wrap; align-items:flex-end; justify-content:space-between; gap:12px; margin-bottom: 6px; }}
  .hero h1 {{ font-size: 2.1rem; font-weight: 800; letter-spacing: -.03em; margin: 0; }}
  .bar {{ height: 8px; background: {RULE}; border-radius: 6px; overflow: hidden; margin-top: 10px; }}
  .bar > div {{ height: 100%; background: {A}; border-radius: 6px; }}
  .step {{ display:grid; grid-template-columns: 74px 1fr auto; gap:10px; align-items:center; padding:9px 0; border-bottom:1px solid {RULE}; font-size:.92rem; }}
  .step:last-child {{ border-bottom: 0; }}
  .t {{ font-family:'JetBrains Mono',monospace; color:{MUTED}; font-size:.82rem; }}
  .sig {{ font-size: 2.4rem; font-weight: 800; letter-spacing: -.03em; }}
  div[data-testid="stDataFrame"] {{ border: 1px solid {RULE}; border-radius: 12px; }}
  .stButton button {{ border-radius: 10px; border: 1px solid {A}; color: {A}; background: transparent; font-weight: 600; }}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- data loaders -----------------------------------
def jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


@st.cache_data(ttl=30)
def load_journal() -> pd.DataFrame:
    j = pd.DataFrame(jsonl(LIVE / "journal.jsonl"))
    if not j.empty:
        j["ts"] = pd.to_datetime(j.ts_et, utc=True).dt.tz_convert(ET); j["day"] = j.ts.dt.date
    return j


@st.cache_data(ttl=30)
def load_signals() -> pd.DataFrame:
    return pd.DataFrame(jsonl(LIVE / "signals.log"))


@st.cache_data(ttl=300)
def load_backtest() -> pd.DataFrame:
    f = ROOT / "research/zb_itb/verify/f3_trades_canonical.csv"
    if not f.exists():
        return pd.DataFrame()
    b = pd.read_csv(f, parse_dates=["date"]).set_index("date")
    b = b[b.d.notna() & (b.d != 0)]
    b["gross"] = b.g_off.where(b.entry_off.notna(), b.g_h1)
    return b


@st.cache_data(ttl=3600)
def regime_now(day_iso: str):
    try:
        from live.zb_itb.trader import regime_corr
        return regime_corr(dt.date.fromisoformat(day_iso), False)
    except Exception:  # noqa: BLE001
        return None


def scoreboard(name: str) -> dict:
    f = ROOT / f"reports/forward/{name}_eval.json"
    return json.loads(f.read_text()) if f.exists() else {}


def fmt_money(x: float) -> str:
    return f"${x:,.0f}" if abs(x) >= 100 else f"${x:,.2f}"


def card(kicker: str, big: str, sub: str = "", cls: str = "") -> str:
    return f'<div class="card"><div class="kicker">{kicker}</div><div class="big {cls}">{big}</div><div class="sub">{sub}</div></div>'


def fig_base(h=300):
    f = go.Figure()
    f.update_layout(height=h, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor=PANEL, plot_bgcolor=PANEL,
                    font=dict(family="Manrope, sans-serif", color=MUTED, size=12), showlegend=False,
                    xaxis=dict(gridcolor=RULE, zeroline=False), yaxis=dict(gridcolor=RULE, zeroline=False))
    return f


import sys; sys.path.insert(0, str(ROOT))
journal, signals, bt = load_journal(), load_signals(), load_backtest()
broker = (Path(ROOT / ".env.broker").read_text().split("=", 1)[1].strip() if (ROOT / ".env.broker").exists() else "alpaca").upper()
mode = "PAPER"
for line in ((ROOT / ".env.ibkr").read_text().splitlines() if broker == "IBKR" and (ROOT / ".env.ibkr").exists() else []):
    if line.startswith("IBKR_MODE="):
        mode = line.split("=", 1)[1].strip().upper() or "PAPER"
now_et = dt.datetime.now(ET)

# ---------------------------------------------------------------- equity source ----------------------------------
eq_rows = journal[journal.event == "day_end_equity"] if not journal.empty else pd.DataFrame()
acct = st.session_state.get("acct")
equity = float(acct["equity"]) if acct else (float(eq_rows.equity.iloc[-1]) if not eq_rows.empty else None)

# ---------------------------------------------------------------- header -----------------------------------------
kill = (LIVE / "KILL").exists()
_rc = regime_now(now_et.date().isoformat())
status_pill = (f'<span class="pill down">KILL switch on</span>' if kill else f'<span class="pill up">armed · {mode.lower()}</span>')
status_pill += (f'<span class="pill {"up" if _rc > CFG.get("regime_min_corr", 0.0) else "down"}">regime {"on" if _rc > CFG.get("regime_min_corr", 0.0) else "off"} · corr {_rc:+.2f}</span>' if _rc is not None else "")
st.markdown(f"""<div class="hero"><div><div class="kicker">Rates → housing · first-hour model</div><h1>gapup Desk</h1></div>
<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center"><span class="pill acc">{broker}</span>{status_pill}
<span class="pill" style="color:{MUTED}">{now_et:%a %d %b · %H:%M ET}</span></div></div>""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
short_min = CFG.get("short_min_equity_usd", 2000)
side_now = "Long-only" if (CFG["side_mode"] == "long_only" or (CFG["side_mode"] == "auto" and (equity or 0) < short_min)) else "Long + short"
with c1:
    st.markdown(card("Account equity", fmt_money(equity) if equity is not None else "—",
                     "from broker" if acct else ("last close-out" if equity else "press Refresh account")), unsafe_allow_html=True)
with c2:
    pnl_total = float(eq_rows.equity.iloc[-1]) - float(eq_rows.equity.iloc[0]) if len(eq_rows) > 1 else 0.0
    st.markdown(card("Live P&L since start", fmt_money(pnl_total) if len(eq_rows) > 1 else "—",
                     f"{len(eq_rows)} trading days logged", "up" if pnl_total > 0 else "down" if pnl_total < 0 else ""), unsafe_allow_html=True)
with c3:
    st.markdown(card("Mode", side_now, f"shorts unlock at {fmt_money(short_min)} · stop {CFG['protective_stop_pct']:.0f}%"), unsafe_allow_html=True)
with c4:
    prog = min((equity or 0) / short_min, 1.0) if short_min else 1.0
    nxt = "$25k: no day-trade limit + add RKT" if (equity or 0) >= short_min else f"{fmt_money(short_min)}: shorts on"
    st.markdown(f'<div class="card"><div class="kicker">Next milestone</div><div class="big acc">{prog * 100:.0f}%</div>'
                f'<div class="sub">{nxt}</div><div class="bar"><div style="width:{prog * 100:.0f}%"></div></div></div>', unsafe_allow_html=True)

b1, b2, _ = st.columns([1, 1, 4])
with b1:
    if st.button("Refresh account", key="refresh"):
        try:
            import sys; sys.path.insert(0, str(ROOT))
            from live.zb_itb.trader import get_broker
            st.session_state["acct"] = get_broker(False).account(); st.rerun()
        except Exception as e:  # noqa: BLE001
            st.warning(f"Couldn't reach {broker}: {str(e)[:160]}")
with b2:
    if st.button("Check today's signal", key="sig"):
        try:
            import sys; sys.path.insert(0, str(ROOT))
            from research.zb_itb.forward import signal
            st.session_state["sig_now"] = signal(now_et.date())
        except Exception as e:  # noqa: BLE001
            st.warning(f"Signal check failed: {str(e)[:160]}")
st.write("")

# ---------------------------------------------------------------- today ------------------------------------------
if show["Today"] or show["Schedule"]:
    l, r = st.columns([1.15, 1])
    today = journal[journal.day == now_et.date()] if not journal.empty else pd.DataFrame()
    if show["Today"]:
        with l:
            sig = st.session_state.get("sig_now")
            if sig is None and not signals.empty:
                last = signals.iloc[-1]; sig = last.get("signal") if last.get("day") == now_et.date().isoformat() else None
            d = (sig or {}).get("d", None)
            from research.forward import nyse
            open_today = nyse.is_session(now_et.date())
            word, cls = ({1: ("LONG ITB", "up"), -1: ("SHORT ITB", "down"), 0: ("NO TRADE", "")}.get(d, ("Waiting for 09:15 ET", "acc") if open_today else ("Market closed today", "")))
            if not open_today:
                nxt_day = nyse.next_session(now_et.date()); mv = f"Next run {nxt_day:%A %d %b} at 09:15 ET (06:15 PT)."
            if d == -1 and side_now == "Long-only":
                word, cls = "SHORT signal · skipped (long-only)", "warn"
            mv = mv if not open_today else ""
            if sig and sig.get("zb_p0_prev1600") and sig.get("zb_p1_0900"):
                mv = f"30-yr bond future {((sig['zb_p1_0900'] / sig['zb_p0_prev1600']) - 1) * 1e4:+.0f} bp overnight (16:00 → 09:00 ET)"
            st.markdown(f'<div class="card"><div class="kicker">Today\'s signal · {now_et:%A}</div><div class="sig {cls}">{word}</div>'
                        f'<div class="sub">{mv or "The signal is computed from ZB futures at 09:15 ET (06:15 PT)."}</div></div>', unsafe_allow_html=True)
    if show["Schedule"]:
        with r:
            ev = set(today.event) if not today.empty else set()
            steps = [("09:15", "Read overnight bond move", "signal" , {"entry_submitted", "skip"}),
                     ("09:27", "Market-on-open order", "order", {"entry_submitted"}),
                     ("09:31", "Confirm fill · place 3% stop", "fill", {"entry_filled", "stop_placed"}),
                     ("10:30", "Close position", "exit", {"close_submitted", "flat"}),
                     ("15:50", "Failsafe flatten", "failsafe", {"failsafe_ok", "failsafe_triggered"})]
            rows = ""
            for t, label, _, keys in steps:
                done = bool(ev & keys); skipped = "skip" in ev and t != "09:15"
                from research.forward import nyse as _n
                if not _n.is_session(now_et.date()):
                    rows += f'<div class="step"><span class="t">{t} ET</span><span>{label}</span><span class="pill" style="color:{MUTED}">market closed</span></div>'; continue
                tag = ('<span class="pill up">done</span>' if done else '<span class="pill" style="color:%s">skipped</span>' % MUTED if skipped
                       else '<span class="pill" style="color:%s">pending</span>' % MUTED)
                rows += f'<div class="step"><span class="t">{t} ET</span><span>{label}</span>{tag}</div>'
            st.markdown(f'<div class="card"><div class="kicker">Today\'s run</div>{rows}</div>', unsafe_allow_html=True)
    st.write("")

# ---------------------------------------------------------------- live P&L ---------------------------------------
if show["Live P&L"]:
    st.markdown("#### Live P&L")
    if len(eq_rows) > 1:
        e = eq_rows.set_index("ts").equity.astype(float)
        f = fig_base(260); f.add_trace(go.Scatter(x=e.index, y=e.values, mode="lines", line=dict(color=A, width=2.6), fill="tozeroy",
                                                   fillcolor=A + "1f")); f.update_yaxes(tickprefix="$")
        st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown(f'<div class="card"><div class="sub">No live trades yet. The first run is the next weekday at 09:15 ET; equity appears here after the 10:30 close.</div></div>', unsafe_allow_html=True)
    st.write("")

# ---------------------------------------------------------------- model health -----------------------------------
if show["Model health"]:
    st.markdown("#### Model health")
    h0, h1, h2, h3 = st.columns(4)
    rc = regime_now(now_et.date().isoformat()); on = rc is not None and rc > CFG.get("regime_min_corr", 0.0)
    with h0:
        st.markdown(card("Regime switch", ("ON" if on else "OFF") if rc is not None else "—",
                         (f"builders vs bonds, 60-day corr {rc:+.2f} · trades only above {CFG.get('regime_min_corr', 0.0):+.1f}" if rc is not None else "correlation unavailable; trader runs without the switch"),
                         "up" if on else "down" if rc is not None else ""), unsafe_allow_html=True)
    for col, (leg, label, key, mu, sd) in zip([h1, h2], [("zb_itb", "ITB forward test", "net_2bp", 22.4, 110.0), ("zb_rkt", "RKT forward test", "net_5bp", 45.3, 230.0)]):
        sb = scoreboard(leg); tr = [t for t in sb.get("trades", []) if key in t]
        x = np.array([t[key] for t in tr]) * 1e4
        if len(x) >= 2:
            llr = float(((mu / 2) * x - (mu / 2) ** 2 / 2).sum() / sd ** 2); A_ = math.log(19)
            verdict, cls = (("edge confirmed", "up") if llr >= A_ else ("edge gone", "down") if llr <= -A_ else ("still deciding", "acc"))
            body = f"{len(x)} trades · {x.mean():+.1f} bp avg · cum {x.sum() / 100:+.1f}%"
        else:
            verdict, cls, body = "collecting trades", "acc", "needs ~100 trades to see the full edge, ~400 to rule out zero"
        with col:
            st.markdown(card(label, verdict, body, cls), unsafe_allow_html=True)
    with h3:
        st.markdown(card("Backtest benchmark", f"+{bt.gross.mean() * 1e4 - 2 * cost_bp:.1f} bp" if not bt.empty else "—",
                         "per trade after your cost setting · 2024–26"), unsafe_allow_html=True)
    st.write("")

# ---------------------------------------------------------------- backtest reference -----------------------------
if show["Backtest reference"] and not bt.empty:
    st.markdown("#### Backtest reference")
    net = bt.gross - 2 * cost_bp / 1e4
    if view == "Long-only":
        net = net.where(bt.d > 0, 0.0)
    eq = start_cap * np.exp(net.cumsum()); yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / start_cap) ** (1 / yrs) - 1; dd = (eq / eq.cummax() - 1).min()
    trd = net[net != 0]
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(card("Backtest yearly", f"{cagr * 100:+.0f}%", f"{view.lower()} · live estimate about half", "up" if cagr > 0 else "down"), unsafe_allow_html=True)
    k2.markdown(card("Sharpe", f"{net.mean() / net.std() * np.sqrt(252):.2f}", f"max drawdown {dd * 100:.0f}%"), unsafe_allow_html=True)
    k3.markdown(card("Win rate", f"{(trd > 0).mean() * 100:.0f}%", f"avg win {trd[trd > 0].mean() * 1e4:+.0f} · avg loss {trd[trd < 0].mean() * 1e4:+.0f} bp"), unsafe_allow_html=True)
    k4.markdown(card(f"{fmt_money(start_cap)} would be", fmt_money(eq.iloc[-1]), f"{eq.index[0]:%b %Y} → {eq.index[-1]:%b %Y}"), unsafe_allow_html=True)
    g1, g2 = st.columns([1.6, 1])
    with g1:
        f = fig_base(300); f.add_trace(go.Scatter(x=eq.index, y=eq.values, mode="lines", line=dict(color=A, width=2.4)))
        f.add_vrect(x0=pd.Timestamp("2026-08-11"), x1=eq.index[-1], fillcolor=WARN, opacity=.12, line_width=0, annotation_text="sealed holdout",
                    annotation_font_color=MUTED, annotation_position="top left"); f.update_yaxes(tickprefix="$")
        st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False})
    with g2:
        mo = net.groupby(net.index.to_period("M")).sum() * 100
        f = fig_base(300); f.add_trace(go.Bar(x=[p.strftime("%b %y") for p in mo.index], y=mo.values,
                                              marker_color=[UP if v >= 0 else DOWN for v in mo.values]))
        f.update_yaxes(ticksuffix="%"); f.update_xaxes(showgrid=False, tickangle=-45, nticks=10)
        st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False})
    st.write("")

# ---------------------------------------------------------------- trade log ---------------------------------------
if show["Trade log"]:
    st.markdown("#### Trade log")
    if journal.empty:
        st.markdown(f'<div class="card"><div class="sub">The journal is empty. Every decision, order, fill and exit the trader makes is listed here.</div></div>', unsafe_allow_html=True)
    else:
        keep = journal[journal.event.isin(["entry_submitted", "entry_filled", "stop_placed", "close_submitted", "skip", "error", "day_end_equity", "kill_drawdown", "failsafe_triggered"])]
        show_df = pd.DataFrame({"time (ET)": keep.ts.dt.strftime("%a %d %b %H:%M"), "event": keep.event.str.replace("_", " "),
                                "detail": keep.apply(lambda r: r.get("reason") or (f"{r.get('side', '')} {r.get('qty', '')} @ {r.get('fill_price', r.get('ref_price', ''))}" if r.event in ("entry_submitted", "entry_filled") else r.get("equity", "") if r.event == "day_end_equity" else r.get("error", "")), axis=1)})
        st.dataframe(show_df.iloc[::-1], hide_index=True, use_container_width=True, height=min(420, 38 + 35 * len(show_df)))

st.markdown(f'<div class="sub" style="margin-top:28px">Rule: sign of the 30-year Treasury future from 16:00 to 09:00 ET → ITB from the 09:30 open to 10:30. '
            f'Backtest numbers are not guarantees. This page reads local logs and places no orders.</div>', unsafe_allow_html=True)
