"""Readable Sunday Slate weekly shortlist: ranked cards and honest records.

Presentation only: selection criteria and frozen archived picks are unchanged.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from sunday_slate.market import valid_american
from sunday_slate.shortlist import HISTORICAL, LABELS, grade, historic_total, history_rate


def _label(team, brands):
    return escape(str(brands.get(team, {}).get("name") or team))


def _record(value):
    wins = int(value["wins"])
    losses = int(value["losses"])
    return f"{wins}–{losses} · {history_rate(wins, losses)}"


def _metric(label: str, value: str, note: str = "") -> str:
    return ('<div class="ss-shortlist-summary-item">'
            f'<div class="ss-shortlist-summary-value">{escape(str(value))}</div>'
            f'<div class="ss-shortlist-summary-label">{escape(label)}</div>'
            f'<div class="ss-shortlist-summary-note">{escape(note)}</div>'
            '</div>')


def _chip(value: str, *, subtle: bool = False) -> str:
    cls = "ss-shortlist-chip ss-shortlist-chip-muted" if subtle else "ss-shortlist-chip"
    return f'<span class="{cls}">{escape(value)}</span>'


def _reason(row: dict, potential: bool) -> str:
    if potential:
        explanations = {
            "PPG projection disagrees": "Scoring outlook disagrees",
            "Scoring confirmation unavailable": "Not enough scoring information",
            "Below core confirmation threshold": "Not enough supporting evidence",
        }
        return explanations.get(row.get("reason"), "Does not meet the core-pick rules")
    return {
        1: "Strong rating advantage",
        2: "Win forecast and projected scoring agree",
        3: "Multiple forecasts favor the same team",
    }.get(row.get("tier"), "Supported by the pregame research")


def _pick_card(row, slate, brands, dk_quotes=None, *, potential=False, rank=None):
    """A single compact card; never invent missing prices, kickoff or score data."""
    indexed = slate.set_index("game_id")
    g = indexed.loc[row["game_id"]] if row["game_id"] in indexed.index else None
    if isinstance(g, pd.DataFrame):
        g = None
    opponent = row["away_team"] if row["team"] == row["home_team"] else row["home_team"]
    name = _label(row["team"], brands)
    opponent_name = _label(opponent, brands)
    tier = row.get("tier") if not potential else None
    label = "Potential addition" if potential else LABELS.get(tier, "Core pick")
    tier_class = f" ss-shortlist-tier-{tier}" if tier in (1, 2, 3) else ""
    if potential:
        tier_class = " ss-shortlist-potential"

    chips = [_chip(f'{row["probability"]:.1%} win chance')]
    if row.get("ppg_agrees") and row.get("ppg_margin") is not None:
        chips.append(_chip(f'{abs(row["ppg_margin"]):.1f}-point scoring edge'))
    result = ""
    if g is not None:
        kickoff = pd.to_datetime(g.get("kickoff_ct"), utc=True, errors="coerce")
        if pd.notna(kickoff):
            chips.append(_chip(kickoff.tz_convert("America/Chicago").strftime("%a, %b %-d · %-I:%M %p CT"),
                               subtle=True))
        if bool(g.get("completed", False)):
            hs, aw = g.get("home_score"), g.get("away_score")
            if pd.notna(hs) and pd.notna(aw):
                actual = (row["home_team"] if float(hs) > float(aw)
                          else row["away_team"] if float(aw) > float(hs) else None)
                result = "Tie" if actual is None else "Correct" if actual == row["team"] else "Incorrect"
    if result:
        chips.append(_chip("Final · " + result, subtle=True))

    # The quoted price is a delayed current DraftKings quote, never a claimed
    # historical price or true opening line.
    quote = (dk_quotes or {}).get(row["game_id"]) or {}
    side = "home" if row["team"] == row["home_team"] else "away"
    odds = valid_american(quote.get(f"{side}_moneyline")) if quote.get("source") == "DraftKings" else None
    if odds is not None and not result:
        chips.append(_chip(f"DK {odds:+d} · delayed", subtle=True))

    rank_html = (f'<span class="ss-shortlist-rank">#{int(rank)}</span>'
                 if rank is not None and not potential else
                 '<span class="ss-shortlist-rank">Research only</span>')
    return (
        f'<article class="ss-shortlist-card{tier_class}">'
        f'<div class="ss-shortlist-top">{rank_html}'
        f'<span class="ss-shortlist-pill">{escape(label)}</span></div>'
        f'<div class="ss-shortlist-title">{name}</div>'
        f'<div class="ss-shortlist-opponent">over {opponent_name}</div>'
        f'<div class="ss-shortlist-chips">{"".join(chips)}</div>'
        f'<div class="ss-shortlist-why"><b>Why it qualifies:</b> '
        f'{escape(_reason(row, potential))}</div>'
        '</article>'
    )


def _history_table(rows: list[tuple[str, dict]]) -> str:
    return ('<div class="ss-history-list">'
            + "".join(
                '<div class="ss-history-row">'
                f'<span>{escape(label)}</span><b>{escape(_record(record))}</b>'
                '</div>'
                for label, record in rows
            ) + '</div>')


def render_shortlist(season: int, week: int, snapshot: dict | None, selected: dict,
                     slate: pd.DataFrame, brands: dict, dk_quotes: dict | None = None):
    """Called before game filters. Uses frozen archives, not current outcomes."""
    st.markdown(
        '<div class="ss-shortlist-header">'
        '<div class="ss-shortlist-eyebrow">Your weekly picks</div>'
        '<div class="ss-shortlist-heading">Weekly Shortlist</div>'
        '<div class="ss-shortlist-intro">A small selection of matchups with stronger supporting evidence.</div>'
        '</div>', unsafe_allow_html=True)
    core = selected.get("core", []) if snapshot is not None else []
    candidates = selected.get("potential", []) if snapshot is not None else []
    total = historic_total()
    st.markdown(
        '<div class="ss-shortlist-summary">'
        + _metric("Core picks", str(len(core)) if snapshot is not None else "—",
                  "Up to five per week" if snapshot is not None else "No saved picks")
        + _metric("Potential additions", str(len(candidates)) if snapshot is not None else "—",
                  "Research only")
        + _metric("Historical record", f'{total["wins"]}–{total["losses"]}',
                  "2023–25 reconstructed")
        + _metric("Historical accuracy", history_rate(total["wins"], total["losses"]),
                  "Straight-up, not ATS")
        + '</div>', unsafe_allow_html=True)

    if snapshot is None:
        st.info(f"No verified pregame picks were archived for {season} Week {week}. "
                "Historical results are available below; we won't create picks after kickoff.")
    else:
        created = pd.Timestamp(snapshot["created_at_utc"])
        created_ct = created.tz_convert("America/Chicago").strftime("%b %-d, %Y · %-I:%M %p CT")
        completed = grade(core, slate)
        results = (f"{completed['wins']} correct · {completed['losses']} incorrect"
                   if completed["wins"] + completed["losses"] else "Games not graded yet")
        st.caption(f"Saved before kickoff · {created_ct} · {results}")
        if not core:
            st.info("No games meet the core-pick standards this week.")
        for pos in range(0, len(core), 2):
            cols = st.columns(2)
            for index, (col, item) in enumerate(zip(cols, core[pos:pos + 2]), start=pos + 1):
                with col:
                    st.markdown(_pick_card(item, slate, brands, dk_quotes, rank=index),
                                unsafe_allow_html=True)

        if candidates:
            with st.expander(f"Potential additions ({len(candidates)}) · Research only"):
                st.caption("These games show some promise but don't meet all the stronger "
                           "requirements. They're not core picks.")
                for item in candidates:
                    st.markdown(_pick_card(item, slate, brands, dk_quotes, potential=True),
                                unsafe_allow_html=True)
        elif len(core) < 3:
            st.caption("No additional games meet the minimum research requirements.")
        st.caption("These are predictions, not guarantees. Before betting, confirm the "
                   "starting quarterback, injuries and current sportsbook price.")

    with st.expander("Historical results · Seasons and pick categories"):
        st.markdown(
            '<div class="ss-shortlist-history-heading">2023–2025 · Core selections</div>'
            + _metric("Record", f'{total["wins"]}–{total["losses"]}')
            + '<div class="ss-history-list">'
            '<div class="ss-history-row"><span>Weeks with 3+ picks</span>'
            f'<b>{HISTORICAL["weeks_at_least_3_2023_2025"]} / '
            f'{HISTORICAL["weeks_2023_2025"]}</b></div></div>',
            unsafe_allow_html=True)
        st.caption("Retrospective analysis using earlier-week data. These were not "
                   "independently verified, publicly issued historical betting picks.")
        st.markdown('<div class="ss-shortlist-history-heading">By season</div>'
                    + _history_table([
                        ("2023", HISTORICAL["seasons"][2023]),
                        ("2024", HISTORICAL["seasons"][2024]),
                        ("2025", HISTORICAL["seasons"][2025]),
                        ("2026 · Weeks 1–5 only", HISTORICAL["seasons"][2026]),
                    ]), unsafe_allow_html=True)
        st.markdown('<div class="ss-shortlist-history-heading">By category · 2023–2025</div>'
                    + _history_table([
                        (LABELS[tier], HISTORICAL["by_tier_2023_2025"][tier])
                        for tier in (1, 2, 3)
                    ]), unsafe_allow_html=True)
        st.markdown('<div class="ss-shortlist-history-heading">Potential additions · Separate from core</div>'
                    + _history_table([
                        ("2023–2025", HISTORICAL["addition_2023_2025"]),
                        ("2026 · Weeks 1–5", HISTORICAL["addition_2026_week1_to_5"]),
                    ]), unsafe_allow_html=True)
        st.caption("Historical figures are fixed reconstructions, not a live season-to-date "
                   "record. New results are graded only against saved pregame picks. "
                   "Straight-up accuracy does not establish betting profitability.")
