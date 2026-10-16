"""Prevent the optional data switches from returning to the page-level UI."""
from pathlib import Path

from sunday_slate.ui import injury_panel, qb_availability_panel

ROOT = Path(__file__).resolve().parents[1]


def test_game_cards_have_an_availability_accordion_slot():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    ui = (ROOT / "sunday_slate" / "ui.py").read_text(encoding="utf-8")
    assert "<!--availability-->" in app
    assert "f'<!--availability-->'" in ui
    assert "Injuries &amp; quarterback status" in app
    assert "injury_panel(" in app
    assert "qb_availability_panel(" in app


def test_no_page_level_injury_or_qb_switches():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Load game-week injury reports (optional)" not in app
    assert "Show quarterback availability & replacement research (optional)" not in app
    assert "show_injury_reports" not in app
    assert "show_qb_availability" not in app
    assert "load_injury_context" not in app
    assert "load_qb_confirmation" not in app


def test_availability_unverified_does_not_appear_healthy_or_confirmed():
    injury_markup = injury_panel("DEN", "SEA", {}, source_available=False)
    qb_markup = qb_availability_panel(None)
    assert "source unavailable" in injury_markup
    assert "unverified" in injury_markup
    assert "Pregame QB context unavailable" in qb_markup
    assert "original Elo pick is unchanged" in qb_markup


def test_card_data_fetch_is_limited_to_upcoming_current_season():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'availability_active = (' in app
    assert 'season == now.year' in app
    assert 'slate["kickoff_ct"].gt(availability_now_utc)' in app
    assert 'if availability_active:' in app
    assert 'qb_player_stats, injury_data, qb_confirmations' in app
