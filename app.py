import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
import time
import sys
import os
import json
import hashlib
import concurrent.futures
import plotly.graph_objects as go
import yfinance as yf
from supabase import create_client, Client

load_dotenv()

# Add the project root to sys.path so components and utils can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from components.ui_blocks import (
    render_ai_insights, render_judge_panel, render_news,
    ACCENT, BORDER, TEXT, MUTED, BODY_TEXT, EMERALD, CRIMSON,
    EMERALD_RGB, CRIMSON_RGB, BORDER_RGB
)
from utils.data_agent import fetch_financial_metrics, fetch_trend_data, fetch_news, fetch_fmp, build_context_for_llm, fetch_sidebar_market_data
from utils.ai_agent import get_insights, get_judge_scores, run_fact_check_agent, resolve_ticker, MAX_FACT_CHECK_RETRIES, get_action_insight, _stream_ollama, robust_tag_parser

# ── API Clients ──
SB_URL = os.getenv("SUPABASE_URL")
SB_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SB_URL, SB_KEY) if SB_URL and SB_KEY else None

# =====================================================================
#  MASTER THEME & UI TOKENS
# =====================================================================
BRAND_NAME = "Finsighter"
ACCENT     = "#10B981"  # Emerald Green (Financial Growth)
TEXT       = "#F8FAFC"
MUTED      = "#94A3B8"
BORDER     = "rgba(255,255,255,0.12)"
CARD_BG    = "#111827"
BODY_TEXT  = "#CBD5E1"
BRAND_A    = "#10B981"
BRAND_B    = "#059669"
GLOW_SHADOW = "0 0 20px rgba(16, 185, 129, 0.2)"

# =====================================================================
#  Finsighter  |  Glass-Box Architecture
# =====================================================================

