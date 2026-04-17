import ollama
import json
import yfinance as yf
from tavily import TavilyClient
import os
import re
import time
import sys
from dotenv import load_dotenv

# =====================================================================
#  AI AGENT MODULE -- Glass-Box Architecture (Ollama Backend)
# =====================================================================

load_dotenv()

# --- Windows-safe UTF-8 console output ---
# Streamlit on Windows can run with a cp1252 console encoding, which will crash on emojis
# used in action labels (e.g., "❓ What's happening?"). Force UTF-8 and replace any
# unencodable characters instead of raising.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    # If the environment doesn't allow reconfigure, we still want the app to run.
    pass

# -- Ollama Models --
# We auto-detect installed models to avoid 404 "model not found" latency.
# You can override with env var OLLAMA_MODELS="gemma3:4b,llama3.1:latest"
DEFAULT_MODEL_PREFERENCE = ["llama3.2:3b", "gemma3:4b", "llama3.1:latest", "llama3.1"]

MAX_FACT_CHECK_RETRIES = 3
MAX_API_RETRIES = 3

# Brand name used across prompts/UI copy (no "Gemini" anywhere)
BRAND_NAME = "AI Financial Insights"

class LLMResponse:
    def __init__(self, text):
        self.text = text

_AVAILABLE_MODELS_CACHE: list[str] | None = None

def _get_available_ollama_models() -> list[str]:
    global _AVAILABLE_MODELS_CACHE
    if _AVAILABLE_MODELS_CACHE is not None:
        return _AVAILABLE_MODELS_CACHE

    override = os.getenv("OLLAMA_MODELS", "").strip()
    if override:
        _AVAILABLE_MODELS_CACHE = [m.strip() for m in override.split(",") if m.strip()]
        return _AVAILABLE_MODELS_CACHE

    # Try to discover installed models via ollama python client.
    try:
        listing = ollama.list()
        models = listing.get("models", []) if isinstance(listing, dict) else []
        installed = []
        for m in models:
            name = (m.get("name") or "").strip()
            if name:
                installed.append(name)
        if installed:
            _AVAILABLE_MODELS_CACHE = installed
            return _AVAILABLE_MODELS_CACHE
    except Exception:
        pass

    # Fallback: Prefer models we know the user has if discovery fails.
    _AVAILABLE_MODELS_CACHE = ["llama3.2:3b", "gemma3:1b", "llama3.1:latest", "llama3.1"]
    return _AVAILABLE_MODELS_CACHE

def _build_model_try_list() -> list[str]:
    installed = _get_available_ollama_models()
    installed_set = {m.lower() for m in installed}
    ordered: list[str] = []

    # Preference order first (only if installed)
    for pref in DEFAULT_MODEL_PREFERENCE:
        if pref.lower() in installed_set:
            ordered.append(pref)

    # Then any remaining installed models
    for m in installed:
        if m.lower() not in {x.lower() for x in ordered}:
            ordered.append(m)

    return ordered

def _primary_model_name() -> str:
    """Best-effort: the first model we would try."""
    try:
        lst = _build_model_try_list()
        return lst[0] if lst else "ollama"
    except Exception:
        return "ollama"

def _call_ollama(contents, config=None, system_instruction=None):
    """Resilient Ollama wrapper with retry + model fallback."""
    cfg_kwargs = config or {}
    sys_inst = cfg_kwargs.get("system_instruction") or system_instruction
    
    messages = []
    if sys_inst:
        messages.append({"role": "system", "content": sys_inst})
        
    messages.append({"role": "user", "content": contents})
    
    options = {}
    if "temperature" in cfg_kwargs:
        options["temperature"] = cfg_kwargs["temperature"]
    # Keep responses bounded and prevent excessively long generations.
    # Ollama's python client passes these into the model options.
    options.setdefault("num_predict", int(cfg_kwargs.get("num_predict", 450)))
    # Encourage shorter, faster responses by default
    options.setdefault("top_p", float(cfg_kwargs.get("top_p", 0.9)))
    options.setdefault("top_k", int(cfg_kwargs.get("top_k", 40)))
    if "top_p" in cfg_kwargs:
        options["top_p"] = cfg_kwargs["top_p"]
    if "top_k" in cfg_kwargs:
        options["top_k"] = cfg_kwargs["top_k"]
        
    format_opt = ""
    if cfg_kwargs.get("response_mime_type") == "application/json":
        format_opt = "json"

    for model_id in _build_model_try_list():
        for attempt in range(1, MAX_API_RETRIES + 1):
            try:
                kwargs = {
                    "model": model_id,
                    "messages": messages,
                    "options": options
                }
                if format_opt:
                    kwargs["format"] = format_opt
                    
                response = ollama.chat(**kwargs)
                return LLMResponse(response['message']['content'])
            except Exception as e:
                err_str = str(e)
                print(f"[OLLAMA] {model_id} Error (attempt {attempt}/{MAX_API_RETRIES}): {err_str}")
                # If the model isn't installed, don't waste retries on it.
                if "not found" in err_str.lower() and "model" in err_str.lower():
                    break
                time.sleep(2)
                continue
        print(f"[OLLAMA] {model_id} exhausted retries. Trying next model...")
    raise Exception("All local Ollama models unavailable after retries.")


