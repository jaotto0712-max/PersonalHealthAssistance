"""Generate SYNTHETIC health documents for tests and evaluation. The patient is fictional.

    cd backend && uv run python ../eval/fixtures/make_fixtures.py

Outputs (eval/fixtures/docs/):
  lab-report.pdf        3-page text PDF (CBC, lipid panel + HbA1c, metabolic panel)
  visit-summary.txt     primary-care visit note
  medication-list.docx  medications + allergies table
  scanned-letter.pdf    1-page image-only PDF with no extractable text (OCR case)
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


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path: Path, pages: list[list[str] | None]) -> None:
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
    head = [b"<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode()]
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
    out += f"trailer\n<< /Size {len(all_objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


def write_docx(path: Path) -> None:
    doc = Document()
    doc.core_properties.created = __import__("datetime").datetime(2026, 8, 21)
    doc.add_paragraph(BANNER)
    doc.add_heading("Medication List - Jordan Sample", level=1)
    doc.add_paragraph("Last updated: 2026-08-21 by Dr. Example")
    table = doc.add_table(rows=1, cols=5)
    for cell, title in zip(table.rows[0].cells, ["Medication", "Dose", "How often", "Reason", "Started"], strict=True):
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
    for p in sorted(OUT.iterdir()):
        print(f"{p.name:24} {p.stat().st_size:>7} bytes")


if __name__ == "__main__":
    main()
