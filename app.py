"""Sunday Slate Phase 1: schedules and pregame comparison dashboard.

Run: streamlit run app.py
No picks, probabilities, or gambling ROI are calculated in this phase.
"""
from __future__ import annotations

from datetime import datetime
from time import sleep
import os
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from sunday_slate import data as source_data
from sunday_slate.data import FeedError, load_schedules, load_teams, load_team_stats
from sunday_slate.metrics import default_week, season_options, stage_mask, weeks_for, with_kickoffs, team_profiles
from sunday_slate.ui import branding_map, css, game_card, prediction_panel, matchup_panel, market_panel, injury_panel, qb_availability_panel
from sunday_slate.model import predict_regular_season, summary, VERSION
from sunday_slate.market import analyze_moneyline, screen_side
from sunday_slate.matchup import team_advanced_profiles, qb_recent_profiles, matchup_research
from sunday_slate.injuries import reported_injuries
from sunday_slate.qb_availability import context as qb_confirmation_context, read_owner_confirmations
from sunday_slate.watch import game_watch_flags, STAT_COLUMNS as WATCH_STAT_COLUMNS
from sunday_slate.coach_flags import coaching_flags
from sunday_slate.coach_ats import coach_history, context as coach_ats_context, weekly_mismatch
from sunday_slate.espn_odds import ESPNFeedError, fetch_week, match_quotes
from sunday_slate.draftkings import DKFeedError, fetch_date, match_games, utc_dates
from sunday_slate.line_movement import load_history, change_for_game
from sunday_slate.shortlist import load_snapshot as load_shortlist_snapshot, shortlist as select_shortlist, snapshot_is_pregame
from sunday_slate.shortlist_ui import render_shortlist

st.set_page_config(page_title="Sunday Slate | NFL Football Analytics", page_icon="🏈", layout="wide", initial_sidebar_state="collapsed")
st.markdown(css(), unsafe_allow_html=True)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_schedule():
    return with_kickoffs(load_schedules())


@st.cache_data(ttl=86400, show_spinner=False)
def cached_brands():
    return load_teams()


@st.cache_data(ttl=3600, show_spinner=False)
def cached_team_stats(season: int):
    return load_team_stats(season)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_predictions(schedule: pd.DataFrame):
    return predict_regular_season(schedule)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_watch_flags(schedule: pd.DataFrame, team_stats: pd.DataFrame,
                       season: int, week: int):
    """Research marker only. Does not affect Elo or moneyline research."""
    return game_watch_flags(schedule, team_stats, season, week)


def _optional_feed(function_name: str, season: int):
    """Optional feed mismatch must never prevent the dashboard from loading."""
    loader = getattr(source_data, function_name, None)
    if not callable(loader):
        raise FeedError(f"{function_name} is not available in this deployed app version")
    return loader(season)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_player_stats(season: int):
    return _optional_feed("load_player_stats", season)


@st.cache_data(ttl=300, show_spinner=False)
def cached_espn_odds(season: int, week: int):
    return fetch_week(season, week)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_dk_snapshot(day: str, key: str):
    return fetch_date(day, key)


@st.cache_data(ttl=900, show_spinner=False)
def cached_line_history():
    # Branch-backed snapshots survive Streamlit restarts without paid storage.
    return load_history()


@st.cache_data(ttl=3600, show_spinner=False)
def cached_injuries(season: int):
    return _optional_feed("load_injury_reports", season)


@st.cache_data(ttl=7200, show_spinner=False)
def cached_qb_depth(season: int):
    return _optional_feed("load_qb_depth_charts", season)


st.markdown('<div class="ss-topline">SIXTY LABS · NFL INTELLIGENCE</div><div class="ss-heading">Sunday Slate <span class="ss-pulse">PHASE 3</span></div><div class="ss-subtitle">Every NFL game. One smarter Sunday. Pregame NFL probabilities, advanced football matchups, and transparent market research.</div>', unsafe_allow_html=True)