def _safe_json_loads(text: str) -> dict:
    """
    Robustly extracts and parses JSON from potentially malformed or truncated LLM output.
    """
    if not text or not isinstance(text, str):
        return {}

    text = text.strip()
    
    # 0. Strip Markdown code blocks if present (common in models like Llama 3)
    # This handles ```json { ... } ``` or just ``` { ... } ```
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    text = text.strip()
    
    # 1. Try standard parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2. Extract content between first { and last }
    m = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    # 3. Handle truncated JSON (missing closing braces)
    # This is a basic repair strategy for local LLM truncation
    repaired = text
    open_braces = repaired.count('{') - repaired.count('}')
    if open_braces > 0:
        repaired += '}' * open_braces
        
    try:
        return json.loads(repaired)
    except Exception:
        pass
        
    # 4. Final attempt: Extract key-value pairs using regex (desperate fallback)
    extracted = {}
    keys = ["signal", "justification", "summary", "accuracy", "completeness", "clarity", "confidence", "status", "feedback", "executive_summary"]
    for k in keys:
        # Match both "key": "value" and "key": num/bool
        # We handle quotes, mid-sentence truncation, and multi-line values
        pattern = rf'"{k}"\s*:\s*(?:["\']?)(.*?)(?:["\']?)(?:,|\s*\n|\s*}}|$)'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            # Clean up value: remove trailing braces/brackets if we caught them
            val = match.group(1).strip().strip('"').strip("'").split(",")[0].strip()
            # If it's a list (for competitors or landscape), we try a separate regex
            if k in ["competitive_landscape", "landscape"]:
                # For simplicity in fallback, we just capture the raw list string
                val = re.search(rf'"{k}"\s*:\s*(\[.*?\])', text, re.DOTALL)
                extracted[k] = _safe_json_loads(val.group(1)) if val else []
            else:
                extracted[k] = val
            
    # Final safety labels for verification status
    if "status" not in extracted and ("passed" in text.lower() or "verified" in text.lower()):
        extracted["status"] = "PASS"

    return extracted if extracted else {"error": "JSON parse failed after all repair attempts", "raw": text[:100]}


def robust_tag_parser(text, tag):
    """
    Greedy parser that extracts content between <tag> and </tag>.
    Handles missing closing tags and nested content by searching for the start tag 
    and matching until the end tag or end of string.
    """
    # Use non-greedy match but ensure we find the tag even if malformed/missing closing
    pattern = rf"<{tag}>(.*?)(?:</{tag}>|$)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def format_intelligence_steps(text):
    """
    Transforms raw <step> tags into professional, styled HTML timeline items.
    """
    if not text:
        return ""
    
    # 1. Extract all content inside <step> tags
    steps = re.findall(r'<step>(.*?)</step>', text, re.DOTALL | re.IGNORECASE)
    
    # If no tags found but text exists, it might be a partial stream
    if not steps and "<step>" in text:
        # Catch partial trailing step
        partial = text.split("<step>")[-1]
        if "</step>" not in partial:
            steps = [partial]

    if not steps:
        return f'<div style="color:#94A3B8; font-style:italic; font-size:0.85rem;">{text}</div>'

    html = '<div style="display:flex; flex-direction:column; gap:10px; margin-top:5px;">'
    for i, step in enumerate(steps):
        step = step.strip()
        if not step: continue
        
        # Determine icon based on content
        icon = "●"
        if "verified" in step.lower() or "passed" in step.lower(): icon = "✓"
        elif "error" in step.lower() or "failed" in step.lower(): icon = "⚠"
        elif "searching" in step.lower() or "tavily" in step.lower(): icon = "🔎"
        elif "yfinance" in step.lower() or "metrics" in step.lower(): icon = "📊"
        
        # NOTE: NO leading spaces here! It triggers markdown code blocks.
        html += '<div style="display:flex; align-items:flex-start; gap:12px; margin-bottom:8px;">'
        html += f'<div style="flex:0 0 24px; height:24px; border-radius:50%; background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.2); color:#10B981; display:flex; align-items:center; justify-content:center; font-size:0.75rem; font-weight:bold;">{icon}</div>'
        html += f'<div style="flex:1; padding-top:2px;"><div style="color:#E2E8F0; font-size:0.88rem; line-height:1.5;">{step}</div></div>'
        html += '</div>'
        
    html += '</div>'
    return html


def _stream_ollama(contents, system_instruction=None):
    """Generates a stream of responses from Ollama for live terminal feedback."""
    model_id = _primary_model_name()
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": contents})

    try:
        stream = ollama.chat(
            model=model_id,
            messages=messages,
            stream=True,
            options={"temperature": 0.15, "num_predict": 900}
        )
        return stream
    except Exception as e:
        print(f"[OLLAMA STREAM ERROR] {e}")
        return None


