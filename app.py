"""Sunday Slate Phase 1: schedules and pregame comparison dashboard.

Run: streamlit run app.py
No picks, probabilities, or gambling ROI are calculated in this phase.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from sunday_slate.data import FeedError, load_schedules, load_teams, load_team_stats
from sunday_slate.metrics import default_week, season_options, weeks_for, with_kickoffs, team_profiles
from sunday_slate.ui import branding_map, css, game_card

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


st.markdown('<div class="ss-topline">SIXTY LABS · NFL INTELLIGENCE</div><div class="ss-heading">Sunday Slate <span class="ss-pulse">PHASE 1</span></div><div class="ss-subtitle">Every NFL game. One smarter Sunday. Schedules and matchup profiles, with pregame predictions coming later.</div>', unsafe_allow_html=True)

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

slate = all_games[(all_games["season"] == season) & (all_games["game_type"] == stage) & (all_games["week"] == selected)].copy()
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

st.caption(f"Showing {len(slate)} matchups · Times shown in America/Chicago (CT) · Team comparisons use earlier weeks only")
if slate.empty:
    st.info("No games match these filters. Try clearing your filters.")
else:
    for idx in range(0, len(slate), 2):
        columns = st.columns(2)
        for col, (_, game) in zip(columns, slate.iloc[idx:idx + 2].iterrows()):
            with col:
                st.markdown(game_card(game, brands, profiles), unsafe_allow_html=True)

with st.expander("About these stats and the current build"):
    st.markdown("""**Phase 1:** schedules, recorded scores, team branding and pregame comparisons. Team records and points-per-game are computed from previously completed regular-season games only. Passing and rushing yards per game come from the available earlier-week team summaries. A dash means the data was unavailable; it does not mean zero.

**Not live play-by-play:** nflverse schedules typically update with recorded results; don't assume that an unfinished game is at its current score. No win probabilities, value picks, spread recommendations, weather tier, parlays, or odds appear until verified and tested in later phases.

**Source:** nflverse / nflreadpy. Most nflverse datasets are CC BY 4.0; attribute nflverse if redistributing. No betting is placed by this app. NFL and team marks belong to their respective owners.""")

st.markdown('<div class="ss-foot">Sunday Slate · Independent NFL research dashboard · Powered by nflverse · Built with Streamlit</div>', unsafe_allow_html=True)
