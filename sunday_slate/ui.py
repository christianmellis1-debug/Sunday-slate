"""Safe HTML matchup cards and reusable dark-mode UI components."""
from __future__ import annotations

from html import escape
from urllib.parse import urlsplit
import re

import pandas as pd

from sunday_slate.metrics import CENTRAL, record_label, time_label
from sunday_slate.model import rationale
from sunday_slate.market import american_text

_STYLE = """
<style>
:root {--ss-panel:#121d30;--ss-edge:#27354e;--ss-muted:#9aa9bf;--ss-accent:#42c5e5;}
.stApp{background:radial-gradient(circle at 90% 0%,#142f48 0%,#0b1220 35%,#080e19 85%);color:#f4f7fb}
.block-container{max-width:1320px;padding-top:1.7rem;padding-bottom:5rem}
#MainMenu{visibility:hidden}
.ss-topline{font-weight:750;letter-spacing:.15em;font-size:.7rem;color:#64d6ec;text-transform:uppercase;margin-bottom:.4rem}
.ss-heading{font-weight:850;font-size:clamp(2.2rem,5vw,3.5rem);line-height:1.05;letter-spacing:-.04em;margin-bottom:.2rem}
.ss-subtitle{color:#a9bdd3;font-size:1rem;margin-bottom:1.4rem}
.ss-pulse{display:inline-block;background:#083946;border:1px solid #0b7684;color:#7be7ec;border-radius:100px;padding:.25rem .65rem;font-size:.76rem;font-weight:750;vertical-align:middle;margin-left:.5rem}
.ss-match{border:1px solid var(--ss-edge);background:linear-gradient(120deg,#142139,#0d1627);border-radius:15px;padding:1.05rem 1.2rem;margin:.45rem 0 .7rem;}
.ss-matchtop{display:flex;justify-content:space-between;gap:.7rem;align-items:center;color:var(--ss-muted);font-size:.78rem;margin-bottom:.95rem}
.ss-matchup{display:grid;grid-template-columns:1fr auto 1fr;gap:.6rem;align-items:center;text-align:center;}
.ss-team{min-width:0}.ss-team img{width:46px;height:46px;object-fit:contain;margin-bottom:.3rem}
.ss-team strong{display:block;font-size:1rem}.ss-team small{display:block;color:#9bb0c8;font-size:.8rem}
.ss-middle{font-weight:800;color:#aac3d5}.ss-score{font-size:1.5rem;color:#f5fbff}
.ss-bot{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;border-top:1px solid #23354d;margin-top:1rem;padding-top:.75rem;color:#a8bdd0;font-size:.79rem}
.ss-bot b{color:#e7f8ff}
.ss-section{color:#c3d7e7;font-weight:750;font-size:.92rem;margin-top:1.2rem;margin-bottom:.5rem}
.ss-foot{font-size:.78rem;color:#8ca5bb;margin-top:.6rem}
div[data-testid="stMetric"]{background:#132137;border:1px solid #28405a;border-radius:12px;padding:.8rem 1rem}
.ss-pick{border-top:1px solid #23354d;margin-top:.8rem;padding-top:.9rem}
.ss-picktop{display:flex;gap:.6rem;align-items:center;justify-content:space-between;flex-wrap:wrap}
.ss-pickname{color:#d8eef7;font-size:.9rem;font-weight:750}
.ss-prob{color:#69dfdd;font-weight:800;font-size:1.14rem}
.ss-picksmall{font-size:.75rem;color:#98acc6;margin-top:.45rem}
.ss-pickresult{color:#b9cadb;font-weight:700}
.ss-research{font-size:.78rem;color:#aebed1;border-top:1px solid #223751;margin-top:.7rem;padding-top:.55rem}
.ss-research summary{cursor:pointer;color:#79d6e8;font-weight:750;margin-bottom:.4rem}
.ss-mini-grid{display:grid;grid-template-columns:1fr 1fr;gap:.4rem .8rem;padding:.45rem 0}
.ss-chip{font-size:.72rem;color:#e3effd;background:#173044;border:1px solid #255c6b;border-radius:6px;padding:.2rem .4rem}
</style>
"""


def css() -> str:
    return _STYLE


def _safe_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme == "https" and parts.netloc.lower() in {"a.espncdn.com", "static.www.nfl.com", "github.com", "raw.githubusercontent.com"}:
            return value
    except ValueError:
        pass
    return None


def branding_map(teams: pd.DataFrame) -> dict[str, dict]:
    result = {}
    if teams is None or teams.empty:
        return result
    for row in teams.to_dict("records"):
        abbr = str(row.get("team_abbr", "")).strip()
        color = str(row.get("team_color", ""))
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            color = "#364f6b"
        result[abbr] = {"name": str(row.get("team_name") or abbr), "logo": _safe_url(row.get("team_logo_espn")), "color": color}
    return result


def _team(team: str, brands: dict[str, dict], profile: dict | None) -> str:
    data = brands.get(team, {})
    name = escape(str(data.get("name") or team))
    logo = data.get("logo")
    icon = f'<img alt="{name} logo" loading="lazy" src="{escape(logo, quote=True)}">' if logo else f'<div style="font-weight:850;font-size:1.5rem;color:#83d9ea">{escape(team)}</div>'
    return f'<div class="ss-team">{icon}<strong>{name}</strong><small>{escape(record_label(profile))}</small></div>'


def _num(profile: dict | None, key: str, suffix: str = "") -> str:
    n = (profile or {}).get(key)
    return f"{n:.1f}{suffix}" if isinstance(n, (int, float)) and pd.notna(n) else "—"