def resolve_ticker(query: str) -> str | None:
    """
    Resolves natural language company names to stock tickers.
    Returns the resolved ticker string, or None if the entity
    cannot be found on any major public exchange.
    """
    print(f"\n{'=' * 55}")
    print(f"[STEP 1: TICKER RESOLUTION] Input: \"{query}\"")
    print(f"{'=' * 55}")

    raw = query.strip().upper()
    raw_original = query.strip()

    def _is_valid_symbol(sym: str) -> bool:
        """
        yfinance .info can 404 intermittently (esp. non-US). Validate via price history / fast_info.
        """
        if not sym:
            return False
        try:
            t = yf.Ticker(sym)
            # Fast path: history exists and has prices
            h = t.history(period="5d")
            if h is not None and not h.empty and "Close" in h.columns:
                return True
        except Exception:
            pass
        try:
            t = yf.Ticker(sym)
            fi = getattr(t, "fast_info", None)
            # fast_info may be a dict-like or object; handle both
            last_price = None
            if isinstance(fi, dict):
                last_price = fi.get("last_price") or fi.get("lastPrice")
            else:
                last_price = getattr(fi, "last_price", None)
            if last_price:
                return True
        except Exception:
            pass
        return False

    # -- Fast path: if input already looks like a valid ticker, verify it --
    if re.match(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$', raw):
        print(f"[STEP 1: TICKER RESOLUTION] Input looks like a ticker. Validating via yFinance...")
        try:
            if _is_valid_symbol(raw):
                print(f"[STEP 1: TICKER RESOLUTION] Validated -> {raw}")
                return raw
        except Exception:
            pass
        print(f"[STEP 1: TICKER RESOLUTION] Direct validation failed. Falling through to search...")

    # -- Local yFinance Search fallback (no API key required) --
    # This lets users type "Apple", "Nvidia", etc. and still get a valid ticker like AAPL/NVDA.
    try:
        if hasattr(yf, "Search") and raw_original:
            print("[STEP 1: TICKER RESOLUTION] Searching locally via yFinance Search...")
            s = yf.Search(raw_original, max_results=8)
            quotes = getattr(s, "quotes", None) or []
            # Prefer equity symbols (when available), then first valid symbol.
            symbol_candidate = None
            for q in quotes:
                sym = (q.get("symbol") or "").upper()
                qtype = (q.get("quoteType") or "").upper()
                if sym and qtype in {"EQUITY", "ETF"}:
                    symbol_candidate = sym
                    break
            if not symbol_candidate and quotes:
                symbol_candidate = (quotes[0].get("symbol") or "").upper()

            if symbol_candidate:
                # Validate candidate quickly via yfinance
                print(f"[STEP 1: TICKER RESOLUTION] yFinance Search candidate: {symbol_candidate}. Validating...")
                if _is_valid_symbol(symbol_candidate):
                    print(f"[STEP 1: TICKER RESOLUTION] Resolved -> {symbol_candidate}")
                    return symbol_candidate

                # Common India fallbacks
                if "." not in symbol_candidate:
                    for suffix in (".NS", ".BO"):
                        cand = f"{symbol_candidate}{suffix}"
                        if _is_valid_symbol(cand):
                            print(f"[STEP 1: TICKER RESOLUTION] Resolved -> {cand}")
                            return cand
    except Exception as e:
        print(f"[STEP 1: TICKER RESOLUTION] yFinance Search fallback failed: {e}")

    # -- Tavily search for natural language input --
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("[STEP 1: TICKER RESOLUTION] WARNING: No TAVILY_API_KEY. Could not resolve company name.")
        return None

    try:
        print(f"[STEP 1: TICKER RESOLUTION] Searching via Tavily...")
        tavily_client = TavilyClient(api_key=api_key)
        response = tavily_client.search(
            query=f"Stock ticker symbol for {query} company NYSE NASDAQ BSE NSE",
            search_depth="basic",
            max_results=3
        )
        results = response.get("results", [])

        if not results:
            print(f"[STEP 1: TICKER RESOLUTION] FAILED -- No search results for \"{query}\"")
            return None

        # Combine top result titles for better extraction
        combined = " | ".join([r.get("title", "") for r in results[:3]])
        prompt = (
            f"Extract ONLY the stock ticker symbol from this text: '{combined}'. "
            f"The company the user is looking for is: '{query}'. "
            f"Output ONLY the ticker (e.g., AAPL, TATAMOTORS.NS, TSLA). No other text."
        )

        print(f"[STEP 1: TICKER RESOLUTION] Extracting ticker via local LLM...")
        try:
            model_res = _call_ollama(
                contents=prompt,
                config={"temperature": 0.0},
            )
            ticker_raw = model_res.text.strip().upper()
            ticker_clean = ticker_raw.split()[0] if ticker_raw.split() else None
        except Exception as gemini_err:
            print(f"[STEP 1: TICKER RESOLUTION] Local LLM extraction failed: {gemini_err}")
            print(f"[STEP 1: TICKER RESOLUTION] Attempting heuristic extraction from search results...")
            # Heuristic: Find things in parentheses or after a colon like (NASDAQ: AAPL)
            match = re.search(r'\(?([A-Z]+):\s*([A-Z]+)\)?', combined)
            if match:
                ticker_clean = match.group(2)
            else:
                # Backup: just find any 1-5 letter uppercase word that isn't a common word
                tokens = re.findall(r'\b[A-Z]{1,5}\b', combined)
                ticker_clean = tokens[0] if tokens else None

        if ticker_clean:
            ticker_clean = re.sub(r'[^A-Z0-9.\-]', '', ticker_clean)

        if not ticker_clean:
            # Final hardcoded failsafes for common stocks if search fails
            failsafes = {"APPLE": "AAPL", "MICROSOFT": "MSFT", "NVIDIA": "NVDA", "TESLA": "TSLA", "GOOGLE": "GOOGL", "AMAZON": "AMZN"}
            ticker_clean = failsafes.get(raw)

        if not ticker_clean:
            print(f"[STEP 1: TICKER RESOLUTION] FAILED -- Could not resolve ticker")
            return None

        # -- Validate the resolved ticker via yfinance --
        print(f"[STEP 1: TICKER RESOLUTION] Candidate: {ticker_clean}. Validating via yFinance...")
        try:
            if _is_valid_symbol(ticker_clean):
                print(f"[STEP 1: TICKER RESOLUTION] Resolved -> {ticker_clean}")
                return ticker_clean
            else:
                # One last try: append .NS if not present, then try again (for Indian stocks)
                if "." not in ticker_clean:
                    ticker_ns = f"{ticker_clean}.NS"
                    if _is_valid_symbol(ticker_ns):
                        return ticker_ns
                    ticker_bo = f"{ticker_clean}.BO"
                    if _is_valid_symbol(ticker_bo):
                        return ticker_bo
                return None
        except Exception:
            return None

    except Exception as e:
        print(f"[STEP 1: TICKER RESOLUTION] FAILED -- Exception: {e}")
        return None


import streamlit as st
@st.cache_data(ttl=3600, show_spinner=False)
def get_insights(context: str, ticker: str, feedback: str = None) -> dict:
    """
    Generates institutional-grade financial insights using the Glass-Box
    system prompt via Gemini. Forces strict numerical compliance with raw data.
    """
    print(f"\n[STEP 3: DRAFT GENERATION] Sending context to local LLM ({_primary_model_name()})...")
    start = time.time()

    # Move from JSON constraint to Tag-Based Freedom
    system_instruction = """### SYSTEM ROLE
You are a High-Precision Financial Research Agent. Your goal is to transform raw data into a professional, zero-hallucination equity report. Use a "Glass-Box" policy: every step of your reasoning must be visible.

### THE COMPLIANCE PROTOCOL
First, you MUST complete the audit trace inside <audit_trace> tags.
Then, you MUST provide the structured report inside <report_json> tags.

<audit_trace>
1. TICKER VERIFICATION: (e.g. RELIANCE.NS)
2. RAW DATA EXTRACTION: List key metrics (Revenue, P/E, D/E, Margin).
3. SOURCE CROSS-CHECK: Identify any conflicting data.
4. HALLUCINATION CHECK: State if any requested data is MISSING.
</audit_trace>

### REPORT CONSTRAINTS
- NO EXTERNAL KNOWLEDGE.
- VERIFIED BADGE CRITERIA: Sections must match yFinance exactly.
- PEER BENCHMARKING: Primary (Industry list) + Secondary (Disruptor from news)."""

    user_prompt = f"""Generate a high-precision research report for {ticker} using ONLY the following context.

STRUCTURE:
1. <audit_trace> (Internal Diagnostic reasoning)
2. <report_json> (JSON report following schema below)

SCHEMA FOR <report_json>:
{{
  "executive_summary": "3 sentences max.",
  "financial_health_matrix": {{
    "revenue": {{"val": "$X.XB", "status": "Verified"}},
    "margins": {{"val": "XX%", "status": "Verified"}},
    "solvency": {{"val": "X.XXx", "status": "Verified"}},
    "efficiency": {{"val": "XX%", "status": "Verified"}}
  }},
  "competitive_landscape": [
    {{"company": "...", "relationship": "...", "metric_compare": "..."}}
  ],
  "signal": "BUY|HOLD|SELL"
}}

CONTEXT:
{context}"""

    if feedback:
        user_prompt += f"\n\nCRITIQUE FEEDBACK (Fix these errors): {feedback}"

    # Use streaming for live UI feedback
    full_response = ""
    # Note: st.cache_data and generators don't play well together. 
    # For SOTA "Vibe", we will handle streaming in app.py directly.
    # This function will act as the "Legacy/Fallback" full-text fetcher.
    
    try:
        response = _call_ollama(
            contents=user_prompt,
            config={
                "system_instruction": system_instruction,
                "temperature": 0.15,
                "num_predict": 1200
            },
        )
        full_response = response.text.strip()
        
        # Robust Parse
        trace = robust_tag_parser(full_response, "audit_trace")
        report_str = robust_tag_parser(full_response, "report_json")
        result = _safe_json_loads(report_str)
        
        # Attach the trace for the UI
        result["audit_trail"] = trace if trace else "Audit trace extraction failed."
        result["executive_summary"] = result.get("executive_summary", "Summary not generated.")
        
        if "signal" not in result: result["signal"] = "HOLD"
        
        return result
    except Exception as e:
        print(f"[STEP 3: DRAFT GENERATION] ERROR: {e}")
        return {"error": str(e)}
    except Exception as e:
        print(f"[STEP 3: DRAFT GENERATION] ERROR: {e}")
        return {"error": str(e)}


@st.cache_data(ttl=3600, show_spinner=False)
def run_fact_check_agent(draft_report: str, raw_data_context: str) -> dict:
    """
    Glass-Box fact-checker: extracts every numerical claim from the draft
    and cross-references against the raw JSON payload. Returns FAIL with
    specific discrepancies if any number deviates from source data.
    """
    print(f"\n[STEP 4: FACT-CHECK AUDIT] Running critique agent via local LLM...")
    start = time.time()

    system_instruction = "You are a strict Financial Compliance Officer. Analyze and return ONLY valid JSON."

    prompt = f"""AUDIT PROTOCOL:
1. Verify EVERY numerical claim ($ figures, %, ratios) in the Draft against the Raw Data.
2. If any value deviates by >1%, return FAIL.
3. Check for specific metrics: Revenue, Profit, D/E, ROE, Margins.

Return ONLY:
{{"status": "PASS", "feedback": "All claims verified."}}
OR:
{{"status": "FAIL", "feedback": "[Briefly explain discrepancy]"}}

RAW DATA: {raw_data_context}
DRAFT REPORT: {draft_report}"""

    try:
        response = _call_ollama(
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "response_mime_type": "application/json",
                "temperature": 0.05,
                "num_predict": 150, # Keep it tight
            },
        )

        raw = response.text.strip()
        result = _safe_json_loads(raw)
        elapsed = time.time() - start
        status = result.get("status", "UNKNOWN")
        print(f"[STEP 4: FACT-CHECK AUDIT] Result: {status} ({elapsed:.1f}s)")
        if status == "FAIL":
            print(f"[STEP 4: FACT-CHECK AUDIT] Feedback: {result.get('feedback', 'N/A')}")
        return result
    except Exception as e:
        print(f"[STEP 4: FACT-CHECK AUDIT] ERROR: {e}")
        return {"status": "FAIL", "feedback": f"Critique engine error: {str(e)}"}


