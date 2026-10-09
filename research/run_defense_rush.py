"""Sunday Slate research: dominant run defense against weak rushing offense.

Before examining results, define dominance as a bottom-quartile rushing yards
allowed PER CARRY and weakness as a bottom-quartile offensive rushing yards PER
CARRY, each based on prior completed regular-season games only. Teams must
have >=3 prior games. Quarter/third/40% are sensitivity checks, NOT an
optimized betting system.

Discovery: 2019–2022. Holdout: 2023–2025. 2026 YTD diagnostic.
Uses frozen pregame weekly snapshots. No contemporaneous outcomes/statistics
or final-season hindsight enter the qualification logic.

Usage: python -m research.run_defense_rush --output rush_study_results.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from research.test_qbr_defense import load_games
from sunday_slate.model import predict_regular_season

TRAIN = (2019, 2020, 2021, 2022)
HOLDOUT = (2023, 2024, 2025)
CURRENT = (2026,)
THRESHOLDS = (0.20, 0.25, 1 / 3, 0.40)
MIN_GAMES = 3
REQUIRED_STATS = {
    "season", "week", "game_id", "team", "opponent_team",
    "season_type", "carries", "rushing_yards",
}


def load_rush_stats(path: str | None = None) -> pd.DataFrame:
    if path:
        raw = pd.read_csv(path, low_memory=False)
    else:
        import nflreadpy
        raw = pd.DataFrame(nflreadpy.load_team_stats(
            seasons=list(TRAIN + HOLDOUT + CURRENT), summary_level="week"
        ).to_dicts())
    missing = REQUIRED_STATS.difference(raw.columns)
    if missing:
        raise ValueError(f"Missing team stats columns: {sorted(missing)}")
    df = raw.copy()
    for col in ("season", "week", "carries", "rushing_yards"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[df.season.isin(TRAIN + HOLDOUT + CURRENT) & df.season_type.eq("REG")]
    df = df[df.carries.gt(0) & df.rushing_yards.notna()].copy()
    for col in ("team", "opponent_team"):
        df[col] = df[col].astype(str).str.upper()
    if df.duplicated(["game_id", "team"]).any():
        dup = df[df.duplicated(["game_id", "team"], keep=False)][["game_id", "team"]]
        raise ValueError(f"Ambiguous multiple team rushing lines: {dup.head(5).to_dict('records')}")
    return df


def _snapshot(stats: dict[str, dict], min_games: int) -> tuple[dict[str, dict], list[float], list[float]]:
    eligible = {}
    for team, data in stats.items():
        if data["games"] < min_games or data["carries"] <= 0 or data["opp_carries"] <= 0:
            continue
        eligible[team] = {
            "rush_ypc": data["rush_yards"] / data["carries"],
            "rush_allowed_ypc": data["opp_rush_yards"] / data["opp_carries"],
            "games": data["games"],
        }
    return (eligible,
            [v["rush_ypc"] for v in eligible.values()],
            [v["rush_allowed_ypc"] for v in eligible.values()])


def _selection(home: str, away: str, ranks: dict[str, dict], weak_cut: float, strong_cut: float):
    if home not in ranks or away not in ranks:
        return None
    # Signal: that side has elite run defense, while its opponent struggles
    # rushing. Both sides qualifying makes it ambiguous: no selection.
    home_yes = ranks[home]["rush_allowed_ypc"] <= strong_cut and ranks[away]["rush_ypc"] <= weak_cut
    away_yes = ranks[away]["rush_allowed_ypc"] <= strong_cut and ranks[home]["rush_ypc"] <= weak_cut
    return home if home_yes and not away_yes else away if away_yes and not home_yes else None


def study(games: pd.DataFrame, rush: pd.DataFrame, min_games: int = MIN_GAMES) -> pd.DataFrame:
    """One game row per threshold, features frozen before all week results."""
    expected = REQUIRED_STATS.difference(rush.columns)
    if expected:
        raise ValueError(f"Team stats schema missing: {sorted(expected)}")
    game_list = games[games.season.isin(TRAIN + HOLDOUT + CURRENT)].copy()
    game_list = game_list.sort_values(["season", "week", "game_id"])
    if game_list.game_id.duplicated().any():
        raise ValueError("Schedule has duplicated game IDs")
    line_by_id = rush.set_index(["game_id", "team"], drop=False)
    if line_by_id.index.duplicated().any():
        raise ValueError("Team stats contain duplicate game/team")
    elo = predict_regular_season(games).set_index("game_id")[["predicted_winner", "pick_probability"]]

    out=[]
    coverage={"regular_games":0, "paired_team_stats":0}
    for season, season_games in game_list.groupby("season", sort=True):
        state = defaultdict(lambda: {
            "games":0, "rush_yards":0., "carries":0., "opp_rush_yards":0., "opp_carries":0.,
        })
        for week, slate in season_games.groupby("week", sort=True):
            ranks, offs, defs = _snapshot(state, min_games=min_games)
            cuts = {
                threshold:(float(pd.Series(offs).quantile(threshold)), float(pd.Series(defs).quantile(threshold)))
                for threshold in THRESHOLDS
            } if len(ranks) >= 10 else {}
            for g in slate.to_dict("records"):
                hs, aw = g["home_score"], g["away_score"]
                if pd.isna(hs) or pd.isna(aw) or hs == aw:
                    continue
                coverage["regular_games"]+=1
                prediction = elo.loc[g["game_id"]]
                home, away = g["home_team"], g["away_team"]
                for threshold, (weak_cut, strong_cut) in cuts.items():
                    candidate = _selection(home, away, ranks, weak_cut, strong_cut)
                    if candidate is None:
                        continue
                    margin = hs-aw
                    ats_line = pd.to_numeric(g.get("spread_line"), errors="coerce")
                    cover = None
                    # nflverse spread_line is a positive home favored margin;
                    # home covers when the home result exceeds the closing line.
                    if pd.notna(ats_line):
                        diff = margin - float(ats_line)
                        if abs(diff) > 1e-8:
                            cover = (diff > 0) if candidate == home else (diff < 0)
                    out.append({
                        "season":int(season), "week":int(week), "game_id":g["game_id"],
                        "threshold":round(float(threshold), 6), "signal_team":candidate,
                        "winner":home if hs>aw else away,
                        "elo_pick":prediction["predicted_winner"],
                        "elo_prob":float(prediction["pick_probability"]),
                        "run_defense_ypc_allowed":ranks[candidate]["rush_allowed_ypc"],
                        "opponent_rushing_ypc":ranks[away if candidate==home else home]["rush_ypc"],
                        "rush_defense_cutoff":strong_cut, "rush_offense_cutoff":weak_cut,
                        "spread_line":float(ats_line) if pd.notna(ats_line) else None,
                        "cover":cover,
                    })
            # Never use current games until ALL current week predictions frozen.
            for g in slate.to_dict("records"):
                if pd.isna(g["home_score"]) or pd.isna(g["away_score"]):
                    continue
                h,a=g["home_team"],g["away_team"]
                if (g["game_id"],h) not in line_by_id.index or (g["game_id"],a) not in line_by_id.index:
                    continue
                hrow=line_by_id.loc[(g["game_id"],h)]
                arow=line_by_id.loc[(g["game_id"],a)]
                if (str(hrow["opponent_team"])!=a or str(arow["opponent_team"])!=h
                    or int(hrow["week"])!=int(week) or int(arow["week"])!=int(week)
                    or int(hrow["season"])!=int(season) or int(arow["season"])!=int(season)):
                    raise ValueError(f"Incompatible opponent/team match for {g['game_id']}")
                coverage["paired_team_stats"]+=1
                for team, row, opponent in ((h,hrow,arow),(a,arow,hrow)):
                    state[team]["games"]+=1
                    state[team]["rush_yards"]+=float(row["rushing_yards"])
                    state[team]["carries"]+=float(row["carries"])
                    state[team]["opp_rush_yards"]+=float(opponent["rushing_yards"])
                    state[team]["opp_carries"]+=float(opponent["carries"])
    df=pd.DataFrame(out)
    df.attrs["coverage"]=coverage
    return df


def rate(data: pd.DataFrame, side: str, outcome_col: str = "winner") -> dict:
    n=len(data)
    w=int((data[side]==data[outcome_col]).sum())
    return {"games":n,"wins":w,"losses":n-w,"pct":round(w/n*100,2) if n else None}


def ats_rate(data: pd.DataFrame) -> dict:
    # pd.Series.eq(True) excludes pushes and missing spreads.
    valid=data[data.cover.notna()]
    n=len(valid)
    w=int((valid.cover==True).sum())
    return {"games":n,"wins":w,"losses":n-w,
            "pct":round(w/n*100,2) if n else None,
            "ungraded":int(len(data)-n)}


def results(df: pd.DataFrame, years: tuple[int,...]) -> list[dict]:
    all=df[df.season.isin(years)]
    out=[]
    for threshold in THRESHOLDS:
        r=all[all.threshold.eq(round(threshold,6))]
        conflict=r[r.signal_team.ne(r.elo_pick)]
        agree=r[r.signal_team.eq(r.elo_pick)]
        out.append({
            "quantile":round(threshold,4),
            "signal_winner":rate(r,"signal_team"),
            "elo_same_games":rate(r,"elo_pick"),
            "closing_spread_ats":ats_rate(r),
            "same_pick_as_elo":rate(agree,"signal_team"),
            "signal_overrides_elo":rate(conflict,"signal_team"),
            "elo_on_conflicts":rate(conflict,"elo_pick"),
            "net_changes_if_override":int((conflict.signal_team==conflict.winner).sum()-(conflict.elo_pick==conflict.winner).sum()),
            "season_breakdown":[{
                "season":int(y),
                "signal_winner":rate(r[r.season.eq(y)],"signal_team"),
                "elo_same_games":rate(r[r.season.eq(y)],"elo_pick"),
                "closing_spread_ats":ats_rate(r[r.season.eq(y)]),
            } for y in years],
        })
    return out


def select_training_rule(discovery: list[dict]) -> dict|None:
    # Must BEAT Elo in discovery both on same games and when overriding;
    # minimum 40 signal matches, 15 override disagreements.
    qualified=[
        r for r in discovery
        if r["signal_winner"]["games"]>=40
        and r["signal_overrides_elo"]["games"]>=15
        and r["net_changes_if_override"]>=5
    ]
    if not qualified:
        return None
    best=sorted(qualified,key=lambda r:(-r["net_changes_if_override"],-r["signal_winner"]["games"]))[0]
    return {"quantile":best["quantile"],"net_changes":best["net_changes_if_override"]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--games")
    parser.add_argument("--rush")
    parser.add_argument("--output")
    options=parser.parse_args()
    games=load_games(options.games)
    rush=load_rush_stats(options.rush)
    print("RAW STATS COLUMNS:",len(rush.columns))
    print("RUSH SOURCE COVERAGE:",rush.groupby("season").size().to_dict(),flush=True)
    study_results=study(games,rush)
    print("MATCHED:",study_results.attrs["coverage"],flush=True)
    discovery=results(study_results,TRAIN)
    holdout=results(study_results,HOLDOUT)
    current=results(study_results,CURRENT)
    chosen=select_training_rule(discovery)
    report={
        "definitions":"Using only prior completed game team stats, each team's seasonal rushing yards per carry; opposite team's rushed yards/carry allowed derived from that opponent's prior same-game rushing box. At least 3 earlier games each. Signal when defensive allowed YPC and opposing offensive YPC both fall within lowest league quantile among eligible teams. Candidate only when one side qualifies.",
        "league_cutoffs":"Computed anew at the start of each week from qualified teams' previous results. Lower defensive YPC allowed = better defense; lower offensive YPC = weaker rushing attack.",
        "source":"nflverse 2019-2026 team weekly statistics; nfldata schedule closing spread_line (positive indicates home favored). Untimestamped historical odds, not executable.",
        "limitations":"Rushing YPC depends on game context and rushing volume, is not opponent adjusted, and is not EPA/success rate. Retrospective reference closing ATS not prospective bet returns. No injury information.",
        "coverage":study_results.attrs["coverage"],
        "discovery_2019_2022":discovery,
        "holdout_2023_2025":holdout,
        "diagnostic_2026_ytd":current,
        "training_only_chosen_rule":chosen,
        "chosen_rule_holdout":next((r for r in holdout if r["quantile"]==chosen["quantile"]),None) if chosen else None,
        "decision":"Do not modify Sunday Slate Elo unless a signal adds consistent out-of-sample accuracy above the Elo baseline.",
    }
    output=json.dumps(report,indent=2,allow_nan=False)
    print("STUDY_JSON_BEGIN\n"+output+"\nSTUDY_JSON_END",flush=True)
    if options.output:
        Path(options.output).write_text(output+"\n")
    if study_results.empty:
        raise RuntimeError("Study produced zero eligible game signals; cannot claim backtest completed.")


if __name__=="__main__":
    main()
