"""Compact native Streamlit interface for research-only pregame parlays."""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from sunday_slate.parlay import (
    CORE_SOURCE, ELO_SOURCE, SORT_CHANCE, SORT_VALUE, eligible_legs, find_parlays,
)


def _team(team: str, brands: dict) -> str:
    return escape(str(brands.get(team, {}).get("name") or team))


def _leg_line(leg: dict, brands: dict) -> str:
    name = _team(leg["team"], brands)
    opponent = _team(leg["opponent"], brands)
    kickoff = pd.Timestamp(leg["kickoff"]).tz_convert("America/Chicago")
    when = kickoff.strftime("%a %-I:%M %p CT")
    mark = (f' · Tier {leg["tier"]}' if leg.get("tier") in (1, 2, 3) else "")
    return (
        '<div style="padding:8px 0;border-bottom:1px solid rgba(150,150,150,.18)">'
        f'<b>{name} ML</b> <span style="opacity:.75">{leg["odds"]:+d}</span>'
        f'<div style="font-size:.85rem;opacity:.72">vs {opponent} · '
        f'{when} · {leg["probability"]:.1%} model win chance{mark}</div>'
        '</div>'
    )


def _parlay_card(rank: int, parlay: dict, brands: dict) -> str:
    chance = parlay["probability"]
    edge = parlay["estimated_roi"]
    edge_line = (
        f'Model-estimated return on stake: {edge:+.1%} (unvalidated)'
        if edge > 0 else f'Model-estimated return on stake: {edge:+.1%} (unvalidated)'
    )
    return (
        '<div style="border:1px solid rgba(150,150,150,.3);'
        'border-radius:14px;padding:15px 18px;margin-bottom:12px">'
        '<div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap">'
        f'<span style="font-weight:750">Combination #{rank}</span>'
        f'<span style="font-weight:800;font-size:1.15rem">DK {parlay["american"]}</span>'
        '</div>'
        + "".join(_leg_line(leg, brands) for leg in parlay["legs"])
        + '<div style="display:flex;gap:16px;flex-wrap:wrap;'
          'padding-top:10px;font-size:.90rem">'
        f'<span><b>{chance:.1%}</b> modeled chance*</span>'
        f'<span><b>{parlay["break_even"]:.1%}</b> break-even chance</span>'
        f'<span><b>${parlay["payout_10"]:.2f}</b> total return on $10</span>'
        '</div>'
        f'<div style="font-size:.79rem;opacity:.72;padding-top:6px">{escape(edge_line)}</div>'
        '</div>'
    )


def render_parlay_finder(
    slate: pd.DataFrame, brands: dict, dk_quotes: dict, predictions: dict,
    snapshot: dict | None, selected: dict, *, now=None,
):
    """A standalone pregame feature: never replaces the saved weekly shortlist."""
    st.markdown('<div class="ss-section">Parlay Finder · DraftKings moneylines</div>',
                unsafe_allow_html=True)
    st.caption(
        "Combine qualifying upcoming games into 2–4 leg moneyline parlays. "
        "Prices are delayed DraftKings quotes, not a sportsbook bet slip."
    )
    options = [CORE_SOURCE, ELO_SOURCE] if snapshot is not None else [ELO_SOURCE]
    a, b, c, d = st.columns([1.5, 1, 1.1, 1.4])
    with a:
        source = st.selectbox(
            "Pick source", options, key="parlay_pick_source",
            help="Archived core picks require a verified pregame snapshot. "
                 "Elo favorites use the app's earlier-week model.",
        )
    with b:
        count = st.selectbox("Legs", [2, 3, 4], key="parlay_leg_count")
    with c:
        threshold = st.selectbox(
            "Minimum leg chance", [0.60, 0.65, 0.70, 0.75, 0.55],
            format_func=lambda x: f"{x:.0%}", key="parlay_min_probability",
        )
    with d:
        order = st.selectbox(
            "Rank by", [SORT_CHANCE, SORT_VALUE], key="parlay_rank_by",
        )

    core = selected.get("core", []) if snapshot is not None else []
    legs = eligible_legs(
        slate, dk_quotes, predictions, core, source=source,
        min_probability=threshold, now=now,
    )
    st.caption(
        f"{len(legs)} eligible games · {source} · "
        "one leg per game · no same-game parlays"
    )
    if len(legs) < count:
        st.info(
            f"Only {len(legs)} eligible leg(s) found; {count} are needed. "
            "Try fewer legs, a lower minimum chance, or Elo favorites. "
            "Games without both DraftKings moneylines are excluded."
        )
    else:
        parlays = find_parlays(legs, count, sort_by=order, limit=3)
        if order == SORT_VALUE:
            st.caption(
                "Value sorting uses uncalibrated model probabilities. "
                "A positive estimate does not prove a profitable opportunity."
            )
        for i, parlay in enumerate(parlays, 1):
            st.markdown(_parlay_card(i, parlay, brands), unsafe_allow_html=True)
        with st.expander(f"All eligible moneyline legs ({len(legs)})"):
            rows = [{
                "Team": brands.get(x["team"], {}).get("name") or x["team"],
                "Opponent": brands.get(x["opponent"], {}).get("name") or x["opponent"],
                "DraftKings ML": f'{x["odds"]:+d}',
                "Model win chance": f'{x["probability"]:.1%}',
                "Kickoff (CT)": x["kickoff"].tz_convert("America/Chicago").strftime("%a %b %-d %-I:%M %p"),
            } for x in legs]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(
        "* Combined win chances multiply the individual model estimates and "
        "assume independent outcomes; they are not empirically validated "
        "parlay probabilities. Returns are illustrative at the quoted prices; "
        "injuries, changing lines, and correlated outcomes can alter the risk. "
        "Check quarterbacks and prices before considering any wager. "
        "No bets are placed in this app."
    )
