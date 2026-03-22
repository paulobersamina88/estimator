# Pinoy Renovation Estimator (Streamlit Starter Package)

A starter Streamlit app for Philippine renovation estimating.

## What it does
- Uploads **PDF** floor plans or **image sketches**
- Extracts readable text from **text-based PDFs**
- Accepts **manual scope notes** for sketches or scanned plans
- Detects common renovation scopes:
  - Painting works
  - Ceiling works
  - Tile works
  - Door replacement
  - Partition wall
  - Plumbing fixture
  - Electrical point
- Lets the user **edit quantities**
- Applies **location factor** and **finish-level factor**
- Outputs a **detailed breakdown** and downloadable CSV / TXT report

## Important limitation
This starter version is intentionally lightweight:
- **CAD PDFs** work best
- **Handwritten sketches** still need manual review
- Full OCR for scanned images can be added later

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Suggested next upgrades
1. Add OCR for image uploads
2. Add room detection from floor plan linework
3. Add unit-price database from your own PH contractor references
4. Add Excel/BOQ export
5. Add PDF proposal export
6. Add client login and project history

## Suggested folder structure
- `app.py` – main Streamlit interface
- `modules/parser.py` – upload text extraction and scope parsing
- `modules/costing.py` – quantity-to-cost logic
- `modules/report.py` – report downloads

## Notes on pricing
The rates inside this starter package are placeholders for demonstration and should be calibrated to your own market references, supplier canvass, and local labor conditions.

## Example manual note format
```text
Living room repaint 45 sqm
Kitchen gypsum ceiling 12 sqm
Replace 2 doors in bedrooms
Partition wall 8 lm
Add 6 electrical points
```