try:
    with st.spinner("Loading NFL schedule…"):
        all_games = cached_schedule()
except FeedError as exc:
    st.error("The NFL schedule feed is unavailable. The app has not fabricated a fallback slate.")
    with st.expander("Technical details"):
        st.code(str(exc))
    if st.button("Try loading again"):
        cached_schedule.clear()
        st.rerun()
    st.stop()

season_list = season_options(all_games)
if not season_list:
    st.warning("No NFL seasons were found in the schedule feed.")
    st.stop()

now = datetime.now(ZoneInfo("America/Chicago"))
default_season = now.year if now.year in season_list and now.month >= 7 else season_list[0]
season_index = season_list.index(default_season) if default_season in season_list else 0

selector1, selector2, selector3 = st.columns([1, 1, 2])
with selector1:
    season = st.selectbox("NFL season", season_list, index=season_index, format_func=lambda x: str(x))
with selector2:
    stage = st.selectbox("Season stage", ["REG", "POST"], format_func=lambda x: "Regular season" if x == "REG" else "Playoffs")
with selector3:
    weeks = weeks_for(all_games, season, stage)
    if not weeks:
        st.info("No games found for this season and stage.")
        st.stop()
    preferred_week = default_week(all_games, season, now, stage)
    selected = st.selectbox("Week", weeks, index=weeks.index(preferred_week) if preferred_week in weeks else 0,
                            key=f"week_{season}_{stage}",
                            format_func=lambda x: f"Week {x}" if stage == "REG" else f"Playoff round {x}")

slate = all_games[(all_games["season"] == season) & stage_mask(all_games, stage) & (all_games["week"] == selected)].copy()
slate = slate.sort_values(["kickoff_ct", "game_id"], na_position="last")
if slate.empty:
    st.info("No matchups in this slate.")
    st.stop()

played = int(slate["completed"].sum())
future = len(slate) - played
m1, m2, m3, m4 = st.columns(4)
m1.metric("Matchups", len(slate))
m2.metric("Completed", played)
m3.metric("Not final", future)
m4.metric("Season", f"{season}")

try:
    brands = branding_map(cached_brands())
except FeedError:
    brands = {}
    st.caption("Team logo feed unavailable. Team abbreviations will be shown instead.")

try:
    stats = cached_team_stats(season)
except FeedError:
    stats = pd.DataFrame()
    st.caption("Weekly yardage data is unavailable; score-based team records and points are still shown.")

profiles = team_profiles(all_games, stats, season, selected)

# Private credential: never publish this value, or persist it to GitHub.
try:
    dk_api_key = str(st.secrets.get("THERUNDOWN_API_KEY", "") or os.environ.get("THERUNDOWN_API_KEY", "")).strip()
except (AttributeError, KeyError, FileNotFoundError, RuntimeError):
    dk_api_key = str(os.environ.get("THERUNDOWN_API_KEY", "")).strip()

dk_by_game = {}
dk_error = None
if stage == "REG" and utc_dates(slate):
    try:
        espn_quotes = match_quotes(slate, cached_espn_odds(season, selected))
        dk_by_game = espn_quotes["DraftKings"]
    except ESPNFeedError:
        st.caption("ESPN odds are temporarily unavailable.")
if stage == "REG" and dk_api_key:
    dates = utc_dates(slate)
    if dates:
        try:
            snapshots = {}
            for i, day in enumerate(dates):
                # The free provider tier permits at most one API request/second.
                if i:
                    sleep(1.05)
                snapshots[day] = cached_dk_snapshot(day, dk_api_key)
            dk_by_game = {**match_games(slate, snapshots), **dk_by_game}
        except DKFeedError:
            dk_error = "Optional DraftKings feed unavailable. ESPN quotes remain available when published."
elif stage == "REG":
    dk_error = "DraftKings odds load through ESPN without a key."

if dk_error and dk_api_key:
    st.caption(dk_error)

line_history = cached_line_history() if stage == 'REG' and season == now.year else {'games': {}}

