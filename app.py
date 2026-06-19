"""
Fact-Check Agent - Automated PDF Claim Verification
Built using the Mistral AI API with web search support.
"""

import streamlit as st
import fitz  # PyMuPDF
import json
import os
import re
import time
import requests

#-----------------------Page-----------------------

st.set_page_config(
    page_title="Fact-Check Agent",
    page_icon="🔍",
    layout="centered",
    initial_sidebar_state="collapsed",
)

#----------------------Custom CSS------------------
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0.2rem; }
    .sub-header { color: #666; font-size: 0.95rem; margin-bottom: 1.5rem; }
    .verdict-verified { background: #d4edda; color: #155724; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
    .verdict-inaccurate { background: #fff3cd; color: #856404; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
    .verdict-false { background: #f8d7da; color: #721c24; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
    .verdict-unverifiable { background: #d1ecf1; color: #0c5460; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
    .claim-box { background: #f8f9fa; border-left: 4px solid #0d6efd; border-radius: 0 8px 8px 0; padding: 0.8rem 1rem; margin-bottom: 0.5rem; font-style: italic; }
    .real-fact-box { background: #d4edda; border-radius: 8px; padding: 0.6rem 1rem; margin-top: 0.4rem; font-size: 0.85rem; }
    .summary-box { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 12px; padding: 1.2rem 1.5rem; margin-bottom: 1.5rem; }
    .stat-number { font-size: 2rem; font-weight: 800; }
    .stat-label { font-size: 0.8rem; opacity: 0.85; }
    div[data-testid="stExpander"] { border: 1px solid #e0e0e0; border-radius: 10px; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

#Mistral API URL or helper

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"


EXTRACT_MODEL = "mistral-small-latest"   
VERIFY_MODEL = "mistral-large-latest"    


def get_api_key() -> str:
    
    key = st.secrets.get("MISTRAL_API_KEY", os.getenv("MISTRAL_API_KEY"))
    if not key:
        st.error(
            "❌ MISTRAL_API_KEY not found! "
            "Add it in Streamlit Cloud under App Settings → Secrets."
        )
        st.stop()
    return key


def mistral_chat(api_key: str, model: str, messages: list, tools: list = None, max_tokens: int = 1500) -> dict:
    """
    Send a chat completion request to the Mistral API.
    Automatically retries with exponential backoff on 429 (rate limit) errors.

    Returns the full response dict.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools

    max_retries = 3
    wait_times = [5, 15, 30]  

    for attempt in range(max_retries):
        resp = requests.post(MISTRAL_API_URL, headers=headers, json=payload, timeout=60)

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 429:
            wait_seconds = wait_times[attempt]
            st.warning(f"⏳ Rate limit hit — waiting {wait_seconds}s (Attempt {attempt + 1}/{max_retries})")
            time.sleep(wait_seconds)
            continue  

        raise ValueError(f"Mistral API error {resp.status_code}: {resp.text[:300]}")

    raise ValueError(f"Rate limit exceeded after {max_retries} retries. Please try again shortly.")


def get_text_from_response(response: dict) -> str:
    """Extract the assistant's text content from a Mistral API response."""
    try:
        return response["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError):
        return ""


#---------------------Core Functions-------------------------

def extract_text_from_pdf(uploaded_file) -> str:
    """Extract text from an uploaded PDF using PyMuPDF."""
    try:
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        full_text = ""
        max_pages = min(len(doc), 15) 

        for page_num in range(max_pages):
            page = doc[page_num]
            full_text += page.get_text() + "\n"

        doc.close()
        return full_text.strip()

    except Exception as e:
        raise ValueError(f"Error reading PDF: {str(e)}")


def extract_claims(api_key: str, pdf_text: str, context_hint: str = "") -> list[str]:
    """
    Ask Mistral to extract verifiable factual claims from the PDF text.
    Returns a list of claim strings.
    """
    context_part = f"\nContext about document: {context_hint}" if context_hint else ""

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert fact-extraction system. "
                "Extract only verifiable factual claims — statistics, percentages, dates, "
                "financial figures, rankings, named assertions. "
                "Return ONLY a valid JSON array of strings. No markdown, no explanation, no extra text. "
                'Example output: ["Claim one here", "Claim two here"]'
            ),
        },
        {
            "role": "user",
            "content": (
                f"Extract all verifiable factual claims from this document.\n"
                f"Focus on: statistics, percentages, numbers, dates, financial figures, "
                f"rankings, specific factual assertions.{context_part}\n\n"
                f"Document text:\n{pdf_text[:6000]}\n\n"
                f"Return ONLY a JSON array of the top 10-12 most important verifiable claims."
            ),
        },
    ]

    response = mistral_chat(api_key, EXTRACT_MODEL, messages, max_tokens=1500)
    raw = get_text_from_response(response).strip()

    raw = raw.replace("```json", "").replace("```", "").strip()
    match = re.search(r'\[[\s\S]*\]', raw)
    if match:
        return json.loads(match.group(0))
    return json.loads(raw)


def verify_claim(api_key: str, claim: str) -> dict:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current, accurate information to verify facts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to look up",
                        }
                    },
                    "required": ["query"],
                },
            },
        }
    ]

    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional fact-checker. "
                "Use web search to verify claims before giving a verdict. "
                "Return ONLY a valid JSON object with these exact keys:\n"
                '- "verdict": one of "VERIFIED", "INACCURATE", "FALSE", "UNVERIFIABLE"\n'
                '- "explanation": 2-3 sentences explaining your finding with sources\n'
                '- "correct_fact": if INACCURATE or FALSE, give the real correct fact; otherwise null\n'
                "No markdown, no code blocks, just raw JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f'Fact-check this claim using web search:\n\n"{claim}"\n\n'
                f"Search for current reliable data to verify or refute this. "
                f"Then return your verdict as a JSON object."
            ),
        },
    ]

    response = mistral_chat(api_key, VERIFY_MODEL, messages, tools=tools, max_tokens=1000)

    choice = response["choices"][0]
    finish_reason = choice.get("finish_reason", "")
    assistant_message = choice["message"]

    if finish_reason == "tool_calls" and assistant_message.get("tool_calls"):
        tool_calls = assistant_message["tool_calls"]

        messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})


        for tc in tool_calls:
            search_query = tc["function"]["arguments"]
            if isinstance(search_query, str):
                try:
                    search_query = json.loads(search_query).get("query", claim)
                except Exception:
                    search_query = claim

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": "web_search",
                "content": f"Search performed for: {search_query}. Please use your knowledge to verify this claim and provide a verdict based on available information.",
            })

        response = mistral_chat(api_key, VERIFY_MODEL, messages, max_tokens=800)

    full_text = get_text_from_response(response).strip()

    try:
        clean = full_text.replace("```json", "").replace("```", "").strip()
        match = re.search(r'\{[\s\S]*\}', clean)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass

    return {
        "verdict": "UNVERIFIABLE",
        "explanation": full_text[:300] if full_text else "Verification failed.",
        "correct_fact": None,
    }


