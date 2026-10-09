"""Retrospective NFL pregame hypothesis tests: Total QBR and defense.

USAGE
 python -m research.test_qbr_defense --output research/scenarios_results.json
 python -m research.test_qbr_defense --games games.csv --qbr qbr_week_level.csv

Definitions, frozen before reviewing results:
1. QB advantage = higher QB-plays-weighted ESPN Total QBR in the preceding
   four regular-season weeks, for each team's highest-usage *prior* QB.
   This is a historical leading-passer proxy, NOT a confirmed starter QBR.
2. Defense advantage = lower points allowed / game in prior regular-season
   weeks of the SAME season. The game being graded never enters the inputs.
3. Skip missing coverage, ties, equal ratings, and week-one comparisons.
4. NFL 2023-2025 regular seasons are primary; 2026 incomplete diagnostic.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from sunday_slate.model import predict_regular_season

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
QBR_URL = "https://github.com/nflverse/nflverse-data/releases/download/espn_data/qbr_week_level.csv"

# Source-specific team labels, normalized to nflverse games abbreviations.
ALIASES = {"LAR":"LA", "STL":"LA", "JAC":"JAX", "WSH":"WAS", "SD":"LAC", "SDG":"LAC", "OAK":"LV"}
def normalized(team: object) -> str:
    name = str(team).strip().upper()
    return ALIASES.get(name, name)


def load_games(path: str | None = None) -> pd.DataFrame:
    x = pd.read_csv(path or GAMES_URL, low_memory=False)
    fields = ["season", "week", "game_type", "game_id", "home_team", "away_team", "home_score", "away_score"]
    if not set(fields).issubset(x.columns):
        raise ValueError("NFL schedule schema missing required fields")
    x = x[x.game_type.eq("REG")].copy()
    x["season"] = pd.to_numeric(x["season"], errors="coerce")
    x["week"] = pd.to_numeric(x["week"], errors="coerce")
    for col in ("home_score", "away_score"):
        x[col] = pd.to_numeric(x[col], errors="coerce")
    for side in ("home", "away"):
        x[side+"_team"] = x[side+"_team"].map(normalized)
    return x


def load_qbr(path: str | None = None) -> pd.DataFrame:
    raw = pd.read_csv(path or QBR_URL, low_memory=False)
    needed = {"season", "season_type", "game_week", "week_num", "team_abb", "player_id", "qbr_total", "qb_plays"}
    if not needed.issubset(raw):
        raise ValueError("ESPN QBR schema missing: " + str(sorted(needed.difference(raw.columns))))
    x = raw.copy()
    for col in ("season", "week_num", "qbr_total", "qb_plays"):
        x[col] = pd.to_numeric(x[col], errors="coerce")
    x = x[x.season_type.astype(str).str.lower().eq("regular")].copy()
    x["team_abb"] = x["team_abb"].map(normalized)
    x = x[x["week_num"].between(1, 18) & x.qbr_total.between(0, 100) & x.qb_plays.gt(0)]
    x = x.dropna(subset=["season", "week_num", "team_abb", "player_id"])
    # Ambiguous duplicate QB-week rows must not double count any plays.
    x = x.drop_duplicates(subset=["season", "week_num", "team_abb", "player_id"], keep=False)
    return x


def _leading_passer_qbr(prior: pd.DataFrame, week: int, min_plays: int) -> dict[str, dict]:
    window = prior[prior.week_num.ge(max(1, week-4)) & prior.week_num.lt(week)]
    leaders = {}
    for team, team_rows in window.groupby("team_abb"):
        candidates = []
        for pid, player in team_rows.groupby("player_id"):
            plays = float(player.qb_plays.sum())
            if plays < min_plays:
                continue
            score = float((player.qbr_total * player.qb_plays).sum() / plays)
            if 0 <= score <= 100:
                candidates.append((plays, str(pid), score, int(len(player))))
        if candidates:
            plays, pid, score, starts = sorted(candidates, key=lambda x: (-x[0], x[1]))[0]
            leaders[team] = {"qbr":score, "plays":plays, "player_id":pid, "games":starts}
    return leaders


def evaluate_games(games: pd.DataFrame, qbr: pd.DataFrame, years: tuple[int, ...] = (2023, 2024, 2025, 2026),
               min_plays: int = 30, min_def_games: int = 1) -> pd.DataFrame:
    """Grades only games with pregame available data. No within-week updates."""
    events = []
    games = games[games.season.isin(years)].copy()
    games = games.sort_values(["season", "week", "game_id"], kind="stable")
    for season, year in games.groupby("season", sort=True):
        qb_year = qbr[qbr.season.eq(season)]
        prev_def = defaultdict(lambda: [0., 0])  # conceded points, games
        for week, slate in year.groupby("week", sort=True):
            qb_prior = _leading_passer_qbr(qb_year, int(week), min_plays)
            current = []
            for g in slate.to_dict("records"):
                hs, aw = g["home_score"], g["away_score"]
                if pd.isna(hs) or pd.isna(aw) or hs == aw:
                    continue
                ht, at = g["home_team"], g["away_team"]
                win = ht if hs > aw else at
                dh, da = prev_def[ht], prev_def[at]
                ddef = None
                if dh[1] >= min_def_games and da[1] >= min_def_games:
                    home_ppa, away_ppa = dh[0]/dh[1], da[0]/da[1]
                    if abs(home_ppa - away_ppa) > 1e-9:
                        ddef = ht if home_ppa < away_ppa else at
                home_qb, away_qb = qb_prior.get(ht), qb_prior.get(at)
                qwinner = None
                if home_qb and away_qb and abs(home_qb["qbr"] - away_qb["qbr"]) > 1e-9:
                    qwinner = ht if home_qb["qbr"] > away_qb["qbr"] else at
                current.append({
                    "season": int(season), "week": int(week), "game_id":g["game_id"],
                    "home_team":ht, "away_team":at, "winning_team":win,
                    "defense_team":ddef, "defense_correct":None if ddef is None else ddef==win,
                    "qbr_team":qwinner, "qbr_correct":None if qwinner is None else qwinner==win,
                    "both_agree":bool(ddef and qwinner and ddef==qwinner),
                    "def_home_ppg_allowed":dh[0]/dh[1] if dh[1] else None,
                    "def_away_ppg_allowed":da[0]/da[1] if da[1] else None,
                    "home_pregame_qbr":home_qb["qbr"] if home_qb else None,
                    "away_pregame_qbr":away_qb["qbr"] if away_qb else None,
                    "home_qb_plays":home_qb["plays"] if home_qb else None,
                    "away_qb_plays":away_qb["plays"] if away_qb else None,
                })
            events.extend(current)
            # Update only after every prediction for this week has been taken.
            for g in slate.to_dict("records"):
                hs, aw = g["home_score"], g["away_score"]
                if pd.isna(hs) or pd.isna(aw):
                    continue
                prev_def[g["home_team"]][0] += aw
                prev_def[g["home_team"]][1] += 1
                prev_def[g["away_team"]][0] += hs
                prev_def[g["away_team"]][1] += 1
    return pd.DataFrame(events)


def stats(frame: pd.DataFrame, team_field: str) -> dict:
    clean = frame[frame[team_field].notna()]
    n = len(clean)
    wins = int((clean[team_field] == clean["winning_team"]).sum())
    return {"wins":wins, "losses":n-wins, "games":n, "win_rate":round(wins/n, 4) if n else None}


def summarize(frame: pd.DataFrame, years: tuple[int, ...]) -> dict:
    s = frame[frame.season.isin(years)].copy()
    comparable = s[s.qbr_team.notna() & s.defense_team.notna()]
    agree = comparable[comparable.qbr_team == comparable.defense_team]
    disagree = comparable[comparable.qbr_team != comparable.defense_team]
    return {
        "year_range": list(years), "decisive_games":int(len(s)),
        "higher_pregame_qbr":stats(s,"qbr_team"),
        "better_defense_ppg_allowed":stats(s,"defense_team"),
        "same_games_qbr":stats(comparable,"qbr_team"),
        "same_games_defense":stats(comparable,"defense_team"),
        "same_games_elo_baseline":stats(comparable,"elo_team") if "elo_team" in comparable else None,
        "qb_and_defense_agree":stats(agree,"qbr_team"),
        "qb_and_defense_agree_elo_baseline":stats(agree,"elo_team") if "elo_team" in agree else None,
        "qb_and_defense_disagree_qb":stats(disagree,"qbr_team"),
        "qb_and_defense_disagree_defense":stats(disagree,"defense_team"),
        "qb_coverage_missing":int(s.qbr_team.isna().sum()),
        "defense_coverage_missing":int(s.defense_team.isna().sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="NFL pregame QBR versus defense hypotheses")
    parser.add_argument("--games")
    parser.add_argument("--qbr")
    parser.add_argument("--output")
    parser.add_argument("--min-qb-plays", type=int, default=30)
    parser.add_argument("--min-def-games", type=int, default=1)
    args = parser.parse_args()
    games, qbr = load_games(args.games), load_qbr(args.qbr)
    print("SOURCES: nflverse games & ESPN Total QBR weekly. QBR release years:",sorted(set(qbr.season.dropna().astype(int).tolist())))
    print("NOTE: Quarterback is the previous 4-week highest-usage QB (NOT guaranteed current starter); Total QBR is approximate plays-weighted average.")
    print("DEFENSE: same-season opponents' PPG allowed in prior weeks; lower wins; ties/missing omitted.")
    scored = evaluate_games(games, qbr, min_plays=args.min_qb_plays, min_def_games=args.min_def_games)
    # Same-game comparison: the original, unchanged Sunday Slate Elo model.
    frozen = predict_regular_season(games)
    lookup = frozen.set_index("game_id")["predicted_winner"]
    scored["elo_team"] = scored.game_id.map(lookup)
    grouped = {
        "combined_2023_2025":summarize(scored,(2023,2024,2025)),
        "2023":summarize(scored,(2023,)),
        "2024":summarize(scored,(2024,)),
        "2025":summarize(scored,(2025,)),
        "2026_incomplete":summarize(scored,(2026,)),
        "2023_2025_three_def_games":summarize(evaluate_games(games,qbr, min_plays=args.min_qb_plays,min_def_games=3),(2023,2024,2025)),
        "2023_2025_higher_100_qb_plays":summarize(evaluate_games(games,qbr,min_plays=100,min_def_games=args.min_def_games),(2023,2024,2025)),
    }
    report={"settings":{"min_qb_plays":args.min_qb_plays,"min_defense_games":args.min_def_games, "metric_defense":"pregame PPG allowed", "metric_qbr":"ESPN Total QBR previous four weeks, weighted mean by QB plays, highest usage prior QB"}, "results":grouped}
    output=json.dumps(report,indent=2,allow_nan=False)
    print(output,flush=True)
    if args.output:
        Path(args.output).parent.mkdir(parents=True,exist_ok=True)
        Path(args.output).write_text(output+"\n")


if __name__=="__main__":
    main()