ats_history = coach_history(all_games)
coach_mismatches = weekly_mismatch(slate, ats_history, dk_by_game) if stage == 'REG' else {}

coach_markers = coaching_flags(slate, season, selected, dk_by_game) if stage == "REG" else {}
coach_specials = {gid: marker for gid, markers in coach_markers.items()
                  for marker in markers if marker["name"] == "BEN JOHNSON SPECIAL"}

watch_flags = {}
if stage == "REG" and selected >= 4:
    if WATCH_STAT_COLUMNS.issubset(stats.columns):
        try:
            watch_flags = cached_watch_flags(all_games, stats, season, selected)
        except (ValueError, TypeError, KeyError, IndexError, ArithmeticError):
            st.caption("Game to Watch screening unavailable for this week; model picks are unaffected.")
    elif season == now.year:
        st.caption("Game to Watch screening requires complete prior-week NFL advanced statistics; missing data never counts as a match.")

advanced = team_advanced_profiles(stats, season, selected) if stage == "REG" else {}
try:
    qb_profiles = qb_recent_profiles(cached_player_stats(season), season, selected) if stage == "REG" else {}
except FeedError:
    qb_profiles = {}
    st.caption("Quarterback research feed unavailable. No starter status is inferred.")

injury_data = pd.DataFrame()
injury_source_available = False

picks = {}
markets = {}
candidates = set()
if stage == "REG":
    try:
        predictions = cached_predictions(all_games)
        picks = {str(p["game_id"]): p for _, p in predictions.iterrows()}
        for _, g in slate.iterrows():
            prediction = picks.get(str(g["game_id"]))
            if prediction is None:
                continue
            dk = dk_by_game.get(str(g["game_id"]), {})
            market = analyze_moneyline(prediction["home_probability"], dk.get("home_moneyline"), dk.get("away_moneyline"))
            if market is not None:
                markets[str(g["game_id"])] = market
                if screen_side(market) is not None:
                    candidates.add(str(g["game_id"]))
        track = summary(predictions, season)
        if track["games"]:
            st.markdown('<div class="ss-section">Model performance · ' + VERSION + '</div>', unsafe_allow_html=True)
            a, b, c = st.columns(3)
            a.metric("Straight-up record", f"{track['wins']}-{track['losses']}")
            b.metric("Accuracy", f"{track['accuracy']:.1%}")
            c.metric("Graded NFL games", track["games"])
        with st.expander("Historical model validation (regular season)"):
            st.caption("Parameters selected on 2019–2022 regular seasons; 2023–2025 held out. Predictions for every week use earlier weeks only. Records are straight-up, not ATS or ROI.")
            for year in (2023, 2024, 2025, 2026):
                result = summary(predictions, year)
                if result["games"]:
                    st.markdown(f"**{year}** · {result['wins']}-{result['losses']} · {result['accuracy']:.1%} · Brier {result['brier']:.3f}")
    except (ValueError, TypeError) as exc:
        st.warning("Model predictions unavailable because historical data failed validation. Scores and team comparisons are unaffected.")
        with st.expander("Model validation details"):
            st.code(str(exc))
else:
    st.caption("Postseason model picks are not published yet; the current backtest covers regular-season games only.")

# Historical records and shortlist calculations use archived pregame research only:
# no additional NFL data feeds, market calls or late-week refitting are needed.
shortlist_selection = {"core": [], "potential": []}
if stage == "REG":
    frozen_shortlist = load_shortlist_snapshot(season, selected)
    if not snapshot_is_pregame(frozen_shortlist, slate):
        frozen_shortlist = None
    if frozen_shortlist is not None:
        shortlist_selection = select_shortlist(frozen_shortlist)
    render_shortlist(season, selected, frozen_shortlist, shortlist_selection,
                     slate, brands, dk_by_game)