def game_card(game: pd.Series, brands: dict[str, dict], profiles: dict[str, dict]) -> str:
    home = str(game["home_team"]); away = str(game["away_team"])
    hp = profiles.get(home); ap = profiles.get(away)
    complete = bool(game["completed"])
    day = escape(time_label(game["kickoff_ct"]))
    middle = f'<span class="ss-score">{int(game["away_score"])} – {int(game["home_score"])}</span>' if complete else '<span>AT</span>'
    kickoff = game["kickoff_ct"]
    pending = pd.notna(kickoff) and kickoff <= pd.Timestamp.now(tz=CENTRAL)
    status = "Final" if complete else ("Result pending" if pending else "Scheduled")
    neutral = " · Neutral site" if str(game.get("location", "")).lower() == "neutral" else ""
    return f'''<article class="ss-match">
      <div class="ss-matchtop"><span>{day}</span><span>{status}{neutral}</span></div>
      <div class="ss-matchup">{_team(away, brands, ap)}<div class="ss-middle">{middle}</div>{_team(home, brands, hp)}</div>
      <div class="ss-bot"><span>Previous weeks: <b>PPG {_num(ap,"ppg")} vs {_num(hp,"ppg")}</b></span><span>Allowed: <b>{_num(ap,"opp_ppg")} vs {_num(hp,"opp_ppg")}</b></span><span>Pass YPG: <b>{_num(ap,"pass_ypg")} vs {_num(hp,"pass_ypg")}</b></span><span>Rush YPG: <b>{_num(ap,"rush_ypg")} vs {_num(hp,"rush_ypg")}</b></span></div>
    </article>'''


def prediction_panel(prediction: pd.Series) -> str:
    """Appends a research forecast to an existing matchup card (no betting tips)."""
    name = escape(str(prediction["predicted_winner"]))
    prob = float(prediction["pick_probability"])
    result = str(prediction["pick_result"])
    note = escape(rationale(prediction))
    result_text = f" · {escape(result)}" if result != "Pending" else " · Not final"
    return (f'<div class="ss-pick"><div class="ss-picktop">'
            f'<span class="ss-pickname">Model winner: {name}</span>'
            f'<span class="ss-prob">{prob:.1%} <span class="ss-pickresult">{result_text}</span></span>'
            f'</div><div class="ss-picksmall">{note}</div>'
            f'<div class="ss-picksmall">Research probability, not a sportsbook edge or guaranteed result.</div></div>')


def _fmt_num(value: object, digits: int = 3, percent: bool = False) -> str:
    try:
        v = float(value)
        if not pd.notna(v):
            return "Unavailable"
        return f"{v:+.{digits}f}" + ("%" if percent else "")
    except (TypeError, ValueError):
        return "Unavailable"


def matchup_panel(home_team: str, away_team: str, research: dict) -> str:
    """Accessible, optional pregame metrics without unsupported matchup claims."""
    h = research.get("home") or {}
    a = research.get("away") or {}
    hq = research.get("home_qb") or {}
    aq = research.get("away_qb") or {}
    items = [
        ("Offensive pass EPA / attempt", "pass_epa_per_att"),
        ("Opponent pass EPA allowed / attempt", "pass_epa_allowed_per_att"),
        ("Offensive rush EPA / carry", "rush_epa_per_carry"),
        ("Opponent rush EPA allowed / carry", "rush_epa_allowed_per_carry"),
        ("Completion % over expected", "pass_cpoe"),
    ]
    rows = []
    for title, col in items:
        hv = escape(_fmt_num(h.get(col), 2))
        av = escape(_fmt_num(a.get(col), 2))
        rows.append(f'<div>{escape(title)}</div><div><strong>{escape(away_team)}:</strong> {av} &nbsp; <strong>{escape(home_team)}:</strong> {hv}</div>')
    qb = []
    for team, info in ((away_team, aq), (home_team, hq)):
        if info:
            name = escape(str(info.get("name") or "Unknown"))
            qb.append(f'<div>{escape(team)} most-used recent passer: <strong>{name}</strong> · YPA {escape(_fmt_num(info.get("yards_per_attempt"), 2))} · Last played W{int(info.get("last_week", 0))}</div>')
        else:
            qb.append(f'<div>{escape(team)} recent passer: unavailable</div>')
    return (f'<details class="ss-research"><summary>Advanced matchup research (earlier weeks)</summary>'
            f'<div class="ss-mini-grid">{"".join(rows)}</div>{"".join(qb)}'
            '<div>Most-used passer is not a confirmed upcoming starter. EPA metrics are prior-game box-score proxies, not adjusted defensive ratings; injuries have not been verified. These statistics do not change model probabilities.</div>'
            '</details>')


def market_panel(home_team: str, away_team: str, market: dict | None, is_candidate: bool) -> str:
    if not market:
        return ('<details class="ss-research"><summary>Moneyline research</summary>'
                '<div>Two-sided reference odds unavailable; cannot calculate a meaningful edge.</div></details>')
    away = market["sides"]["away"]
    home = market["sides"]["home"]
    def line(team: str, side: dict) -> str:
        return (f'<div>{escape(team)} <strong>{escape(american_text(side["odds"]))}</strong>'
                f' · Model {side["model"]:.1%} · No-vig market {side["no_vig"]:.1%}'
                f' · Difference {side["edge"]:+.1%}</div>')
    flag = ('<span class="ss-chip">Experimental screen match · not recommended</span>' if is_candidate else
            '<span class="ss-chip">Does not meet experimental screen</span>')
    return (f'<details class="ss-research"><summary>Moneyline research · reference lines only</summary>'
            f'{flag}{line(away_team, away)}{line(home_team, home)}'
            '<div>Historical/untimestamped reference prices, not confirmed current DraftKings or executable odds. A positive model-to-market difference does not establish profitable value.</div>'
            '</details>')
