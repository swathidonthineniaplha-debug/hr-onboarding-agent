"""Generate the fictional sample PDFs in sample_documents/.

Run from the project root:  python scripts/generate_sample_pdfs.py

The PDFs are deliberately plain text (no logos, layouts or security features),
so they test text extraction and classification, not image handling.
"""

from pathlib import Path

from fpdf import FPDF

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "sample_documents"
HEADER = "SAMPLE - FICTIONAL TEST DATA"

DOCUMENTS = {
    "passport_jordan_placeholder.pdf": """
PASSPORT - fictional test copy
Republic of Testland (fictional country)

Name: Jordan Placeholder
Nationality: Testlandian
Date of birth: 03 Sep 1985
Passport No: AB000002
Issued: 20 Feb 2019
Expires: 19 Feb 2029

Not a real passport. Created for software testing only.
""",
    "driving_licence_alex_example.pdf": """
DRIVING LICENCE - fictional test copy

1. Surname: EXAMPLE
2. Forename(s): ALEX
3. Date of birth: 12.04.1990
4. Expiry date: 11.04.2033
5. Licence number: DL000001
8. Address: 1 Example Street, Sampletown, ZZ1 1ZZ
9. Categories: AM, B

Not a real licence. Created for software testing only.
""",
    "employee_jordan_placeholder.pdf": """
Placeholder Analytics Ltd (fictional)
HR Department

Re: Pre-employment summary for Jordan Placeholder

Dear Hiring Team,

Please find below the background details supplied by our new joiner,
Jordan Placeholder, born on the third of September 1985 and aged 41.

Jordan's career began at Mock Retail Group, where they worked as a
Store Operations Coordinator from March 2010 until December 2016. Their
manager at the time, Casey Sample, has agreed to provide a reference and
can be reached on 01632 960003 or casey.sample@example.com.

From January 2017 to July 2026 Jordan held the role of Operations
Manager at Testbridge Services Ltd. The nominated referee is Riley
Fakename, Regional Director, contactable at riley.fakename@example.com.

Kind regards,
Taylor Demo
HR Advisor (fictional)
""",
}


def build_pdf(body: str, path: Path) -> None:
    pdf = FPDF(format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, HEADER, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, body.strip())
    pdf.output(str(path))


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    for filename, body in DOCUMENTS.items():
        build_pdf(body, OUTPUT_DIR / filename)
        print(f"wrote {filename}")


if __name__ == "__main__":
    main()
