# DocuDude

DocuDude is a Streamlit app that extracts text from digital PDFs, scanned PDFs
and images, and can optionally analyse the result with an AI model on Ollama
Cloud. Developed by Huzaifa Ameer.

## Features

**Text extraction** (runs locally with Tesseract, nothing is sent to an AI service)

- Pages are cleaned before OCR. The app inverts light-on-dark text, resizes
  text to the size Tesseract reads best, rotates sideways or upside-down
  pages, straightens tilted scans and removes shadows or uneven lighting.
- Multi-pass OCR (*Balanced* and *Best* modes) reads each page more than
  once with different preprocessing and keeps the most confident result.
- In PDFs, the app uses the embedded text when it is reliable. It OCRs
  scanned pages, pages with broken embedded text, and mostly-image pages.
  Pages are processed in parallel.
- Wide gaps between words are kept, so tables and invoices stay aligned.
- Multi-page TIFFs, WEBP and transparent PNGs are supported.
- Words read with low confidence are highlighted for review. Text can be
  edited before download (TXT or JSON).

**AI analysis** (opt-in, sends only the extracted text)

- Returns the document type, title, a summary of up to 750 characters, key
  fields and reliability notes, using a JSON schema with temperature 0.
- The model must copy every key value verbatim and quote its source line. Each
  value is checked against the OCR text. Values that cannot be found are
  marked **⚠️ Check** instead of being shown as fact.
- Numbers in the summary that don't appear in the source are flagged.
- Long documents are analysed in sections and combined, not silently cut off.

The displayed confidence is Tesseract's own estimate, and AI output can be
wrong. Always verify important names, numbers, dates and totals against the
original.

## Run

1. Install the Python dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

2. Install the [Tesseract OCR engine](https://github.com/UB-Mannheim/tesseract/wiki)
   with the language data you need (plus `osd` for auto-rotation). The app
   finds Tesseract on `PATH` and in the standard Windows install folders,
   including the per-user `%LOCALAPPDATA%\Programs\Tesseract-OCR`. To point to
   another location, set `TESSERACT_CMD`.

3. (Optional) Configure AI analysis in `.env` (see `.env.example`):

   ```dotenv
   OLLAMA_API_KEY=paste-your-api-key-here
   OLLAMA_MODEL=gemma4:31b
   ```

   `.env` is ignored by Git. You can use Streamlit secrets instead.

4. Start the app:

   ```powershell
   streamlit run app.py
   ```

## Tests

```powershell
python -m pip install pytest
python -m pytest tests
```

OCR tests are skipped automatically when Tesseract is not installed.

## Project structure

```
app.py                     Streamlit entry point
docudude/
  config.py                Constants and settings lookup (.env / secrets)
  preprocessing.py         Image clean-up: rotation, deskew, scaling, shadows
  ocr.py                   Tesseract OCR, PDF/TIFF handling, multi-pass scoring
  analysis.py              Ollama Cloud analysis with output verification
  document.py              Processed-document model and TXT/JSON export
  ui/
    styles.py              Global CSS
    layout.py              Navbar, home page, footer
    workspace.py           Upload → settings → run workflow
    results.py             Metrics, per-document tabs, review and downloads
tests/                     Unit and OCR tests
```
