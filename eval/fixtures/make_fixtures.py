"""Generate SYNTHETIC health documents for tests and evaluation. The patient is fictional.

    cd backend && uv run python ../eval/fixtures/make_fixtures.py

Outputs (eval/fixtures/docs/):
  lab-report.pdf        3-page text PDF (CBC, lipid panel + HbA1c, metabolic panel)
  visit-summary.txt     primary-care visit note
  medication-list.docx  medications + allergies table
  scanned-letter.pdf    1-page image-only PDF with no extractable text (OCR case)
  lab-report-columns.pdf  commercial-lab style table: current AND previous result columns,
                        superscript lab codes, flags, comment lines, legal footer
  lab-report-renal.pdf  renal panel + urine panel: blood AND urine creatinine (same-name
                        ambiguity), "Not Estab." references, values that rose since last time
"""

from pathlib import Path

from docx import Document

OUT = Path(__file__).parent / "docs"
BANNER = "SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT REAL MEDICAL DATA"

LAB_PAGES = [
    [
        "Gainesville Community Lab (fictional)",
        BANNER,
        "Patient: Jordan Sample    DOB: 1980-04-12    MRN: TEST-000123",
        "Collected: 2026-08-14    Ordering clinician: Dr. Example",
        "",
        "COMPLETE BLOOD COUNT (CBC)",
        "White blood cells ....... 6.8 x10^3/uL   (ref 4.0-11.0)",
        "Hemoglobin .............. 14.2 g/dL      (ref 13.5-17.5)",
        "Platelets ............... 245 x10^3/uL   (ref 150-400)",
    ],
    [
        BANNER,
        "LIPID PANEL (fasting)",
        "Total cholesterol ....... 238 mg/dL   (ref < 200)   HIGH",
        "LDL cholesterol ......... 162 mg/dL   (ref < 100)   HIGH",
        "HDL cholesterol ......... 48 mg/dL    (ref > 40)",
        "Triglycerides ........... 140 mg/dL   (ref < 150)",
        "",
        "HEMOGLOBIN A1C",
        "Hemoglobin A1C .......... 6.1 %       (ref < 5.7)   HIGH",
        "Interpretation: 5.7-6.4 % is consistent with prediabetes.",
    ],
    [
        BANNER,
        "COMPREHENSIVE METABOLIC PANEL",
        "Glucose, fasting ........ 108 mg/dL   (ref 70-99)   HIGH",
        "Creatinine .............. 0.9 mg/dL   (ref 0.7-1.3)",
        "eGFR .................... > 90 mL/min/1.73m2",
        "ALT ..................... 28 U/L      (ref 7-56)",
        "Potassium ............... 4.2 mmol/L  (ref 3.5-5.1)",
        "",
        "Report reviewed electronically. End of report.",
    ],
]

VISIT_SUMMARY = f"""{BANNER}

PRIMARY CARE VISIT SUMMARY
Patient: Jordan Sample    Date of visit: 2026-08-21    Clinician: Dr. Example

Reason for visit: Follow-up of annual lab results.

Vitals: Blood pressure 138/88 mmHg. Heart rate 72 bpm. Weight 86 kg. BMI 27.9.

Assessment:
1. Elevated LDL cholesterol (162 mg/dL on 2026-08-14).
2. Prediabetes (hemoglobin A1C 6.1%).
3. Elevated blood pressure without a diagnosis of hypertension.

Plan:
- Start atorvastatin 20 mg by mouth once nightly.
- Diet and exercise counseling: 150 minutes per week of moderate activity.
- Recheck lipid panel and A1C in 3 months.
- Home blood pressure log; return if readings stay above 140/90.

Next appointment: 2026-11-20.
"""

MEDICATIONS = [
    ("Atorvastatin", "20 mg", "Once nightly", "High cholesterol", "2026-08-21"),
    ("Lisinopril", "10 mg", "Once daily", "Blood pressure", "2024-02-03"),
    ("Vitamin D3", "1000 IU", "Once daily", "Supplement", "2023-11-10"),
]


