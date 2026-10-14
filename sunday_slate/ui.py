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
.ss-match.ss-watch{border-color:#e9b75b;background:linear-gradient(120deg,#28303a,#161f2f);box-shadow:inset 3px 0 0 #e9b75b,0 0 0 1px rgba(233,183,91,.10)}
.ss-watch-banner{display:flex;align-items:center;gap:.55rem;flex-wrap:wrap;margin:-.12rem 0 .88rem;font-size:.78rem}
.ss-watch-pill{display:inline-flex;gap:.28rem;align-items:center;background:#4e3819;border:1px solid #b99145;color:#ffde95;border-radius:999px;padding:.29rem .63rem;font-weight:850;letter-spacing:.055em}
.ss-watch-note{color:#f3d59a;font-weight:650}
.ss-watch-caveat{font-size:.72rem;color:#cbb88e;margin:.48rem 0 .05rem}
.ss-match.ss-ben-johnson{border-color:#58cdc2;box-shadow:inset 3px 0 0 #58cdc2}
.ss-ben-johnson-banner{margin:-.12rem 0 .85rem;display:flex;gap:.55rem;flex-wrap:wrap;align-items:center;font-size:.78rem}
.ss-ben-johnson-pill{background:#0b453e;border:1px solid #369d92;border-radius:999px;color:#b5fff2;padding:.29rem .65rem;font-weight:850;letter-spacing:.035em}
.ss-ben-johnson-note{color:#c9efe8;font-weight:620}
.ss-coach-row{display:flex;flex-wrap:wrap;gap:.45rem;align-items:center;margin:.15rem 0 .8rem;font-size:.77rem}
.ss-coach-flag{background:#3b2a58;color:#ecd9ff;border:1px solid #9d7dc9;border-radius:999px;padding:.28rem .6rem;font-weight:840}
.ss-dk-quote{font-size:.76rem;color:#9ee7df;margin:.3rem 0 .7rem;font-weight:600}

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
.ss-odds-table{width:100%;border-collapse:collapse;margin:.65rem 0;font-size:.78rem;color:#dce8f5}
.ss-odds-table th{color:#94aac0;font-size:.7rem;font-weight:600;text-align:right;padding:.3rem .25rem}
.ss-odds-table th:first-child,.ss-odds-table td:first-child{text-align:left}
.ss-odds-table td{text-align:right;padding:.42rem .25rem;border-top:1px solid #23354d}
.ss-card-details{border-top:1px solid #23354d;margin-top:.55rem;padding-top:.55rem;font-size:.78rem;color:#b7c8da}
.ss-card-details>summary{cursor:pointer;font-weight:650;color:#c5d9e9;padding:.2rem 0}
.ss-card-details[open]>summary{margin-bottom:.65rem}
.ss-source-note{font-size:.7rem;color:#91a5bc;line-height:1.5;overflow-wrap:anywhere;margin:.45rem 0}
.ss-card-details .ss-dk-quote{color:#c3d2e1;line-height:1.65;font-weight:400}
.ss-card-details .ss-dk-quote>div:has(>b){margin-top:.65rem}
.ss-card-details .ss-bot{margin-top:0;border-top:0;padding-top:0}
.ss-match .ss-pick{background:#142c3b;border:0;border-radius:9px;padding:.7rem .8rem;margin:.7rem 0}
.ss-match .ss-pickresult{font-size:.72rem}
@media(max-width:600px){.ss-match{padding:.85rem}.ss-team strong{font-size:.9rem}.ss-team img{width:38px;height:38px}.ss-matchtop{font-size:.7rem;margin-bottom:.7rem}.ss-odds-table{font-size:.74rem}}
.ss-team-odds{display:flex;justify-content:center;gap:.5rem;flex-wrap:wrap;color:#a9c0d3;font-size:.75rem;margin:.45rem 0}.ss-team-odds b{color:#e7f6ff}.ss-coach-summary{border-top:1px solid #263b52;margin-top:.7rem;padding-top:.6rem;font-size:.75rem;color:#b4c8d9}.ss-coach-summary>span{display:block;font-weight:600}.ss-coach-summary small{font-size:.68rem;margin:.25rem 0}.ss-coach-summary b{color:#79d9cd;font-size:.85rem}.ss-matchup{align-items:start}.ss-middle{align-self:start;padding-top:2.5rem}
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


def quote_time(quote):
    if quote.get("feed") == "Covers":
        updated = escape(str(quote.get("updated_at") or "unavailable"))
        return f"Via Covers · Source timestamp {updated} · may be delayed"
    if quote.get("feed") == "ESPN":
        fetched = escape(str(quote.get("fetched_at") or "unavailable"))
        return f"Via ESPN · Retrieved {fetched} · provider update time unavailable"
    updated = escape(str(quote.get("updated_at") or "unavailable"))
    return f"Via TheRundown · Quote updated {updated} · delayed pregame data"


def coach_ats_panel(coaches):
    if not coaches:
        return ""
    def fmt(r):
        if not r['games']:
            return "No qualifying games"
        pct = f" · {r['pct']:.1f}%" if r['pct'] is not None else ""
        return f"{r['wins']}–{r['losses']}–{r['pushes']}{pct} · {r['games']} games"
    parts = ['<details class="ss-card-details"><summary>More coach ATS splits</summary><div class="ss-dk-quote">']
    for c in coaches:
        parts.append(f"<div><b>{escape(c['team'])} · {escape(c['coach'] or 'Coach unavailable')}</b></div>")
        if not c['coach']:
            continue
        parts.append(f"<div>{escape(c['venue'])}: {fmt(c['venue_record'])}</div>")
        for sit in c['situations']:
            parts.append(f"<div>{escape(sit['role'])}: {fmt(sit['role_record'])}</div>")
            parts.append(f"<div><b>{escape(c['venue'])} {escape(sit['role'].lower())}: {fmt(sit['combined_record'])}</b></div>")
            parts.append(f"<div>{escape(sit['book'])} {sit['spread']:+g} defines this situation</div>")
        if not c['situations']:
            parts.append('<div>Favorite/underdog splits unavailable until a spread is available.</div>')
    parts.append(f"<div>{escape(coaches[0]['seasons'])} regular season · Head-coaching games across all teams · W–L–P · Pushes excluded from %. Historical nflverse reference spreads; not sportsbook-specific. Prior dates only.</div></div></details>")
    return ''.join(parts)


def game_card(game: pd.Series, brands: dict[str, dict], profiles: dict[str, dict],
              watch: dict | None = None, ben_johnson: dict | None = None,
              coaching: list[dict] | None = None, dk_quote: dict | None = None,
              fd_quote: dict | None = None, coach_ats: list | None = None) -> str:
    home = str(game["home_team"]); away = str(game["away_team"])
    hp = profiles.get(home); ap = profiles.get(away)
    complete = bool(game["completed"])
    day = escape(time_label(game["kickoff_ct"]))
    middle = f'<span class="ss-score">{int(game["away_score"])} – {int(game["home_score"])}</span>' if complete else '<span>AT</span>'
    kickoff = game["kickoff_ct"]
    pending = pd.notna(kickoff) and kickoff <= pd.Timestamp.now(tz=CENTRAL)
    status = "Final" if complete else ("Result pending" if pending else "Scheduled")
    neutral = " · Neutral site" if str(game.get("location", "")).lower() == "neutral" else ""
    flagged = isinstance(watch, dict) and "magnitude" in watch
    markers = list(coaching or ([] if ben_johnson is None else [ben_johnson]))
    special = bool(markers)
    highlight = (" ss-watch" if flagged else "") + (" ss-ben-johnson" if special else "")
    special_banner = ""
    if markers:
        parts = []
        for marker in markers:
            name = escape(str(marker.get("name") or "BEN JOHNSON SPECIAL"))
            points = float(marker["favored_by"])
            team = escape(str(marker.get("team") or ""))
            parts.append(f'<span class="ss-coach-flag">★ {name}</span>'
                         f'<span class="ss-ben-johnson-note">{team} favored by {points:g}'
                         ' · DraftKings only · experimental</span>')
        special_banner = '<div class="ss-coach-row">' + "".join(parts) + '</div>'
    sources = []
    quote = dk_quote if isinstance(dk_quote, dict) and dk_quote.get('source') == 'DraftKings' else None
    show_odds = not complete and not pending
    if show_odds:
        sources.append(f'<div class="ss-source-note">DraftKings: {quote_time(quote)}</div>' if quote else
                       '<div class="ss-source-note">DraftKings odds unavailable.</div>')
    def team_display(side, abbreviation, profile):
        markup = _team(abbreviation, brands, profile)
        odds_line = ""
        if show_odds:
            if quote:
                ml = american_text(quote.get(side + '_moneyline'))
                spread = quote.get(side + '_spread')
                handicap = '—' if spread is None else f'{float(spread):+g}'
                odds_line = f'<div class="ss-team-odds"><span>ML <b>{ml if ml != "Unavailable" else "—"}</b></span><span>Spread <b>{handicap}</b></span></div>'
            else:
                odds_line = '<div class="ss-team-odds">Odds unavailable</div>'
        markup = markup.replace('</strong>', '</strong>' + odds_line, 1)
        coach = next((c for c in (coach_ats or []) if c['team'] == abbreviation), None)
        if coach and coach.get('coach'):
            situation = next((v for v in coach['situations'] if v['book'] == 'DraftKings'), None)
            if situation:
                r = situation['combined_record']
                label = f"{coach['venue']} {situation['role'].lower()} ATS"
            else:
                r = coach['venue_record']
                label = f"{coach['venue']} ATS · spread unavailable"
            numbers = f"{r['wins']}–{r['losses']}" + (f"–{r['pushes']}" if r['pushes'] else '')
            pct = f" · {r['pct']:.1f}%" if r['pct'] is not None else ''
            value = numbers + pct if r['games'] else 'No qualifying games'
            summary = (f'<div class="ss-coach-summary"><span>{escape(coach["coach"])}</span>'
                       f'<small>{escape(label)}</small><b>{value}</b></div>')
            markup = markup[:-6] + summary + '</div>'
        return markup
    watch_banner = ""
    watch_caveat = ""
    if flagged:
        magnitude = float(watch["magnitude"])
        home_name = escape(str(brands.get(home, {}).get("name") or home))
        watch_banner = (
            '<div class="ss-watch-banner"><span class="ss-watch-pill">★ GAME TO WATCH</span>'
            f'<span class="ss-watch-note">Home Field Advantage · {home_name} · Magnitude {magnitude:.2f}</span></div>'
        )
        watch_caveat = (
            '<div class="ss-watch-caveat">Pregame statistical matchup flag · '
            'not a tier, betting recommendation, or change to Elo.</div>'
        )
    # Keep the card in one HTML block: blank optional banners plus indentation
    # make Markdown treat the matchup or appended prediction as a code block.
    return (
        f'<article class="ss-match{highlight}">'
        f'{special_banner}{watch_banner}'
        f'<div class="ss-matchtop"><span>{day}</span><span>{status}{neutral}</span></div>'
        f'<div class="ss-matchup">{team_display("away", away, ap)}<div class="ss-middle">{middle}</div>{team_display("home", home, hp)}</div>'
        f'<!--prediction-->'
        f'<details class="ss-card-details"><summary>Team stats</summary>'
        f'<div class="ss-bot"><span>Previous weeks: <b>PPG {_num(ap,"ppg")} vs {_num(hp,"ppg")}</b></span><span>Allowed: <b>{_num(ap,"opp_ppg")} vs {_num(hp,"opp_ppg")}</b></span><span>Pass YPG: <b>{_num(ap,"pass_ypg")} vs {_num(hp,"pass_ypg")}</b></span><span>Rush YPG: <b>{_num(ap,"rush_ypg")} vs {_num(hp,"rush_ypg")}</b></span></div>'
        f'</details>'
        f'{coach_ats_panel(coach_ats)}'
        f'<details class="ss-card-details"><summary>Odds sources &amp; notes</summary>{"".join(sources)}{watch_caveat}</details>'
        f'</article>'
    )


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
            f'</div><details class="ss-card-details"><summary>Prediction details</summary><div class="ss-picksmall">{note}</div>'
            f'<div class="ss-picksmall">Research probability, not a sportsbook edge or guaranteed result.</div></details></div>')


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
                '<div>DraftKings moneylines unavailable; no other sportsbook is substituted.</div></details>')
    away = market["sides"]["away"]
    home = market["sides"]["home"]
    def line(team: str, side: dict) -> str:
        return (f'<div>{escape(team)} <strong>{escape(american_text(side["odds"]))}</strong>'
                f' · Model {side["model"]:.1%} · No-vig market {side["no_vig"]:.1%}'
                f' · Difference {side["edge"]:+.1%}</div>')
    flag = ('<span class="ss-chip">Experimental screen match · not recommended</span>' if is_candidate else
            '<span class="ss-chip">Does not meet experimental screen</span>')
    return (f'<details class="ss-research"><summary>DraftKings pregame moneyline research</summary>'
            f'{flag}{line(away_team, away)}{line(home_team, home)}'
            '<div>DraftKings-only prices via a delayed pregame feed; not confirmed executable quotes. A positive model-to-market difference does not prove betting value.</div>'
            '</details>')


def injury_panel(home_team: str, away_team: str, reports: dict[str, list[dict]],
                 source_available: bool = True) -> str:
    if not source_available:
        return ('<details class="ss-research"><summary>Injury report · source unavailable</summary>'
                '<div>Current official player statuses are unverified. Missing data must not be treated as healthy.</div></details>')
    parts = []
    for team in (away_team, home_team):
        rows = reports.get(team, [])
        if rows:
            for item in rows:
                parts.append(f'<div><strong>{escape(team)} · {escape(str(item["name"]))}</strong> — '
                             f'{escape(str(item["status"]))} · Source updated: {escape(str(item["updated_utc"]))}</div>')
        else:
            parts.append(f'<div>{escape(team)}: No dated qualifying game-status entries from this feed (not a healthy designation).</div>')
    return ('<details class="ss-research"><summary>Game-week injury reports · informational</summary>'
            + "".join(parts) +
            '<div>Only source records dated before kickoff, for the selected game week, are included. Report status may change. Not included in model probabilities or verified starting lineups.</div></details>')



def qb_availability_panel(game_context: dict | None) -> str:
    """Transparent QB projections, reports and research-only replacement quality."""
    if not isinstance(game_context, dict) or not game_context.get("available"):
        return ('<details class="ss-research"><summary>Quarterback availability</summary>'
                '<div>Pregame QB context unavailable. The original Elo pick is unchanged.</div></details>')
    sections=[]
    for team, info in (game_context.get("teams") or {}).items():
        team_name=escape(str(team))
        expected=info.get("expected") or {}
        projected=info.get("projected") or {}
        backup=info.get("depth_backup") or {}
        previous=info.get("previous") or {}
        name=escape(str(expected.get("name") or "Unknown"))
        label=escape(str(info.get("classification") or "Unconfirmed"))
        sections.append(f'<div style="margin-top:.65rem"><strong>{team_name}: {name}</strong>'
                        f' · {label}</div>')
        if projected:
            sections.append('<div>Depth-chart QB1: '+escape(str(projected.get("name") or "?"))
                            +(' · as of '+escape(str(info["depth_asof"])) if info.get("depth_asof") else "")
                            +'</div>')
        if backup:
            sections.append('<div>Depth-chart alternate: '+escape(str(backup.get("name") or "?"))
                            +' (not a confirmed starter)</div>')
        if previous:
            sections.append('<div>Previous completed-game starter: '
                            +escape(str(previous.get("name") or previous.get("gsis_id") or "Unavailable"))
                            +' · week '+escape(str(previous.get("week")))+'</div>')
        injury=info.get("report")
        if injury:
            sections.append('<div>Source-dated QB game status: <strong>'
                            +escape(str(injury["status"]))+'</strong> · updated '
                            +escape(str(injury["updated_at"]))+'</div>')
        else:
            sections.append('<div>Dated QB injury status: unavailable (not a healthy designation).</div>')
        ann=info.get("confirmation")
        if ann:
            sections.append('<div>Owner-cited announcement: <a target="_blank" rel="noopener noreferrer" href="'
                            +escape(str(ann["source_url"]),quote=True)+'">NFL source</a> · dated '
                            +escape(str(ann["reported_at"]))
                            +' · supplied by app owner, not independently fact-checked.</div>')
        delta=info.get("replacement_delta_epa")
        if delta is not None:
            sections.append(f'<div><strong>Replacement performance difference: {float(delta):+.3f}'
                            ' passing EPA / dropback</strong> (estimated from earlier regular-season games, '
                            '150-play shrinkage; positive means the projected QB has performed better).</div>')
        elif info.get("change_indicated"):
            sections.append('<div>Replacement performance difference: unavailable '
                            '(insufficient earlier-game quarterback data).</div>')
        else:
            sections.append('<div>No verified change from the previously recorded starter '
                            'or no prior-season-local starter established.</div>')
    return ('<details class="ss-research"><summary>QB availability &amp; replacement quality · experimental</summary>'
            + "".join(sections)
            + '<div style="margin-top:.5rem">Depth charts are projections, not announcements. '
              'Source-dated injuries do not confirm a replacement. Owner-cited NFL announcements '
              'require a pregame timestamp but are not verified by this app. '
              'No quarterback status or replacement-quality estimate changes official Elo '
              'picks, probabilities or betting recommendations.</div></details>')
