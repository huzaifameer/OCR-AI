# Image & PDF OCR

Streamlit app for extracting English text from digital PDFs, scanned PDFs, and
images. Developed by Huzaifa Ameer.

The app supports multiple files in one run, shows each file's extracted text
separately, and clears previous results when the selected files change. Use the
**Clear** button to reset the uploader and results.

OCR uses Tesseract. The sidebar lets you tune the language, page layout, scan
resolution, and image enhancement. Image enhancement corrects EXIF orientation,
adjusts contrast, sharpens text edges, and resizes very small or large scans.
Scanned PDF pages are rendered at the selected DPI. The displayed confidence is
Tesseract's word-confidence estimate, not a measure that guarantees the text is
correct; verify important names, numbers, dates, and totals against the source
document.

## Run

1. Install the Python dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

2. Install the Tesseract OCR engine. On Windows, the app uses
   `C:\Program Files\Tesseract-OCR\tesseract.exe` when present. To use another
   location, set the `TESSERACT_CMD` environment variable to the executable
   path. Install the Tesseract language data for each language you select in
   the app.

3. Start the app:

   ```powershell
   streamlit run app.py
   ```

`app.py` contains the Streamlit interface. PDF and image extraction functions
are in `document_processing.py`.
