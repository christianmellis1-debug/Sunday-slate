# Tier 2 proposed +6 PPG rule — frozen research candidate

**As of October 13, 2026. Research only.**

We are evaluating a revised version of **Tier 2 — Double Confirmation**. The official research waterfall remains at **+7 PPG** and the live Streamlit prediction model is unchanged. No betting line or non-DraftKings odds are used.

## Candidate qualification (first-match-wins, after Heavy Favorite)

- Elo win probability >=60% and <75%.
- Both teams have at least three prior regular-season games in the current season.
- Overall preweek offensive PPG and defensive PPG allowed yield the same winner as Elo.
- Their adjusted PPG projected winning margin is **at least +6 points** (rather than the original +7).
- All forecasts use statistics available before the scheduled game week.

The projected score difference is *not* the sportsbook spread. The Elo 75%+ **Heavy Favorite** category still gets priority.

## Historical comparison

| Window | +6 candidate | +7 original | Newly included 6 to under 7 |
| --- | ---: | ---: | ---: |
| 2014–2018 exploratory | 100–37, 73.0% | 71–21, 77.2% | 29–16, 64.4% |
| 2019–2022 development | 79–26, 75.2% | 49–16, 75.4% | 30–10, 75.0% |
| 2023–2025 previously inspected | **68–19, 78.2%** | 47–16, 74.6% | **21–3, 87.5%** |
| **2026 through Week 5** | **1–1, 50.0%** | **1–1, 50.0%** | No games |

The +6 margin is more inclusive but does not universally beat +7 historically. The 2023–2025 period was already inspected to choose +6, so this is exploratory and should **not** be called independent validation.

## Every completed 2026 Tier 2 (+6) matchup

| Week | Game | Elo selection | Elo confidence | PPG projected edge | Actual score | Result |
| --- | --- | --- | ---: | ---: | --- | --- |
| 4 | Chargers at Seahawks | Seattle | 71.7% | SEA +11.5 | SEA 30–23 LAC | Win |
| 4 | Patriots at Bills | Buffalo | 65.2% | BUF +8.3 | NE 29–26 BUF | Loss |

No added +6-to-under-+7 qualifiers occurred in completed Weeks 1–5.

## The next **frozen**, not yet completed 2026 week

[October 13 Week 6 archive](snapshots/2026_week_06.json): Chargers at Chiefs, **Kansas City**, Elo **68.0%** and projected PPG margin **KC +11.625**. Qualifies under both +6 and +7.

No other Week 6 game meets the +6-specific rule. Later-season games are **not** asserted as confirmed qualifiers because later preweek results are unknown.

## Research implementation and weekly tracking

The [research classification evaluator](tiers_validation.py) reports +6 and +7 side-by-side without changing the existing four-tier waterfall. The [frozen archive grader](frozen_weekly.py) grades +6 / +7 / newly-added 6–under–7 matches from the **original** saved picks each week. It does not rewrite archived JSON or historical predictions.

Preserve both threshold definitions throughout prospective 2026 analysis. On each new week report the number and record of extra +6-to-under-+7 games. Do not promote +6 to production until its newer performance and sample size support that decision.
