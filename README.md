# 🔍 Fact-Check Agent

An AI-powered Streamlit app that automatically extracts factual claims from any PDF document and verifies each one against live web search — flagging outdated stats, inaccurate figures, and unverifiable assertions.

**Live demo:** [Add your Streamlit Cloud link here]

---

## Overview

Documents — reports, pitch decks, marketing one-pagers — are full of numbers that sound authoritative but are often outdated or simply wrong. This tool automates the fact-checking process end-to-end:

1. **Upload a PDF** — text is extracted directly from the document.
2. **Claim extraction** — an LLM identifies the key verifiable claims (statistics, dates, financial figures, rankings).
3. **Live verification** — each claim is checked against real-time web search and given a verdict.
4. **Results dashboard** — verdicts, explanations, and corrected facts are displayed, with a downloadable JSON report.

---

## How It Works

| Step | Description |
|------|-------------|
| **1. Text Extraction** | `PyMuPDF` (`fitz`) parses the uploaded PDF and extracts raw text (up to 15 pages). |
| **2. Claim Extraction** | `mistral-small-latest` reads the extracted text and returns a structured JSON list of the 10–12 most important verifiable claims. |
| **3. Claim Verification** | `mistral-large-latest` is called with a `web_search` tool definition for each claim. If the model issues a tool call, the result is fed back into the conversation before a final verdict is generated. |
| **4. Verdict Classification** | Each claim is labeled **VERIFIED**, **INACCURATE**, **FALSE**, or **UNVERIFIABLE**, with a short explanation and (if applicable) the correct fact. |
| **5. Results Display** | A summary dashboard + expandable per-claim breakdown, with a JSON export option. |

---

## Tech Stack

- **Streamlit** — UI and app framework
- **Mistral AI API** — claim extraction (`mistral-small-latest`) and web-search-grounded verification (`mistral-large-latest`)
- **PyMuPDF (`fitz`)** — PDF text extraction
- **Requests** — direct HTTP calls to the Mistral chat completions endpoint, with retry/backoff handling for rate limits

---

## Project Structure

```
.
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
└── README.md
```

---

## Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/taruns111/<repo-name>.git
cd <repo-name>
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Add your Mistral API key

**For local development**, create a `.streamlit/secrets.toml` file in the project root:
```toml
MISTRAL_API_KEY = "your_api_key_here"
```
> Add `.streamlit/secrets.toml` to your `.gitignore` — never commit real API keys.

### 4. Run the app
```bash
streamlit run app.py
```

---

## Deploying on Streamlit Community Cloud

1. Push this repo to GitHub (without any secrets file).
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo.
3. Under **App Settings → Secrets**, add:
   ```toml
   MISTRAL_API_KEY = "your_api_key_here"
   ```
4. Deploy — the app will pick up the key automatically via `st.secrets`.

---

## Verdict Legend

| Verdict | Meaning |
|---------|---------|
| ✅ **VERIFIED** | Claim is accurate and supported by current data |
| ⚠️ **INACCURATE** | Claim is outdated or partially incorrect |
| ❌ **FALSE** | No supporting evidence found |
| 🔵 **UNVERIFIABLE** | Insufficient information to confirm or deny |

---

## Limitations

- Only the first 15 pages of a PDF are processed.
- Scanned/image-only PDFs without embedded text are not supported (OCR is not implemented).
- The web search tool call is currently a single round-trip per claim; results depend on the model's own search capability rather than a dedicated search API (e.g. Tavily/SerpAPI), which could be added for more grounded verification.
- A short delay is added between claims to stay within API rate limits, so large documents may take a few minutes to fully process.

---

## Future Improvements

- Integrate a dedicated search API (Tavily/SerpAPI) for more reliable, source-linked verification
- Add OCR support for scanned documents
- Support multi-file batch fact-checking
- Add confidence scores alongside verdicts

---

## Author

**Tarun Saini**
Data Analyst | [Portfolio](https://tarun-saini.vercel.app) | [GitHub](https://github.com/taruns111)
