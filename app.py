import io

import pandas as pd
import streamlit as st
from PIL import Image

from modules.parser import parse_uploaded_file
from modules.costing import (
    DEFAULT_LOCATION_FACTORS,
    DEFAULT_FINISH_FACTORS,
    build_estimate,
    default_unit_rates_df,
)
from modules.report import generate_csv_bytes, generate_text_report

# Optional OCR imports
OCR_AVAILABLE = True
OCR_IMPORT_ERROR = ""

try:
    import cv2
    import numpy as np
    import pytesseract
except Exception as e:
    OCR_AVAILABLE = False
    OCR_IMPORT_ERROR = str(e)


st.set_page_config(page_title="Pinoy Renovation Estimator", layout="wide")

st.title("🇵🇭 Pinoy Renovation Estimator")
st.caption(
    "Upload a floor plan image or PDF, review extracted scope items, then generate a Philippine-style renovation cost estimate."
)


# =========================================================
# OCR HELPERS
# =========================================================
def extract_text_from_image_ocr(file_bytes: bytes) -> tuple[str, list[str]]:
    """
    Lightweight OCR pipeline for image uploads.
    Requires: opencv-python, numpy, pytesseract, and Tesseract installed on system.
    """
    notes = []

    if not OCR_AVAILABLE:
        notes.append(
            "OCR libraries are not available. Install opencv-python, numpy, pytesseract, "
            "and ensure Tesseract OCR is installed on the machine."
        )
        if OCR_IMPORT_ERROR:
            notes.append(f"OCR import error: {OCR_IMPORT_ERROR}")
        return "", notes

    try:
        file_arr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(file_arr, cv2.IMREAD_COLOR)

        if img is None:
            notes.append("Could not decode the uploaded image for OCR.")
            return "", notes

        # Basic preprocessing
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)

        # OCR config tuned for general block text
        config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_string(thresh, config=config)

        if text.strip():
            notes.append("OCR text extracted from image successfully.")
        else:
            notes.append(
                "OCR ran but returned little or no text. Photo may be blurry, rotated, dim, or handwritten too roughly."
            )

        return text, notes

    except Exception as e:
        notes.append(f"OCR failed: {e}")
        return "", notes


def preview_uploaded_image(uploaded_file):
    try:
        img = Image.open(uploaded_file)
        st.image(img, caption="Uploaded Image Preview", use_container_width=True)
    except Exception:
        st.warning("Could not preview the uploaded image.")


# =========================================================
# SESSION STATE
# =========================================================
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

if "ocr_text" not in st.session_state:
    st.session_state.ocr_text = ""


# =========================================================
# SIDEBAR
# =========================================================
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

    st.divider()
    st.subheader("OCR Status")
    if OCR_AVAILABLE:
        st.success("Image OCR libraries detected.")
    else:
        st.warning("Image OCR libraries not installed yet.")
        st.caption("Install: opencv-python, numpy, pytesseract")
        st.caption("Also install the Tesseract engine on your machine.")


# =========================================================
# TABS
# =========================================================
tab1, tab2, tab3 = st.tabs(["1) Upload & Extract", "2) Review Scope", "3) Estimate Output"])

with tab1:
    uploaded = st.file_uploader(
        "Upload floor plan or sketch",
        type=["pdf", "png", "jpg", "jpeg"],
        help="CAD PDF is best. Hand-drawn sketches also work, especially with OCR + manual notes.",
    )

    use_image_ocr = st.checkbox(
        "Use OCR for image uploads",
        value=True,
        help="For JPG/PNG uploads, the app will try to read printed or handwritten notes from the image.",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        manual_scope = st.text_area(
            "Optional manual/typed scope notes",
            placeholder=(
                "Example:\n"
                "Living room repaint all walls 45 sqm\n"
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

    if uploaded is not None:
        file_name = uploaded.name.lower()
        if file_name.endswith((".png", ".jpg", ".jpeg")):
            preview_uploaded_image(uploaded)
            uploaded.seek(0)

    if st.button("Extract Scope Items", type="primary", use_container_width=True):
        if uploaded is None and not manual_scope.strip():
            st.warning("Please upload a file or provide manual scope notes.")
        else:
            parse_notes = []
            final_raw_text = ""
            parsed = None

            if uploaded is not None:
                file_name = uploaded.name.lower()

                # =========================================================
                # IMAGE FLOW WITH OCR
                # =========================================================
                if file_name.endswith((".png", ".jpg", ".jpeg")):
                    uploaded_bytes = uploaded.read()

                    ocr_text = ""
                    if use_image_ocr:
                        ocr_text, ocr_notes = extract_text_from_image_ocr(uploaded_bytes)
                        parse_notes.extend(ocr_notes)

                    st.session_state.ocr_text = ocr_text

                    combined_text_parts = []
                    if ocr_text.strip():
                        combined_text_parts.append(ocr_text)
                    if manual_scope.strip():
                        combined_text_parts.append(manual_scope)

                    combined_text = "\n".join(combined_text_parts).strip()

                    if not combined_text:
                        parse_notes.append(
                            "No OCR text or manual notes were available. Please type some scope notes manually."
                        )
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
                        st.session_state.raw_text = ""
                        st.session_state.last_parse_notes = parse_notes
                    else:
                        # Feed combined OCR text + manual notes to existing parser logic
                        parsed = parse_uploaded_file(None, combined_text)

                # =========================================================
                # PDF FLOW
                # =========================================================
                elif file_name.endswith(".pdf"):
                    uploaded.seek(0)
                    parsed = parse_uploaded_file(uploaded, manual_scope)

                else:
                    parse_notes.append("Unsupported file type.")

            else:
                # Manual text only
                parsed = parse_uploaded_file(None, manual_scope)

            if parsed is not None:
                merged_notes = parse_notes + parsed.get("notes", [])
                st.session_state.extracted_df = parsed["items_df"]
                st.session_state.raw_text = parsed["raw_text"]
                st.session_state.last_parse_notes = merged_notes

    if st.session_state.ocr_text:
        st.subheader("OCR Text from Image")
        st.code(st.session_state.ocr_text[:10000], language="text")

    if st.session_state.raw_text:
        st.subheader("Extracted / Combined Raw Text")
        st.code(st.session_state.raw_text[:10000], language="text")

    if st.session_state.last_parse_notes:
        st.subheader("Parser / OCR Notes")
        for note in st.session_state.last_parse_notes:
            st.info(note)


with tab2:
    st.subheader("Editable Quantity Review")
    st.write(
        "Review and correct quantities before computing the estimate. "
        "This is important especially for sketches, photos, and handwritten plans."
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
