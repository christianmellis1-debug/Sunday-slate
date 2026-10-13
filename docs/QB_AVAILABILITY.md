# QB Availability Confirmation — Sunday Slate

**Status: experimental research panel. The official NFL-ELO-1.0 pick, probability, tiers, and value screens never change.** This feature is opt-in to preserve Streamlit Community Cloud startup performance.

## How to use

1. Open the 2026 (or later) **current** regular season on Sunday Slate and select an upcoming week.
2. Switch on **Show quarterback availability & replacement research (optional)**.
3. Open **QB availability & replacement quality · experimental** on a matchup card.

The panel shows the latest source-dated projected QB1 and depth-chart alternate, the prior completed-game starter, any timestamped QB game-status report, and a research-only passing-EPA/dropback difference when both players have available earlier-season data. Unavailable information is explicitly labeled. An NFLverse depth-chart position **does not** prove that a player will start.

The costly depth-chart feed is fetched *only* after opt-in, and reduced to QB records before caching (two-hour cache). The ordinary app uses the same untouched Elo and value-screen calculations.

## Optional owner-supplied official announcements

There is no verified zero-cost, uniform, timestamped NFL inactive-list API connected. To cite an **NFL-origin** starter announcement reviewed by the app owner, add this optional private key under Streamlit Community Cloud > App settings > Secrets:

```toml
QB_CONFIRMATIONS_JSON = '''
{
  "2026_06_HOU_BAL": {
    "BAL": {
      "gsis_id": "00-0033662",
      "player_name": "Example QB",
      "reported_at": "2026-10-10T16:00:00Z",
      "source_url": "https://www.nfl.com/news/example"
    }
  }
}
'''
```

**These are example-only values and must be replaced with correctly reviewed player ID, game ID, URL, and real announcement timestamp.** Never copy the example as a genuine announcement. Use each schedule's game ID and team abbreviation. The app requires an HTTPS NFL-domain URL, a pre-kickoff publication timestamp no older than 14 days, and a publication time no later than now; it does not programmatically open or verify the article. It therefore labels the record *owner-supplied*, not independently verified.

If a documented unavailable quarterback is ruled out, only a separately cited starter announcement identifies the replacement. A QB1 still listed on a depth chart but marked Out is flagged as **starter unconfirmed**, never silently substituted.

## Timing, data gaps and constraints

- The depth chart is frozen to the last dated snapshot **before the earlier of the present UTC time or kickoff minus two hours**; snapshots over 14 days old are ignored. This mirrors the historical research's strict pregame cutoff.
- Source-dated injury statuses are considered only for the *selected game week*, *same quarterback*, and only if issued before kickoff and before the current time. Some nflreadpy injury seasons (including 2025) omit the `date_modified` field: they are **not usable as time-verifiable reports**, and the panel explicitly says status is unavailable.
- QB passing EPA and dropbacks are taken only from earlier regular-season weeks of the selected season, shrunk by 150 hypothetical neutral dropbacks and capped in magnitude at 0.45 EPA/dropback. Missing stats produce **unavailable**, never a fabricated zero.
- Week 1 often lacks a previous *same-season* starter, so the estimated performance difference is unavailable. The feature intentionally does not guess offseason transfers or starting lineup changes.
- Historical completed games don't show live QB availability panels, preventing current depth charts from rewriting old pregame assumptions.
- NFL team/player identity, team depth chart, and injury information may be revised by providers; this is neither a verified as-of official injuries archive nor proof of bettable odds.
- No current automatic NFL inactives ingestion is implemented. Owners must supply citations to announcements if they need an explicit verified-source claim.

## Validation and next steps

The isolated historical QB quality study on a research branch found mixed outcomes; 2019–2022 fit, 2023–2025 retrospective and early 2026 do **not** justify promoting a replacement adjustment into official Elo. Keep collecting pre-kickoff archives and test the confirmation layer prospectively before applying any real prediction adjustment.

Regression tests in `tests/test_qb_availability.py` verify data timestamps, provenance, unavailable statuses, missing QB quality, and unchanged Elo.
