# Sunday Slate — Higher pregame QB QBR + lower PPG allowed
**Research date:** October 19, 2026  
**Scope:** 2023–2025 regular seasons; 2026 completed through Week 6. Week 1 excluded.  
**Research workflow:** [Successful historical test](https://github.com/christianmellis1-debug/Sunday-slate/actions/runs/39310667085)  
**Reproduce:** `python -m research.qbr_ppg_historical_validation`  
**Outputs:** GitHub Actions JSON/CSV artifact (30-day retention). Production model unchanged.

## Definitions and leakage limits
* Higher QBR: player selected as team’s most-used QB **in target game** (retrospective QB ID); compute his ESPN weekly Total QBR weighted by QB plays from **earlier games only in that season**, with >=30 prior QB plays. **Not** ESPN’s official season composite QBR, not a verified pregame starter, and vulnerable to retrospective player-selection bias.
* Defense: fewer average points allowed in previous **same-season** completed regular-season games; freeze predictions at start of week. No opponent/venue adjustment. Never use target-game defensive points.
* Elo: existing Sunday Slate NFL-ELO-1.0 predictions, unchanged, same-game comparison.
* Qualifying match: both QBR proxies present and unequal; both defensive PPG present and unequal; factors select the same team; no tied final game.
* Week 1 omitted to avoid uncalibrated current-season defensive ratings.
* Historical nflverse QBR releases and schedules were retrieved retrospectively and may contain subsequent statistical revisions.
* Spread is a reference closing spread, not a verified executable historical sportsbook price.

## Historical outcomes

| Season | QBR + lower PPG | Win % | Elo, same games |
|---|---:|---:|---:|
| 2023 | 75–48 | 60.98% | 84–39 (68.29%) |
| 2024 | 73–36 | 66.97% | 75–34 (68.81%) |
| 2025 | 84–32 | 72.41% | 87–29 (75.00%) |
| **2023–2025** | **232–116** | **66.67%** | **246–102 (70.69%)** |
| **2026 Weeks 2–6** | **20–9** | **68.97%** | **21–8 (72.41%)** |

### Season maturity
* 2023–2025 Weeks 2–6: 51–43, **54.26%**; Elo 63–31, **67.02%**.
* 2023–2025 Weeks 7–18: 181–73, **71.26%**; Elo 183–71, **72.05%**.
* Individual early cohorts: 2023 21–13 (61.76%), **2024 9–18 (33.33%)**, 2025 21–12 (63.64%), 2026 20–9 (68.97%).
* Minimum five earlier games each: 2023–2025 191–76 (71.54%), Elo 193–74 (72.28%).

### Elo agreement versus override
* Elo + QBR + PPG agree: 210–80, **72.41%** across 290 games.
* QBR + PPG disagree with Elo: 22–36, **37.93%**, across 58 games. **Do not override Elo** on this evidence.
* 2026 Weeks 2–6 three-factor agreement: 16–4 (80.00%), 20 games.
* 2026 Weeks 2–6 against Elo: QBR + PPG 4–5, Elo 5–4, nine games.

### Strength-of-signal strata (2023–2025)
| Defensive PPG allowed advantage | QBR + PPG | Elo on same games |
|---|---:|---:|
| Under 3 | 66–49 (57.39%) | 76–39 (66.09%) |
| 3 to under 7 | 97–42 (69.78%) | 98–41 (70.50%) |
| 7+ | 69–25 (73.40%) | 72–22 (76.60%) |

| QBR advantage | QBR + PPG | Elo on same games |
|---|---:|---:|
| Under 5 | 37–16 (69.81%) | 39–14 (73.58%) |
| 5 to under 10 | 38–23 (62.30%) | 46–15 (75.41%) |
| 10 to under 20 | 67–35 (65.69%) | 68–34 (66.67%) |
| 20+ | 90–42 (68.18%) | 93–39 (70.45%) |

* Pre-reviewed retrospective threshold QBR gap >=10 and PPG allowed gap >=7: **54–18 (75%)**; Elo **55–17 (76.39%)** on same 72. Selection bias cautions apply.
* The 2026 small sample does **not** replicate the monotonically stronger defense gap: defense gap 7+ was 8–7 (53.33%) versus 0–3 at 5–1 and 3–7 at 7–1.

### Home/away, market context
* Historical home selections 129–49 (72.47%); road selections 103–67 (60.59%).
* Higher-QBR/better-defense chosen side was a closing-spread favorite in **303 of 348 games**. Favorites 223–80, underdogs **9–36**.
* Against reference closing spreads: **168–173, 7 pushes (49.27% of decisions)** in 2023–2025. Does not establish a positive betting edge.
* 2026 early reference ATS: **13–13, 3 pushes**, 50.00% of decisions.

### Forward-look sensitivity (less selection hindsight)
* Using the **prior-most-used** QB as the QB selection (without seeing target-game play shares), 2023–2025 signal: **267–143 (65.12%)**, Elo **287–123 (70.00%)** on same 410 selections.
* 2026 Weeks 2–6 prior QB leader + defense: 24–9 (72.73%), Elo 24–9 on those 33 games.
* An earlier, different Sunday Slate study averaged only the prior four QB weeks and found 248–150 (62.31%) versus Elo 271–127 on that historical agreement cohort. This uses a DIFFERENT QB methodology and cannot be directly merged with current counts.

## Decision
1. **Do not replace Elo** or deploy an override. More historical winners among a subset does not imply incremental model skill or sportsbook value.
2. Keep as **research-only confirmation and explanation** of why an Elo favorite looks supported by the passing game and scoring defense.
3. Prospectively archive starter identity, as-of QBR, defensive PPG, Elo pick and sportsbook moneyline **before kickoff**, then grade future games.
4. Review across a separate later-season set and compare against implied sportsbook probability, especially favorites; test smaller explicit rule families without tuning them to the already inspected historical data.
