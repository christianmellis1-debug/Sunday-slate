"""Inspect available pre-kickoff injury and depth-chart datasets."""
import json
import traceback
import nflreadpy as nfl
import pandas as pd

for kind, func, year in [
    ("depth", nfl.load_depth_charts, 2025),
    ("injuries", nfl.load_injuries, 2024),
    ("injuries", nfl.load_injuries, 2025),
    ("depth", nfl.load_depth_charts, 2024)
]:
    print("\n=== DATASET", kind, year, flush=True)
    try:
        df=pd.DataFrame(func(seasons=year).to_dicts())
        print("ROW COUNT",len(df),"COLS",df.columns.tolist(),flush=True)
        print("EXAMPLE",json.dumps(df.head(2).astype(str).to_dict("records"),ensure_ascii=True),flush=True)
        if kind=="depth" and "dt" in df:
            dt=pd.to_datetime(df.dt,errors="coerce",utc=True)
            print("DT RANGE",str(dt.min()),str(dt.max()),"COUNT",dt.nunique(),flush=True)
            print("FIRSTS",df.dt.dropna().sort_values().unique()[:6],flush=True)
            print("2025 QB RECORDS",json.dumps(df.loc[(df.pos_abb=="QB") & (df.team=="KC")].head(3).astype(str).to_dict("records")),flush=True)
        if kind=="injuries":
            print("QB REPORT STATUS",df[df.position.eq("QB")].report_status.value_counts(dropna=False).head(15).to_dict(),flush=True)
            print("dates",str(pd.to_datetime(df.date_modified,errors="coerce",utc=True).min()),str(pd.to_datetime(df.date_modified,errors="coerce",utc=True).max()),flush=True)
    except Exception as e:
        print("DATASET ERROR",type(e).__name__,str(e)[:800],flush=True)
