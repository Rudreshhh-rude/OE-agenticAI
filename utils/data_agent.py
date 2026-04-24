import yfinance as yf
from tavily import TavilyClient
import streamlit as st
import os
import json
import pandas as pd
import requests
import traceback

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_financial_metrics(ticker: str):
    """Fetches high-level metrics required for the top dashboard row and company strip."""
    print(f"[DEBUG] Fetching metrics for: {ticker}")
    
    def _scalar(x, default=0.0):
        if x is None: return default
        if isinstance(x, (list, tuple)): return _scalar(x[0], default=default) if x else default
        try: return float(x)
        except: return default

    def _resilient_history(stock, periods):
        for p in periods:
            try:
                h = stock.history(period=p)
                if not h.empty: return h
            except: continue
        return pd.DataFrame()

    def format_financial_number(num):
        if not num: return "N/A"
        try: val = float(num)
        except: return str(num)
        if abs(val) >= 1e12: return f"${val/1e12:.2f} Trillion"
        if abs(val) >= 1e9: return f"${val/1e9:.2f} Billion"
        if abs(val) >= 1e6: return f"${val/1e6:.2f} Million"
        return f"${val:,.2f}"

    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info: info = {}

        long_name = info.get("longName", ticker.upper())
        sector = info.get("sector", "N/A Sector")
        market_cap = _scalar(info.get("marketCap"), default=0.0)
        mcap_str = format_financial_number(market_cap)
        growth_pct = round(_scalar(info.get("revenueGrowth"), default=0.0) * 100, 2)

        # Summary
        summary = info.get("longBusinessSummary", "No summary available.")
        if summary != "No summary available.":
            sentences = [s for s in summary.split('.') if s.strip()]
            summary = '. '.join(sentences[:3]) + "." if sentences else summary

        # Logo
        logo_url = ""
        website = info.get("website", "")
        if website:
            domain = website.replace("http://", "").replace("https://", "").replace("www.", "").strip("/")
            logo_url = f"https://logo.clearbit.com/{domain}"

        # Execs
        ceo, cfo = "N/A", "N/A"
        for off in info.get("companyOfficers", []):
            title = (off.get("title", "") or "").upper()
            name = off.get("name", "N/A")
            if ceo == "N/A" and ("CEO" in title or "CHIEF EXECUTIVE" in title): ceo = name
            if cfo == "N/A" and ("CFO" in title or "CHIEF FINANCIAL" in title): cfo = name

        # Performance History
        hist = _resilient_history(stock, ["3y", "5y", "max"])
        perf_metrics = {"1 Month": "-", "6 Months": "-", "This Year": "-", "1 Year": "-", "3 Years": "-"}
        if not hist.empty:
            curr = hist['Close'].iloc[-1]
            def get_p(days):
                if len(hist) > days:
                    past = hist['Close'].iloc[-(days+1)]
                    return round(((curr - past) / past) * 100, 2)
                return "-"
            
            perf_metrics["1 Month"] = get_p(21)
            perf_metrics["6 Months"] = get_p(126)
            perf_metrics["1 Year"] = get_p(252)
            perf_metrics["3 Years"] = get_p(len(hist)-1)
            
            # YTD
            try:
                ytd_h = hist[hist.index >= f"{pd.Timestamp.now().year}-01-01"]
                if not ytd_h.empty:
                    ytd_start = ytd_h['Close'].iloc[0]
                    perf_metrics["This Year"] = round(((curr - ytd_start) / ytd_start) * 100, 2)
            except: pass

        # Chart Data
        chart_dates, chart_prices = [], []
        h6m = _resilient_history(stock, ["6mo", "1y", "2y"])
        if not h6m.empty:
            chart_dates = [d.strftime("%Y-%m-%d") for d in h6m.index]
            chart_prices = [round(float(p), 2) for p in h6m["Close"]]

        # Dividends
        div_years, div_vals = [], []
        if not stock.dividends.empty:
            try:
                d = stock.dividends[stock.dividends.index >= '2020-01-01'].resample('YE').sum()
                div_years = [i.strftime('%Y') for i in d.index]
                div_vals = [round(float(v), 2) for v in d.values]
            except: pass

        # Annual Returns (10y)
        ann_years, ann_returns = [], []
        h10 = _resilient_history(stock, ["10y", "max"])
        if not h10.empty:
            try:
                ann_c = h10['Close'].resample('YE').last()
                rets = ann_c.pct_change() * 100
                ann_years = [i.strftime('%Y') for i in rets.index[1:]]
                ann_returns = [round(v, 2) for v in rets.values[1:]]
            except: pass

        return {
            "Total Revenue": format_financial_number(_scalar(info.get("totalRevenue"))),
            "Gross Profit": format_financial_number(_scalar(info.get("grossProfits"))),
            "Trailing EPS": _scalar(info.get("trailingEps"), "N/A"),
            "Growth (%)": f"{growth_pct}%",
            "_company_name": long_name,
            "_sector": sector,
            "_market_cap": mcap_str,
            "_price_change_pct": round(_scalar(info.get("regularMarketChangePercent")), 2),
            "_52_week_high": format_financial_number(_scalar(info.get("fiftyTwoWeekHigh"))),
            "_52_week_low": format_financial_number(_scalar(info.get("fiftyTwoWeekLow"))),
            "_description": summary,
            "_industry": info.get("industry", "N/A"),
            "_logo_url": logo_url,
            "_ceo": ceo,
            "_cfo": cfo,
            "_performance": perf_metrics,
            "_chart_dates": chart_dates,
            "_chart_prices": chart_prices,
            "_div_years": div_years,
            "_div_vals": div_vals,
            "_ann_years": ann_years,
            "_ann_returns": ann_returns
        }
    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        return {"error": str(e), "_company_name": ticker.upper()}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_trend_data(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        q = stock.quarterly_financials
        if not q.empty and "Total Revenue" in q.index:
            rev = q.loc["Total Revenue"].dropna().sort_index()
            prof = q.loc["Gross Profit"].dropna().sort_index() if "Gross Profit" in q.index else rev * 0.2
            return {
                "dates": [d.strftime("%Y-%m-%d") for d in rev.index],
                "revenue": rev.tolist(),
                "profit": prof.tolist(),
                "type": "financials"
            }
        hist = stock.history(period="6mo")
        return {
            "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
            "price": hist['Close'].tolist(),
            "type": "price_action"
        }
    except: return {"error": "Trend fetch failed"}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fmp(ticker: str):
    try:
        info = yf.Ticker(ticker).info
        return {
            "Debt-to-Equity Ratio": f"{_scalar(info.get('debtToEquity'))/100:.22f}x" if info.get('debtToEquity') else "N/A",
            "Return on Equity (ROE)": f"{_scalar(info.get('returnOnEquity'))*100:.2f}%" if info.get('returnOnEquity') else "N/A",
            "Net Profit Margin": f"{_scalar(info.get('profitMargins'))*100:.2f}%" if info.get('profitMargins') else "N/A"
        }
    except: return {"error": "FMP fetch failed"}

def _scalar(x, default=0.0):
    if x is None: return default
    try: return float(x[0] if isinstance(x, (list,tuple)) else x)
    except: return default

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_news(query: str):
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key: return [{"title": "API Missing", "content": "Tavily key missing", "url": "#"}]
    try:
        res = TavilyClient(api_key=api_key).search(query=query, max_results=5)
        return res.get("results", [])
    except: return []

def build_context_payload(ticker: str, metrics: dict, trends: dict, news: list) -> str:
    payload = {
        "ticker": ticker,
        "profile": {k: v for k, v in metrics.items() if not k.startswith("_")},
        "description": metrics.get("_description", ""),
        "performance": metrics.get("_performance", {}),
        "trends": trends,
        "news_summary": [n.get("content", "")[:300] for n in news[:3]]
    }
    return json.dumps(payload, indent=2)
