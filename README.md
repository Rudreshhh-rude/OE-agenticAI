# Finsighter: Institutional-Grade Agentic Terminal

A professional-grade financial intelligence dashboard that behaves like an on-demand **equity research analyst** while enforcing a **glass-box / zero-hallucination** policy.

---

## 🏗️ Architecture (Glass-Box workflow)

```mermaid
graph TD
    A[User UI - Streamlit] -->|Input: Stock Ticker| B(Agent Controller)
    
    subgraph "Phase 1: Intelligence Gathering"
        B --> C{Ticker Resolver}
        C -->|Success| D[yFinance API]
        C -->|Deep Search| E[Tavily Search API]
        D --> F[Raw Financial Data Context]
        E --> F
    end

    subgraph "Phase 2: Reasoning & Synthesis"
        F --> G[Synthesis Agent - Mixtral]
        G -->|Output| H[<audit_trace> Reasoning Chain]
        G -->|Output| I[<report_json> Draft Report]
    end

    subgraph "Phase 3: The Audit Gate"
        F -.-> J[Fact-Check Auditor - Mixtral]
        I -.-> J
        J -->|Validation| K{Verified Mode}
        K -->|PASS| L[Judge Agent - Mixtral]
        K -->|FAIL| L
    end

    subgraph "Phase 4: Scoring & Render"
        L --> M[4D Confidence Score]
        M --> N[Secure Terminal UI]
        I --> N
        H --> N
    end

    style K fill:#10B981,stroke:#fff,stroke-width:2px;
    style G fill:#5CA5F1,stroke:#fff,stroke-width:1px;
    style J fill:#EF4444,stroke:#fff,stroke-width:1px;
    style L fill:#F59E0B,stroke:#fff,stroke-width:1px;
```

---

## 🚀 Key Features

- **Symbol Resolution**: Resolve company names to tickers using yFinance + Tavily fallbacks.
- **Agentic Synthesis**: Live "Chain-of-Thought" reasoning visible via the Glass-Box feed.
- **Numerical Audit**: Fact-checking agent cross-references every AI claim against raw data.
- **Institutional Judge**: 4D scoring rubric (Accuracy, Completeness, Clarity, Confidence).
- **High-Aesthetic UI**: Premium dark-mode terminal inspired by institutional trading platforms.

---

## 🛠️ Tech Stack

- **Core**: Python 3.11+, Streamlit
- **Intelligence**: Groq LPU (Mixtral 8x7B)
- **Search API**: Tavily AI
- **Financial Data**: yFinance
- **Database**: Supabase (User Auth)
- **Deployment**: Streamlit Cloud / Railway

---

## 🗝️ Setup & Configuration

Create a `.env` file in the root directory:

```toml
GROQ_API_KEY = "your_key"
TAVILY_API_KEY = "your_key"
SUPABASE_URL = "your_url"
SUPABASE_KEY = "your_key"
FMP_API_KEY = "your_key"
```

Run the terminal:
```bash
streamlit run app.py
```

---

## 📊 Evaluation Rubrics Compliance
- **Problem Statement**: Clarity on verifiable financial AI.
- **Task Decomposition**: Multi-stage agentic pipeline.
- **LLM-as-Judge**: Verified 4-tier scoring integration.
- **Deployment**: Live on Streamlit Cloud.


