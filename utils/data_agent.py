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
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info or not isinstance(info, dict):
            info = {}
            print(f"[ERROR] yFinance returned empty data for {ticker}")
            try:
                fi = stock.fast_info
                info["longName"] = ticker.upper()
                info["marketCap"] = getattr(fi, "market_cap", 0)
                info["regularMarketPrice"] = getattr(fi, "last_price", 0)
            except:
                pass
        
        def _scalar(x, default=0.0):
            """Coerce yfinance values to float when they come back as lists/strings."""
            if x is None:
                return default
            if isinstance(x, (list, tuple)):
                return _scalar(x[0], default=default) if x else default
            try:
                return float(x)
            except Exception:
                return default

        revenue_growth = _scalar(info.get("revenueGrowth"), default=0.0)
        growth_pct = round(revenue_growth * 100, 2) if revenue_growth else 0.0
        
        # New Extracted Fields for Company Strip
        long_name = info.get("longName", ticker.upper())
        sector = info.get("sector", "N/A Sector")
        market_cap = _scalar(info.get("marketCap"), default=0.0)
        
        print(f"[DEBUG] Ticker Name: {long_name}, MCAP: {market_cap}")
        
        def format_financial_number(num):
            if not num: return "N/A"
            try:
                val = float(num)
            except:
                return str(num)
            if abs(val) >= 1e12: return f"${val/1e12:.2f} Trillion"
            if abs(val) >= 1e9: return f"${val/1e9:.2f} Billion"
            if abs(val) >= 1e6: return f"${val/1e6:.2f} Million"
            return f"${val:,.2f}"
            
        mcap_str = format_financial_number(market_cap)

        long_business_summary = info.get("longBusinessSummary", "")
        if long_business_summary:
            sentences = [s for s in long_business_summary.split('.') if s.strip()]
            truncated_summary = '. '.join(sentences[:3]) + "." if sentences else "No summary available."
        else:
            truncated_summary = "No summary available."

        # -- Improved Logo Logic --
        logo_url = ""
        website = info.get("website", "")
        if website:
            domain = website.replace("http://", "").replace("https://", "").replace("www.", "").strip("/")
            logo_url = f"https://logo.clearbit.com/{domain}"
        
        # -- Robust Executive Extraction --
        officers = info.get("companyOfficers", [])
        ceo, cfo = "N/A", "N/A"
        
        # 1. Try yFinance list
        for off in officers:
            title = (off.get("title", "") or "").upper()
            name = off.get("name", "N/A")
            if not name or name == "N/A":
                continue

            # CEO title variants
            if ceo == "N/A":
                if ("CHIEF EXECUTIVE" in title) or (" CEO" in f" {title} ") or ("PRESIDENT & CEO" in title) or ("PRESIDENT AND CEO" in title):
                    ceo = name

            # CFO title variants
            if cfo == "N/A":
                if ("CHIEF FINANCIAL" in title) or (" CFO" in f" {title} ") or ("FINANCE DIRECTOR" in title) or ("VP FINANCE" in title):
                    cfo = name

            if ceo != "N/A" and cfo != "N/A":
                break
        
        # 2. Tavily Fallback for Missing Executives
        if (ceo == "N/A" or cfo == "N/A") and os.getenv("TAVILY_API_KEY"):
            try:
                tav_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
                search_query = f"Who is the current CEO and CFO of {long_name} ({ticker})? Answer with names ONLY."
                tav_res = tav_client.search(query=search_query, search_depth="basic", max_results=1)
                results = tav_res.get("results", [])
                if results:
                    content = results[0].get("content", "").lower()
                    # Basic extraction for CEO
                    if ceo == "N/A":
                        idx = content.find("ceo")
                        if idx != -1:
                            ceo_part = content[idx:idx+50].split(':')[-1].split('is')[-1].strip()
                            ceo = ceo_part.split('.')[0].split(',')[0].title()
                    # Basic extraction for CFO
                    if cfo == "N/A":
                        idx = content.find("cfo")
                        if idx != -1:
                            cfo_part = content[idx:idx+50].split(':')[-1].split('is')[-1].strip()
                            cfo = cfo_part.split('.')[0].split(',')[0].title()
            except:
                pass

        # Fetch 3-year history for performance metrics
        # SWITCH: Use yf.download instead of stock.history as it uses a different endpoint often less rate-limited
        hist = yf.download(ticker, period="3y", progress=False)
        perf_metrics = {"1 Month": "-", "6 Months": "-", "This Year": "-", "1 Year": "-", "3 Years": "-"}
        if not hist.empty:
            current_idx = len(hist) - 1
            current_price = hist['Close'].iloc[current_idx]
            
            def get_pct(days_back, from_ytd=False):
                if from_ytd:
                    import datetime
                    now = datetime.datetime.now()
                    start_of_year = f"{now.year}-01-01"
                    try:
                        ytd_hist = hist[hist.index >= start_of_year]
                        if not ytd_hist.empty:
                            return round(((current_price - ytd_hist['Close'].iloc[0]) / ytd_hist['Close'].iloc[0]) * 100, 2)
                    except:
                        pass
                    return "-"
                
                target_idx = current_idx - days_back
                if target_idx >= 0:
                    past_price = hist['Close'].iloc[target_idx]
                    return round(((current_price - past_price) / past_price) * 100, 2)
                elif len(hist) > 0 and days_back > len(hist):
                     past_price = hist['Close'].iloc[0]
                     return round(((current_price - past_price) / past_price) * 100, 2)
                return "-"
            
            perf_metrics["1 Month"] = get_pct(21)
            perf_metrics["6 Months"] = get_pct(126)
            perf_metrics["This Year"] = get_pct(0, from_ytd=True)
            perf_metrics["1 Year"] = get_pct(252)
            perf_metrics["3 Years"] = get_pct(252*3)
        
        # Trend / Change variables for ↑/↓ icons
        price_change_pct = _scalar(info.get("regularMarketChangePercent"), default=0.0)
        
        # 52-Week High / Low narrative variables
        f52h = _scalar(info.get("fiftyTwoWeekHigh"), default=0.0)
        f52l = _scalar(info.get("fiftyTwoWeekLow"), default=0.0)
        fiftyTwoWeekHigh = format_financial_number(f52h) if f52h else "N/A"
        fiftyTwoWeekLow = format_financial_number(f52l) if f52l else "N/A"

        # Arrays for plotting
        chart_dates, chart_prices = [], []
        if not hist.empty:
            # Last 6 months for the area chart
            h6m = yf.download(ticker, period="6mo", progress=False)
            if not h6m.empty and "Close" in h6m.columns:
                # Be robust: sometimes the index is not a DatetimeIndex
                idx = pd.to_datetime(h6m.index, errors="coerce")
                if hasattr(idx, "strftime"):
                    chart_dates = idx.strftime("%Y-%m-%d").tolist()
                else:
                    chart_dates = [str(x) for x in list(h6m.index)]
                chart_prices = [round(float(p), 2) for p in h6m["Close"].tolist()]
            
        div_series = stock.dividends
        div_years, div_vals = [], []
        if not div_series.empty:
            try:
                div_series = div_series[div_series.index >= '2020-01-01']
                div_annual = div_series.resample('YE').sum()
            except:
                div_annual = div_series.resample('Y').sum()
            # yfinance/pandas can sometimes yield a DataFrame here; normalize to Series
            if isinstance(div_annual, pd.DataFrame) and not div_annual.empty:
                div_annual = div_annual.iloc[:, 0]
            div_idx = pd.to_datetime(div_annual.index, errors="coerce")
            div_years = div_idx.strftime('%Y').tolist() if hasattr(div_idx, "strftime") else [str(x) for x in list(div_annual.index)]
            div_vals = [round(float(v), 2) for v in div_annual.values.tolist()]
            
        ann_years, ann_returns = [], []
        h10y = stock.history(period="10y")
        if not h10y.empty:
            try:
                annual_close = h10y['Close'].resample('YE').last()
            except:
                annual_close = h10y['Close'].resample('Y').last()
            returns = annual_close.pct_change() * 100
            ret_idx = pd.to_datetime(returns.index, errors="coerce")
            ann_years = (ret_idx.strftime('%Y').tolist()[1:] if hasattr(ret_idx, "strftime") else [str(x) for x in list(returns.index)][1:])
            ann_returns = [round(v, 2) for v in returns.values.tolist()[1:]]

        metrics = {
            "Total Revenue": format_financial_number(_scalar(info.get("totalRevenue"), default=0.0)),
            "Gross Profit": format_financial_number(_scalar(info.get("grossProfits"), default=0.0)),
            "Trailing EPS": _scalar(info.get("trailingEps"), default="N/A") if info.get("trailingEps") is not None else "N/A",
            "Growth (%)": f"{growth_pct}%",
            "_company_name": long_name,
            "_sector": sector,
            "_market_cap": mcap_str,
            "_price_change_pct": round(price_change_pct, 2),
            "_52_week_high": fiftyTwoWeekHigh,
            "_52_week_low": fiftyTwoWeekLow,
            "_description": truncated_summary,
            "_industry": info.get("industry", "N/A Industry"),
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
        
        return metrics
    except Exception as e:
        print(f"[ERROR] execute_yfinance (fetch_financial_metrics) failed fetching data for '{ticker}': {str(e)}")
        print(traceback.format_exc())
        return {"error": str(e), "_company_name": ticker.upper(), "_sector": "Unknown", "_market_cap": "Unknown", "_price_change_pct": 0.0}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_trend_data(ticker: str):
    """Fetches quarterly financials to plot revenue and profit trends. 
    Falls back to stock price history if financials aren't immediately available.
    """
    try:
        stock = yf.Ticker(ticker)
        q_fin = stock.quarterly_financials
        
        trend_data = {}
        if not q_fin.empty and "Total Revenue" in q_fin.index and "Gross Profit" in q_fin.index:
            # We want chronological order (oldest to newest)
            rev = q_fin.loc["Total Revenue"].dropna().sort_index()
            prof = q_fin.loc["Gross Profit"].dropna().sort_index()
            
            trend_data["dates"] = [d.strftime("%Y-%m-%d") for d in rev.index]
            trend_data["revenue"] = rev.tolist()
            trend_data["profit"] = prof.tolist()
            trend_data["type"] = "financials"
        else:
            # Fallback to 6 Month Price Action
            hist = stock.history(period="6mo")
            idx = pd.to_datetime(hist.index, errors="coerce")
            trend_data["dates"] = (idx.strftime("%Y-%m-%d").tolist() if hasattr(idx, "strftime") else [str(x) for x in list(hist.index)])
            trend_data["price"] = hist['Close'].tolist()
            trend_data["volume"] = hist['Volume'].tolist()
            trend_data["type"] = "price_action"
            
        return trend_data
    except Exception as e:
        return {"error": str(e)}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fmp(ticker: str):
    """Fetches fundamental accounting metrics natively via yfinance."""
    import yfinance as yf
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        roe = info.get("returnOnEquity")
        roe_display = f"{roe * 100:.2f}%" if roe else "N/A"

        margins = info.get("profitMargins")
        margins_display = f"{margins * 100:.2f}%" if margins else "N/A"

        # yfinance returns D/E as a percentage-like number (102.63 = 1.03x ratio)
        debt_raw = info.get("debtToEquity")
        debt_display = f"{debt_raw / 100:.2f}x" if debt_raw else "N/A"

        return {
            "Debt-to-Equity Ratio": debt_display,
            "Return on Equity (ROE)": roe_display,
            "Net Profit Margin": margins_display
        }
    except Exception as e:
        print(f"[ERROR] fetch_fmp (yfinance fallback) exception for '{ticker}': {str(e)}")
        return {"error": str(e)}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_news(query: str):
    """Fetches FAANG-level contextual news cards via Tavily."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or api_key == "your_key_here":
        return [{"title": "API Missing", "content": "Tavily API key not found in .env.", "url": "#"}]
        
    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query=f"{query} stock news partnerships earnings", search_depth="basic", max_results=4)
        results = response.get("results", [])
        cleaned = []
        for r in results:
            cleaned.append({
                "title": r.get('title'),
                "content": r.get('content', '')[:200].replace('\n', ' ') + "...", 
                "url": r.get('url')
            })
        return cleaned
    except Exception as e:
        return [{"title": "Search Failed", "content": str(e), "url": "#"}]

def build_context_for_llm(ticker: str, metrics: dict, trends: dict, news: list, fmp: dict) -> str:
    """Serializes the fetched data into a dense string for Llama 3.1"""
    context = f"=== FINANCIAL METRICS FOR {ticker} ===\n"
    context += json.dumps(metrics, indent=2) + "\n\n"
    
    context += f"=== ACCOUNTING & SOLVENCY (FMP) ===\n"
    context += json.dumps(fmp, indent=2) + "\n\n"
    
    context += f"=== TREND DATA ({trends.get('type', 'unknown')}) ===\n"
    if trends.get("type") == "financials":
         context += f"Dates: {trends.get('dates', [])[-4:]}\nRevenue: {trends.get('revenue', [])[-4:]}\nProfit: {trends.get('profit', [])[-4:]}\n\n"
    elif trends.get("type") == "price_action":
         prices = trends.get('price', [])
         if prices:
             context += f"Current Trend: Start Price {prices[0]:.2f} -> End Price {prices[-1]:.2f}\n\n"
         
    context += "=== RECENT NEWS HEADLINES ===\n"
    for item in news:
        context += f"- {item.get('title')}: {item.get('content')}\n"
        
    context += f"\n=== BENCHMARKING GOALS ===\n"
    context += f"Target Sector: {metrics.get('_sector')}\n"
    context += f"Target Industry: {metrics.get('_industry')}\n"
    context += f"Goal: Compare {ticker} against its primary sector peers and identify any emerging disruptors mentioned in the news above.\n"
    
    return context
@st.cache_data(ttl=300, show_spinner=False)
def fetch_sidebar_market_data():
    """Fetches high-level data for a few marquee tickers for the side dock."""
    tickers = ["NVDA", "AAPL", "TSLA", "RELIANCE.NS", "BTC-USD"]
    results = []
    
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            # Use fast_info if available, or basic history
            hist = stock.history(period="2d")
            if len(hist) >= 2:
                current_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                change_pct = ((current_price - prev_price) / prev_price) * 100
            else:
                current_price = stock.info.get('regularMarketPrice') or 0.0
                change_pct = stock.info.get('regularMarketChangePercent') or 0.0
                
            results.append({
                "ticker": t,
                "price": round(current_price, 2),
                "change": round(change_pct, 2)
            })
        except Exception as e:
            print(f"[SIDEBAR DATA] Error fetching {t}: {e}")
            results.append({"ticker": t, "price": "Offline", "change": 0.0})
            
    return results
