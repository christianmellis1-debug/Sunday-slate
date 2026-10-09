"""Sunday Slate Phase 1: schedules and pregame comparison dashboard.

Run: streamlit run app.py
No picks, probabilities, or gambling ROI are calculated in this phase.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from sunday_slate.data import FeedError, load_schedules, load_teams, load_team_stats, load_player_stats
from sunday_slate.metrics import default_week, season_options, stage_mask, weeks_for, with_kickoffs, team_profiles
from sunday_slate.ui import branding_map, css, game_card, prediction_panel, matchup_panel, market_panel
from sunday_slate.model import predict_regular_season, summary, VERSION
from sunday_slate.market import analyze_moneyline, screen_side, historical_screen, historical_report, SCREEN_EDGE, SCREEN_MIN_PROB
from sunday_slate.matchup import team_advanced_profiles, qb_recent_profiles, matchup_research

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
def cached_player_stats(season: int):
    return load_player_stats(season)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_historical_screen(schedule: pd.DataFrame, predictions: pd.DataFrame):
    return historical_screen(schedule, predictions)


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

advanced = team_advanced_profiles(stats, season, selected) if stage == "REG" else {}
try:
    qb_profiles = qb_recent_profiles(cached_player_stats(season), season, selected) if stage == "REG" else {}
except FeedError:
    qb_profiles = {}
    st.caption("Quarterback research feed unavailable. No starter status is inferred.")

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
            market = analyze_moneyline(prediction["home_probability"], g.get("home_moneyline"), g.get("away_moneyline"))
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

if stage == "REG" and picks:
    st.markdown('<div class="ss-section">Value Research · experimental</div>', unsafe_allow_html=True)
    st.caption("Market differences below are research signals only, not recommendations. The nflverse schedule supplies unverified reference moneylines, not sportsbook-specific, time-stamped quotes.")
    try:
        historic = cached_historical_screen(all_games, predictions)
        aggregate = historical_report(historic)
        with st.expander("Historical moneyline screen · 2023–2025 · reference prices"):
            st.markdown("**Research filter:** model probability at least 60%, model versus no-vig market difference at least 5 percentage points, odds from -300 to +200. **This rule is NOT validated as profitable.**")
            x, y, z = st.columns(3)
            x.metric("Historical selections", aggregate["bets"])
            y.metric("Wins–losses", f"{aggregate['wins']}–{aggregate['losses']}")
            z.metric("Flat-stake ROI", f"{aggregate['roi']:+.1%}" if aggregate["roi"] is not None else "Unavailable")
            st.caption("Reference prices from retrospective season schedules are NOT documented, pre-kickoff executable quotes; this is a retrospective sensitivity check, not a verified betting backtest.")
            for yr in (2023, 2024, 2025):
                yr_result = historical_report(historic[historic["season"].eq(yr)])
                st.markdown(f"**{yr}:** {yr_result['wins']}–{yr_result['losses']} · ROI {yr_result['roi']:+.1%}" if yr_result["roi"] is not None else f"**{yr}:** No eligible reference lines")
    except (ValueError, KeyError) as exc:
        st.caption("Historical reference-odds research is not currently available; model predictions are unaffected.")

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
    research_filter = st.selectbox("Matchup display", ["All matchups", "Experimental value research matches"], key="market_research_filter")
    if research_filter != "All matchups":
        slate = slate[slate["game_id"].astype(str).isin(candidates)]
else:
    research_filter = "All matchups"

st.caption(f"Showing {len(slate)} matchups · Times in CT · Prior-week football statistics · Reference market lines are not verified live odds")
if slate.empty:
    st.info("No games match these filters. Try clearing your filters.")
else:
    for idx in range(0, len(slate), 2):
        columns = st.columns(2)
        for col, (_, game) in zip(columns, slate.iloc[idx:idx + 2].iterrows()):
            with col:
                html = game_card(game, brands, profiles)
                prediction = picks.get(str(game["game_id"]))
                panels = []
                if prediction is not None:
                    panels.append(prediction_panel(prediction))
                    panels.append(matchup_panel(str(game["home_team"]), str(game["away_team"]),
                                                matchup_research(str(game["home_team"]), str(game["away_team"]), advanced, qb_profiles)))
                    panels.append(market_panel(str(game["home_team"]), str(game["away_team"]),
                                                markets.get(str(game["game_id"])), str(game["game_id"]) in candidates))
                if panels:
                    html = html.replace("</article>", "".join(panels) + "</article>")
                st.markdown(html, unsafe_allow_html=True)

with st.expander("About these stats and the current build"):
    st.markdown("""**Phase 3:** schedules, recorded scores, team branding, pregame comparisons, research-only market screens and results-based NFL probabilities. Team records and points-per-game are computed from previously completed regular-season games only. Passing and rushing yards per game come from the available earlier-week team summaries. A dash means the data was unavailable; it does not mean zero.

**Not live play-by-play:** nflverse schedules typically update with recorded results; don't assume that an unfinished game is at its current score. Straight-up model probabilities and historical grading are provided for regular-season games only. The Value Research panel shows *reference* moneylines from the source schedule, not DraftKings quotes or confirmed executable prices. The basic exploratory rule has not demonstrated consistent profitable returns. Injuries, confirmed starting quarterbacks, weather tiers, parlays, and official recommended picks remain unavailable until their feeds and betting performance are independently verified.

**Source:** nflverse / nflreadpy. Most nflverse datasets are CC BY 4.0; attribute nflverse if redistributing. No betting is placed by this app. NFL and team marks belong to their respective owners.""")

st.markdown('<div class="ss-foot">Sunday Slate · Independent NFL research dashboard · Powered by nflverse · Built with Streamlit</div>', unsafe_allow_html=True)
