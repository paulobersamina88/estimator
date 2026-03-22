from typing import Dict

import pandas as pd

DEFAULT_LOCATION_FACTORS = {
    "NCR / Metro Manila": 1.00,
    "Luzon Urban": 0.95,
    "Visayas Urban": 0.93,
    "Mindanao Urban": 0.92,
    "Provincial / Remote": 1.05,
}

DEFAULT_FINISH_FACTORS = {
    "Budget": 0.90,
    "Midrange": 1.00,
    "Premium": 1.20,
}

BASE_UNIT_RATES = {
    "painting": {"scope_name": "Painting works", "unit": "sqm", "unit_rate": 280.0},
    "ceiling": {"scope_name": "Ceiling works", "unit": "sqm", "unit_rate": 950.0},
    "tile": {"scope_name": "Tile works", "unit": "sqm", "unit_rate": 1450.0},
    "door": {"scope_name": "Door replacement", "unit": "set", "unit_rate": 8500.0},
    "partition": {"scope_name": "Partition wall", "unit": "lm", "unit_rate": 1800.0},
    "plumbing_fixture": {"scope_name": "Plumbing fixture", "unit": "set", "unit_rate": 6500.0},
    "electrical_point": {"scope_name": "Electrical point", "unit": "point", "unit_rate": 1800.0},
}


def default_unit_rates_df(location: str, finish_level: str) -> pd.DataFrame:
    loc_factor = DEFAULT_LOCATION_FACTORS[location]
    fin_factor = DEFAULT_FINISH_FACTORS[finish_level]
    rows = []
    for code, row in BASE_UNIT_RATES.items():
        rows.append(
            {
                "scope_code": code,
                "scope_name": row["scope_name"],
                "unit": row["unit"],
                "base_rate_php": row["unit_rate"],
                "adjusted_rate_php": row["unit_rate"] * loc_factor * fin_factor,
            }
        )
    return pd.DataFrame(rows)


def build_estimate(
    scope_df: pd.DataFrame,
    location: str,
    finish_level: str,
    contingency_pct: float = 0.05,
    overhead_pct: float = 0.10,
    vat_pct: float = 0.12,
) -> Dict:
    loc_factor = DEFAULT_LOCATION_FACTORS[location]
    fin_factor = DEFAULT_FINISH_FACTORS[finish_level]

    rows = []
    for _, r in scope_df.iterrows():
        code = str(r.get("scope_code", "")).strip()
        qty = float(r.get("quantity", 0) or 0)
        remarks = r.get("remarks", "")
        location_tag = r.get("location_tag", "")
        unit = str(r.get("unit", "")).strip()

        if code not in BASE_UNIT_RATES:
            continue

        base = BASE_UNIT_RATES[code]
        effective_unit = unit if unit else base["unit"]
        unit_rate = base["unit_rate"] * loc_factor * fin_factor
        amount = qty * unit_rate

        rows.append(
            {
                "scope_code": code,
                "scope_name": base["scope_name"],
                "location_tag": location_tag,
                "quantity": qty,
                "unit": effective_unit,
                "unit_rate_php": round(unit_rate, 2),
                "amount_php": round(amount, 2),
                "remarks": remarks,
            }
        )

    detail_df = pd.DataFrame(rows)
    direct_cost = float(detail_df["amount_php"].sum()) if not detail_df.empty else 0.0
    contingency_cost = direct_cost * contingency_pct
    overhead_cost = direct_cost * overhead_pct
    subtotal_before_vat = direct_cost + contingency_cost + overhead_cost
    vat_cost = subtotal_before_vat * vat_pct
    grand_total = subtotal_before_vat + vat_cost

    summary = {
        "direct_cost": round(direct_cost, 2),
        "contingency_cost": round(contingency_cost, 2),
        "overhead_cost": round(overhead_cost, 2),
        "vat_cost": round(vat_cost, 2),
        "grand_total": round(grand_total, 2),
    }

    if not detail_df.empty:
        grouped = (
            detail_df.groupby("scope_name", as_index=False)["amount_php"]
            .sum()
            .sort_values("amount_php", ascending=False)
        )
        summary["grouped"] = grouped
    else:
        summary["grouped"] = pd.DataFrame(columns=["scope_name", "amount_php"])

    return {"detail_df": detail_df, "summary": summary}