def get_judge_scores(insights_json: str, raw_context: str = "") -> dict:
    """Grades AI-generated insights against raw source data for accuracy."""
    print(f"\n[STEP 5: FINAL OUTPUT] Scoring via local LLM (LLM-as-Judge)...")
    start = time.time()

    system_instruction = "You are a Senior Compliance Auditor at a financial regulator. You must output ONLY valid JSON."

    prompt = f"""Grade the following AI-generated research note on a scale of 1 to 5 across four dimensions.

GRADING CRITERIA (1-5 scale):
- Accuracy (1-5): Do the numbers in the report EXACTLY match the raw data? Any fabricated number = score of 1.
- Completeness (1-5): Does the report cover revenue, profit, D/E ratio, ROE, margins, and 52-week context? Missing more than 2 = score below 3.
- Clarity (1-5): Is the language specific and decisive? Hedging language ("may", "might") = score below 3.
- Confidence (1-5): Overall quality. Would this pass institutional compliance review?

You MUST output ONLY valid JSON:
{{"accuracy": 4, "completeness": 5, "clarity": 4, "confidence": 4}}

RAW SOURCE DATA:
{raw_context}

REPORT TO GRADE:
{insights_json}"""

    try:
        response = _call_ollama(
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "response_mime_type": "application/json",
                "temperature": 0.0,
                "num_predict": 220,
            },
        )

        raw = response.text.strip()
        scores = _safe_json_loads(raw)
        elapsed = time.time() - start

        # Clamp all scores to 1-5 range
        for key in ["accuracy", "completeness", "clarity", "confidence"]:
            val = scores.get(key, 0)
            if isinstance(val, (int, float)):
                if val > 5:
                    scores[key] = min(5, round(val / 20))  # Handle 0-100 scale
                scores[key] = max(1, min(5, scores[key]))
            else:
                scores[key] = 1

        print(f"[STEP 5: FINAL OUTPUT] Scores -- Acc:{scores.get('accuracy')}/5  Comp:{scores.get('completeness')}/5  Clar:{scores.get('clarity')}/5  Conf:{scores.get('confidence')}/5  ({elapsed:.1f}s)")
        return scores
    except Exception as e:
        print(f"[STEP 5: FINAL OUTPUT] ERROR: {e}")
        return {"error": str(e), "accuracy": 1, "completeness": 1, "clarity": 1, "confidence": 1}