# Commercial-lab table layout (positions mimic real borderless reports). Traps for column
# confusion: creatinine normal now but high before; potassium high now but normal before.
COLUMN_LAB_ROWS = [
    # name, lab code (superscript), current, flag, previous, prev date, units, reference
    ("Glucose", "01", "108", "High", "92", "03/02/2026", "mg/dL", "70-99"),
    ("BUN", "01", "15", "", "28", "03/02/2026", "mg/dL", "6-20"),
    ("Creatinine", "01", "0.98", "", "1.62", "03/02/2026", "mg/dL", "0.76-1.27"),
    ("eGFR", "", "101", "", "52", "03/02/2026", "mL/min/1.73", ">59"),
    ("Potassium", "01", "5.6", "High", "4.4", "03/02/2026", "mmol/L", "3.5-5.2"),
    ("Sodium", "01", "139", "", "137", "03/02/2026", "mmol/L", "134-144"),
]
COLUMN_HEADER = [
    (36, "Test"), (191, "Current Result and Flag"), (325, "Previous Result and Date"),
    (463, "Units"), (521, "Reference Interval"),
]  # fmt: skip


def column_lab_cells() -> list[tuple[float, float, float, str]]:
    """(x, top, font size, text) cells for the column-layout lab report."""
    cells = [
        (18, 40, 9, BANNER),
        (18, 58, 9, "Jordan Sample   DOB: 1980-04-12   Patient Report"),
        (18, 74, 8, "Date Collected: 05/04/2026   Date Reported: 05/05/2026   Fasting: Yes"),
        (18, 100, 9, "Basic Metabolic Panel"),
    ]
    top = 122
    cells += [(x, top, 8, text) for x, text in COLUMN_HEADER]
    for name, code, cur, flag, prev, date, units, ref in COLUMN_LAB_ROWS:
        top += 14
        cells.append((36, top, 8, name))
        if code:  # small raised footnote marker right after the name, like real reports
            cells.append((36 + 4.6 * len(name), top - 2, 5, code))
        cells.append((198, top, 8, cur))
        if flag:
            cells.append((230, top, 8, flag))
        cells += [(333, top, 8, prev), (385, top, 8, date)]
        cells += [(460, top, 8, units), (540, top, 8, ref)]
    top += 30
    cells.append((18, top, 9, "Hemoglobin"))
    top += 20
    cells += [(x, top, 8, text) for x, text in COLUMN_HEADER]
    top += 14
    cells += [(36, top, 8, "Hemoglobin"), (36 + 4.6 * 10, top - 2, 5, "01"), (198, top, 8, "11.8"),
              (230, top, 8, "Low"), (460, top, 8, "g/dL"), (540, top, 8, "13.0-17.7")]  # fmt: skip
    top += 14
    cells.append((163, top, 8, "Specimen slightly hemolyzed; result may be affected."))
    cells += [
        (60, 740, 7, "(c) 2026 Example Laboratory Holdings. All Rights Reserved. Page 1 of 1"),
        (60, 752, 7, "This document contains private and confidential health information."),
    ]
    return cells


RENAL_ROWS = [
    # name, lab code, current, flag, previous, prev date, units, reference
    ("Creatinine", "01", "1.31", "High", "0.95", "03/10/2026", "mg/dL", "0.76-1.27"),
    ("BUN", "01", "24", "High", "16", "03/10/2026", "mg/dL", "6-20"),
    ("eGFR", "", "68", "", "96", "03/10/2026", "mL/min/1.73", ">59"),
    ("Sodium", "01", "141", "", "139", "03/10/2026", "mmol/L", "134-144"),
]
URINE_ROWS = [
    ("Creatinine, Urine", "01", "88.2", "", "", "", "mg/dL", "Not Estab."),
    ("Protein, Total, Urine", "01", "12.5", "", "", "", "mg/dL", "Not Estab."),
    ("Protein/Creat Ratio", "01", "142", "", "", "", "mg/g creat", "0-200"),
]


def _table_rows(rows, top: float) -> tuple[list[tuple[float, float, float, str]], float]:
    cells = [(x, top, 8, text) for x, text in COLUMN_HEADER]
    for name, code, cur, flag, prev, date, units, ref in rows:
        top += 14
        cells.append((36, top, 8, name))
        if code:
            cells.append((36 + 4.6 * len(name), top - 2, 5, code))
        cells.append((198, top, 8, cur))
        if flag:
            cells.append((230, top, 8, flag))
        if prev:
            cells += [(333, top, 8, prev), (385, top, 8, date)]
        for x, text in ((460, units), (532, ref)):
            for word in text.split(" "):  # real word spacing so words don't merge
                cells.append((x, top, 8, word))
                x += 4.6 * len(word) + 4
    return cells, top