if stage == "REG" and picks:
    st.markdown('<div class="ss-section">DraftKings value research · experimental</div>', unsafe_allow_html=True)
    st.caption("All moneyline comparisons use DraftKings pregame odds exclusively. "
               "The free feed is at least five minutes delayed; this is not a live executable quote. "
               "No historical DraftKings odds have been verified for a retrospective ROI calculation, "
               "so historical reference-price ROI is not displayed.")

if watch_flags:
    st.caption(f"★ {len(watch_flags)} Game to Watch matchup(s) match the pregame Home Field Advantage pattern · research flag only, not a pick.")
if coach_markers:
    st.caption(f"★ {sum(len(markers) for markers in coach_markers.values())} DraftKings Coaching Trend(s) · "
               "Ben Johnson Special, Schottenheimer Favorite or Stefanski Mid-Range Favorite · research only.")

st.markdown('<div class="ss-section">Browse matchups</div>', unsafe_allow_html=True)
filter1, filter2, filter3 = st.columns([2, 1.2, 1])
with filter1:
    needle = st.text_input("Find a team", placeholder="Cowboys, Saints, DAL, NO…")
with filter2:
    when = st.selectbox("Game window", ["All days", "Thursday", "Friday", "Saturday", "Sunday", "Monday", "Other days"])
with filter3:
    hide_final = st.toggle("Upcoming only", value=False)

if needle.strip():
    search = needle.strip().casefold()
    def matches(game):
        names = [str(game["away_team"]), str(game["home_team"])]
        names.extend(str(brands.get(t, {}).get("name") or "") for t in names[:])
        return any(search in n.casefold() for n in names)
    slate = slate[slate.apply(matches, axis=1)]
if hide_final:
    slate = slate[~slate["completed"]]
if when != "All days":
    days = slate["kickoff_ct"].apply(lambda dt: dt.strftime("%A") if pd.notna(dt) else "Unknown")
    slate = slate[days.isin(["Tuesday", "Wednesday"] if when == "Other days" else [when])]

if stage == "REG":
    research_filter = st.selectbox("Matchup display", ["All matchups", "Weekly shortlist only", "Potential shortlist additions", "Game to Watch only", "Ben Johnson Special only", "Schottenheimer Favorite only", "Stefanski Mid-Range Favorite only", "Any Coaching Trend", "Experimental value research matches"], key="market_research_filter")
    if research_filter == "Weekly shortlist only":
        slate = slate[slate["game_id"].astype(str).isin({p["game_id"] for p in shortlist_selection["core"]})]
    elif research_filter == "Potential shortlist additions":
        slate = slate[slate["game_id"].astype(str).isin({p["game_id"] for p in shortlist_selection["potential"]})]
    elif research_filter == "Game to Watch only":
        slate = slate[slate["game_id"].astype(str).isin(watch_flags)]
    elif research_filter == "Ben Johnson Special only":
        slate = slate[slate["game_id"].astype(str).isin(coach_specials)]
    elif research_filter in ("Schottenheimer Favorite only", "Stefanski Mid-Range Favorite only"):
        label = ("SCHOTTENHEIMER FAVORITE" if research_filter.startswith("Schottenheimer")
                 else "STEFANSKI MID-RANGE FAVORITE")
        matching = {gid for gid, markers in coach_markers.items()
                    if any(m["name"] == label for m in markers)}
        slate = slate[slate["game_id"].astype(str).isin(matching)]
    elif research_filter == "Any Coaching Trend":
        slate = slate[slate["game_id"].astype(str).isin(coach_markers)]
    elif research_filter == "Experimental value research matches":
        slate = slate[slate["game_id"].astype(str).isin(candidates)]
else:
    research_filter = "All matchups"

load_injury_context = st.toggle("Load game-week injury reports (optional)", value=False, key="show_injury_reports") if stage == "REG" and season == now.year else False
if load_injury_context:
    try:
        injury_data = cached_injuries(season)
        injury_source_available = not injury_data.empty
    except FeedError:
        st.caption("Current game-week injury feed unavailable. No health conclusions will be drawn from missing entries.")