# =====================================================================
#  ACTION INSIGHT ENGINE -- Premium Terminal Reports via local LLM
# =====================================================================

# Black Pill HTML sub-header template injected into all prompts
BLACK_PILL_HEADER_INSTRUCTION = """
CRITICAL FORMATTING RULE:
- All sub-headings MUST use: <span style="background-color: black; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; display: inline-block; margin-bottom: 10px;">Header Text Here</span>
- Bold key metrics: <b>$1.2 Billion</b>.
- Use standard Markdown for bullet points and tables.
- Wrap your ENTIRE response in a <div> with Inter font.
- NO triple backticks (```html) in the response.
"""

ACTION_GLASSBOX_GUARDRAILS = """
GLASS-BOX CONSTRAINTS (ZERO-FALSE-DATA POLICY):
- You MUST treat the provided CONTEXT as the ONLY source of truth.
- Do NOT use outside knowledge. Do NOT guess. Do NOT infer numbers.
- If a fact (number, date, quote, competitor ticker, partner name) is not explicitly present in CONTEXT, write: "Not available in provided data."
- For any numeric claim, the exact number MUST appear verbatim in CONTEXT.
- Prefer short, high-signal answers. Avoid long narratives.
"""

def _extract_context_blocks(context_data: str) -> dict:
    """
    Best-effort extraction of JSON blocks and news lines from build_context_for_llm().
    Returns dict with keys: metrics (dict), fmp (dict), news_lines (list[str]).
    """
    out = {"metrics": {}, "fmp": {}, "news_lines": []}
    if not isinstance(context_data, str) or not context_data.strip():
        return out

    def _slice_between(s: str, start: str, end: str) -> str:
        i = s.find(start)
        if i == -1:
            return ""
        i2 = s.find(end, i + len(start)) if end else -1
        if i2 == -1:
            return s[i + len(start):]
        return s[i + len(start):i2]

    metrics_raw = _slice_between(context_data, "=== FINANCIAL METRICS", "=== ACCOUNTING")
    fmp_raw = _slice_between(context_data, "=== ACCOUNTING & SOLVENCY (FMP) ===", "=== TREND DATA")
    news_raw = _slice_between(context_data, "=== RECENT NEWS HEADLINES ===", "")

    # Extract JSON dicts (they were dumped with json.dumps(indent=2))
    for key, blob in [("metrics", metrics_raw), ("fmp", fmp_raw)]:
        blob = blob.strip()
        if not blob:
            continue
        # Find first '{' and last '}' to be resilient
        a = blob.find("{")
        b = blob.rfind("}")
        if a != -1 and b != -1 and b > a:
            try:
                out[key] = json.loads(blob[a:b+1])
            except Exception:
                out[key] = {}

    # News lines are "- title: content"
    lines = [ln.strip() for ln in news_raw.splitlines() if ln.strip().startswith("- ")]
    out["news_lines"] = lines[:6]
    return out

