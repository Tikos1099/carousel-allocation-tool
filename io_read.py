from __future__ import annotations

import pandas as pd


def read_flights_excel(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    # normalize common column names
    rename_map = {
        "heur de dÃ©part": "DepartureTime",
        "Heure de dÃ©part": "DepartureTime",
        "departure time": "DepartureTime",
        "Departure time": "DepartureTime",
        "flight number": "FlightNumber",
        "Flight number": "FlightNumber",
        "category": "Category",
        "Category": "Category",
        "position": "Positions",
        "Position": "Positions",
        "make up opening": "MakeupOpening",
        "Make up opening": "MakeupOpening",
        "make up closing": "MakeupClosing",
        "Make up closing": "MakeupClosing",
    }
    df = df.rename(columns={c: rename_map.get(c, c) for c in df.columns})
    return df