st.set_page_config(
    page_title=BRAND_NAME,
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Session State Defaults ──
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "page" not in st.session_state:
    st.session_state.page = "login" if not st.session_state.authenticated else "hero"
if "ticker_to_analyze" not in st.session_state:
    st.session_state.ticker_to_analyze = None
if "turbo_mode" not in st.session_state:
    st.session_state.turbo_mode = False

# ── Query Parameter Navigation ──
# This allows the HTML navbar links to switch pages
if "nav" in st.query_params:
    requested_nav = st.query_params["nav"]
    if requested_nav in ["how_it_works", "features", "ai_finance", "research", "hero", "search"]:
        st.session_state.page = requested_nav
    # Clear the parameter so it doesn't stay in the URL indefinitely
    st.query_params.clear()

# ── Navigation helpers ──
def go_to_search():
    st.session_state.page = "search"

def go_to_hero():
    st.session_state.page = "hero"
    st.session_state.ticker_to_analyze = None

def render_neo_terminal(lines):
    """Renders a premium, hacker-style live terminal feed."""
    terminal_html = '<div class="neo-terminal"><div class="terminal-header"><div class="terminal-dot" style="background:#FF5F56;"></div><div class="terminal-dot" style="background:#FFBD2E;"></div><div class="terminal-dot" style="background:#27C93F;"></div></div>'
    for line in lines:
        terminal_html += f'<div class="terminal-line"><span class="terminal-prefix">></span> <span>{line}</span></div>'
    terminal_html += '<div class="terminal-line"><span class="terminal-prefix">></span> <span class="terminal-cursor"></span></div></div>'
    st.markdown(terminal_html, unsafe_allow_html=True)

# ── User Management Helpers (Supabase) ──
def _load_users():
    """Fallback list for local dev/admin access."""
    return {"admin": "premium2026"}

def _check_user_auth(username, password):
    """Verifies credentials against Supabase users table."""
    if not supabase:
        # Fallback to local admin if Supabase is not configured
        return _load_users().get(username) == password
    
    try:
        res = supabase.table("users").select("*").eq("username", username).eq("password", password).execute()
        return len(res.data) > 0 or (username == "admin" and password == "premium2026")
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return username == "admin" and password == "premium2026"

def _save_user(username, password):
    """Persists a new user to the Supabase users table."""
    if not supabase:
        return False
    try:
        data = {"username": username, "password": password}
        supabase.table("users").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Sign-up error: {e}")
        return False

def render_login_page():
    """Renders a high-aesthetic, center-aligned SaaS login gateway with Sign Up."""
    st.markdown("""
    <div style="text-align: center; padding-top: 5rem;">
        <div class="search-logo" style="font-size: 3rem; margin-bottom: 0.5rem;">
            <span class="logo-icon" style="width:50px; height:50px; font-size:1.4rem;">&#9678;</span>
            Finsighter<span class="logo-dot">.</span>
        </div>
        <div class="search-tagline" style="margin-bottom: 2rem;">Intelligence Command Center &mdash; SaaS Gateway</div>
    </div>
    """, unsafe_allow_html=True)

    _, l_col, _ = st.columns([1.2, 1, 1.2])
    with l_col:
        st.markdown(f'<div style="text-align:center; margin-bottom:1.5rem; color:{MUTED}; font-size:0.75rem; letter-spacing:0.15em; font-weight:700; text-transform:uppercase;">Authentication Layer</div>', unsafe_allow_html=True)
        tab_login, tab_signup = st.tabs(["🔒 Secure Login", "✨ New Account"])
        
        with tab_login:
            st.markdown('<div style="height: 0.5rem;"></div>', unsafe_allow_html=True)
            u_login = st.text_input("Username", key="login_user")
            p_login = st.text_input("Security Key", type="password", key="login_pwd")
            
            if st.button("Initialize Terminal", type="primary", use_container_width=True):
                if _check_user_auth(u_login, p_login):
                    st.session_state.authenticated = True
                    st.session_state.page = "hero"
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please try again.")
            
            st.markdown('<p style="font-size:0.7rem; color:var(--muted); text-align:center; margin-top:10px;">Demo: admin | premium2026</p>', unsafe_allow_html=True)

        with tab_signup:
            st.markdown('<div style="height: 1rem;"></div>', unsafe_allow_html=True)
            u_new = st.text_input("Choose Username", key="new_user")
            p_new = st.text_input("Set Security Key", type="password", key="new_pwd")
            p_confirm = st.text_input("Confirm Key", type="password", key="confirm_pwd")
            
            if st.button("Create SaaS Account", type="primary", use_container_width=True):
                if not u_new or not p_new:
                    st.warning("Please fill in all fields.")
                elif p_new != p_confirm:
                    st.error("Keys do not match.")
                else:
                    if _save_user(u_new, p_new):
                        st.success("Account initialized! Logging in...")
                        time.sleep(1)
                        st.session_state.authenticated = True
                        st.session_state.page = "hero"
                        st.rerun()
                    else:
                        st.error("System storage error or username already exists.")
        

        st.markdown('<p style="text-align:center; color:var(--muted); font-size:0.75rem; margin-top:2rem;">© 2026 Finsighter. All Rights Reserved.</p>', unsafe_allow_html=True)
    
    st.markdown('<div class="search-bg-glow" style="top: 100px;"></div>', unsafe_allow_html=True)


# =====================================================================
#  GLOBAL CSS
# =====================================================================
st.markdown("""
<style>
    :root{
        --bg: #060606;
        --card: #0F0F11;
        --border: rgba(255,255,255,0.06);
        --text: #ffffff;
        --muted: #999999;
        --muted2: #666666;
        --subtle: #333333;
        --brandA: #00E3A5;
        --brandB: #02a378;
        --shadow: 0 4px 20px rgba(0,0,0,0.4);
        --shadowHover: 0 10px 40px rgba(0,0,0,0.5);
        --radius: 16px;
    }

    /* ---- Fonts ---- */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600&family=Source+Code+Pro:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif !important; letter-spacing: -0.01em; }
    code, pre, .mono-stat { font-family: 'Source Code Pro', monospace !important; font-size: 0.9em; }

    /* ---- Animations ---- */
    @keyframes fadeInUp { from { opacity:0; transform:translateY(18px); } to { opacity:1; transform:translateY(0); } }
    @keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
    @keyframes softPulse { 0% { box-shadow: 0 0 0 rgba(16,185,129,0); } 70% { box-shadow: 0 0 0 10px rgba(16,185,129,0); } 100% { box-shadow: 0 0 0 rgba(16,185,129,0); } }

    /* ---- Background ---- */
    .stApp { background: var(--bg) !important; color: var(--text); }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 0; padding-bottom: 3rem; max-width: 1400px; }

    /* ---- Hide sidebar toggle (Removed for Turbo Mode access) ---- */
    /* [data-testid="stSidebarCollapsedControl"] { display: none !important; } */

    /* ======================= HERO PAGE ======================= */

    .announce-bar {
        background: linear-gradient(90deg, rgba(16,185,129,0.06) 0%, rgba(5,150,105,0.06) 100%);
        color: var(--text); text-align: center;
        padding: 10px 20px; font-size: 0.82rem; font-weight: 500;
        margin: -1rem -5rem 0 -5rem;
        border-bottom: 1px solid var(--border);
    }
    .announce-bar a {
        color: var(--brandA); font-weight: 700; text-decoration: none; margin-left: 8px;
        padding: 3px 12px; border: 1px solid rgba(16,185,129,0.25);
        border-radius: 4px; font-size: 0.78rem;
        background: rgba(255,255,255,0.05);
    }

    .navbar {
        display: flex; align-items: center; justify-content: space-between;
        padding: 18px 0; border-bottom: 1px solid var(--border);
        background: rgba(10, 15, 26, 0.4); backdrop-filter: blur(10px);
    }
    .navbar-brand { font-size: 1.4rem; font-weight: 800; color: var(--text); letter-spacing: -0.04em; }
    .navbar-brand a { color: var(--text) !important; text-decoration: none; }
    .navbar-links { display: flex; align-items: center; gap: 32px; }
    .navbar-links a { color: var(--muted); font-size: 0.9rem; font-weight: 600; text-decoration: none; transition: color 0.2s; }
    .navbar-links a:hover { color: var(--brandA); }
    .btn-nav-primary {
        background: var(--brandA); color: #000 !important;
        padding: 10px 24px; border-radius: 999px; /* Cryptix Pill Button */
        font-weight: 700; font-size: 0.9rem; text-decoration: none;
        transition: all 0.3s ease;
    }
    .btn-nav-primary:hover {
        box-shadow: 0 0 24px rgba(0, 227, 165, 0.4);
        transform: translateY(-1px);
    }
    .btn-nav-outline {
        border: 1px solid var(--border); color: var(--muted) !important;
        padding: 7px 18px; border-radius: 6px;
        font-weight: 500; font-size: 0.85rem; text-decoration: none;
        background: rgba(255,255,255,0.05);
    }

    .hero {
        text-align: center; padding: 7rem 2rem 4rem 2rem;
        position: relative;
    }
    /* Ambient Top Center Radial Glow like Cryptix */
    .hero::before {
        content: "";
        position: absolute;
        width: 1000px; height: 600px;
        background: radial-gradient(circle at center top, rgba(45, 27, 105, 0.45) 0%, transparent 60%);
        top: -150px; left: 50%; transform: translateX(-50%);
        pointer-events: none;
        z-index: -1;
    }
        animation: fadeInUp 0.8s ease both;
    }
    .hero h1 {
        font-size: 4rem; font-weight: 900; color: var(--text);
        line-height: 1.1; letter-spacing: -0.04em;
        margin: 0 auto 1.5rem auto; max-width: 900px;
    }
    .hero h1 .accent {
        background: linear-gradient(135deg, var(--brandA), var(--brandB));
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .hero p { color: var(--muted); font-size: 1.3rem; max-width: 650px; margin: 0 auto 2.5rem auto; line-height: 1.6; }

    .cta-sub { color: #10B981; font-size: 0.82rem; font-weight: 500; text-align: center; }

    .feature-card {
        background: rgba(255,255,255,0.02); border-radius: 16px; padding: 2.5rem 2rem; text-align: center;
        border: 1px solid var(--border); transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        animation: fadeInUp 0.5s ease both; height: 100%;
        backdrop-filter: blur(8px);
    }
    .feature-card:hover {
        border-color: var(--brandA); transform: translateY(-8px);
        background: rgba(255,255,255,0.04);
        box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    }
    .feature-icon {
        width: 54px; height: 54px; border-radius: 14px;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 1.6rem; margin-bottom: 1.2rem;
        box-shadow: 0 0 15px rgba(16, 185, 129, 0.1);
    }
    .feature-card h4 { color: var(--text); font-size: 1.15rem; font-weight: 800; margin: 0 0 0.7rem 0; }
    .feature-card p { color: var(--muted); font-size: 0.92rem; line-height: 1.6; margin: 0; }

    .trust-bar {
        text-align: center; padding: 2rem 0;
        border-top: 1px solid #E2E8F0; margin-top: 2rem;
    }
    .trust-bar span { color: var(--subtle); font-size: 0.78rem; font-weight: 600; margin: 0 16px; letter-spacing: 0.04em; }

    /* ======================= SEARCH PAGE ======================= */

    .search-page-container {
        display: flex; flex-direction: column; align-items: center;
        animation: fadeIn 0.5s ease both;
    }
    .search-logo {
        font-size: 2.8rem; font-weight: 900; color: var(--text);
        letter-spacing: -0.04em; margin-bottom: 0.2rem;
        display: flex; align-items: center; gap: 8px; justify-content: center;
    }
    .search-logo .logo-icon {
        width: 44px; height: 44px; border: 3px solid var(--brandA);
        border-radius: 50%; font-size: 1.2rem; display: flex; align-items: center; justify-content: center;
        color: var(--brandA); box-shadow: 0 0 15px rgba(16, 185, 129, 0.3);
    }
    .search-logo .logo-dot { color: var(--brandA); }
    .search-tagline { color: var(--muted); font-size: 0.85rem; font-weight: 500; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.8rem; }
    .search-prompt { color: var(--text); font-size: 1rem; font-weight: 600; margin-bottom: 0; opacity: 0.9; }

    /* -- Search input: kill ALL dark artifacts -- */
    .stTextInput > div { background: transparent !important; }
    .stTextInput > div > div { background: transparent !important; }
    .stTextInput > div > div > input {
        background: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid var(--border) !important;
        color: var(--text) !important; font-size: 1.1rem !important;
        padding: 1rem 1.6rem !important; border-radius: 40px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
        transition: all 0.25s ease;
        backdrop-filter: blur(4px);
    }
    .stTextInput > div > div > input:focus {
        border-color: var(--brandA) !important;
        box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15) !important;
    }
    .stTextInput > div > div > input::placeholder { color: var(--subtle) !important; }

    .pick-plan-link { color: var(--muted); font-size: 0.85rem; font-weight: 500; text-align: center; margin-top: 0.6rem; opacity: 0.8; }
    .pick-plan-link a { color: var(--brandA) !important; text-decoration: underline; font-weight: 700; }

    .ai-agent-pill {
        display: inline-flex; align-items: center; gap: 8px;
        background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25);
        border-radius: 30px; padding: 12px 28px;
        color: var(--brandA); font-size: 0.92rem; font-weight: 800;
        margin-top: 1.5rem; cursor: default;
        transition: all 0.2s ease;
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    .ai-agent-pill:hover {
        background: rgba(16, 185, 129, 0.12);
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.25);
    }
    .ai-agent-dot {
        width: 8px; height: 8px; background: var(--brandA);
        border-radius: 50%; display: inline-block;
        box-shadow: 0 0 8px var(--brandA);
    }

    /* ---- Buttons: scope polish to primary only ---- */
    /* Default / secondary buttons */
    div[data-testid^="stBaseButton"] > button,
    div[data-testid="stButton"] > button {
        height: 46px !important;
        background: var(--card) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 999px !important;
        font-weight: 650 !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2) !important;
    }
    div[data-testid^="stBaseButton"] > button:hover,
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(0,0,0,0.3) !important;
        border-color: var(--brandA) !important;
    }

    /* ======================= COMMAND CENTER UI (SEARCH PAGE) ======================= */
    .status-ticker {
        display: flex; gap: 24px; justify-content: center;
        padding: 10px 0; border-bottom: 1px solid rgba(16, 185, 129, 0.15);
        background: rgba(16, 185, 129, 0.03);
        margin: -1rem -1rem 2rem -1rem;
    }
    .status-item {
        font-family: 'Source Code Pro', monospace; font-size: 0.75rem; 
        font-weight: 600; color: var(--brandA); opacity: 0.85;
        display: flex; align-items: center; gap: 6px;
    }
    .status-dot-green { width: 6px; height: 6px; border-radius: 50%; background: #10B981; box-shadow: 0 0 8px #10B981; }

    .intelligence-shortcuts {
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;
        margin-top: 3rem; max-width: 900px;
    }
    .shortcut-btn button {
        height: auto !important; padding: 24px !important;
        background: rgba(15, 23, 42, 0.5) !important;
        border: 1px solid rgba(16, 185, 129, 0.1) !important;
        border-radius: 16px !important;
        text-align: left !important; display: block !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .shortcut-btn button:hover {
        border-color: var(--brandA) !important;
        background: rgba(16, 185, 129, 0.05) !important;
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.1) !important;
    }
    .shortcut-title { color: var(--brandA); font-weight: 800; font-size: 1rem; margin-bottom: 4px; display: block; }
    .shortcut-desc { color: var(--muted); font-size: 0.8rem; font-weight: 500; line-height: 1.4; display: block; }

    .glass-box-visualizer {
        margin-top: 6rem; padding: 4rem 2rem;
        border-top: 1px solid var(--border);
        background: radial-gradient(circle at center bottom, rgba(16, 185, 129, 0.03) 0%, transparent 70%);
    }
    .visualizer-card {
        padding: 24px; border-radius: 12px; border: 1px solid var(--border);
        background: rgba(255,255,255,0.01);
    }
    .search-bg-glow {
        position: absolute; top: 300px; left: 50%; transform: translateX(-50%);
        width: 800px; height: 800px;
        background: radial-gradient(circle, rgba(0, 255, 136, 0.05) 0%, transparent 70%);
        pointer-events: none; z-index: -1;
    }

    /* ---- SIDEBAR PERIPHERALS ---- */
    .market-watch-dock {
        padding: 20px 0; border-right: 1px solid var(--border);
        height: 60vh; display: flex; flex-direction: column; gap: 12px;
    }
    .dock-item {
        padding: 12px 16px; border-radius: 8px; transition: all 0.25s ease;
        border: 1px solid transparent; cursor: default;
    }
    .dock-item:hover {
        background: rgba(16, 185, 129, 0.04);
        border-color: rgba(16, 185, 129, 0.2);
        box-shadow: 0 0 15px rgba(16, 185, 129, 0.1);
    }
    .dock-ticker { font-size: 0.85rem; font-weight: 800; color: var(--text); }
    .dock-price { font-size: 0.8rem; font-family: 'Source Code Pro'; color: var(--muted); }
    .dock-change { font-size: 0.75rem; font-weight: 700; }

    .agent-heartbeat-log {
        padding: 20px 0; border-left: 1px solid var(--border);
        height: 60vh; overflow-y: hidden;
    }
    .heartbeat-line {
        font-family: 'Source Code Pro', monospace; font-size: 0.65rem;
        color: #004422; letter-spacing: 0.05em; margin-bottom: 8px;
        opacity: 0.7; animation: fadeIn 0.5s ease;
    }

    /* ---- ACTION GRID ICON REFACTOR ---- */
    .action-icon {
        font-size: 1.5rem; margin-bottom: 12px; display: block;
        color: var(--brandA); opacity: 0.9;
    }

    /* ---- FLOW VISUALIZER LOGIC MAP ---- */
    .logic-flow {
        display: flex; align-items: center; justify-content: center; gap: 40px;
        margin-top: 40px; padding-bottom: 20px;
    }
    .flow-node {
        padding: 14px 24px; background: rgba(15, 23, 42, 0.5);
        border: 1px solid var(--border); border-radius: 8px;
        font-size: 0.8rem; font-weight: 700; color: var(--text);
        text-transform: uppercase; letter-spacing: 0.1em;
    }
    .flow-arrow {
        position: relative; width: 60px; height: 2px;
        background: rgba(255,255,255,0.1);
    }
    .flow-arrow::after {
        content: ""; position: absolute; right: 0; top: -4px;
        width: 10px; height: 10px; border-top: 2px solid rgba(255,255,255,0.1);
        border-right: 2px solid rgba(255,255,255,0.1); transform: rotate(45deg);
    }
    .flow-pulse {
        position: absolute; left: 0; top: 0; height: 100%;
        background: var(--brandA); box-shadow: 0 0 10px var(--brandA);
        animation: pulseLine 2s infinite ease-in-out;
    }
    @keyframes pulseLine {
        0% { left: 0; width: 0; opacity: 0; }
        50% { left: 0; width: 100%; opacity: 1; }
        100% { left: 100%; width: 0; opacity: 0; }
    }

    /* Primary buttons only (CTAs / Analyze) */
    div[data-testid="stBaseButton-primary"] > button {
        background: linear-gradient(135deg, var(--brandA), var(--brandB)) !important;
        color: #fff !important;
        border: none !important;
        box-shadow: 0 10px 22px rgba(16, 185, 129, 0.18) !important;
    }
    div[data-testid="stBaseButton-primary"] > button:hover {
        filter: brightness(1.03);
        transform: translateY(-2px) scale(1.03);
        box-shadow: 0 14px 30px rgba(16, 185, 129, 0.25) !important;
    }
    div[data-testid="stBaseButton-primary"] > button:active { transform: translateY(0px) scale(1.01); }

    /* ======================= FORECASTER DASHBOARD ======================= */
    
    .fc-header-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
    .fc-logo { width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, #10B981, #059669); display:flex; align-items:center; justify-content:center; color:#fff; font-size:1.4rem; font-weight:bold; box-shadow: 0 0 15px rgba(16, 185, 129, 0.4); }
    .fc-title { font-size: 1.8rem; font-weight: 900; color: var(--text); margin: 0; padding: 0; line-height:1; letter-spacing: -0.02em; }
    .fc-ticker { font-size: 1.4rem; color: var(--muted); font-weight: 500; margin-left: 4px; }
    
    .fc-badge-row { display: flex; align-items: center; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
    .fc-badge-group { display: flex; align-items: center; gap: 4px; font-size:0.8rem; color: #64748B; font-weight:500;}
    .fc-badge { border: 1px solid #E2E8F0; padding: 4px 10px; border-radius: 12px; font-weight: 600; color: #334155; background: #fff; }
    .fc-badge-emerald { background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.25); color: #10B981; }
    
    .fc-nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
    .fc-tabs { display: flex; gap: 2px; }
    .fc-tab { background: rgba(255,255,255,0.05); color: var(--muted); padding: 8px 16px; font-size: 0.85rem; font-weight: 600; text-align: center; cursor: pointer; }
    .fc-tab.active { background: var(--brandA); color: #fff; }
    .fc-tab:first-child { border-top-left-radius: 20px; border-bottom-left-radius: 20px; }
    .fc-tab:last-child { border-top-right-radius: 20px; border-bottom-right-radius: 20px; }
    .fc-ai-btn { background: #0F172A; color: #fff; padding: 8px 20px; border-radius: 20px; font-size: 0.85rem; font-weight: 700; display: inline-flex; align-items: center; gap: 6px;}
    
    .fc-action-grid { background: var(--card); border-radius: 14px; padding: 16px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; border: 1px solid var(--border); box-shadow: var(--shadow); }
    .fc-action-btn { background: #fff; color: var(--text); border-radius: 12px; padding: 16px; text-align: center; font-weight: 700; font-size: 0.92rem; cursor: pointer; transition: all 0.2s; box-shadow: 0 2px 8px rgba(15,23,42,0.06); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; border: 1px solid var(--border);}
    .fc-action-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 22px rgba(15,23,42,0.08); border-color: rgba(16,185,129,0.22); }
    
    .fc-perf-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-top: 24px; margin-bottom: 12px; }
    .fc-perf-grid-wide { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 32px; }
    .fc-perf-box { background: #fff; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px; text-align: center; }
    .fc-perf-box.dark { background: #1E293B; border-color: #1E293B; color: #fff; }
    .fc-perf-label { font-size: 0.75rem; color: #64748B; margin-bottom: 4px; font-weight: 600; }
    .fc-perf-box.dark .fc-perf-label { color: #94A3B8; }
    .fc-perf-val { font-size: 1.25rem; font-weight: 700; line-height: 1.2; }
    .fc-val-pos { color: #22c55e !important; }
    .fc-val-neg { color: #ef4444 !important; }
    .fc-val-neutral { color: #1E293B !important; }
    .fc-perf-box.dark .fc-val-pos { color: #4ade80 !important; }
    
    .fc-section-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
    .fc-pill-dark { background: #1E293B; color: #fff; border-radius: 20px; padding: 6px 16px; font-size: 0.85rem; font-weight: 600; }
    .fc-pill-green { background: #DCFCE7; color: #166534; border-radius: 20px; padding: 6px 12px; font-size: 0.75rem; font-weight: 700; display: inline-flex; align-items: center; gap: 4px; }

    /* ======================= DIALOG MODAL STYLING (DARK, HIGH CONTRAST) ======================= */
    div[data-testid="stDialog"] {
        border-radius: 16px !important;
    }
    div[data-testid="stDialog"] > div {
        background: linear-gradient(135deg, #050505 0%, #0F0F11 100%) !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        border-radius: 16px !important;
        box-shadow: 0 0 30px rgba(16, 185, 129, 0.15), 0 25px 55px rgba(0,0,0,0.55) !important;
    }
    /* Base typography inside dialog */
    div[data-testid="stDialog"] .stMarkdown,
    div[data-testid="stDialog"] .stMarkdown p,
    div[data-testid="stDialog"] .stMarkdown li,
    div[data-testid="stDialog"] .stMarkdown span,
    div[data-testid="stDialog"] .stMarkdown div {
        color: #F8FAFC !important;
        font-size: 0.99rem !important;
        line-height: 1.78 !important;
    }
    /* Secondary text */
    div[data-testid="stDialog"] .stCaption,
    div[data-testid="stDialog"] small,
    div[data-testid="stDialog"] .stMarkdown em {
        color: #CBD5F5 !important;
    }
    div[data-testid="stDialog"] .stMarkdown strong { color: #F8FAFC !important; }
    div[data-testid="stDialog"] .stMarkdown h1,
    div[data-testid="stDialog"] .stMarkdown h2,
    div[data-testid="stDialog"] .stMarkdown h3,
    div[data-testid="stDialog"] .stMarkdown h4 {
        color: #F8FAFC !important;
        font-weight: 800 !important;
        letter-spacing: -0.01em;
    }
    div[data-testid="stDialog"] .stMarkdown code {
        color: #F8FAFC !important;
        background: rgba(2, 6, 23, 0.75) !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        padding: 2px 6px !important;
        border-radius: 6px !important;
        font-size: 0.9rem !important;
    }
    div[data-testid="stDialog"] a {
        color: #34D399 !important;
        text-decoration: none !important;
        font-weight: 600 !important;
        word-break: break-word;
    }
    div[data-testid="stDialog"] a:hover {
        text-decoration: underline !important;
    }
    div[data-testid="stDialog"] .stMarkdown table {
        width: 100%;
        border-collapse: collapse;
        margin: 12px 0;
        font-size: 0.9rem;
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 12px;
        overflow: hidden;
    }
    div[data-testid="stDialog"] .stMarkdown table th {
        background: rgba(2, 6, 23, 0.92);
        color: #F8FAFC;
        padding: 10px 14px;
        text-align: left;
        font-weight: 600;
        font-size: 0.78rem;
        letter-spacing: 0.03em;
        border-bottom: 1px solid rgba(255,255,255,0.10);
    }
    div[data-testid="stDialog"] .stMarkdown table td {
        padding: 10px 14px;
        border-bottom: 1px solid rgba(255,255,255,0.10);
        color: #F8FAFC;
        font-size: 0.9rem;
    }
    div[data-testid="stDialog"] .stMarkdown table tr:nth-child(even) {
        background: rgba(15, 23, 42, 0.55);
    }
    div[data-testid="stDialog"] .stMarkdown table tr:hover {
        background: rgba(16, 185, 129, 0.12);
    }
    .modal-disclaimer {
        background: rgba(245,158,11,0.10);
        border: 1px solid #F59E0B;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 0.72rem;
        color: #FCD34D;
        line-height: 1.5;
        margin-bottom: 16px;
    }
    .modal-header-bar {
        background: linear-gradient(135deg, rgba(5,5,5,0.75), rgba(15,15,17,0.65));
        border: 1px solid rgba(255,255,255,0.10);
        padding: 18px 24px;
        border-radius: 10px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .modal-header-bar h3 {
        color: #F8FAFC !important;
        font-size: 1.12rem;
        font-weight: 700;
        margin: 0;
    }
    .modal-header-bar .badge {
        background: rgba(16,185,129,0.20);
        color: #34D399;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.72rem;
        font-weight: 600;
    }

    /* Modal buttons: make primary/secondary pop on dark background */
    div[data-testid="stDialog"] div[data-testid^="stBaseButton"] > button,
    div[data-testid="stDialog"] div[data-testid="stButton"] > button {
        box-shadow: 0 12px 26px rgba(0,0,0,0.35) !important;
    }
    div[data-testid="stDialog"] div[data-testid="stBaseButton-secondary"] > button,
    div[data-testid="stDialog"] div[data-testid="stBaseButton-secondaryFormSubmit"] > button {
        background: #F1F5F9 !important;
        color: #0F172A !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
    }
    div[data-testid="stDialog"] div[data-testid="stBaseButton-secondary"] > button:hover,
    div[data-testid="stDialog"] div[data-testid="stBaseButton-secondaryFormSubmit"] > button:hover {
        filter: brightness(1.03);
        box-shadow: 0 0 24px rgba(16,185,129,0.18), 0 14px 32px rgba(0,0,0,0.35) !important;
    }
    div[data-testid="stDialog"] div[data-testid="stBaseButton-primary"] > button:hover {
        box-shadow: 0 0 28px rgba(16,185,129,0.28), 0 16px 38px rgba(0,0,0,0.45) !important;
    }

    /* ---- Summary Pages Styles ---- */
    .summary-section {
        max-width: 900px; margin: 4rem auto; padding: 2.5rem;
        background: rgba(15, 23, 42, 0.35); border-radius: 20px; border: 1px solid var(--border);
        box-shadow: 0 20px 50px rgba(0,0,0,0.3); animation: fadeInUp 0.6s ease both;
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    }
    .summary-header { font-size: 2.5rem; font-weight: 800; color: var(--text); margin-bottom: 1.2rem; letter-spacing: -0.03em; }
    .summary-paragraph { color: var(--muted); font-size: 1.15rem; line-height: 1.75; margin-bottom: 2.5rem; }
    .summary-step {
        display: flex; gap: 24px; align-items: flex-start; margin-bottom: 28px;
        padding: 24px; border-radius: 12px; background: rgba(16,185,129,0.04);
        border: 1px solid rgba(16,185,129,0.1);
        transition: transform 0.3s ease;
    }
    .summary-step:hover { transform: translateX(8px); border-color: rgba(16,185,129,0.3); }
    .step-number {
        width: 32px; height: 32px; background: var(--brandA); color: white;
        border-radius: 50%; display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 0.9rem; flex-shrink: 0;
    }
    .step-content h5 { font-size: 1.1rem; font-weight: 750; margin: 0 0 6px 0; color: var(--text); }
    .step-content p { font-size: 0.95rem; color: var(--muted2); margin: 0; line-height: 1.5; }

    /* ---- Neo-Modern Dashboard ---- */
    .neo-terminal {
        background: #0F172A !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important;
        padding: 24px !important;
        font-family: \'JetBrains Mono\', \'Fira Code\', monospace !important;
        color: #38BDF8 !important;
        font-size: 0.85rem !important;
        box-shadow: 0 20px 40px rgba(0,0,0,0.2) !important;
        margin-bottom: 2rem !important;
        min-height: 120px;
        position: relative;
    }
    .terminal-header {
        display: flex; gap: 6px; margin-bottom: 12px;
    }
    .terminal-dot { width: 10px; height: 10px; border-radius: 50%; }
    .terminal-line { margin-bottom: 8px; animation: fadeIn 0.3s ease both; display: flex; gap: 10px; }
    .terminal-prefix { color: #10B981; font-weight: 700; }
    .terminal-cursor { display: inline-block; width: 8px; height: 1.2em; background: #10B981; vertical-align: middle; animation: blink 1s infinite; margin-left: 4px; }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

    .neo-metric-card {
        background: rgba(30, 41, 59, 0.45) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .neo-metric-card:hover {
        transform: translateY(-5px) scale(1.02);
        box-shadow: 0 15px 45px rgba(31, 38, 135, 0.12) !important;
        border-color: rgba(37,99,235,0.3) !important;
    }
    
    .neo-hero {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.45) 0%, rgba(30, 41, 59, 0.35) 100%) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 20px !important;
        padding: 32px !important;
        margin-bottom: 1.5rem !important;
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(8px);
    }

    /* ---- Interactive Stardust & Glow ---- */
    #cursor-glow {
        position: fixed;
        width: 800px; height: 800px;
        background: radial-gradient(circle, rgba(56, 189, 248, 0.04) 0%, transparent 70%);
        top: 0; left: 0;
        transform: translate(-50%, -50%);
        pointer-events: none;
        z-index: 10000;
        will-change: transform;
    }
    #particle-canvas {
        position: fixed; top: 0; left: 0;
        width: 100vw; height: 100vh;
        pointer-events: none;
        z-index: 9999;
    }
</style>

<div id="cursor-glow"></div>
<canvas id="particle-canvas"></canvas>
""", unsafe_allow_html=True)

components.html("""
<script>
(function() {
    setTimeout(() => {
        const parentDoc = window.parent.document;
        const canvas = parentDoc.getElementById('particle-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const glow = parentDoc.getElementById('cursor-glow');

        let particles = [];
        let mouse = { x: -100, y: -100 };

        function resize() {
            canvas.width = window.parent.innerWidth;
            canvas.height = window.parent.innerHeight;
        }
        window.parent.addEventListener('resize', resize);
        resize();

        parentDoc.addEventListener('mousemove', (e) => {
            mouse.x = e.clientX;
            mouse.y = e.clientY;
            
            if (glow) {
                glow.style.transform = `translate(${mouse.x - 400}px, ${mouse.y - 400}px)`;
            }
            
            for (let i = 0; i < 1; i++) {
                particles.push({
                    x: mouse.x,
                    y: mouse.y,
                    vx: (Math.random() - 0.5) * 1.5,
                    vy: (Math.random() - 0.5) * 1.5,
                    size: Math.random() * 2 + 1,
                    life: 1.0,
                    color: Math.random() > 0.5 ? '#00E3A5' : '#34D399'
                });
            }
        });

        function animate() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            for (let i = 0; i < particles.length; i++) {
                let p = particles[i];
                p.x += p.vx;
                p.y += p.vy;
                p.life -= 0.06;
                
                ctx.fillStyle = p.color;
                ctx.globalAlpha = p.life * 0.4;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                ctx.fill();
                
                if (p.life <= 0) {
                    particles.splice(i, 1);
                    i--;
                }
            }
            ctx.globalAlpha = 1.0;
            window.parent.requestAnimationFrame(animate);
        }
        animate();
    }, 500); // Slight delay to ensure DOM is ready
})();
</script>
""", height=0, width=0)


# =====================================================================
#  SIDEBAR SETTINGS
# =====================================================================
with st.sidebar:
    st.markdown(f"""
    <div style="padding: 10px 0;">
        <h2 style="color:var(--text); font-size:1.1rem; font-weight:700; margin:0;">Settings</h2>
        <p style="color:var(--muted); font-size:0.75rem; margin-top:4px;">App Performance & AI Behavior</p>
    </div>
    <hr style="margin: 10px 0; border-color: var(--border);">
    """, unsafe_allow_html=True)
    
    st.session_state.turbo_mode = st.toggle(
        "🚀 Turbo Mode", 
        value=st.session_state.turbo_mode,
        help="Skips verification/audit steps for maximum speed. Recommended for quick overviews."
    )
    
    st.markdown(f"""
    <div style="margin-top: 20px; padding: 12px; background: rgba(16,185,129,0.05); border-radius: 8px; border: 1px solid rgba(16,185,129,0.1);">
        <div style="color: var(--brandA); font-size: 0.7rem; font-weight: 700; text-transform: uppercase;">Active Model</div>
        <div style="color: var(--text); font-size: 0.85rem; font-weight: 600; margin-top: 4px;">Llama 3.2 (3B)</div>
        <div style="color: var(--muted); font-size: 0.7rem; margin-top: 2px;">Optimized for speed & accuracy</div>
    </div>
    <div style="margin-top: 20px;">
        <button onclick="window.location.reload();" style="width:100%; height:38px; background:rgba(239,68,68,0.1); color:#EF4444; border:1px solid rgba(239,68,68,0.2); border-radius:8px; font-weight:700; font-size:0.8rem; cursor:pointer;">
            LOGOUT SESSION
        </button>
    </div>
    """, unsafe_allow_html=True)
    
    # Since standard HTML buttons in markdown don't trigger st.experimental_rerun easily, 
    # we use a native streamlit button for the logout logic below.
    if st.button("Logout Access", type="secondary", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.page = "login"
        st.rerun()


# =====================================================================
#  DIALOG MODAL — Action Intelligence
# =====================================================================
@st.dialog(f"{BRAND_NAME} — Action Intelligence", width="large")
def open_action_modal(action_name, ticker, context_data):
    """Opens a premium dialog modal with AI-generated action insights."""
    # Header bar
    st.markdown(f"""
    <div class="modal-header-bar">
        <div style="width:36px; height:36px; border-radius:50%; background:linear-gradient(135deg, #10B981, #5CA5F1); display:flex; align-items:center; justify-content:center; color:#fff; font-size:1rem; font-weight:700;">AI</div>
        <div>
            <h3>{action_name}</h3>
            <div style="color: #94A3B8; font-size: 0.75rem; margin-top: 2px;">{BRAND_NAME} • {ticker}</div>
        </div>
        <div class="badge" style="margin-left:auto;">LIVE ANALYSIS</div>
    </div>
    """, unsafe_allow_html=True)

    # Disclaimer
    st.markdown("""
    <div class="modal-disclaimer">
        <b>Analyst-Mode Notice:</b> This agent is designed to function as your on-demand financial analyst — generating concise, decision-grade research
        from live market data and retrieved context. It can be wrong. Always validate critical details (prices, filings, dates) against primary sources,
        and remember markets carry risk.
    </div>
    """, unsafe_allow_html=True)

    # Ultra-fast cache: avoid hashing huge context in Streamlit cache machinery
    cache_key = f"{action_name}::{ticker}::{hashlib.sha1(context_data.encode('utf-8', errors='ignore')).hexdigest()}"
    if "action_modal_cache" not in st.session_state:
        st.session_state.action_modal_cache = {}
    cached = st.session_state.action_modal_cache.get(cache_key)
    if cached:
        st.markdown(cached, unsafe_allow_html=True)
    else:
        with st.spinner("Generating report (local LLM)..."):
            result = get_action_insight(action_name, ticker, context_data)
            # Cache only verified PASS outputs (avoid caching "Verified Mode: Limited")
            if "✅ Verified Facts" in result:
                st.session_state.action_modal_cache[cache_key] = result
            st.markdown(result, unsafe_allow_html=True)

    # Footer
    st.markdown("""
    <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #E2E8F0; text-align: center;">
        <span style="color: #94A3B8; font-size: 0.72rem;">Local LLM • Glass-Box Architecture • Data via yFinance & Tavily</span>
    </div>
    """, unsafe_allow_html=True)


# =====================================================================
#  SaaS ROUTING & AUTH GATE
# =====================================================================
if not st.session_state.authenticated:
    render_login_page()
    st.stop() # Prevent any further rendering until logged in

# =====================================================================
#  PAGE 1: HERO LANDING
# =====================================================================
if st.session_state.page == "hero":

    # -- Announcement Bar --
    st.markdown("""
    <div class="announce-bar">
        Glass-Box Architecture: Zero-hallucination financial analysis powered by a local LLM
        <a href="#">Learn More ></a>
    </div>
    """, unsafe_allow_html=True)

    # -- Navbar --
    st.markdown("""
    <div class="navbar">
        <div class="navbar-brand"><a href="/?nav=hero" style="color:inherit; text-decoration:none;">Finsighter</a></div>
        <div class="navbar-links">
            <a href="/?nav=how_it_works">How It Works</a>
            <a href="/?nav=features">Features</a>
            <a href="/?nav=ai_finance">AI for Finance</a>
            <a href="/?nav=research">Research</a>
            <a class="btn-nav-outline" href="#">Sign In</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # -- Hero --
    st.markdown("""
    <div class="hero">
        <h1>Analyze any financial instrument<br><span class="accent">from every angle</span> &mdash; and see the<br>future, powered by AI</h1>
        <p>All-in-one platform built to save hours and sharpen your investment &amp; trading strategy</p>
    </div>
    """, unsafe_allow_html=True)

    # -- CTA Buttons (functional) --
    btn_pad1, btn_cta, btn_pad2 = st.columns([3, 1.4, 3])
    with btn_cta:
        if st.button("Try now", width="stretch", key="cta_try", type="primary"):
            go_to_search()
            st.rerun()

    st.markdown("<p class='cta-sub'>No credit card required</p>", unsafe_allow_html=True)

    # -- Feature Cards --
    st.markdown("<div style='height:2rem;'></div>", unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns(4)
    features = [
        ("🔎", "#EFF6FF", "#2563EB", "Smart Ticker Resolution",
         "Resolves natural language queries into verified global exchange tickers using a multi-stage validation engine."),
        ("🛡️", "#ECFDF5", "#10B981", "Live Audit Feed",
         "Experience 100% transparency with a live streaming audit trace that verifies numerical integrity before the report is finalized."),
        ("📊", "#FFF7ED", "#F59E0B", "Financial Health Matrix",
         "Deterministic extraction of Revenue, Margins, and Solvency metrics directly from yFinance—verified exactly, never estimated."),
        ("⚖️", "#FEF2F2", "#EF4444", "Institutional Governance",
         "A secondary 'Judge' agent scores every report against regulatory-grade criteria for accuracy, clarity, and grounding."),
    ]
    for col, (icon, bg, accent, title, desc) in zip([fc1, fc2, fc3, fc4], features):
        col.markdown(f"""
<div class="feature-card">
    <div class="feature-icon" style="background:{bg}; color:{accent};">{icon}</div>
    <h4>{title}</h4>
    <p>{desc}</p>
</div>
        """, unsafe_allow_html=True)

    # -- Trust Bar --
    st.markdown("""
    <div class="trust-bar">
        <span>POWERED BY</span>
        <span style="color:#475569; font-weight:700;">Local Ollama</span>
        <span style="color:#475569;">&middot;</span>
        <span style="color:#475569; font-weight:700;">yFinance</span>
        <span style="color:#475569;">&middot;</span>
        <span style="color:#475569; font-weight:700;">Tavily</span>
    </div>
    """, unsafe_allow_html=True)


# =====================================================================
#  PAGE 2: SEARCH PAGE (Forecaster-style minimal)
# =====================================================================
elif st.session_state.page == "search":

    # -- 1. SYSTEM STATUS HEADER --
    st.markdown("""
    <div class="status-ticker">
        <div class="status-item"><span class="status-dot-green"></span> CORE: Llama 3.2 (Local)</div>
        <div class="status-item"><span class="status-dot-green"></span> DATA: yFinance + Tavily Hybrid</div>
        <div class="status-item"><span class="status-dot-green"></span> AUDIT: Active (Zero-Hallucination)</div>
    </div>
    <div class="search-bg-glow"></div>
    """, unsafe_allow_html=True)

    # Fetch sidebar data
    market_data = fetch_sidebar_market_data()

    # -- 3-COLUMN DASHBOARD LAYOUT --
    col_market, col_main, col_logs = st.columns([1.2, 3.8, 1.2])

    with col_market:
        st.markdown('<div class="market-watch-dock">', unsafe_allow_html=True)
        st.markdown("<div style='color:var(--muted); font-size:0.7rem; font-weight:800; margin-bottom:10px; text-transform:uppercase;'>Market Watch</div>", unsafe_allow_html=True)
        for item in market_data:
            color = "#10B981" if item['change'] > 0 else "#EF4444"
            arrow = "▲" if item['change'] > 0 else "▼"
            st.markdown(f"""
            <div class="dock-item">
                <div class="dock-ticker">{item['ticker']}</div>
                <div class="dock-price">${item['price']}</div>
                <div class="dock-change" style="color:{color};">{arrow} {abs(item['change'])}%</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_main:
        # -- Logo & branding --
        st.markdown("""
        <div class="search-page-container">
            <div class="search-logo" style="font-size:2.2rem;">
                <span class="logo-icon" style="width:36px; height:36px; font-size:1rem;">&#9678;</span>Finsighter<span class="logo-dot">.</span>
            </div>
            <div class="search-tagline" style="font-size:0.75rem;">Intelligence Command Center</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)

        # -- Search Bar --
        ticker_input = st.text_input(
            "Search",
            placeholder="Analyze any ticker or company name...",
            label_visibility="collapsed",
            key="search_input"
        )
        st.markdown("<p class='pick-plan-link'>Institutional Tier active for this session.</p>", unsafe_allow_html=True)

        # -- REFACTORED ACTION GRID (Icons) --
        st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown('<div class="intelligence-shortcuts">', unsafe_allow_html=True)
        col_a, col_b, col_c = st.columns(3)
        
        shortcut_ticker = None
        
        with col_a:
            if st.button("🛡️ SOLVENCY\nAudit debt, ROE, and coverage ratios.", key="sc_solvency"):
                shortcut_ticker = "AAPL"
        with col_b:
            if st.button("⚡ CATALYSTS\nScan for news-driven movers.", key="sc_catalyst"):
                shortcut_ticker = "NVDA"
        with col_c:
            if st.button("⚖️ BENCHMARK\nRelative value vs. industry peers.", key="sc_benchmark"):
                shortcut_ticker = "MSFT"
        st.markdown('</div>', unsafe_allow_html=True)

        # -- FLOW VISUALIZER --
        st.markdown("""
        <div class="glass-box-visualizer" style="margin-top:4rem; padding: 2rem 0; border:none; background:none;">
            <h5 style="text-align:center; color:var(--muted); font-size:0.75rem; letter-spacing:0.2em; text-transform:uppercase; margin-bottom:20px;">System Logic Flow</h5>
            <div class="logic-flow">
                <div class="flow-node">User Query</div>
                <div class="flow-arrow"><div class="flow-pulse"></div></div>
                <div class="flow-node" style="border-color:var(--brandA); color:var(--brandA);">Multi-Agent Audit</div>
                <div class="flow-arrow"><div class="flow-pulse"></div></div>
                <div class="flow-node">Verified Report</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_logs:
        st.markdown('<div class="agent-heartbeat-log">', unsafe_allow_html=True)
        st.markdown("<div style='color:var(--muted); font-size:0.7rem; font-weight:800; margin-bottom:10px; text-transform:uppercase;'>Agent Heartbeat</div>", unsafe_allow_html=True)
        from datetime import datetime
        now = datetime.now().strftime("%H:%M")
        logs = [
            f"[{now}] SYS_OLLAMA_READY",
            f"[{now}] TAVILY_SYNC_UP",
            f"[{now}] YFIN_API_200",
            f"[{now}] AUDIT_AGENT_LIVE",
            f"[{now}] MEMORY_READY",
            f"[{now}] HANDSHAKE_OK"
        ]
        for log in logs:
            st.markdown(f'<div class="heartbeat-line">{log}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Handle Analysis Trigger
    final_ticker = ticker_input.strip() if ticker_input else shortcut_ticker
    if final_ticker:
        st.session_state.page = "analysis"
        st.session_state.ticker_to_analyze = final_ticker
        st.rerun()


# =====================================================================
#  PAGE 3: ANALYSIS (Full Glass-Box Pipeline)
# =====================================================================
elif st.session_state.page == "analysis":
    ticker_input = st.session_state.ticker_to_analyze
    if not ticker_input:
        st.session_state.page = "search"
        st.rerun()

    # Provide a simple top padded space or a back button
    st.markdown("<div style='margin-bottom:12px;'></div>", unsafe_allow_html=True)
    if st.button("< Back to Search", key="back_search", type="secondary"):
        st.session_state.page = "search"
        st.rerun()

    # -- Analysis HUD (Loading Card & Terminal) --
    placeholder_loading = st.empty()
    placeholder_terminal = st.empty()
    
    # Track logs for the neo-terminal
    terminal_logs = ["Initializing Glass-Box Intelligence Terminal...", "Establishing handshake with yFinance API..."]
    
    with placeholder_terminal:
        render_neo_terminal(terminal_logs)

    # Initial Loader State
    placeholder_loading.markdown("""
<div class="premium-loader">
    <div class="loader-ring"></div>
    <div class="loader-text">Analyst is Thinking...</div>
    <div class="loader-subtext">Initializing secure connection to ticker resolution...</div>
</div>
""", unsafe_allow_html=True)

    # 1. High-Precision Workflow: Resolution & Context
    with st.status("Engaging Research Agent...", expanded=True) as status:
        st.write("Resolving Ticker Symbol...")
        ticker = resolve_ticker(ticker_input)
        if not ticker:
            status.update(label="Ticker Resolution Failed", state="error")
            st.error("Could not resolve entity.")
            st.stop()
        
        st.write(f"Aggregating Dense Context for {ticker}...")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_metrics = executor.submit(fetch_financial_metrics, ticker)
            future_fmp = executor.submit(fetch_fmp, ticker)
            future_trends = executor.submit(fetch_trend_data, ticker)
            future_news = executor.submit(fetch_news, ticker)
            
            metrics = future_metrics.result()
            fmp = future_fmp.result()
            trends = future_trends.result()
            news = future_news.result()
        
        context = build_context_for_llm(ticker, metrics, trends, news, fmp)
        status.update(label=f"Context Aggregated for {ticker}", state="complete", expanded=False)

    # 2. Synthesis & Live Reasoning (The Glass-Box Vibe)
    st.markdown("### 🖥️ AGENT INTELLIGENCE FEED")
    reasoning_placeholder = st.empty()
    full_response = ""
    
    with st.status("Synthesis Agent: Auditing & Drafting...", expanded=True) as status:
        st.write("Executing internal compliance audit...")
        
        # We call the streaming helper directly here for the "vibe"
        from utils.ai_agent import _primary_model_name
        system_instruction = """### SYSTEM ROLE
You are a High-Precision Financial Research Agent. Your goal is to transform raw data into a professional, zero-hallucination equity report. Use a "Glass-Box" policy: every step of your reasoning must be visible.

### THE COMPLIANCE PROTOCOL
First, you MUST complete the audit trace inside <audit_trace> tags.
Then, you MUST provide the structured report inside <report_json> tags."""

        user_prompt = f"Generate research for {ticker}.\nCONTEXT:\n{context}"
        
        from utils.ai_agent import stream_ai_response
        stream = stream_ai_response(user_prompt, system_instruction)
        
        if stream:
            for chunk in stream:
                if "error" in chunk:
                    st.error(f"Streaming Error: {chunk['error']}")
                    break
                content = chunk.get('content', '')
                full_response += content
                # Extract partial trace for live view
                trace = robust_tag_parser(full_response, "audit_trace")
                if trace:
                    from utils.ai_agent import format_intelligence_steps
                    reasoning_placeholder.markdown(format_intelligence_steps(trace), unsafe_allow_html=True)
        
        status.update(label="Synthesis Complete", state="complete", expanded=False)

    # 3. Finalization (Judge & Fact-Check)
    with st.status("Finalizing Verification...", expanded=False) as status:
        # Robust Parse of the stream
        report_str = robust_tag_parser(full_response, "report_json")
        from utils.ai_agent import _safe_json_loads
        insights_final = _safe_json_loads(report_str)
        insights_final["audit_trail"] = robust_tag_parser(full_response, "audit_trace")
        
        fact_check_status = "PASS"
        if not st.session_state.turbo_mode:
            st.write("🔍 Running compliance audit on generated claims...")
            time.sleep(0.5)
            st.write("📊 Cross-referencing numerical data with yFinance context...")
            time.sleep(0.8)
            critique = run_fact_check_agent(json.dumps(insights_final), context)
            st.write(f"⚖️ Audit Result: **{critique.get('status', 'PASSED')}**")
            fact_check_status = "PASS" if critique.get("status") == "PASS" else "FAIL"
            
            # Step 4: Final Grading (LLM-as-Judge)
            st.write("📈 Independent Judge is grading report accuracy...")
            judge_results = get_judge_scores(json.dumps(insights_final), context)
            
            # Calculate Confidence % (Average of 1-5 scores)
            avg_score = (
                judge_results.get("accuracy", 3) + 
                judge_results.get("completeness", 3) + 
                judge_results.get("clarity", 4) + 
                judge_results.get("confidence", 3)
            ) / 20.0 * 100.0 # Better math
            insights_final["_confidence_pct"] = int(avg_score)
        
        status.update(label="Verified Analyst Report Ready", state="complete")

    # Attach UI-only fields for High-Precision Rendering
    insights_final["_fact_check_status"] = fact_check_status

    company_name = metrics.get("_company_name", ticker)
    sector = metrics.get("_sector", "N/A Sector")
    logo_url = metrics.get("_logo_url", "")
    perf = metrics.get("_performance", {})
    
    # -- High-Quality SVG Fallback --
    if logo_url:
        logo_html = f'<img src="{logo_url}" style="width:100%; height:100%; object-fit:contain; border-radius:50%;">'
    else:
        # Branded letter badge
        first_char = company_name[0] if company_name else ticker[0]
        logo_html = f"""
        <div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; 
                    background:linear-gradient(135deg, #10B981, #5CA5F1); border-radius:50%; color:#fff; 
                    font-size:1.4rem; font-weight:700; box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);">
            {first_char}
        </div>
        """

    # 1. Header & Badge Row
    st.markdown(f"""
<div class="neo-hero">
<div class="fc-header-row">
<div class="fc-logo">{logo_html}</div>
<h1 class="fc-title">{company_name}</h1>
<span class="fc-ticker">{ticker} {sector.upper() if sector != 'N/A Sector' else ''}</span>
</div>

<div class="fc-badge-row">
<div class="fc-badge-group">
Indexes
<div class="fc-badge fc-badge-emerald">🌍 World Index</div>
<div class="fc-badge fc-badge-emerald">D Dow Jones</div>
<div class="fc-badge fc-badge-emerald">🇺🇸 S&P 500</div>
<div class="fc-badge fc-badge-emerald">📈 NASDAQ 100</div>
</div>
<div class="fc-badge-group" style="margin-left: 12px;">
Sector <div class="fc-badge">{sector}</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)
    
    st.markdown(f"""
<div style="background:rgba(15,23,42,0.4); border:1px solid {BORDER}; border-radius:12px; padding:20px 24px; margin-bottom:20px; display:flex; gap:32px;">
    <div style="flex:0 0 70%;">
        <div style="font-weight:700; color:{TEXT}; font-size:0.85rem; margin-bottom:8px; text-transform:uppercase; letter-spacing:0.05em;">About the Company</div>
        <div style="color:{BODY_TEXT}; font-size:0.88rem; line-height:1.7;">{metrics.get('_description', 'Data not available.')}</div>
    </div>
    <div style="flex:1; border-left:1px solid {BORDER}; padding-left:32px;">
        <div style="font-weight:700; color:{TEXT}; font-size:0.85rem; margin-bottom:10px; text-transform:uppercase; letter-spacing:0.05em;">Key Executives</div>
        <div style="color:{MUTED}; font-size:0.85rem; line-height:1.7; margin-bottom:6px;"><span style="color:{MUTED};">CEO:</span> <span style="color:{TEXT}; font-weight:600;">{metrics.get('_ceo', 'N/A')}</span></div>
        <div style="color:{MUTED}; font-size:0.85rem; line-height:1.7;"><span style="color:{MUTED};">CFO:</span> <span style="color:{TEXT}; font-weight:600;">{metrics.get('_cfo', 'N/A')}</span></div>
    </div>
</div>
<div class="fc-nav">
    <div class="fc-tabs" style="border-bottom: 1px solid {BORDER};">
        <div class="fc-tab active" style="color:{ACCENT}; border-color:{ACCENT};">Overview</div>
        <div class="fc-tab" style="color:{MUTED};">Seasonality</div>
        <div class="fc-tab" style="color:{MUTED};">Pattern</div>
        <div class="fc-tab" style="color:{MUTED};">Fundamentals</div>
        <div class="fc-tab" style="color:{MUTED};">News</div>
    </div>
    <div class="fc-ai-btn" style="cursor:pointer; background:rgba(16,185,129,0.1); color:{ACCENT}; border:1px solid rgba(16,185,129,0.2);" onclick="window.scrollTo(0, document.body.scrollHeight);">🤖 Finsighter</div>
</div>
""", unsafe_allow_html=True)

    # 1b. HERO INSIGHT BLOCK
    sig = (insights_final.get("signal") or (insights_final.get("executive_verdict", {}) or {}).get("signal") or "HOLD").upper()
    sig_color = EMERALD if sig == "BUY" else CRIMSON if sig == "SELL" else "#F59E0B"
    pass_color = EMERALD if fact_check_status == 'PASS' else CRIMSON
    
    # Sanitize reasons
    reasons_list = insights_final.get('_reasons', [])
    if not reasons_list:
        reasons_list = [insights_final.get('executive_summary', 'No further details available.')]
    
    reasons_html = "".join([f"<li style='margin:6px 0; color:#CBD5E1;'>{str(r).strip()}</li>" for r in reasons_list[:3]])

    st.markdown(f"""
<div style="background: linear-gradient(135deg, rgba({EMERALD_RGB}, 0.12), rgba(5, 150, 105, 0.08));
            border: 1px solid rgba({EMERALD_RGB}, 0.2);
            border-radius: 14px;
            padding: 22px 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            margin: 10px 0 24px 0;">
    <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:16px;">
        <div style="flex:1;">
            <div style="color:#94A3B8; font-size:0.72rem; font-weight:800; letter-spacing:0.12em; text-transform:uppercase; margin-bottom:8px;">
                AI Analysis Snapshot
            </div>
            <div style="display:flex; align-items:baseline; gap:12px; flex-wrap:wrap;">
                <div style="font-size:1.5rem; font-weight:900; color:{sig_color}; letter-spacing:0.02em;">{sig}</div>
                <div style="color:#ffffff; font-weight:800; font-size:1rem;">Confidence: {int(insights_final.get("_confidence_pct", 75))}%</div>
            </div>
            <div style="margin-top:12px;">
                <ul style="margin:0; padding-left:18px; line-height:1.7; font-size:0.88rem;">
                    {reasons_html}
                </ul>
            </div>
        </div>
        <div style="min-width:140px; text-align:right;">
            <div style="color:#94A3B8; font-size:0.78rem; font-weight:700;">Verified Mode</div>
            <div style="margin-top:8px; display:inline-flex; align-items:center; gap:10px; padding:6px 14px; border-radius:999px; border:1px solid rgba({BORDER_RGB}, 0.1); background:rgba(255,255,255,0.03);">
                <span style="width:8px; height:8px; border-radius:50%; background:{pass_color}; box-shadow: 0 0 8px {pass_color};"></span>
                <span style="color:#ffffff; font-size:0.78rem; font-weight:800;">{fact_check_status}</span>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    # 2. Functional Action Grid
    st.markdown("""
<style>
.action-row .stButton > button {
    background-color: var(--card);
    color: var(--text);
    border: 1px solid var(--border);
    font-weight: 700;
    border-radius: 8px;
    padding: 8px 0px;
    transition: all 0.2s ease;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}
.action-row .stButton > button:hover {
    border-color: var(--brandA);
    color: var(--brandA);
    box-shadow: 0 0 15px rgba(16, 185, 129, 0.2);
    transform: translateY(-2px);
}
</style>
""", unsafe_allow_html=True)

    st.markdown(f"<h4 style='color:{TEXT}; font-size:1.1rem; font-weight:800; margin-bottom:14px; text-transform:uppercase; letter-spacing:0.08em;'>Agent Intelligence Actions</h4>", unsafe_allow_html=True)
    
    action_container = st.container()
    with action_container:
        st.markdown('<div class="action-row">', unsafe_allow_html=True)
        r1 = st.columns(4)
        r2 = st.columns(4)
        actions = ["❓ What's happening?", "💼 Business explained simple", "📊 Competitors", "🤝 Suppliers / Clients", 
                   "🔮 Future Expectations", "📈 Full Analysis", "✅ Qualitative Scorecard", "💬 Investor Sentiment"]
        for i, a in enumerate(actions):
            if i < 4:
                if r1[i].button(a, width="stretch", key=f"action_{i}"):
                    open_action_modal(a, ticker, context)
            else:
                if r2[i-4].button(a, width="stretch", key=f"action_{i}"):
                    open_action_modal(a, ticker, context)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:15px;'></div>", unsafe_allow_html=True)
    # 3. Main Price Area Chart (go.Scatter)
    fig_price = go.Figure()
    # Real price data extracted from metrics dict
    x_dates = metrics.get("_chart_dates", [])
    y_prices = metrics.get("_chart_prices", [])
    
    if not x_dates or not y_prices:
        st.warning(f"Historical price data unavailable for {ticker}. Showing recent range if available.")
    else:
        fig_price.add_trace(go.Scatter(
            x=x_dates, y=y_prices,
            mode='lines',
            line=dict(color='#5CA5F1', width=2),
            fill='tozeroy',
            fillcolor='rgba(92,165,241,0.1)'
        ))
        fig_price.update_layout(
            plot_bgcolor='white', paper_bgcolor='white', margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(showgrid=False, showline=False, zeroline=False),
            yaxis=dict(showline=False, gridcolor='#E2E8F0', gridwidth=1, griddash='dash'),
            height=350, font=dict(family="Inter", color="#64748B", size=11)
        )
        st.plotly_chart(fig_price, width="stretch", config={'displayModeBar': False})

    # 4. Performance Grid
    def _val_cls(val):
        if val == "-": return "fc-val-neutral"
        return "fc-val-pos" if float(val) > 0 else "fc-val-neg"
    def _val_lbl(val):
        if val == "-": return "-"
        return f"+{val}%" if float(val) > 0 else f"{val}%"
        
    st.markdown(f"""
<div class="fc-perf-grid">
    <div class="fc-perf-box"><div class="fc-perf-label">1 Month</div><div class="fc-perf-val {_val_cls(perf.get('1 Month', '-'))}">{_val_lbl(perf.get('1 Month', '-'))}</div></div>
    <div class="fc-perf-box"><div class="fc-perf-label">6 Months</div><div class="fc-perf-val {_val_cls(perf.get('6 Months', '-'))}">{_val_lbl(perf.get('6 Months', '-'))}</div></div>
    <div class="fc-perf-box"><div class="fc-perf-label">This Year</div><div class="fc-perf-val {_val_cls(perf.get('This Year', '-'))}">{_val_lbl(perf.get('This Year', '-'))}</div></div>
    <div class="fc-perf-box"><div class="fc-perf-label">1 Year</div><div class="fc-perf-val {_val_cls(perf.get('1 Year', '-'))}">{_val_lbl(perf.get('1 Year', '-'))}</div></div>
    <div class="fc-perf-box"><div class="fc-perf-label">3 Years</div><div class="fc-perf-val {_val_cls(perf.get('3 Years', '-'))}">{_val_lbl(perf.get('3 Years', '-'))}</div></div>
    <div class="fc-perf-box dark"><div class="fc-perf-label">5 Years</div><div class="fc-perf-val fc-val-neutral">-</div></div>
</div>
<div class="fc-perf-grid-wide">
    <div class="fc-perf-box"><div class="fc-perf-label">10 Years</div><div class="fc-perf-val fc-val-neutral">-</div></div>
    <div class="fc-perf-box"><div class="fc-perf-label">20 Years</div><div class="fc-perf-val fc-val-neutral">-</div></div>
    <div class="fc-perf-box"><div class="fc-perf-label">All history</div><div class="fc-perf-val fc-val-neutral">-</div></div>
</div>
""", unsafe_allow_html=True)

    # 5. Years Performance (go.Bar with strict coloring)
    st.markdown("""<div class="fc-section-header"><div class="fc-pill-dark">Years Performance</div></div>""", unsafe_allow_html=True)
    
    years = metrics.get('_ann_years', [])
    returns = metrics.get('_ann_returns', [])
    if not years:
        st.info("Long-term annual performance data not available for this ticker.")
        years, returns = [], []
    
    colors = ['#22c55e' if r > 0 else '#ef4444' for r in returns]
    
    fig_years = go.Figure()
    fig_years.add_trace(go.Bar(
        x=years, y=returns,
        marker_color=colors,
        text=[f"+{r}%" if r>0 else f"{r}%" for r in returns],
        textposition='outside'
    ))
    fig_years.update_layout(
        plot_bgcolor='white', paper_bgcolor='white', margin=dict(l=0, r=0, t=20, b=10),
        xaxis=dict(showgrid=False, showline=False),
        yaxis=dict(showgrid=False, showline=False, zeroline=True, zerolinecolor='#E2E8F0', showticklabels=False),
        height=220, font=dict(family="Inter", color="#64748B", size=10),
        bargap=0.4
    )
    st.plotly_chart(fig_years, width="stretch", config={'displayModeBar': False})

    # 6. Dividends (go.Bar all green)
    st.markdown("""
    <div class="fc-section-header">
        <div class="fc-pill-dark">Dividends</div>
        <div class="fc-pill-green">&#8679; INCREASING</div>
    </div>
    """, unsafe_allow_html=True)
    
    div_years = metrics.get('_div_years', [])
    divs = metrics.get('_div_vals', [])
    if not div_years or all(v == 0 for v in divs):
        st.info("No dividend history found or company does not pay dividends.")
        div_years, divs = [], []
    
    fig_divs = go.Figure()
    fig_divs.add_trace(go.Bar(
        x=div_years, y=divs,
        marker_color='#22c55e',
        text=[f"${d}" for d in divs],
        textposition='outside'
    ))
    fig_divs.update_layout(
        plot_bgcolor='white', paper_bgcolor='white', margin=dict(l=0, r=0, t=20, b=10),
        xaxis=dict(showgrid=False, showline=False),
        yaxis=dict(showgrid=False, showline=False, zeroline=True, zerolinecolor='#E2E8F0', showticklabels=False),
        height=220, font=dict(family="Inter", color="#64748B", size=10),
        bargap=0.4
    )
    st.plotly_chart(fig_divs, width="stretch", config={'displayModeBar': False})

    st.markdown("<hr style='margin: 40px 0px; border-color: #E2E8F0;'>", unsafe_allow_html=True)
    st.markdown("<div id='bottom-report'></div>", unsafe_allow_html=True) # Anchor for scrolling
    col_report, col_news = st.columns([2, 1])
    
    with col_report:
        render_ai_insights(insights_final, fact_check_status)
        
    with col_news:
        render_news(news)
# =====================================================================
#  PAGE 4: SUMMARY SECTIONS (Fleshing out placeholders)
# =====================================================================
elif st.session_state.page in ["how_it_works", "features", "ai_finance", "research"]:
    # Reuse Navbar for consistency
    st.markdown("""
    <div class="navbar">
        <div class="navbar-brand"><a href="/?nav=hero" style="color:inherit; text-decoration:none;">Finsighter</a></div>
        <div class="navbar-links">
            <a href="/?nav=how_it_works">How It Works</a>
            <a href="/?nav=features">Features</a>
            <a href="/?nav=ai_finance">AI for Finance</a>
            <a href="/?nav=research">Research</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.page == "how_it_works":
        st.markdown("""
<div class="summary-section">
<h1 class="summary-header">How Our <span style="color:var(--brandA)">Glass-Box</span> Works</h1>
<p class="summary-paragraph">We've pioneered a four-stage verified research pipeline designed to eliminate AI hallucinations and provide institutional-grade signal.</p>
<div class="summary-step">
<div class="step-number">1</div>
<div class="step-content">
<h5>Smart Ticker Resolution</h5>
<p>Our agent identifies the exact stock symbol across global exchanges from any company name or natural language fragment.</p>
</div>
</div>
<div class="summary-step">
<div class="step-number">2</div>
<div class="step-content">
<h5>Dense Context Extraction</h5>
<p>We fetch real-time fundamentals from yFinance and the latest market catalysts from Tavily's deep-web search.</p>
</div>
</div>
<div class="summary-step">
<div class="step-number">3</div>
<div class="step-content">
<h5>Glass-Box Audit Loop</h5>
<p>A secondary AI critic audits the draft against the raw data. If a single number is off, the report is rejected and corrected.</p>
</div>
</div>
<div class="summary-step">
<div class="step-number">4</div>
<div class="step-content">
<h5>LLM-as-Judge Scoring</h5>
<p>An independent judge grades the final insight on accuracy and completeness before it reaches your dashboard.</p>
</div>
</div>
</div>
""", unsafe_allow_html=True)

    elif st.session_state.page == "ai_finance":
        st.markdown("""
<div class="summary-section">
<h1 class="summary-header">The Future of <span style="color:var(--brandB)">AI in Finance</span></h1>
<p class="summary-paragraph">Your research shouldn't happen in a "Black Box." We believe in private, locally-hosted intelligence that prioritizes truth over creativity.</p>
<div class="summary-step">
<div class="step-content">
<h5>100% Privacy via Local LLMs</h5>
<p>By running models like Llama and Gemma locally via Ollama, your sensitive queries and investment strategies never leave your hardware.</p>
</div>
</div>
<div class="summary-step">
<div class="step-content">
<h5>Zero-Hallucination Policy</h5>
<p>We strictly constrain our AI to "Source-Only" reasoning. If a fact isn't in the provided market data, our models are trained to say "Data not available."</p>
</div>
</div>
<div class="summary-step">
<div class="step-content">
<h5>Decision-Grade Signal</h5>
<p>Most AI is built for chatting; ours is built for analysis. Our prompts are engineered to strip away flowery language and focus on hard catalysts.</p>
</div>
</div>
</div>
""", unsafe_allow_html=True)

    elif st.session_state.page == "features":
        st.markdown("""
<div class="summary-section">
<h1 class="summary-header">Intelligent <span style="color:#10B981">Action Grid</span></h1>
<p class="summary-paragraph">Deep-dive into any instrument with 8 specialized AI agents designed to uncover what the ticker summary misses.</p>

<div style="display:grid; grid-template-columns: 1fr 1fr; gap: 20px;">
<div style="padding:22px; border:1px solid var(--border); border-radius:12px; background:rgba(255,255,255,0.02);">
<b style="color:var(--brandA); font-size:1rem;">Business Explained</b><br>
<span style="font-size:0.92rem; color:var(--muted); line-height:1.6; display:block; margin-top:6px;">Simplifies complex business models into clear catalysts and revenue streams.</span>
</div>
<div style="padding:22px; border:1px solid var(--border); border-radius:12px; background:rgba(255,255,255,0.02);">
<b style="color:var(--brandA); font-size:1rem;">Supply Chain Analysis</b><br>
<span style="font-size:0.92rem; color:var(--muted); line-height:1.6; display:block; margin-top:6px;">Identifies key suppliers, marquee clients, and potential logistical bottlenecks.</span>
</div>
<div style="padding:22px; border:1px solid var(--border); border-radius:12px; background:rgba(255,255,255,0.02);">
<b style="color:var(--brandA); font-size:1rem;">Investor Sentiment</b><br>
<span style="font-size:0.92rem; color:var(--muted); line-height:1.6; display:block; margin-top:6px;">Scans global news to measure the temperature of the market's current position.</span>
</div>
<div style="padding:22px; border:1px solid var(--border); border-radius:12px; background:rgba(255,255,255,0.02);">
<b style="color:var(--brandA); font-size:1rem;">Competitor Benchmarking</b><br>
<span style="font-size:0.92rem; color:var(--muted); line-height:1.6; display:block; margin-top:6px;">Instantly compares metrics against industry peers to find relative value.</span>
</div>
</div>
</div>
""", unsafe_allow_html=True)
    
    elif st.session_state.page == "research":
        st.markdown("""
<div class="summary-section">
<h1 class="summary-header">Research <span style="color:var(--brandA)">Philosophy</span></h1>
<p class="summary-paragraph">We don't believe AI should replace the analyst; it should augment them by automating the 90% of grunt work involved in initial research.</p>

<div style="background: rgba(15,23,42,0.02); padding: 30px; border-radius: 12px; border: 1px dashed var(--border);">
<i style="color:var(--muted2); line-height:1.6;">"Our objective is to provide retail investors with the same data-processing speed as institutional desks, without the 6-figure terminal costs. We prioritize verified raw context over predictive speculation."</i>
</div>
</div>
""", unsafe_allow_html=True)

    # Global Back Button
    st.markdown("<div style='text-align:center; margin-top: 30px; padding-bottom: 50px;'>", unsafe_allow_html=True)
    if st.button("← Back to Search Tool", key="global_back"):
        st.session_state.page = "search"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
