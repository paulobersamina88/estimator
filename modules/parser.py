import io
import re
from typing import Dict, List

import pandas as pd

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

from PIL import Image

SCOPE_PATTERNS = [
    {
        "scope_code": "painting",
        "scope_name": "Painting works",
        "keywords": ["paint", "painting", "repaint", "pintura", "re-paint"],
        "default_unit": "sqm",
    },
    {
        "scope_code": "ceiling",
        "scope_name": "Ceiling works",
        "keywords": ["ceiling", "gypsum", "kisame"],
        "default_unit": "sqm",
    },
    {
        "scope_code": "tile",
        "scope_name": "Tile works",
        "keywords": ["tile", "tiles", "tiling", "floor tile", "wall tile"],
        "default_unit": "sqm",
    },
    {
        "scope_code": "door",
        "scope_name": "Door replacement",
        "keywords": ["door", "pinto", "replace door", "change door"],
        "default_unit": "set",
    },
    {
        "scope_code": "partition",
        "scope_name": "Partition wall",
        "keywords": ["partition", "drywall", "wall divider"],
        "default_unit": "lm",
    },
    {
        "scope_code": "plumbing_fixture",
        "scope_name": "Plumbing fixture",
        "keywords": ["toilet", "lavatory", "sink", "faucet", "water closet", "bidet", "plumbing"],
        "default_unit": "set",
    },
    {
        "scope_code": "electrical_point",
        "scope_name": "Electrical point",
        "keywords": ["light", "lighting", "outlet", "switch", "electrical", "socket"],
        "default_unit": "point",
    },
]

ROOM_HINTS = [
    "bedroom", "kitchen", "toilet", "bathroom", "cr", "living", "dining", "hall", "office",
    "master", "garage", "porch", "laundry", "utility"
]


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    if fitz is None:
        return ""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        chunks = []
        for page in doc:
            chunks.append(page.get_text("text"))
        return "\n".join(chunks)
    except Exception:
        return ""


def _extract_text_from_image(file_bytes: bytes) -> str:
    # Placeholder image handling:
    # We load the image so future OCR integration is easy,
    # but we keep the package lightweight and rely on manual notes when OCR is unavailable.
    try:
        img = Image.open(io.BytesIO(file_bytes))
        _ = img.size
    except Exception:
        pass
    return ""


def _find_quantity_and_unit(text: str, default_unit: str):
    lower = text.lower()
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(sqm|sq\.m|m2|sq m)',
        r'(\d+(?:\.\d+)?)\s*(lm|m|lin\.m|linear meter)',
        r'(\d+(?:\.\d+)?)\s*(sets|set|pcs|pc|points|point)',
    ]
    for pat in patterns:
        m = re.search(pat, lower)
        if m:
            qty = float(m.group(1))
            raw_unit = m.group(2)
            unit_map = {
                "sq.m": "sqm",
                "sq m": "sqm",
                "m2": "sqm",
                "sets": "set",
                "pcs": "pc",
                "points": "point",
                "m": "lm",
                "lin.m": "lm",
                "linear meter": "lm",
            }
            unit = unit_map.get(raw_unit, raw_unit)
            return qty, unit
    # If no explicit unit found, try standalone number.
    m = re.search(r'(\d+(?:\.\d+)?)', lower)
    if m:
        return float(m.group(1)), default_unit
    return 1.0, default_unit


def _find_room_hint(text: str) -> str:
    lower = text.lower()
    for room in ROOM_HINTS:
        if room in lower:
            return room.title()
    return ""


def _normalize_lines(raw_text: str) -> List[str]:
    lines = []
    for line in raw_text.splitlines():
        clean = re.sub(r'\s+', ' ', line).strip()
        if clean:
            lines.append(clean)
    return lines


def _parse_scope_items(raw_text: str) -> pd.DataFrame:
    rows = []
    lines = _normalize_lines(raw_text)
    for line in lines:
        lower = line.lower()
        for scope in SCOPE_PATTERNS:
            if any(k in lower for k in scope["keywords"]):
                qty, unit = _find_quantity_and_unit(line, scope["default_unit"])
                rows.append(
                    {
                        "scope_code": scope["scope_code"],
                        "scope_name": scope["scope_name"],
                        "location_tag": _find_room_hint(line),
                        "quantity": qty,
                        "unit": unit,
                        "remarks": line,
                    }
                )
                break

    if not rows:
        return pd.DataFrame(
            columns=["scope_code", "scope_name", "location_tag", "quantity", "unit", "remarks"]
        )
    return pd.DataFrame(rows)


def parse_uploaded_file(uploaded, manual_scope: str = "") -> Dict:
    notes = []
    raw_text_parts = []

    if uploaded is not None:
        file_bytes = uploaded.read()
        name = uploaded.name.lower()

        if name.endswith(".pdf"):
            pdf_text = _extract_text_from_pdf(file_bytes)
            if pdf_text.strip():
                notes.append("PDF text extracted successfully.")
                raw_text_parts.append(pdf_text)
            else:
                notes.append(
                    "No readable text was extracted from the PDF. "
                    "If this is a scanned file, add manual notes or integrate OCR later."
                )
        else:
            _ = _extract_text_from_image(file_bytes)
            notes.append(
                "Image upload detected. OCR is left lightweight in this starter package, "
                "so please use the manual notes box for best results."
            )

    if manual_scope.strip():
        raw_text_parts.append(manual_scope)
        notes.append("Manual scope notes appended to extraction pipeline.")

    raw_text = "\n".join(raw_text_parts).strip()
    items_df = _parse_scope_items(raw_text)

    if items_df.empty and raw_text:
        notes.append(
            "No known scope items were recognized from the text. "
            "Edit the text and include keywords like paint, ceiling, tile, door, partition, plumbing, or electrical."
        )

    return {"raw_text": raw_text, "items_df": items_df, "notes": notes}
