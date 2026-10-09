# Scenario 03 — Elite defensive rush EPA versus weak offensive rush EPA

**Test performed:** October 9, 2026. Historical data: nflverse weekly team statistics and NFL schedule, fetched at execution.

[Reproducible Python study](run_defense_rush_epa.py) · [Successful historical GitHub run and archived JSON results](https://github.com/christianmellis1-debug/Sunday-slate/actions/runs/37989584110)

## Pregame hypothesis and rules

This repeats [Scenario 02: rushing yards per carry](RUN_DEFENSE_RUSH_FINDINGS.md) using **EPA per rushing attempt** rather than yards per rushing attempt.

- Offensive rushing efficiency = team's *sum of rushing EPA* / *sum of carries*, from regular-season games **completed before the target week**.
- Defensive rushing EPA allowed = *sum of opponents' rushing EPA* / *sum of opponent carries*, derived by joining each previous game to its opposing offense's recorded line. **Lower allowed EPA/carry is stronger defense.**
- An eligible team must have a top-quartile defense by lowest EPA allowed/carry, while the opposing offense must be bottom-quartile by lowest offensive rushing EPA/carry. This includes negative EPA.
- Rank teams by prior-game-only cumulative efficiency before the selected week's games. At least **3 prior games for both teams**; exclude both-teams-qualify ambiguities.
- Sensitivity calculations are exploratory for 20%, 25%, 33⅓%, and 40% league quantiles. **25%** is the primary prespecified threshold.
- Discovery 2019–2022; later evaluation 2023–2025; small, incomplete 2026 separate.
- Compare all signal game outcomes with **frozen NFL-ELO-1.0 on identical games**, without updating the application model. For ATS use nflverse historical reference closing spread; pushes and ungraded spreads are excluded.

EPA is already model-derived. Neither reported EPA nor the archived reference closing line has an independent historical pre-kickoff availability guarantee.

## Primary 25% threshold

| Period | EPA signal straight up | Elo straight up, same games | Historical closing ATS |
|---|---|---|---|
| 2019–2022 discovery | 49–32 (60.49%), 81 games | 59–22 (72.84%) | 44–36 (55.00%), 1 ungraded |
| **2023–2025 evaluation** | **44–29 (60.27%), 73 games** | **51–22 (69.86%)** | **41–31 (56.94%), 1 ungraded** |
| 2026 preliminary | 2–1, 3 games | 3–0 | 0–1, 2 ungraded |

### ATS by holdout season

- 2023: **13–15** (46.43%).
- 2024: **16–4** (80.00%).
- 2025: **12–12** (50.00%).

**2024 accounts for the historical ATS improvement; it did not hold consistently in the adjacent seasons.**

### What happens when the EPA signal disagrees with Elo?

- 2019–2022: EPA signal **7–17** in 24 conflicts; Elo **17–7**.
- 2023–2025: EPA signal **7–14** in 21 conflicts; Elo **14–7**.

No threshold passed the discovery-period rule for overriding Elo, so the code selects **no** new rule. Applying the signal instead of Elo would have reduced accuracy across these conflicts.

## Threshold sensitivity: 2023–2025

| EPA quartile cutoff | Qualifying games | Straight-up | Elo on same games | ATS reference spread |
|---|---:|---|---|---|
| Top/bottom 20% | 49 | 31–18 (63.27%) | 35–14 (71.43%) | 29–19 (60.42%) out of 48 |
| **Top/bottom 25%** | **73** | **44–29 (60.27%)** | **51–22 (69.86%)** | **41–31 (56.94%)** out of 72 |
| Top/bottom 33⅓% | 142 | 89–53 (62.68%) | 102–40 (71.83%) | 78–62 (55.71%) out of 140 |
| Top/bottom 40% | 192 | 124–68 (64.58%) | 135–57 (70.31%) | 103–86 (54.50%) out of 189 |

The top/bottom 20% line looks strongest for ATS but includes only **48 graded spread results**, including a 12–1 run in 2024, compared with 8–9 in 2023 and 9–9 in 2025. It is **not a proven profitable strategy**.

## Comparison to the earlier yards-per-carry test

| 2023–2025, 25% definition | Rushing YPC | Rushing EPA |
|---|---:|---:|
| Games | 85 | 73 |
| Straight-up win rate | 50–35 (58.82%) | 44–29 (60.27%) |
| Historical ATS cover rate | 46–37 (55.42%) | 41–31 (56.94%) |
| Elo win rate on selected games | 60–25 (70.59%) | 51–22 (69.86%) |

The two screens have **different qualifying matches**, so their win-rate differences do not form a direct matched-pairs statistical test. The observed EPA cover rate is only modestly higher and is concentrated in one year.

## Decision

**Do not alter Elo or launch a betting tier.** The EPA matchup is a descriptive historical signal and may help flag football matchups, but it does not establish predictive improvements over Elo. The historical 56.94% reference ATS rate lacks consistency by season and does not include authenticated bettable pre-kickoff odds, prices, or realistic returns.

For further research, compare **rush success rate and defensive EPA per rush** with adjusted opponent strength, excluding garbage time and controlling for game script and rushing volume. Score only pre-registered selections against actually archived pre-kickoff spreads/odds.

## Coverage and reproduction

- 3,872 eligible team-week rows across 2019–2026
- 1,936 complete game pairs with rushing EPA team statistics
- 1,930 decisive completed regular-season games in the research window (eligible-game screening later restricts this)
- Missing/invalid stats fail closed; no current-week EPA or game results are used to qualify a team.

```bash
python -m research.run_defense_rush_epa --output rush_epa_results.json
```

The source may revise historical EPA and reference lines; to replicate the exact historical snapshot, archive and supply the specific input CSVs using `--games games.csv --epa stats.csv`.
