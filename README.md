# AI Financial Insights

A beginner-friendly Streamlit financial dashboard that behaves like an on-demand **equity research analyst** while enforcing a **glass-box / zero-false-data** policy.

It supports:
- Search by **company name** (not just valid tickers) with robust symbol resolution
- A full analysis dashboard (charts + performance + verified report)
- An **Action Intelligence** modal system with **instant “Quick Snapshot”** and optional detailed, verified reports

---

## Product idea (what this is)

**Replace the first 30–60 minutes of manual “what’s going on?” research** a retail investor does after typing a company name:
- Resolve company name → tradable symbol
- Pull market + fundamentals context
- Produce a clear **BUY / HOLD / SELL** verdict with reasons
- Provide action-specific deep dives (news, competitors, suppliers/clients, scorecards, sentiment)
- Ensure outputs are **constrained to the data context** (no invented facts)

---

## Pages & UX flow (no navigation redesign)

The app is intentionally a simple 3-step flow:

1. **Hero**
   - Landing content + CTA buttons
2. **Search**
   - Minimal search entry
3. **Analysis**
   - Data pipeline status panel
   - Dashboard header + company strip
   - Charts + performance blocks
   - Verified report panel + live news stream
   - Action grid buttons → modal reports

---

## Architecture (Glass-Box workflow)

### 1) Symbol resolution (company name → ticker)

Implemented in `utils/ai_agent.py:resolve_ticker()`:
- First tries **yfinance Search** (works without API keys)
- Validates candidates using reliable checks:
  - `history(period="5d")` and/or `fast_info` (instead of `.info`, which can 404)
- Adds **India exchange fallbacks**: tries `.NS` and `.BO` where appropriate
- Optional Tavily + local LLM extraction fallback (if configured)

### 2) Data extraction

Implemented in `utils/data_agent.py`:
- `fetch_financial_metrics()` (company strip + performance blocks + chart series + dividends + annual returns)
  - Hardened against yFinance quirks (index types, dividend resample types)
  - Corrected yFinance periods (e.g., `6mo` instead of invalid `6m`)
- `fetch_trend_data()` (financial trend or fallback price action)
- `fetch_fmp()` (solvency and accounting ratios)
- `fetch_news()` (Tavily news context; shows a helpful message if missing)
- `build_context_for_llm()` produces a single dense CONTEXT string used by the report engines

### 3) Verified “main report” generation

Implemented in `utils/ai_agent.py`:
- `get_insights()` generates a JSON report using a **local Ollama model**
- `run_fact_check_agent()` critiques the draft against raw context (numerical + compliance checks)
- If critique fails, the report is re-generated with feedback (glass-box correction loop)

In the UI (`components/ui_blocks.py`):
- The main report panel shows a **Verified** badge when the critique passes

### 4) Action Intelligence modal reports (Action Grid)

Implemented in:
- `app.py`: native Streamlit `@st.dialog` modal + Action Grid button wiring
- `utils/ai_agent.py:get_action_insight()` and prompt builder

Key behavior:
- **Instant default response**: a deterministic **Quick Snapshot** (no LLM call) using only the provided context
- Optional **Detailed Report** button runs the local LLM and applies:
  - strict formatting rules (“Black Pill” sub-headers)
  - glass-box guardrails (no claims outside context)
  - an audit loop that refuses to output unverified facts

---

## AI/Agent behavior & safety

### “Zero-false-data” policy

The system is designed to **refuse** unsupported claims:
- If a fact is not in CONTEXT, it must say: **“Not available in provided data.”**
- Numeric claims must match the CONTEXT exactly
- Action reports are audited against CONTEXT and will regenerate (limited retries). If still failing, they output a safe limited report.

### Beginner-friendly language

The main report prompt is tuned to:
- short sentences
- minimal jargon
- explain what a metric means (“good/bad/neutral” implication)

---

## UI upgrades implemented (polish, not redesign)

All changes were incremental: **no layout removal**, no navigation changes.

### Styling & consistency
- Tokenized CSS variables for consistent spacing/colors
- Softer light theme for the main app (background `#F8FAFC`, white cards, subtle borders)
- Card polish: shadow + hover lift
- Button system: primary (gradient + glow) vs secondary (white + border) using Streamlit’s button `type`

### Charts (Plotly)
In `components/ui_blocks.py` chart rendering:
- smooth spline lines, slightly thicker strokes
- gradient fills
- lighter gridlines and clean white template
- improved unified hover tooltip styling

### Confidence ring
In `components/ui_blocks.py:render_sidebar_confidence()`:
- animated circular ring (0 → value)
- gradient stroke (green → blue) + subtle glow

### “Hero Insight” block (analysis page)
Added at top of the analysis page (without removing any sections):
- Signal + Confidence %
- 2–3 beginner-friendly reasons
- PASS/FAIL verified mode indicator

### News stream readability
News cards now include:
- headline emphasis
- spacing and card styling
- **Key takeaway** 1-liner for quick scanning

### Modal visibility fix (dark overlay)
Modal uses a high-contrast dark theme:
- background gradient `#020617 → #0F172A`
- white primary text and readable secondary text
- improved badge and warning styles
- buttons pop with clear primary/secondary distinction

---

## Tech stack

- **Frontend/App**: Streamlit
- **Charts**: Plotly
- **Market data**: yFinance
- **Web search/news context**: Tavily (optional but recommended)
- **Local LLM**: Ollama (`ollama` Python client)
- **Env management**: `python-dotenv`

---

## Requirements

- Python 3.10+ recommended (works on Windows)
- Ollama installed + running
- At least one local model pulled (e.g., `llama3.1:latest` or `gemma3:4b`)

Check installed models:

```bash
ollama list
```

---

## Setup & run (Windows / PowerShell)

From the project root:

```powershell
cd "D:\Agentic_AI_Project"
.\.venv\Scripts\Activate.ps1
python -m streamlit run app.py
```

Streamlit will print a local URL (e.g., `http://localhost:85xx`).

---

## Configuration

### Tavily (optional)

Create a `.env` in the project root:

```text
TAVILY_API_KEY=your_key_here
```

If missing, the app still runs, but news and some resolution fallbacks will be limited.

### Ollama model selection

The app auto-detects installed Ollama models and will only try those.

You can override the model try order:

```powershell
$env:OLLAMA_MODELS="gemma3:4b,llama3.1:latest"
python -m streamlit run app.py
```

---

## Troubleshooting

### “Resolution Failed” / yFinance 404 spam
- yFinance `.info` can 404 even for valid symbols; this project validates via **history/fast_info**.
- If a company isn’t listed on Yahoo Finance, it cannot be resolved.

### Action modal takes long
- Use **Quick Snapshot** (instant, no LLM).
- Detailed report uses Ollama + verification; model speed depends on your hardware and model choice.
- Prefer smaller models (e.g., `gemma3:4b`) for faster detailed responses.

### Emojis causing Unicode errors (Windows)
- The app forces UTF-8 console output to avoid crashes on emoji button labels.

---

## Key files

- `app.py`: Streamlit pages, global CSS, analysis workflow, action modal wiring
- `components/ui_blocks.py`: modular UI renderers (sidebar, charts, report panel, news)
- `utils/data_agent.py`: yFinance + Tavily data fetch + context builder
- `utils/ai_agent.py`: Ollama calls, symbol resolution, report generation + critique/audit loops