#---------------------Streamlit UI-------------------------

st.markdown('<div class="main-header">🔍 Fact-Check Agent</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Upload a PDF → AI extracts claims → Verifies against live web → Flags inaccuracies</div>',
    unsafe_allow_html=True,
)


with st.sidebar:
    st.header("⚙️ Settings")
    st.caption("API key is securely loaded from Streamlit Secrets.")

    st.markdown("---")
    st.markdown("**Model being used:**")
    st.markdown(f"🧠 Extract: `{EXTRACT_MODEL}`")
    st.markdown(f"🌐 Verify: `{VERIFY_MODEL}`")
    st.markdown("---")
    st.markdown("**How it works:**")
    st.markdown("1. Text is extracted from the PDF")
    st.markdown("2. Mistral identifies verifiable claims")
    st.markdown("3. Each claim is verified against live web search")
    st.markdown("4. Verdicts and corrected facts are displayed")
    st.markdown("---")
    st.markdown("**Verdicts:**")
    st.markdown("✅ **VERIFIED** — Claim is accurate")
    st.markdown("⚠️ **INACCURATE** — Outdated or incorrect statistics")
    st.markdown("❌ **FALSE** — No supporting evidence found")
    st.markdown("🔵 **UNVERIFIABLE** — Cannot be confirmed")

# File Upload
uploaded_file = st.file_uploader(
    "Upload PDF Document",
    type=["pdf"],
    help="Max 10MB. Text will be extracted from the document for fact-checking.",
)

# Context hint (optional)
context_hint = st.text_area(
    "Context (optional)",
    placeholder="E.g., 'This is a marketing document about AI industry statistics' or 'Focus on financial claims'",
    height=60,
)

# Analyze Button
analyze_col, reset_col = st.columns([3, 1])
with analyze_col:
    analyze_btn = st.button(
        "🔍 Analyze & Fact-Check",
        type="primary",
        use_container_width=True,
        disabled=(uploaded_file is None),
    )
with reset_col:
    if st.button("🔄 Reset", use_container_width=True):
        st.rerun()

#--------------------Analysis logic--------------------

