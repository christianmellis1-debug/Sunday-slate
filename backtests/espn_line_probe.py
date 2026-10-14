"""Probe ESPN's archived 2024–2026 NFL scorecards for independently recorded opening and closing lines.

Research-only, never modifies the production prediction model.
"""
import json
from pathlib import Path
from urllib.request import Request, urlopen


def get(url):
    req = Request(url, headers={"User-Agent":"Mozilla/5.0 SundaySlateResearch/1.0","Accept":"application/json"})
    with urlopen(req, timeout=20) as handle:
        return json.load(handle)


def main():
    output = {}
    for season, week in ((2025, 6), (2025, 15), (2024, 6), (2026, 4)):
        key = f"{season}_{week}"
        url = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
               f"?dates={season}&seasontype=2&week={week}&limit=100")
        try:
            response = get(url)
            events = response.get("events", [])
            result = {"events":len(events),"examples":[]}
            for event in events[:3]:
                for comp in event.get("competitions", []):
                    odds = comp.get("odds", [])
                    result["examples"].append({"event_id": event.get("id"),
                        "teams": [(x.get("homeAway"),x.get("team",{}).get("abbreviation"),x.get("score")) for x in comp.get("competitors",[])],
                        "status": comp.get("status",{}).get("type",{}),
                        "odds_count": len(odds),
                        "odds": odds[:2]})
            if events:
                event_id = events[0]["id"]
                core_url = ("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"
                            f"events/{event_id}/competitions/{event_id}/odds?limit=100")
                try:
                    core = get(core_url)
                    result["core"] = {"count":core.get("count"),"items":core.get("items",[])[:4]}
                    for i,item in enumerate(core.get("items",[])[:2]):
                        try:
                            row=get(item.get("$ref",""))
                            result.setdefault("core_odds",[]).append(row)
                        except Exception as e:
                            result.setdefault("core_errors",[]).append(str(e))
                except Exception as e:
                    result["core_error"] = str(e)
            output[key] = result
        except Exception as e:
            output[key] = {"error":str(e)}
    path=Path("backtests/output/espn_odds_probe.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(output,indent=2)+"\n")
    print(json.dumps({k: {"events":v.get("events"),"error":v.get("error"),
                            "odds_counts":[x["odds_count"] for x in v.get("examples",[])],
                            "core_count":v.get("core",{}).get("count")}
                      for k,v in output.items()},indent=2))

if __name__=="__main__":
    main()