def get_action_insight_fast(action_name: str, ticker: str, context_data: str) -> str:
    """
    Instant, deterministic, zero-hallucination action snapshot.
    Uses ONLY the provided context_data (no LLM calls).
    """
    blocks = _extract_context_blocks(context_data)
    metrics = blocks.get("metrics") or {}
    news_lines = blocks.get("news_lines") or []

    perf = (metrics.get("_performance") or {}) if isinstance(metrics, dict) else {}
    past_week = perf.get("1 Month", "-")  # best available proxy from existing metrics
    past_month = perf.get("1 Month", "-")
    ytd = perf.get("This Year", "-")

    def pill(title: str) -> str:
        return f'<span style="background-color: black; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; display: inline-block; margin-bottom: 10px;">{title} 🚀</span>'

    # Build per-action minimal content (only what we can verify from context)
    body = []

    if "What's happening" in action_name:
        body.append(pill("📰 Recent News (from your data)"))
        if news_lines:
            items = "".join([f"<li style='margin:6px 0;'>{ln[2:]}</li>" for ln in news_lines])
            body.append(f"<ul style='margin:0 0 10px 18px; padding:0;'>{items}</ul>")
        else:
            body.append("<div>Not available in provided data.</div>")

        body.append(pill("📊 Performance Snapshot"))
        body.append(
            """
            <div class="stMarkdown">
            <table>
              <thead><tr><th>Period</th><th>Performance</th><th>Note</th></tr></thead>
              <tbody>
                <tr><td>Past Week</td><td>-</td><td>Not available in provided data.</td></tr>
                <tr><td>Past Month</td><td>{pm}</td><td>From provided performance metrics.</td></tr>
                <tr><td>Year-to-Date</td><td>{ytd}</td><td>From provided performance metrics.</td></tr>
              </tbody>
            </table>
            </div>
            """.format(pm=past_month, ytd=ytd)
        )

    elif "Business explained" in action_name:
        body.append(pill("🏢 Business explained (from your data)"))
        about = metrics.get("_longBusinessSummary") if isinstance(metrics, dict) else None
        body.append(f"<div>{about if about else 'Not available in provided data.'}</div>")

    else:
        body.append(pill("⚡ Quick Snapshot"))
        body.append("<div>This action needs more context. Click <b>Generate detailed report</b> for the full analysis.</div>")

    html = (
        '<div style="font-family: Inter, sans-serif; color: inherit; font-size: 0.98rem; line-height: 1.75;">'
        f"<div style='margin-bottom:10px; color: #475569; font-weight:700;'>Verified snapshot for <b>{ticker}</b>. No AI guesses.</div>"
        + "".join(body)
        + "</div>"
    )
    return html

def _audit_action_report(report_html: str, context_data: str) -> dict:
    """
    Audits an action report for unsupported claims vs the provided context.
    Returns JSON dict: {status: PASS|FAIL, feedback: str}
    """
    system_instruction = "You are a strict financial compliance auditor. Output ONLY valid JSON."
    prompt = f"""Audit the REPORT against the CONTEXT with a zero-false-data policy.

Rules:
1) Any number (%, $, ratios) must appear EXACTLY in CONTEXT. If not, FAIL.
2) Any factual claim about real-world events, partnerships, earnings, competitors, suppliers, clients must be supported by CONTEXT. If not, FAIL.
3) Subjective assessments and opinions are allowed (e.g., "risk looks moderate", "moat appears strong") IF they do NOT introduce new facts.
4) If REPORT uses vague external assertions (e.g., 'recently announced', 'reported by', 'according to') without explicit support in CONTEXT, FAIL.

Return ONLY JSON in one of these forms:
{{"status":"PASS","feedback":"OK"}}
{{"status":"FAIL","feedback":"List the exact unsupported claims and what to replace them with. Keep it short."}}

CONTEXT:
{context_data}

REPORT:
{report_html}"""
    try:
        res = _call_ollama(
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "response_mime_type": "application/json",
                "temperature": 0.0,
                "num_predict": 260,
            },
        )
        return _safe_json_loads(res.text.strip())
    except Exception as e:
        return {"status": "FAIL", "feedback": f"Audit engine error: {str(e)}"}