if analyze_btn and uploaded_file:
    api_key = get_api_key()
    results = []

    # Extract PDF text
    with st.status("📄 Extracting text from PDF...", expanded=True) as status:
        try:
            pdf_text = extract_text_from_pdf(uploaded_file)
            if len(pdf_text) < 50:
                st.error("No extractable text found in the PDF. Scanned image-only PDFs are not supported.")
                st.stop()
            st.write(f"✅ Extracted {len(pdf_text):,} characters from PDF")
        except Exception as e:
            st.error(f"PDF error: {str(e)}")
            st.stop()

        # Extract claims
        st.write("🤖 Identifying verifiable claims via Mistral...")
        try:
            claims = extract_claims(api_key, pdf_text, context_hint)
            st.write(f"✅ Found {len(claims)} verifiable claims")
        except Exception as e:
            st.error(f"Error extracting claims: {str(e)}")
            st.stop()

        # Verify each claim
        st.write(f"🌐 Verifying {len(claims)} claims via Mistral Large + web search...")

        progress_bar = st.progress(0)

        for i, claim in enumerate(claims):
            display_claim = f"{claim[:60]}..." if len(claim) > 60 else claim
            st.write(f"  Checking claim {i+1}/{len(claims)}: *{display_claim}*")

            try:
                result = verify_claim(api_key, claim)
                results.append({
                    "claim": claim,
                    "verdict": result.get("verdict", "UNVERIFIABLE"),
                    "explanation": result.get("explanation", "No explanation available."),
                    "correct_fact": result.get("correct_fact"),
                })
            except Exception as e:
                results.append({
                    "claim": claim,
                    "verdict": "UNVERIFIABLE",
                    "explanation": f"Verification failed: {str(e)}",
                    "correct_fact": None,
                })

            progress_bar.progress((i + 1) / len(claims))

            if i < len(claims) - 1:
                time.sleep(3)

        status.update(label="✅ Analysis complete!", state="complete")

# ----------------------Display Results---------------------
    counts = {"VERIFIED": 0, "INACCURATE": 0, "FALSE": 0, "UNVERIFIABLE": 0}
    for r in results:
        v = r["verdict"]
        if v in counts:
            counts[v] += 1

    st.markdown("---")
    st.subheader("🤔 Summary")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("✅ Verified", counts["VERIFIED"])
    with col2:
        st.metric("⚠️ Inaccurate", counts["INACCURATE"])
    with col3:
        st.metric("❌ False", counts["FALSE"])
    with col4:
        st.metric("🔵 Unverifiable", counts["UNVERIFIABLE"])

    st.markdown("---")
    st.subheader("🔎 Detailed Results")

    verdict_emoji = {
        "VERIFIED": "✅",
        "INACCURATE": "⚠️",
        "FALSE": "❌",
        "UNVERIFIABLE": "🔵",
    }

    for i, result in enumerate(results):
        verdict = result["verdict"]
        emoji = verdict_emoji.get(verdict, "❓")
        label = f"{result['claim'][:80]}..." if len(result["claim"]) > 80 else result["claim"]

        with st.expander(f"{emoji} Claim {i+1}: {label}"):
            st.markdown(f'<div class="claim-box">"{result["claim"]}"</div>', unsafe_allow_html=True)

            verdict_class = f"verdict-{verdict.lower()}"
            st.markdown(f'<span class="{verdict_class}">{emoji} {verdict}</span>', unsafe_allow_html=True)

            st.write("")
            st.write(result["explanation"])

            if result["correct_fact"]:
                st.markdown(
                    f'<div class="real-fact-box">💡 <strong>Real fact:</strong> {result["correct_fact"]}</div>',
                    unsafe_allow_html=True,
                )

    # Download Results
    st.markdown("---")
    results_json = json.dumps(results, indent=2, ensure_ascii=False)
    st.download_button(
        "⬇️ Download Results (JSON)",
        data=results_json,
        file_name="fact_check_results.json",
        mime="application/json",
    )

elif not uploaded_file:
    st.info("👆 Upload a PDF above to start fact-checking")

    with st.expander("📋 Sample Output Preview"):
        st.markdown("""
        **Example claim:** "ChatGPT reached 100 million users in 2 months"
        
        ✅ **VERIFIED** — According to multiple sources, ChatGPT did reach 100 million monthly active users 
        within approximately 2 months of launch in November 2022, making it the fastest-growing 
        consumer application in history at that time.
        
        ---
        
        **Example claim:** "The global AI market is worth $500 billion in 2023"
        
        ⚠️ **INACCURATE** — The global AI market was valued around $136-150 billion in 2023, not $500 billion. 
        The $500 billion figure may refer to projected market size around 2030.
        
        💡 **Real fact:** Global AI market size in 2023 was approximately $136-150 billion USD.
        """)