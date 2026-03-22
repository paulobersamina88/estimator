import streamlit as st
import pandas as pd
from modules.parser import parse_uploaded_file
from modules.costing import (
    DEFAULT_LOCATION_FACTORS,
    DEFAULT_FINISH_FACTORS,
    build_estimate,
    default_unit_rates_df,
)
from modules.report import generate_csv_bytes, generate_text_report

st.set_page_config(page_title="Pinoy Renovation Estimator", layout="wide")

st.title("🇵🇭 Pinoy Renovation Estimator")
st.caption(
    "Upload a floor plan image or PDF, review extracted scope items, then generate a Philippine-style renovation cost estimate."
)

with st.sidebar:
    st.header("Project Settings")
    location = st.selectbox(
        "Project Location",
        list(DEFAULT_LOCATION_FACTORS.keys()),
        index=0,
        help="Location factor adjusts unit costs to reflect typical differences across PH locations.",
    )
    finish_level = st.selectbox(
        "Finish Level",
        list(DEFAULT_FINISH_FACTORS.keys()),
        index=1,
        help="Budget / Midrange / Premium multiplier for materials and fixtures.",
    )
    contingency_pct = st.slider("Contingency (%)", 0.0, 20.0, 5.0, 0.5)
    overhead_pct = st.slider("OHP / Contractor Markup (%)", 0.0, 30.0, 10.0, 0.5)
    vat_pct = st.slider("VAT (%)", 0.0, 12.0, 12.0, 0.5)

tab1, tab2, tab3 = st.tabs(["1) Upload & Extract", "2) Review Scope", "3) Estimate Output"])

if "extracted_df" not in st.session_state:
    st.session_state.extracted_df = pd.DataFrame(
        columns=[
            "scope_code",
            "scope_name",
            "location_tag",
            "quantity",
            "unit",
            "remarks",
        ]
    )

if "raw_text" not in st.session_state:
    st.session_state.raw_text = ""

if "last_parse_notes" not in st.session_state:
    st.session_state.last_parse_notes = []

with tab1:
    uploaded = st.file_uploader(
        "Upload floor plan or sketch",
        type=["pdf", "png", "jpg", "jpeg"],
        help="CAD PDF is best. Hand-drawn sketches also work, but extracted items should still be reviewed.",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        manual_scope = st.text_area(
            "Optional manual/typed scope notes",
            placeholder=(
                "Example:\n"
                "Living room repaint all walls\n"
                "Kitchen install gypsum ceiling 12 sqm\n"
                "Replace 2 doors in bedrooms\n"
                "Tile replacement toilet 6 sqm"
            ),
            height=180,
        )
    with c2:
        st.markdown("**Supported starter scopes**")
        st.markdown(
            """
- Painting works  
- Ceiling works  
- Tile works  
- Door replacement  
- Partition wall  
- Plumbing fixture  
- Electrical point
"""
        )

    if st.button("Extract Scope Items", type="primary", use_container_width=True):
        if uploaded is None and not manual_scope.strip():
            st.warning("Please upload a file or provide manual scope notes.")
        else:
            parsed = parse_uploaded_file(uploaded, manual_scope)
            st.session_state.extracted_df = parsed["items_df"]
            st.session_state.raw_text = parsed["raw_text"]
            st.session_state.last_parse_notes = parsed["notes"]

    if st.session_state.raw_text:
        st.subheader("Extracted / Combined Raw Text")
        st.code(st.session_state.raw_text[:10000] if st.session_state.raw_text else "", language="text")

    if st.session_state.last_parse_notes:
        st.subheader("Parser Notes")
        for note in st.session_state.last_parse_notes:
            st.info(note)

with tab2:
    st.subheader("Editable Quantity Review")
    st.write(
        "Review and correct quantities before computing the estimate. "
        "This is important especially for sketches and handwritten plans."
    )

    if st.session_state.extracted_df.empty:
        st.info("No extracted items yet. Go to the first tab and run extraction.")
    else:
        edited_df = st.data_editor(
            st.session_state.extracted_df,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_scope",
        )
        st.session_state.extracted_df = edited_df

        st.markdown("**Quick Add Row**")
        with st.form("quick_add_row"):
            a1, a2, a3, a4, a5 = st.columns(5)
            with a1:
                scope_name = st.selectbox(
                    "Scope",
                    [
                        "Painting works",
                        "Ceiling works",
                        "Tile works",
                        "Door replacement",
                        "Partition wall",
                        "Plumbing fixture",
                        "Electrical point",
                    ],
                    key="quick_scope",
                )
            with a2:
                location_tag = st.text_input("Room/Area", key="quick_loc", placeholder="Kitchen")
            with a3:
                quantity = st.number_input("Quantity", min_value=0.0, value=1.0, step=1.0, key="quick_qty")
            with a4:
                unit = st.selectbox("Unit", ["sqm", "lm", "set", "pc", "point"], key="quick_unit")
            with a5:
                remarks = st.text_input("Remarks", key="quick_remarks", placeholder="white paint")
            add_now = st.form_submit_button("Add Item")
            if add_now:
                code_map = {
                    "Painting works": "painting",
                    "Ceiling works": "ceiling",
                    "Tile works": "tile",
                    "Door replacement": "door",
                    "Partition wall": "partition",
                    "Plumbing fixture": "plumbing_fixture",
                    "Electrical point": "electrical_point",
                }
                new_row = pd.DataFrame(
                    [
                        {
                            "scope_code": code_map.get(scope_name, "painting"),
                            "scope_name": scope_name,
                            "location_tag": location_tag,
                            "quantity": quantity,
                            "unit": unit,
                            "remarks": remarks,
                        }
                    ]
                )
                st.session_state.extracted_df = pd.concat(
                    [st.session_state.extracted_df, new_row], ignore_index=True
                )
                st.rerun()

with tab3:
    st.subheader("Estimate")
    if st.session_state.extracted_df.empty:
        st.info("No scope items available yet.")
    else:
        estimate = build_estimate(
            st.session_state.extracted_df,
            location=location,
            finish_level=finish_level,
            contingency_pct=contingency_pct / 100.0,
            overhead_pct=overhead_pct / 100.0,
            vat_pct=vat_pct / 100.0,
        )

        summary = estimate["summary"]
        detail_df = estimate["detail_df"]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Direct Cost", f"₱ {summary['direct_cost']:,.2f}")
        m2.metric("Contingency", f"₱ {summary['contingency_cost']:,.2f}")
        m3.metric("OHP", f"₱ {summary['overhead_cost']:,.2f}")
        m4.metric("Grand Total", f"₱ {summary['grand_total']:,.2f}")

        st.markdown("### Detailed Breakdown")
        st.dataframe(detail_df, use_container_width=True)

        st.markdown("### Default Unit Rates Used")
        st.dataframe(default_unit_rates_df(location=location, finish_level=finish_level), use_container_width=True)

        csv_bytes = generate_csv_bytes(detail_df)
        report_text = generate_text_report(summary, detail_df, location, finish_level)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download Breakdown CSV",
                data=csv_bytes,
                file_name="pinoy_renovation_breakdown.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "Download Text Report",
                data=report_text.encode("utf-8"),
                file_name="pinoy_renovation_report.txt",
                mime="text/plain",
                use_container_width=True,
            )

st.divider()
st.caption(
    "Important: This is a starter estimating assistant. Final pricing still depends on site verification, "
    "actual plan interpretation, supplier quotations, access conditions, and local labor market conditions."
)
