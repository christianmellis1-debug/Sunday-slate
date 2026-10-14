import pandas as pd
from research.weekly_shortlist import ranked_candidates, pregame_flags, weekly_scores


def rows():
    def row(id,conf,ppg,correct=True,ch=.8):
        return {"season":2026,"week":6,"game_id":id,"pick_probability":conf,
                "home_probability":conf,"predicted_winner":id,
                "challenger_home_probability":ch,"ppg_projected_margin":ppg,
                "min_prior_games":5,
                "pick_result":"Correct" if correct else "Incorrect"}
    return pd.DataFrame([row("heavy",.80,-10,False),row("double",.69,8),
                         row("consensus",.65,3),row("weak",.55,13),
                         row("borderline",.61,-4)])


def test_tiers_and_no_forced_weak_picks():
    f=rows()
    chosen=ranked_candidates(f,"Tier priority 1–3, maximum 5")
    assert [r["game_id"] for r in chosen]==["heavy","double","consensus"]
    strict=ranked_candidates(f,"Strict Tier 1–2, maximum 5")
    assert [r["game_id"] for r in strict]==["heavy","double"]
    assert pregame_flags(f.iloc[0])["tier"]==1


def test_outcomes_never_select_or_rank_the_picks():
    first=rows()
    second=first.copy()
    second["pick_result"]="Incorrect"
    assert [r["game_id"] for r in ranked_candidates(first,"Tier priority 1–3, maximum 5")]==[
        r["game_id"] for r in ranked_candidates(second,"Tier priority 1–3, maximum 5")]


def test_no_partial_week_in_backtest():
    x=rows()
    x.loc[x.game_id=="weak","pick_result"]="Pending"
    assert weekly_scores(x,"Elo top 3 (unfiltered baseline)")==[]
