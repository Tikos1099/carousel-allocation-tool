from __future__ import annotations

import pandas as pd


def write_summary_txt(path: str, flights_out: pd.DataFrame, extra_cols: list[str] | None = None):
    cols = ["DepartureTime", "FlightNumber", "Category", "Positions", "MakeupOpening", "MakeupClosing", "AssignedCarousel"]
    existing = [c for c in cols if c in flights_out.columns]
    extra_cols = [c for c in (extra_cols or []) if c in flights_out.columns and c not in existing]
    s = flights_out.sort_values("DepartureTime")[existing + extra_cols]
    with open(path, "w", encoding="utf-8") as f:
        for _, r in s.iterrows():
            base = (
                f"{r.get('DepartureTime')} | {r.get('FlightNumber')} | {r.get('Category')} | "
                f"pos={r.get('Positions')} | open={r.get('MakeupOpening')} | close={r.get('MakeupClosing')} | "
                f"carousel={r.get('AssignedCarousel')}"
            )
            if extra_cols:
                extras = " | ".join([f"{c}={r.get(c)}" for c in extra_cols])
                f.write(f"{base} | {extras}\n")
            else:
                f.write(f"{base}\n")


def write_summary_csv(path: str, flights_out: pd.DataFrame):
    flights_out.sort_values("DepartureTime").to_csv(path, index=False, encoding="utf-8")
