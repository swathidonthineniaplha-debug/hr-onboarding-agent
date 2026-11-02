# Sample documents

**All files here are fictional test data.** Names, numbers, addresses and countries are invented. Phone numbers use the UK Ofcom drama range (01632 960xxx), and emails use the reserved `example.com` domain. No file copies a real government layout, logo, crest, MRZ or security feature.

## Fictional people

| | Alex Example | Jordan Placeholder |
|---|---|---|
| DOB | 1990-04-12 | 1985-09-03 |
| Passport | AB000001 | AB000002 |
| Licence | DL000001 | DL000002 |

## Files and expected classification

| File | Expected class | What it tests |
|---|---|---|
| `passport_alex_example.txt` | `Passport` | Labelled fields, DD/MM/YYYY dates |
| `passport_jordan_placeholder.pdf` | `Passport` | Same fields from a PDF, `03 Sep 1985` dates |
| `driving_licence_alex_example.pdf` | `DrivingLicence` | Numbered fields, `DD.MM.YYYY` dates |
| `driving_licence_jordan_placeholder.txt` | `DrivingLicence` | Dotted-leader layout, ISO dates |
| `employee_alex_example.txt` | `EmployeeDocument` | Form layout, **clean record, expected Processed**. Stated age 36 matches the DOB (until the next birthday on 2027-04-12, see note below). Right to work: Skilled Worker visa, expires 2028-03-31 |
| `employee_jordan_placeholder.pdf` | `EmployeeDocument` | Letter written as prose, dates written out in words. **No right-to-work details** |
| `ambiguous_note.txt` | `Other` (low confidence) | Vague mention of "ID seen" and a reference number |

> **Age depends on today's date.** `run_local.py` checks stated ages against today's date. From 2027-04-12, Alex turns 37, so his form will show an age mismatch until the sample is updated. The tests always use a fixed date (2026-11-01), so they are not affected.

## Regenerating the PDFs

```powershell
python scripts/generate_sample_pdfs.py
```