# Expensive NFLverse historical depth feed is strictly opt-in, preserving the
# existing fast Saturday startup and the fully validated Elo prediction flow.
load_qb_confirmation = (
    st.toggle("Show quarterback availability & replacement research (optional)",
              value=False, key="show_qb_availability")
    if stage == "REG" and season == now.year and season >= 2025 else False
)
qb_depth_data = pd.DataFrame()
qb_injury_data = pd.DataFrame()
qb_confirmations = {}
if load_qb_confirmation:
    try:
        qb_depth_data = cached_qb_depth(season)
    except FeedError:
        st.caption("Dated QB depth-chart data unavailable. No starter projection is assumed.")
    # Only source-dated injury rows qualify. Untimestamped injury summaries
    # remain unavailable rather than being retroactively labeled pregame.
    try:
        qb_injury_data = cached_injuries(season)
    except FeedError:
        st.caption("Timestamped quarterback injury statuses unavailable; this does not imply a healthy QB.")
    try:
        qb_confirmations = read_owner_confirmations(
            st.secrets.get("QB_CONFIRMATIONS_JSON", ""))
    except (AttributeError, KeyError, FileNotFoundError, RuntimeError, TypeError):
        qb_confirmations = {}
    st.caption("QB1 depth charts are unconfirmed projections. Official-source citations, if "
               "provided by the app owner, are source-labeled and not independently checked. "
               "The original NFL-ELO-1.0 picks and chances stay unchanged.")

st.caption(f"Showing {len(slate)} matchups · Times in CT · Prior-week football statistics · DraftKings odds")
if stage == "REG" and season == now.year:
    st.caption("Line movement compares first captured vs latest ESPN-published DraftKings quotes. "
               "History is collected approximately every 3 hours; no earlier opening lines are invented. "
               "Tracking begins after the collector’s first successful run.")
if slate.empty:
    st.info("No games match these filters. Try clearing your filters.")
else:
    for idx in range(0, len(slate), 2):
        columns = st.columns(2)
        for col, (_, game) in zip(columns, slate.iloc[idx:idx + 2].iterrows()):
            with col:
                html = game_card(game, brands, profiles,
                                 watch=watch_flags.get(str(game["game_id"])),
                                 coaching=coach_markers.get(str(game["game_id"])),
                                 coach_mismatch=coach_mismatches.get(str(game["game_id"])),
                                 dk_quote=dk_by_game.get(str(game["game_id"])),
                                 coach_ats=coach_ats_context(game, ats_history,
                                      dk_by_game.get(str(game["game_id"]))),
                                  line_movement=change_for_game(line_history, game,
                                      dk_by_game.get(str(game["game_id"]))))
                prediction = picks.get(str(game["game_id"]))
                panels = []
                if prediction is not None:
                    html = html.replace("<!--prediction-->", prediction_panel(prediction))
                    if load_qb_confirmation and not bool(game["completed"]):
                        try:
                            qb_info = qb_confirmation_context(
                                game.to_dict(), all_games, qb_depth_data,
                                cached_player_stats(season) if qb_depth_data is not None
                                and not qb_depth_data.empty else pd.DataFrame(),
                                qb_injury_data, qb_confirmations,
                                pd.Timestamp.now(tz="UTC"))
                            panels.append(qb_availability_panel(qb_info))
                        except (ValueError, TypeError, KeyError, OverflowError):
                            panels.append(qb_availability_panel(None))
                    panels.append(matchup_panel(str(game["home_team"]), str(game["away_team"]),
                                                matchup_research(str(game["home_team"]), str(game["away_team"]), advanced, qb_profiles)))
                    panels.append(market_panel(str(game["home_team"]), str(game["away_team"]),
                                                markets.get(str(game["game_id"])), str(game["game_id"]) in candidates))
                    if load_injury_context and not bool(game["completed"]) and season == now.year:
                        injury_research = reported_injuries(injury_data, season, selected, game["kickoff_ct"],
                                                            (str(game["home_team"]), str(game["away_team"])))
                        panels.append(injury_panel(str(game["home_team"]), str(game["away_team"]),
                                                   injury_research, source_available=injury_source_available))
                if panels:
                    html = html.replace("</article>", '<details class="ss-card-details"><summary>More matchup research</summary>' + "".join(panels) + "</details></article>")
                st.markdown(html, unsafe_allow_html=True)

