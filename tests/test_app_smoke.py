"""Offline Streamlit + nflreadpy adapters smoke test."""
import importlib
import sys
import types
import pandas as pd

from test_slate import schedule, stats


class FakeFrame:
    def __init__(self, data):
        self.data = data
    def to_dicts(self):
        return self.data.to_dict("records")


class Column:
    def metric(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *_): pass


class Cache:
    def __call__(self, **kwargs):
        def wrap(f):
            f.clear = lambda: None
            return f
        return wrap


class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.cache_data = Cache()
        self.html_cards = []
    def set_page_config(self, **kwargs): pass
    def markdown(self, content, unsafe_allow_html=False):
        if '<article class="ss-match">' in content: self.html_cards.append(content)
    def spinner(self, *_): return Column()
    def expander(self, *_): return Column()
    def columns(self, widths): return [Column() for _ in (range(widths) if isinstance(widths,int) else widths)]
    def metric(self, *args, **kwargs): pass
    def caption(self, *args): pass
    def selectbox(self, _, options, **kwargs): return list(options)[kwargs.get("index", 0)]
    def text_input(self, *args, **kwargs): return ''
    def toggle(self, *args, **kwargs): return False
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def code(self, *args, **kwargs): pass
    def stop(self): raise AssertionError("App unexpectedly stopped")


def test_standalone_app_boot_with_nflverse_contract(monkeypatch):
    fake_st = FakeStreamlit()
    fake_nfl = types.ModuleType("nflreadpy")
    fake_nfl.load_schedules = lambda seasons: FakeFrame(schedule())
    fake_nfl.load_team_stats = lambda seasons, summary_level: FakeFrame(stats())
    fake_nfl.load_teams = lambda: FakeFrame(pd.DataFrame([dict(team_abbr="DAL", team_name="Dallas Cowboys", team_logo_espn="https://a.espncdn.com/i/teamlogos/nfl/500/dal.png", team_color="#002244")]))
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    monkeypatch.setitem(sys.modules, "nflreadpy", fake_nfl)
    # Simulate Streamlit Cloud temporarily serving an older data helper while
    # loading the newer app entrypoint. Optional feeds must not crash startup.
    from sunday_slate import data as source_data
    monkeypatch.delattr(source_data, "load_player_stats", raising=False)
    monkeypatch.delattr(source_data, "load_injury_reports", raising=False)
    sys.modules.pop("app", None)
    importlib.import_module("app")
    assert len(fake_st.html_cards) >= 1
    assert "Dallas Cowboys" in " ".join(fake_st.html_cards)
    assert "Passing" not in " ".join(fake_st.html_cards)
    sys.modules.pop("app", None)
