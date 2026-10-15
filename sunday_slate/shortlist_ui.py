"""Compact, readable Sunday Slate weekly shortlist presentation."""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from sunday_slate.shortlist import HISTORICAL, LABELS, grade, historic_total, history_rate


def _label(team, brands):
    return escape(str(brands.get(team, {}).get("name") or team))


def _record(value):
    wins = int(value["wins"])
    losses = int(value["losses"])
    return f"{wins}–{losses} · {history_rate(wins,losses)}"


def _pick_card(row, slate, brands, dk_quotes=None, *, potential=False):
    """User-friendly summary without exposing advanced-stat formulas or model internals."""
    indexed = slate.set_index("game_id")
    g = indexed.loc[row["game_id"]] if row["game_id"] in indexed.index else None
    if isinstance(g, pd.DataFrame):
        g = None
    opponent = row["away_team"] if row["team"] == row["home_team"] else row["home_team"]
    name = _label(row["team"], brands)
    opponent_name = _label(opponent, brands)
    label = "Additional candidate · Not a core pick" if potential else LABELS[row["tier"]]
    detail = ("Strong Elo forecast and challenger agreement; " + row["reason"]
              if potential else
              "Strong results-based team rating"
              if row["tier"] == 1 else
              "Elo and projected scoring margin both favor this team"
              if row["tier"] == 2 else
              "Elo, projected scoring and challenger agree")
    if not potential and row["ppg_agrees"] and row["ppg_margin"] is not None:
        detail += f" · scoring edge {abs(row['ppg_margin']):.1f} pts"
    date = ""
    status = ""
    if g is not None:
        kickoff = pd.to_datetime(g.get("kickoff_ct"), utc=True, errors="coerce")
        if pd.notna(kickoff):
            date = escape(kickoff.tz_convert("America/Chicago").strftime("%a, %b %-d · %-I:%M %p CT"))
        if bool(g.get("completed", False)):
            hs = g.get("home_score")
            aw = g.get("away_score")
            if pd.notna(hs) and pd.notna(aw):
                actual = row["home_team"] if float(hs) > float(aw) else row["away_team"] if float(aw) > float(hs) else None
                status = " · Final: " + ("Correct" if actual == row["team"] else "Incorrect" if actual else "Tie")
    quote = (dk_quotes or {}).get(row["game_id"]) or {}
    side = "home" if row["team"] == row["home_team"] else "away"
    ml = quote.get(f"{side}_moneyline") if quote.get("source") == "DraftKings" else None
    price = ""
    if isinstance(ml, (int, float)) and not isinstance(ml, bool):
        price = f' · DK moneyline {int(ml):+d} (delayed)'
    return (
        f'<div class="ss-shortlist-card{" ss-shortlist-potential" if potential else ""}">'
        f'<div class="ss-shortlist-label">{escape(label)}</div>'
        f'<div class="ss-shortlist-title">{name} <span>over {opponent_name}</span></div>'
        f'<div class="ss-shortlist-confidence">Elo win estimate: {row["probability"]:.1%}</div>'
        f'<div class="ss-shortlist-detail">{escape(detail)}</div>'
        f'<div class="ss-shortlist-meta">{date}{escape(status)}{escape(price)}</div>'
        '</div>'
    )


def render_shortlist(season: int, week: int, snapshot: dict | None, selected: dict,
                     slate: pd.DataFrame, brands: dict, dk_quotes: dict | None = None):
    """Call this BEFORE matchup search filters; no extra data feeds are loaded."""
    st.markdown('<div class="ss-section">🏈 Weekly Shortlist · Straight-up picks</div>',
                unsafe_allow_html=True)
    st.caption("Target: 3–5 high-conviction picks each week. Only pre-kickoff frozen forecasts "
               "qualify for the core list. No games are forced into the shortlist.")

    if snapshot is None:
        st.info(f"No verified pregame shortlist is archived for {season} Week {week}. "
                "Historical reconstructed results are available below. New shortlists "
                "appear when a valid pregame weekly snapshot is saved.")
    else:
        core = selected.get("core", [])
        candidates = selected.get("potential", [])
        created = pd.Timestamp(snapshot["created_at_utc"])
        created_ct = created.tz_convert("America/Chicago").strftime("%b %-d, %Y · %-I:%M %p CT")
        completed = grade(core, slate)
        a, b, c = st.columns(3)
        a.metric("Core selections", f"{len(core)} / 5")
        b.metric("Potential additions", len(candidates))
        c.metric("Frozen pick results", f"{completed['wins']}–{completed['losses']}"
                 if completed["wins"] + completed["losses"] else "Not graded")
        st.caption(f"Frozen {created_ct} · Research-only selection · Separate from model-wide picks")
        if not core:
            st.info("No matchup meets our core standards this week.")
        for pos in range(0, len(core), 2):
            cols = st.columns(2)
            for col, item in zip(cols, core[pos:pos+2]):
                with col:
                    st.markdown(_pick_card(item, slate, brands, dk_quotes), unsafe_allow_html=True)
        if candidates:
            with st.expander(f"Potential additions · {len(candidates)} (research only)"):
                st.caption("These games have at least 68% Elo confidence and agree with the "
                           "frozen challenger, but failed the stronger core rules. They are "
                           "NOT counted as recommended games; prior historical additions "
                           "have a much weaker record.")
                for item in candidates:
                    st.markdown(_pick_card(item, slate, brands, dk_quotes, potential=True),
                                unsafe_allow_html=True)
        elif len(core) < 3:
            st.caption("No credible secondary candidates meet the minimum research screen.")
        st.caption("Before betting, verify the starting quarterback, injury report, "
                   "current sportsbook line and price. Win probability is not betting value.")

    with st.expander("Historical shortlist record · 2023–2026"):
        total = historic_total()
        a, b, c = st.columns(3)
        a.metric("2023–25 core picks", f"{total['wins']}–{total['losses']}")
        b.metric("Core accuracy", history_rate(total["wins"], total["losses"]))
        c.metric("Weeks with 3+ core picks", "40 / 54")
        st.caption("Retrospective preweek-input reconstruction, not independently verified "
                   "published betting picks. Straight-up wins only; no ATS or ROI claim.")
        for year in (2023, 2024, 2025):
            st.markdown(f"**{year}** · {_record(HISTORICAL['seasons'][year])}")
        st.markdown("**2026 Weeks 1–5 (reconstructed)** · "
                    + _record(HISTORICAL["seasons"][2026]))
        st.markdown("**Historical record by selected core category (2023–2025)**")
        for tier in (1, 2, 3):
            st.markdown(f"{LABELS[tier]} · {_record(HISTORICAL['by_tier_2023_2025'][tier])}")
        st.markdown("**Potential additions, evaluated separately:** "
                    + _record(HISTORICAL["addition_2023_2025"])
                    + " (2023–2025); "
                    + _record(HISTORICAL["addition_2026_week1_to_5"])
                    + " (2026 Weeks 1–5).")
        st.caption("2026 historical numbers above cover only Weeks 1–5 and are not "
                   "a continually updated full-season record. Later weeks use dated frozen "
                   "snapshots; results are displayed on the matching week's cards. "
                   "Historical filters were examined repeatedly, so future validation is essential.")
        st.caption("Source: Sunday Slate weekly shortlist and near-miss backtests. "
                   "The same games are not counted twice between core and candidates.")
