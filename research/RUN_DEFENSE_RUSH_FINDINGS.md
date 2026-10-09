# Scenario 02: Dominant run defense versus weak rushing offense

**Executed:** October 9, 2026  
**Repository research code:** [run_defense_rush.py](run_defense_rush.py)  
**Results:** [GitHub Actions run and downloadable JSON](https://github.com/christianmellis1-debug/Sunday-slate/actions/runs/37988424440)

## Hypothesis and pregame-only definition

Does a defense that is unusually effective at stopping the run beat an opponent with an unusually inefficient rushing attack, straight-up or ATS?

- **Dominant run defense:** Bottom quartile of NFL teams in *opponent rushing yards per carry allowed*. Lower allowed YPC is better.
- **Weak rushing offense:** Bottom quartile of NFL teams in *own rushing yards per carry*. Lower offensive YPC is worse.
- Compute each team's cumulative yards/carries **using earlier completed regular-season games within the same season**. Recreate rankings at the start of each game week, using only eligible teams' previous matches.
- Require **at least three prior games for both teams**. Signal is eligible only if one and only one team satisfies this strong-defense vs. weak-offense matchup. If both qualify, omit as ambiguous.
- Do not use target-week results or final-season rankings when assigning the pregame signals.
- For straight-up records, exclude tied finishes and unplayed games.
- Grade ATS at NFLverse historical `spread_line`: positive means the home team was favored; margin-minus-spread > 0 means home covered. Pushes/missing spreads do not count in ATS denominator.
- **2019–2022:** discovery cohort. **2023–2025:** later historical evaluation. **2026:** incomplete diagnostic, not part of conclusions.
- Sensitivity: 20%, 25% (primary), 33.33%, 40% quantiles. Quartiles are defined relative to all teams with the required prior-game history in that same week; these are *not* calibrated numeric cutoff YPC values.

The yardage-per-carry test is a rushing efficiency proxy, **not** a measure of defensive rushing EPA, rushing success rate, tackle-for-loss rate, injuries, or opponent-adjusted strength.

## Primary results: 25th-percentile threshold

| Cohort | Games | Signal straight-up | Frozen Sunday Slate Elo straight-up on same games | Historical ATS | Elo override |
| --- | ---: | ---: | ---: | ---: | ---: |
| Discovery 2019–2022 | 97 | 60–37 (61.86%) | 67–30 (69.07%) | 45–50 (47.37%), two ungraded | 15–22 when conflicting (37 games) |
| **Holdout 2023–2025** | **85** | **50–35 (58.82%)** | **60–25 (70.59%)** | **46–37 (55.42%), two ungraded** | **13–23 when conflicting (36 games)** |
| Preliminary 2026 | 2 | 0–2 | 2–0 | 1–0, one ungraded | 0–2 |

**Against-the-spread 2023–2025 by year:**
- 2023: 13–12 (52.0%), 27 SU qualifying games
- 2024: 17–14 (54.84%), 31 SU qualifying games
- 2025: 16–11 (59.26%), 27 SU qualifying games

The 2019–2022 ATS result was **negative**, and the later 2023–2025 positive ATS rate is based on just 83 graded spreads, not a validated profitable betting edge. Odds price, bet availability, bookmaker, line-change timing, and staking are unverified; do not present as real returns or guaranteed profit.

### Sensitivity comparison (2023–2025)

| Cutoff | Qualifying games | Signal SU | Elo SU, same games | Signal historical ATS | Override Elo SU |
| --- | ---: | ---: | ---: | ---: | ---: |
| 20% | 66 | 40–26 (60.61%) | 45–21 (68.18%) | 35–29 (54.69%), two ungraded | 13–18 (31 games) |
| **25% primary** | **85** | **50–35 (58.82%)** | **60–25 (70.59%)** | **46–37 (55.42%), two ungraded** | **13–23 (36 games)** |
| 33.33% | 144 | 82–62 (56.94%) | 98–46 (68.06%) | 72–69 (51.06%), three ungraded | 20–36 (56 games) |
| 40% | 185 | 104–81 (56.22%) | 126–59 (68.11%) | 93–87 (51.67%), five ungraded | 26–48 (74 games) |

The script checks whether any discovery-only rule has >=40 signals, >=15 disagreements with Elo, and would **correct at least five Elo errors**. No threshold met this improvement requirement. **No threshold was selected for deployment**. The held-out years have not been used to tune an official rule.

## Decision

**Do not override Elo or introduce a run-defense betting tier from this test.** Even on the most favorable threshold, the signal does not outperform the existing model when compared on identical games. The 25% filter's 55.4% historical cover rate is potentially worth further exploration, but the discovery period's 47.4% is inconsistent and not a reliable claim of betting value.

Next worthwhile tests:
- Use **defensive rush EPA per rush** and offensive rush EPA per rush, calculated before kickoff, instead of basic YPC.
- Control for game script, opponent rushing volume, sportsbook spread size and rushing attempts.
- Repeat on separate 2026 forward-only weekly snapshots to establish what could have been known at the time.
- If exploring ATS value, require independently timestamped pre-kickoff lines and prices.

## Attribution, reproducibility

- Team rushing box scores from NFLverse through `nflreadpy.load_team_stats` (`summary_level="week"`), joined to game ID and opposing team. The research workflow matched **1,936 completed game pairs** in 2019–2026, including ties, and identified 1,930 decisive games for evaluation.
- Game results and closing spreads from NFLverse NFL schedules, which define `spread_line` as positive when home is favored. The reported ATS comparison is **retrospective reference-spread grading**, not a simulated bet record.

Re-run on current releases:
```bash
python -m research.run_defense_rush --output run_defense_rush_results.json
```

Use `--games` and `--rush` for locally pinned files. Results can shift if providers update historical data.
