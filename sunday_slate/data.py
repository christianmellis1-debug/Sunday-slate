"""Source-boundary helpers for nflverse data. Remote feeds are cached in the app."""
from __future__ import annotations

import pandas as pd

SCHEDULE_COLUMNS = frozenset({"game_id", "season", "game_type", "week", "gameday", "gametime", "home_team", "away_team", "home_score", "away_score"})


class FeedError(RuntimeError):
    """Raised when the required external data cannot be loaded or parsed."""


def _load(method: str, **kwargs) -> pd.DataFrame:
    try:
        import nflreadpy as nfl
        result = getattr(nfl, method)(**kwargs)
        # nflreadpy returns Polars frames; direct dictionary conversion avoids pyarrow.
        frame = pd.DataFrame(result.to_dicts())
    except Exception as exc:
        raise FeedError(f"Unable to load {method} from nflverse: {exc}") from exc
    return frame


def load_schedules() -> pd.DataFrame:
    """Load the shared NFL schedules release, filter season in memory."""
    frame = _load("load_schedules", seasons=True)
    missing = SCHEDULE_COLUMNS.difference(frame.columns)
    if missing:
        raise FeedError(f"Schedule data missing columns: {', '.join(sorted(missing))}")
    frame = frame.copy()
    for col in ("season", "week", "home_score", "away_score"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def load_teams() -> pd.DataFrame:
    frame = _load("load_teams")
    if "team_abbr" not in frame.columns:
        raise FeedError("Team branding dataset has no team_abbr column")
    return frame


def load_team_stats(season: int) -> pd.DataFrame:
    frame = _load("load_team_stats", seasons=int(season), summary_level="week")
    if not {"season", "week", "team"}.issubset(frame.columns):
        raise FeedError("Weekly team statistics are missing season, week, or team")
    return frame


def load_player_stats(season: int) -> pd.DataFrame:
    """Historical player boxes; optional research view, not a starter projection."""
    frame = _load("load_player_stats", seasons=int(season), summary_level="week")
    if not {"season", "week", "team", "position", "player_display_name"}.issubset(frame.columns):
        raise FeedError("Player data missing fields for quarterback research")
    return frame


def load_injury_reports(season: int) -> pd.DataFrame:
    """Optional nflverse injury feed. Missing/empty data never implies healthy."""
    frame = _load("load_injuries", seasons=int(season))
    needed = {"season", "week", "team", "report_status", "full_name", "date_modified"}
    if not needed.issubset(frame.columns):
        raise FeedError("Injury feed missing status or updated-at fields")
    return frame
