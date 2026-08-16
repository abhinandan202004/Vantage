"""
Downloads a symbol's annual report PDFs from NSE (via the `nse`
library), extracts text, and ingests it into the RAG store as
`company_filing` chunks tagged to that symbol.

IMPORTANT: I have NOT been able to verify this end-to-end against a
live NSE response — same sandbox network limitation as nse_client.py.
The `annual_reports()` method's exact response shape (which key holds
the PDF URL) is my best inference from the library's method signature
and general NSE filing-metadata conventions, not a confirmed field
name. Run this with a stray `print(reports)` uncommented below the
first time to see the actual shape, and adjust `_extract_pdf_url()` if
the key name doesn't match.

Also worth knowing: annual reports can run 100-300+ pages. Extracting
and chunking the FULL document works but produces a lot of chunks per
report (expect hundreds) — consider extracting only specific sections
(MD&A, financial statements) if you want a more focused knowledge
base once you can see what a real filing's text looks like.
"""
from pathlib import Path

from app.db import SessionLocal
from app.data_ingestion.nse_client import _CACHE_DIR
from app.rag.store import add_document

_FILINGS_DOWNLOAD_DIR = _CACHE_DIR.parent / "filings"
_FILINGS_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _extract_pdf_url(report_record: dict) -> str | None:
    """
    Best-effort extraction of the PDF URL from one annual_reports()
    record. NSE filing metadata commonly uses one of these key names
    across different endpoints — try them in order. UNVERIFIED against
    a live response; adjust if none match what you actually see.
    """
    for key in ("fileName", "pdfLink", "attachment", "url", "link"):
        if key in report_record and report_record[key]:
            return report_record[key]
    return None


def _extract_pdf_text(pdf_path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text)


def ingest_annual_reports(symbol: str, max_reports: int = 1) -> None:
    """
    Fetches and ingests up to `max_reports` most recent annual reports
    for `symbol`. Defaults to just 1 (the latest) since each report is
    a large document — raise max_reports once you've confirmed the
    pipeline works end-to-end and are comfortable with the volume.
    """
    from nse import NSE

    db = SessionLocal()
    try:
        print(f"  [filings] {symbol}: fetching filing list from NSE...")
        with NSE(download_folder=_CACHE_DIR) as nse:
            reports_by_year = nse.annual_reports(symbol)
            # print(reports_by_year)  # uncomment to inspect the real response shape

            if not reports_by_year:
                print(f"  [filings] {symbol}: no annual reports found")
                return

            # flatten {year: [records]} into a flat list, most recent years first
            all_records = []
            for year in sorted(reports_by_year.keys(), reverse=True):
                all_records.extend(reports_by_year[year])

            processed = 0
            for record in all_records[:max_reports]:
                pdf_url = _extract_pdf_url(record)
                if pdf_url is None:
                    print(f"  [filings] {symbol}: couldn't find a PDF URL in record "
                          f"(keys: {list(record.keys())}) — see module docstring")
                    continue

                try:
                    print(f"  [filings] {symbol}: downloading {pdf_url} ...")
                    pdf_path = nse.download_document(pdf_url, folder=_FILINGS_DOWNLOAD_DIR)
                    print(f"  [filings] {symbol}: downloaded, extracting text "
                          f"(large reports can take a while here — pypdf reads page by page)...")
                    text = _extract_pdf_text(pdf_path)
                    print(f"  [filings] {symbol}: extracted {len(text.split())} words from PDF")
                except Exception as e:
                    print(f"  [filings] {symbol}: failed to download/extract {pdf_url}: {e}")
                    continue

                title = f"{symbol} Annual Report ({record.get('year', 'unknown year')})"
                n_chunks = add_document(
                    db, text=text, source_type="company_filing",
                    title=title, source_url=pdf_url, symbol=symbol,
                )
                db.commit()
                print(f"  [filings] {symbol}: ingested '{title}' — {n_chunks} chunks")
                processed += 1

            if processed == 0:
                print(f"  [filings] {symbol}: no reports successfully processed")
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    ingest_annual_reports(sym)