def renal_lab_cells() -> list[tuple[float, float, float, str]]:
    """Renal panel with a blood creatinine AND, in a second table, a urine creatinine."""
    cells = [
        (18, 40, 9, BANNER),
        (18, 58, 9, "Jordan Sample   DOB: 1980-04-12   Patient Report"),
        (18, 74, 8, "Date Collected: 06/12/2026   Date Reported: 06/13/2026   Fasting: No"),
        (18, 100, 9, "Renal Function Panel"),
    ]
    rows, top = _table_rows(RENAL_ROWS, 122)
    cells += rows
    cells.append((18, top + 30, 9, "Urine Protein/Creatinine Ratio (Random)"))
    rows, top = _table_rows(URINE_ROWS, top + 50)
    cells += rows
    cells += [
        (60, 740, 7, "(c) 2026 Example Laboratory Holdings. All Rights Reserved. Page 1 of 1"),
        (60, 752, 7, "This document contains private and confidential health information."),
    ]
    return cells


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path: Path, pages: list) -> None:
    """Minimal PDF writer. A page of None is image-only (a filled shape, no text)."""
    objects: list[bytes] = []
    page_ids: list[int] = []
    n_pages = len(pages)
    font_id = 3 + 2 * n_pages
    for i, lines in enumerate(pages):
        page_id, content_id = 3 + 2 * i, 4 + 2 * i
        page_ids.append(page_id)
        if lines is None:
            stream = "0.6 g 72 300 468 400 re f 0.2 g 100 600 300 20 re f"
        elif isinstance(lines, dict):  # positioned cells: (x, top-from-page-top, size, text)
            stream = "".join(
                f"BT /F1 {size} Tf 1 0 0 1 {x} {792 - top - size} Tm ({_pdf_escape(text)}) Tj ET "
                for x, top, size, text in lines["cells"]
            )
        else:
            body = " T* ".join(f"({_pdf_escape(line)}) Tj" for line in lines)
            stream = f"BT /F1 11 Tf 14 TL 60 740 Td {body} ET"
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )
        data = stream.encode("latin-1")
        objects.append(b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream")
    kids = " ".join(f"{p} 0 R" for p in page_ids)
    head = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode(),
    ]
    font = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    all_objects = head + objects + [font]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for num, obj in enumerate(all_objects, start=1):
        offsets.append(len(out))
        out += f"{num} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(all_objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    trailer = f"trailer\n<< /Size {len(all_objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    out += trailer.encode()
    path.write_bytes(bytes(out))


def write_docx(path: Path) -> None:
    doc = Document()
    doc.core_properties.created = __import__("datetime").datetime(2026, 8, 21)
    doc.add_paragraph(BANNER)
    doc.add_heading("Medication List - Jordan Sample", level=1)
    doc.add_paragraph("Last updated: 2026-08-21 by Dr. Example")
    table = doc.add_table(rows=1, cols=5)
    for cell, title in zip(
        table.rows[0].cells, ["Medication", "Dose", "How often", "Reason", "Started"], strict=True
    ):
        cell.text = title
    for row in MEDICATIONS:
        cells = table.add_row().cells
        for cell, value in zip(cells, row, strict=True):
            cell.text = value
    doc.add_heading("Allergies", level=2)
    doc.add_paragraph("Penicillin - hives (2015).")
    doc.add_paragraph("No known food allergies.")
    doc.save(path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_pdf(OUT / "lab-report.pdf", LAB_PAGES)
    (OUT / "visit-summary.txt").write_text(VISIT_SUMMARY)
    write_docx(OUT / "medication-list.docx")
    write_pdf(OUT / "scanned-letter.pdf", [None])
    write_pdf(OUT / "lab-report-columns.pdf", [{"cells": column_lab_cells()}])
    write_pdf(OUT / "lab-report-renal.pdf", [{"cells": renal_lab_cells()}])
    for p in sorted(OUT.iterdir()):
        print(f"{p.name:24} {p.stat().st_size:>7} bytes")


if __name__ == "__main__":
    main()