with st.expander("About these stats and the current build"):
    st.markdown("""**Phase 3:** schedules, recorded scores, team branding, pregame comparisons, research-only market screens and results-based NFL probabilities. Team records and points-per-game are computed from previously completed regular-season games only. Passing and rushing yards per game come from the available earlier-week team summaries. A dash means the data was unavailable; it does not mean zero.

**Not live play-by-play:** nflverse schedules typically update with recorded results; don't assume that an unfinished game is at its current score. Straight-up model probabilities and historical grading are provided for regular-season games only. All displayed odds-based coaching flags and value research use *DraftKings-only* pregame prices through ESPN or TheRundown, not nflverse reference odds. Free-tier prices are delayed and are not confirmed executable quotes. The basic exploratory rule has not demonstrated consistent profitable returns. Optional game-week injury report status may appear when a dated source row is available; this is informational and does not adjust win probabilities. Quarterback projections and replacement-quality research can be loaded on upcoming current-season games. Depth charts alone do not establish confirmed starters, and no quarterback research changes the official Elo pick. Weather tiers and parlays remain unavailable pending independent validation. The Weekly Shortlist is a separate, research-qualified straight-up selection feature, not a promise of profitable betting returns. Historical shortlist records are retrospective, while new weekly picks require verified pregame archives.

**Game to Watch:** An independent informational flag for non-neutral home teams with both stronger pregame offensive and defensive statistical ratings and an advantage magnitude from 0.25 up to (but not including) 0.50. Requires at least three earlier regular-season games and complete two-team weekly records. The flag does not depend on moneylines; it is not a tier or betting recommendation and never overrides the Elo prediction. Flags may change if historical source data is revised or incomplete previous-week results arrive.

**Weekly Shortlist:** Heavy Favorite requires Elo 75%+. Double Confirmation requires Elo 60%+, projected scoring advantage of at least seven points agreeing with Elo, and at least three prior games. Strong Consensus additions require Elo 65%+, scoring advantage of at least three points in agreement, challenger model agreement, and at least three prior games. A maximum of five Core Picks is shown, prioritized by category then confidence. Potential Additions require Elo 68%+ and challenger agreement but failed the stronger core rules, and are not counted as recommendations. Historical records cover reconstructed 2023–2025 inputs and a dated 2026 Weeks 1–5 cohort; upcoming selections use immutable pregame weekly archives. Missing archives do not trigger retroactive predictions. Straight-up accuracy does not establish moneyline betting value.\n\n**Line movement:** Captures DraftKings-attributed pregame quotes from ESPN roughly every three hours, when the scheduled collector runs and quotes are published. The first captured quote is not necessarily the opening line. Changes in a team's spread or moneyline are shown separately with observation times; these are not live executable prices, and saved history cannot be reconstructed for earlier games. Historical snapshots remain in the dedicated line-history branch rather than Streamlit's temporary filesystem. Line movement does not change Elo picks or create betting tiers.

**DraftKings Coaching Trends:** Ben Johnson Special when his team is favored by 0.5–3; Schottenheimer Favorite when Dallas is favored by at least 0.5; Stefanski Mid-Range Favorite when his team is favored by 3.5–7. All require DraftKings-attributed prices; if those are absent, no flag appears. Coaching flags do not change Elo and are not proven betting edges.

**Source:** nflverse / nflreadpy. Most nflverse datasets are CC BY 4.0; attribute nflverse if redistributing. No betting is placed by this app. NFL and team marks belong to their respective owners.""")

st.markdown('<div class="ss-foot">Sunday Slate · Independent NFL research dashboard · Powered by nflverse · Built with Streamlit</div>', unsafe_allow_html=True)