def _build_action_prompt(action_name: str, ticker: str, context_data: str) -> tuple:
    """Builds action-specific system instruction and user prompt for local LLM."""

    base_system = f"""You are a senior financial analyst at a premium research terminal called "{BRAND_NAME}".
You produce beautifully formatted, data-rich reports using HTML and Markdown.
{BLACK_PILL_HEADER_INSTRUCTION}
{ACTION_GLASSBOX_GUARDRAILS}
"""

    if "What's happening" in action_name:
        system = base_system + """
You specialize in summarizing recent market events, news catalysts, and price action.
Structure your output as:
1. A brief opening paragraph summarizing the current situation (2-3 sentences).
2. A "Black Pill" sub-header for "📰 Recent News & Catalysts" followed by bullet points of key events.
3. A "Black Pill" sub-header for "📊 Performance Snapshot" followed by a Markdown table with columns: Period | Performance | Trend. Include rows for "Past Week", "Past Month", and "Year-to-Date".
4. A "Black Pill" sub-header for "🔮 What to Watch" with 2-3 bullet points on upcoming events.
"""
        prompt = f"""Analyze what's currently happening with {ticker} based on the context data below.
Focus on recent news, price movements, and market sentiment.

CONTEXT DATA:
{context_data}"""

    elif "Business explained" in action_name:
        system = base_system + """
You specialize in explaining complex businesses to beginners in simple, engaging language.
Structure your output as:
1. A brief 2-sentence overview of what the company does in plain English.
2. For each of 2-3 core business segments, use a "Black Pill" sub-header with the segment name and a relevant emoji (e.g., "💻 Data Center & AI"). Follow each with a short paragraph explaining what this segment does and why it matters.
3. A "Black Pill" sub-header for "💰 How They Make Money" with a simple bullet-point breakdown of revenue streams.
4. A "Black Pill" sub-header for "🌟 Why It Matters" with 2-3 bullet points on competitive advantages.
"""
        prompt = f"""Explain the business model of {ticker} to a beginner investor.
Use the company's business summary and financial data provided below.
Make it simple, engaging, and easy to understand.

CONTEXT DATA:
{context_data}"""

    elif "Competitors" in action_name:
        system = base_system + """
You specialize in competitive landscape analysis.
Structure your output as:
1. A brief opening paragraph about the competitive dynamics of the sector (2-3 sentences).
2. For each of 2-3 main competitors, use a "Black Pill" sub-header formatted as: "CompanyName (TICKER) 🏢" (e.g., "Advanced Micro Devices (AMD) 🏢"). Follow each with a paragraph explaining the rivalry — what they compete on, relative strengths, and market position differences.
3. A "Black Pill" sub-header for "⚔️ Competitive Moat" with bullet points describing the analyzed company's defensive advantages.
4. A Markdown table comparing the main company vs its competitors on 3-4 key metrics (e.g., Market Cap, Revenue, Growth Rate, Market Share).
"""
        prompt = f"""Identify and analyze the 2-3 main competitors of {ticker}.
Explain the competitive dynamics, rivalry, and relative positioning.

CONTEXT DATA:
{context_data}"""

    elif "Suppliers" in action_name or "Clients" in action_name:
        system = base_system + """
You specialize in supply chain and value chain analysis.
Structure your output as:
1. A brief opening paragraph about the company's position in the supply chain (2-3 sentences).
2. A "Black Pill" sub-header for "🔧 Key Suppliers" — For each major supplier, use a nested "Black Pill" sub-header with the supplier name and emoji. Follow with bullet points explaining the relationship and dependency level.
3. A "Black Pill" sub-header for "🤝 Major Clients & Partners" — For each key client/partner, use a nested "Black Pill" sub-header. Follow with bullet points explaining the business relationship.
4. A "Black Pill" sub-header for "⚠️ Supply Chain Risks" with bullet points on concentration risks and vulnerabilities.
"""
        prompt = f"""Analyze the supply chain of {ticker}. Identify key suppliers and major clients/partners.
Explain the business relationships and dependencies.

CONTEXT DATA:
{context_data}"""

    elif "Future" in action_name or "Expectations" in action_name:
        system = base_system + """
You specialize in forward-looking analysis and earnings expectations.
Structure your output as:
1. A "Black Pill" sub-header for "📈 Analyst Consensus" with a summary of market expectations.
2. A "Black Pill" sub-header for "🚀 Growth Catalysts" with numbered bullet points of upcoming growth drivers.
3. A "Black Pill" sub-header for "⚡ Risk Factors" with bullet points of potential headwinds.
4. A "Black Pill" sub-header for "🎯 Price Targets" — present analyst price targets in a simple Markdown table if available from context, otherwise provide a qualitative outlook.
"""
        prompt = f"""Analyze the future expectations and outlook for {ticker}.
Focus on growth catalysts, risk factors, and market consensus.

CONTEXT DATA:
{context_data}"""

    elif "Full Analysis" in action_name:
        system = base_system + """
You produce comprehensive, institutional-grade equity research reports.
Structure your output as:
1. A "Black Pill" sub-header for "📋 Executive Summary" with a 3-sentence thesis.
2. A "Black Pill" sub-header for "💹 Financial Health" with key metrics in a Markdown table (Revenue, Profit, D/E, ROE, Margins).
3. A "Black Pill" sub-header for "📊 Valuation Analysis" with discussion of current valuation vs historical and sector peers.
4. A "Black Pill" sub-header for "🔍 Technical Outlook" with price trend analysis.
5. A "Black Pill" sub-header for "⚖️ Bull vs Bear Case" with two columns of argument (use bullet points).
6. A "Black Pill" sub-header for "🎯 Verdict" with a final assessment.
"""
        prompt = f"""Produce a comprehensive full analysis report for {ticker}.
Cover all fundamental, technical, and qualitative dimensions.

CONTEXT DATA:
{context_data}"""

    elif "Scorecard" in action_name:
        system = base_system + """
You produce qualitative scorecards that grade companies across multiple dimensions.
Structure your output as:
1. A "Black Pill" sub-header for "📊 Qualitative Scorecard" with a Markdown table. Columns: Dimension | Score (1-10) | Assessment. Rows for: Management Quality, Competitive Position, Growth Trajectory, Financial Discipline, Innovation Pipeline, ESG & Governance.
2. A "Black Pill" sub-header for "🏆 Strengths" with bullet points.
3. A "Black Pill" sub-header for "⚠️ Areas of Concern" with bullet points.
4. A "Black Pill" sub-header for "📝 Overall Grade" with a letter grade (A+ to F) and justification.
"""
        prompt = f"""Create a qualitative scorecard for {ticker} grading the company across multiple dimensions.
Be data-driven and reference specific metrics where possible.

CONTEXT DATA:
{context_data}"""

    elif "Sentiment" in action_name:
        system = base_system + """
You specialize in investor sentiment analysis and market psychology.
Structure your output as:
1. A "Black Pill" sub-header for "🌡️ Sentiment Overview" with an overall sentiment gauge (Bullish/Neutral/Bearish) and justification.
2. A "Black Pill" sub-header for "📱 Social & Media Sentiment" analyzing the tone of recent news from the context.
3. A "Black Pill" sub-header for "🏛️ Institutional Activity" discussing any institutional signals from the data.
4. A "Black Pill" sub-header for "📊 Sentiment Indicators" with a Markdown table of sentiment metrics.
5. A "Black Pill" sub-header for "💡 Contrarian View" presenting a counter-argument to the prevailing sentiment.
"""
        prompt = f"""Analyze the current investor sentiment around {ticker}.
Cover social sentiment, institutional signals, and market psychology.

CONTEXT DATA:
{context_data}"""

    else:
        # Generic fallback
        system = base_system
        prompt = f"""Provide a detailed analysis on "{action_name}" for {ticker}.

CONTEXT DATA:
{context_data}"""

    return system, prompt


