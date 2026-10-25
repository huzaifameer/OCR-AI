# Image & PDF OCR

Streamlit app for extracting English text from digital PDFs, scanned PDFs, and
images. Developed by Huzaifa Ameer.

The app provides two separate workflows:

- **Text extraction** runs OCR and displays editable extracted text without an
  Ollama request.
- **Extract + AI analysis** runs OCR first, then can send the extracted text to
  Ollama Cloud for a concise, evidence-based description.

Both workflows support multiple files, show results separately, and clear
previous results when the selected inputs or settings change. Use **Clear** to
reset a workflow's uploader and results.

The home page provides separate shortcuts for text extraction and AI analysis,
an About section, and Huzaifa Ameer's WhatsApp contact. The compact navigation
opens the two document workspaces; OCR settings are shown in the sidebar only
while a workspace is open. A floating WhatsApp button remains available across
the app, and the Streamlit top header is hidden for a cleaner interface.

OCR uses Tesseract. The sidebar lets you tune the language, page layout, scan
resolution, and image enhancement. Image enhancement corrects EXIF orientation,
adjusts contrast, sharpens text edges, and resizes very small or large scans.
Scanned PDF pages are rendered at the selected DPI. The displayed confidence is
Tesseract's word-confidence estimate, not a measure that guarantees the text is
correct; verify important names, numbers, dates, and totals against the source
document.

## Optional Ollama Cloud analysis

The app can optionally send the extracted OCR text to Ollama Cloud for analysis.
The selected model analyzes the OCR text and returns one description that
highlights the document's purpose and important content, capped at 750
characters. The image or PDF itself is not sent to Ollama. The prompt instructs
the model to use only facts present in the OCR, and generation uses zero
temperature to reduce variation. This cannot guarantee that a model will never
make an error; verify the description against the original. The original OCR
output is never changed.

1. Create an Ollama Cloud API key.
2. Open the project `.env` file and set your key and preferred model:

   ```dotenv
   OLLAMA_API_KEY=paste-your-api-key-here
   OLLAMA_MODEL=gemma4:31b
   ```

   The app loads `.env` automatically at startup. `.env` is ignored by Git so
   your real key won't be committed. `.env.example` is a safe template.
   Alternatively, configure environment variables or Streamlit secrets:

   ```toml
   OLLAMA_API_KEY = "paste-your-api-key-here"
   OLLAMA_MODEL = "gemma4:31b"
   ```

   The secrets file is ignored by Git. The sidebar selector includes `beam`,
   `gemma4:31b`, `gpt-oss:120b`, `gpt-oss:20b`,
   `nemotron-3-nano:30b`, `nemotron-3-super`, and `nemotron-3-ultra`.
   `gemma4:31b` is selected by default. `OLLAMA_MODEL` is optional.

3. Enable Ollama analysis and explicitly opt in before document content is sent.
   The app sends the extracted text only. Documents with more than 60,000 OCR
   characters are truncated for AI analysis; the complete OCR output remains
   available in the app.

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

3. (Optional) Add your Ollama key to `.env`, then start the app:

   ```powershell
   streamlit run app.py
   ```

`app.py` contains the Streamlit interface. PDF and image extraction functions
are in `document_processing.py`.
