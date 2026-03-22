import io
import pandas as pd

def generate_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

def generate_text_report(summary: dict, detail_df: pd.DataFrame, location: str, finish_level: str) -> str:
    lines = []
    lines.append("PINOY RENOVATION ESTIMATOR REPORT")
    lines.append("=" * 40)
    lines.append(f"Location: {location}")
    lines.append(f"Finish Level: {finish_level}")
    lines.append("")
    lines.append(f"Direct Cost: PHP {summary['direct_cost']:,.2f}")
    lines.append(f"Contingency: PHP {summary['contingency_cost']:,.2f}")
    lines.append(f"Overhead/OHP: PHP {summary['overhead_cost']:,.2f}")
    lines.append(f"VAT: PHP {summary['vat_cost']:,.2f}")
    lines.append(f"GRAND TOTAL: PHP {summary['grand_total']:,.2f}")
    lines.append("")
    lines.append("DETAILED ITEMS")
    lines.append("-" * 40)
    if detail_df.empty:
        lines.append("No items.")
    else:
        for _, r in detail_df.iterrows():
            lines.append(
                f"{r['scope_name']} | {r['quantity']} {r['unit']} | PHP {r['unit_rate_php']:,.2f} | PHP {r['amount_php']:,.2f} | {r['location_tag']} | {r['remarks']}"
            )
    lines.append("")
    lines.append("NOTE")
    lines.append(
        "This is a conceptual estimate only. Final costing must still be validated through actual plan interpretation, "
        "site inspection, supplier quotations, and contractor methodology."
    )
    return "\n".join(lines)