def get_action_insight(action_name: str, ticker: str, context_data: str) -> str:
    """
    Generates a premium, HTML-formatted financial report for a specific action.
    Uses Gemini with strict formatting instructions for Black Pill styled output.
    Returns rendered HTML/Markdown string ready for st.markdown().
    """
    print(f"\n[ACTION INSIGHT] Generating '{action_name}' report for {ticker}...")
    start = time.time()

    system_instruction, user_prompt = _build_action_prompt(action_name, ticker, context_data)
    # Keep prompts small for fast generation (context is already dense JSON).
    if isinstance(user_prompt, str) and len(user_prompt) > 8000:
        user_prompt = user_prompt[:8000] + "\n\n[Context truncated for speed]"

    try:
        last_feedback = None
        for attempt in range(1, 2):  # strict+fast: generate then audit; at most 1 regeneration
            tuned_prompt = user_prompt
            if last_feedback:
                tuned_prompt = (
                    tuned_prompt
                    + "\n\nCRITIQUE FAILED — you MUST fix these issues by removing unsupported claims and replacing them with 'Not available in provided data.':\n"
                    + last_feedback
                )

            response = _call_ollama(
                contents=tuned_prompt,
                config={
                    "system_instruction": system_instruction,
                    "temperature": 0.15,
                    "num_predict": 280,
                    "top_p": 0.9,
                    "top_k": 40,
                },
            )

            result = response.text.strip()
            
            # Strip markdown code blocks if the LLM habitually wraps its response
            if result.startswith("```"):
                result = result.split("\n", 1)[-1]
            if result.endswith("```"):
                result = result.rsplit("\n", 1)[0]
            result = result.strip()
            if result.lower().startswith("html"):
                result = result[4:].strip()

            # Wrap in container div if the model didn't do it
            if not result.startswith("<div"):
                result = f'<div style="font-family: Inter, sans-serif; color: inherit; font-size: 0.98rem; line-height: 1.75;">{result}</div>'

            audit = _audit_action_report(result, context_data)
            if audit.get("status") == "PASS":
                elapsed = time.time() - start
                print(f"[ACTION INSIGHT] '{action_name}' verified PASS in {elapsed:.1f}s (attempt {attempt})")
                return result + (
                    '<div style="margin-top:14px; padding-top:12px; border-top:1px solid rgba(148,163,184,0.18);">'
                    '<span style="background-color: black; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; display: inline-block; margin-bottom: 10px;">✅ Verified Facts 🚀</span>'
                    '<div style="color: rgba(226,232,240,0.9);">All factual claims are constrained to the provided context.</div>'
                    "</div>"
                )

            last_feedback = audit.get("feedback", "Unsupported claims detected.")

        # If still failing, return a safe, minimal report
        elapsed = time.time() - start
        print(f"[ACTION INSIGHT] '{action_name}' verification FAIL after retries ({elapsed:.1f}s)")
        safe_warning = (
            '<div style="margin-top:20px; padding:14px; background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.3); border-radius:8px;">'
            '<span style="background-color: #F59E0B; color: black; padding: 4px 10px; border-radius: 6px; font-weight: bold; display: inline-block; margin-bottom: 8px;">⚠️ Unverified Claims Detected</span>'
            "<div style='color: #E2E8F0; font-size: 0.9rem;'>The evaluator agent flagged some facts in the above analysis as missing from the primary data context. Read with caution!</div>"
            "</div>"
        )
        return result + safe_warning

    except Exception as e:
        print(f"[ACTION INSIGHT] ERROR: {e}")
        return f'<div style="font-family: Inter, sans-serif; color: inherit; padding: 20px;"><div style="background: rgba(239, 68, 68, 0.10); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 8px; padding: 16px;"><span style="background-color: #EF4444; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; display: inline-block; margin-bottom: 10px;">⚠️ Generation Error</span><p style="color: #FCA5A5; margin: 8px 0 0 0;">The report engine encountered an error while generating this report. Please try again.</p><p style="color: #FECACA; font-size: 0.8rem; margin: 8px 0 0 0;"><code>{str(e)}</code></p></div></div>'
