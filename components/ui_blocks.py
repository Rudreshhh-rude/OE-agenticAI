import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import time
from string import Template

# ═══════════════════════════════════════════════════════════════
#  COMPONENT LIBRARY — Glass-Box Professional UI
# ═══════════════════════════════════════════════════════════════

# ── Color Constants (Institutional Dark Mode) ──
EMERALD = "#10B981"
CRIMSON = "#EF4444"
EMERALD_RGB = "16, 185, 129"
CRIMSON_RGB = "239, 68, 68"
ACCENT  = "#10B981"       # Switched from Blue to Emerald
CARD_BG = "#111827"
BORDER  = "rgba(255,255,255,0.08)"
BORDER_RGB = "255, 255, 255"
MUTED   = "#94A3B8"
TEXT    = "#F9FAFB"
SUBTLE  = "#64748B"
BODY_TEXT = "#E2E8F0"

# We use $variable syntax instead of {variable} to avoid CSS conflicts
EXEC_SUMMARY_TEMPLATE = Template("""
<div style="background:rgba(15,23,42,0.4); border-left:4px solid $border_color; 
            padding:1.2rem 1.4rem; border-radius:6px; margin-bottom:2rem; 
            border:1px solid rgba(255,255,255,0.08); animation: fadeInUp 0.5s ease-out;">
    <p style="color:#E2E8F0; font-size:0.95rem; line-height:1.7; margin:0;">$summary_text</p>
    <div style="margin-top: 1.2rem; border-top:1px solid rgba(255,255,255,0.08); padding-top:0.8rem;">
        <span style="font-size:0.7rem; font-weight:700; color:#94A3B8; text-transform:uppercase; margin-right:8px;">Verdict:</span>
        <span style="background:$badge_bg; color:$badge_text; padding:0.4rem 1.2rem; 
                     font-size:0.8rem; font-weight:700; border-radius:30px;">$verdict</span>
    </div>
</div>
""")


def render_executive_summary(summary_text, verdict):
    # Default fallback if LLM skips the summary
    if not summary_text or len(summary_text) < 5:
        summary_text = "Analysis complete. Awaiting final compliance audit of numerical data..."

    # Define the color-coded "Signaling" for the Verdict
    config = {
        "BUY":  {"color": "#00ff88", "bg": "rgba(0, 255, 136, 0.15)", "border": "#00ff88"},
        "HOLD": {"color": "#F59E0B", "bg": "rgba(245, 158, 11, 0.15)", "border": "#F59E0B"},
        "SELL": {"color": "#EF4444", "bg": "rgba(239, 68, 68, 0.15)", "border": "#EF4444"}
    }
    
    # Get styles for the current verdict (default to HOLD if not found)
    style = config.get(verdict.upper(), config["HOLD"])

    # Substitute variables into the Template
    html_output = EXEC_SUMMARY_TEMPLATE.substitute(
        summary_text=summary_text,
        verdict=verdict.upper(),
        border_color=style["border"],
        badge_bg=style["bg"],
        badge_text=style["color"]
    )

    st.markdown(html_output, unsafe_allow_html=True)


def render_sidebar_brand():
    """Renders the branded sidebar header."""
    st.markdown(f"""
<div style="padding: 1.2rem 0 0.8rem 0;">
    <h1 style="color:{TEXT}; font-size:1.3rem; font-weight:900; margin:0; letter-spacing:-0.02em;">AI <span style="color:{EMERALD}">Financial</span> Insights</h1>
    <p style="color:{MUTED}; font-size:0.75rem; margin:4px 0 0 0; font-weight:600; text-transform:uppercase; letter-spacing:0.05em;">Glass-Box Research Terminal</p>
</div>
<div style="height:1px; background:{BORDER}; margin:0 0 1.2rem 0;"></div>
    """, unsafe_allow_html=True)


def render_sidebar_confidence(score=None, is_loading=False):
    """Renders the AI Confidence Score gauge in the sidebar (1-5 scale)."""
    if is_loading:
        score_text = "—"
        score_color = "#475569"
        ring_pct = 0
    else:
        score_val = score if score else 0
        score_text = f"{score_val}"
        score_color = EMERALD if score_val >= 4 else "#F59E0B" if score_val >= 3 else CRIMSON
        ring_pct = (score_val / 5) * 100  # Convert 1-5 to percentage

    # Animate ring from 0 -> target and use gradient stroke (Emerald -> Mint)
    dash_target = ring_pct * 2.89
    st.markdown(f"""
<div style="text-align:center; padding:1.2rem 0.8rem; background:{CARD_BG}; border-radius:10px; border:1px solid {BORDER}; margin:0.8rem 0; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
    <div style="color:{MUTED}; font-size:0.65rem; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; margin-bottom:0.8rem;">Confidence Score</div>
    <div style="position:relative; width:110px; height:110px; margin:0 auto;">
        <svg width="110" height="110" viewBox="0 0 110 110">
            <defs>
                <linearGradient id="confGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="{EMERALD}" />
                    <stop offset="100%" stop-color="#34D399" />
                </linearGradient>
                <filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%">
                    <feGaussianBlur stdDeviation="3" result="blur"/>
                    <feMerge>
                        <feMergeNode in="blur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
            </defs>
            <circle cx="55" cy="55" r="46" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="6"/>
            <circle cx="55" cy="55" r="46" fill="none" stroke="url(#confGrad)" stroke-width="6"
                    stroke-dasharray="0 289"
                    stroke-dashoffset="0" stroke-linecap="round"
                    transform="rotate(-90 55 55)"
                    filter="url(#softGlow)">
                <animate attributeName="stroke-dasharray"
                         dur="1.2s"
                         fill="freeze"
                         values="0 289; {dash_target:.2f} 289" />
            </circle>
        </svg>
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);">
            <div style="color:{score_color}; font-size:2rem; font-weight:700; line-height:1;">{score_text}</div>
            <div style="color:{MUTED}; font-size:0.6rem; font-weight:500; margin-top:2px;">/ 5</div>
        </div>
    </div>
</div>
    """, unsafe_allow_html=True)


def render_sidebar_status():
    """Renders system status indicators."""
    st.markdown(f"""
<div style="margin-top:0.8rem;">
    <div style="color:{MUTED}; font-size:0.65rem; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; margin-bottom:0.6rem;">System Status</div>
    <div style="display:flex; align-items:center; padding:0.5rem 0.7rem; background:rgba(15,15,15,0.4); border-radius:6px; margin-bottom:0.4rem; border:1px solid {BORDER};">
        <div style="width:6px; height:6px; background:{EMERALD}; border-radius:50%; margin-right:8px;"></div>
        <span style="color:{SUBTLE}; font-size:0.75rem; font-weight:500;">Llama 3.1</span>
        <span style="margin-left:auto; color:{EMERALD}; font-size:0.65rem; font-weight:600;">ONLINE</span>
    </div>
    <div style="display:flex; align-items:center; padding:0.5rem 0.7rem; background:rgba(15,15,15,0.4); border-radius:6px; margin-bottom:0.4rem; border:1px solid {BORDER};">
        <div style="width:6px; height:6px; background:{EMERALD}; border-radius:50%; margin-right:8px;"></div>
        <span style="color:{SUBTLE}; font-size:0.75rem; font-weight:500;">Tavily Search</span>
        <span style="margin-left:auto; color:{EMERALD}; font-size:0.65rem; font-weight:600;">LINKED</span>
    </div>
    <div style="display:flex; align-items:center; padding:0.5rem 0.7rem; background:rgba(15,15,15,0.4); border-radius:6px; border:1px solid {BORDER};">
        <div style="width:6px; height:6px; background:{EMERALD}; border-radius:50%; margin-right:8px;"></div>
        <span style="color:{SUBTLE}; font-size:0.75rem; font-weight:500;">yFinance</span>
        <span style="margin-left:auto; color:{EMERALD}; font-size:0.65rem; font-weight:600;">ACTIVE</span>
    </div>
</div>
    """, unsafe_allow_html=True)


def render_sidebar_pipeline():
    """Renders the pipeline steps."""
    st.markdown(f"""
<div style="margin-top:1.2rem;">
    <div style="color:{MUTED}; font-size:0.65rem; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; margin-bottom:0.6rem;">Pipeline</div>
    <div style="padding-left:1rem; border-left:1px solid {BORDER};">
        <div style="margin-bottom:0.8rem;">
            <div style="color:{SUBTLE}; font-size:0.72rem; font-weight:600;">Ticker Resolution</div>
            <div style="color:#475569; font-size:0.65rem;">Tavily + yFinance validation</div>
        </div>
        <div style="margin-bottom:0.8rem;">
            <div style="color:{SUBTLE}; font-size:0.72rem; font-weight:600;">Data Extraction</div>
            <div style="color:#475569; font-size:0.65rem;">yFinance + Solvency</div>
        </div>
        <div style="margin-bottom:0.8rem;">
            <div style="color:{SUBTLE}; font-size:0.72rem; font-weight:600;">AI Synthesis</div>
            <div style="color:#475569; font-size:0.65rem;">Llama 3.1 Draft</div>
        </div>
        <div style="margin-bottom:0.8rem;">
            <div style="color:{EMERALD}; font-size:0.72rem; font-weight:600;">Fact-Check Audit</div>
            <div style="color:#475569; font-size:0.65rem;">Hallucination kill-switch</div>
        </div>
        <div>
            <div style="color:{SUBTLE}; font-size:0.72rem; font-weight:600;">LLM-as-Judge</div>
            <div style="color:#475569; font-size:0.65rem;">Compliance scoring (1-5)</div>
        </div>
    </div>
</div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  MAIN PANEL COMPONENTS
# ═══════════════════════════════════════════════════════════════

def render_company_strip(ticker: str, metrics: dict, is_evaluating: bool = True, ai_score: int = None):
    """Renders the company header strip."""
    price_change = metrics.get("_price_change_pct", 0.0)
    change_icon = "▲" if price_change >= 0 else "▼"
    change_color = EMERALD if price_change >= 0 else CRIMSON

    st.markdown(f"""
<div style="display:flex; justify-content:space-between; align-items:center; padding:1.4rem 1.8rem; background:{CARD_BG}; border-radius:10px; border:1px solid {BORDER}; margin-bottom:1.5rem; animation: fadeInUp 0.4s ease both;">
    <div>
        <h2 style="color:{TEXT}; margin:0; font-size:1.6rem; font-weight:700; letter-spacing:-0.02em;">{metrics.get('_company_name', ticker.upper())}</h2>
        <div style="display:flex; align-items:center; gap:12px; margin-top:6px;">
            <span style="color:{MUTED}; font-size:0.82rem; font-weight:500;">{ticker.upper()}</span>
            <span style="color:#334155;">·</span>
            <span style="color:{MUTED}; font-size:0.82rem;">{metrics.get('_sector', 'N/A')}</span>
            <span style="color:#334155;">·</span>
            <span style="color:{MUTED}; font-size:0.82rem;">{metrics.get('_market_cap', 'N/A')}</span>
        </div>
    </div>
    <div style="display:flex; align-items:center; gap:6px; padding:0.5rem 1rem; border-radius:6px; border:1px solid {BORDER};">
        <span style="color:{change_color}; font-size:1rem; font-weight:700;">{change_icon} {abs(price_change)}%</span>
    </div>
</div>
    """, unsafe_allow_html=True)


def render_metrics_row(metrics: dict):
    """Renders the 4 KPI metric cards — clean, no emojis."""
    cols = st.columns(4)
    display_keys = [k for k in metrics.keys() if not k.startswith("_") and k != "error"]

    for i, col in enumerate(cols):
        if i >= len(display_keys):
            break

        label = display_keys[i]
        val = metrics[label]

        col.markdown(f"""
<div class="neo-metric-card">
    <div class="kpi-label">{label}</div>
    <div class="kpi-value" style="font-size:1.5rem; font-weight:800; color:var(--text); margin-top:4px;">{val}</div>
</div>
        """, unsafe_allow_html=True)


def render_charts(trend_data: dict):
    """Renders clean financial charts with Emerald/Crimson palette."""
    if "error" in trend_data:
        st.error(f"Chart Data Error: {trend_data['error']}")
        return

    dates = trend_data.get("dates", [])
    if not dates:
        st.info("Insufficient historical data for charting.")
        return

    chart_type = trend_data.get("type", "price_action")

    base_layout = dict(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=35, b=0),
        font=dict(family="Inter, sans-serif", color="#94A3B8", size=11),
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.05)", showline=False,
            tickfont=dict(size=10, color="#64748B"), zeroline=False
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.05)", showline=False,
            tickfont=dict(size=10, color="#64748B"), zeroline=False,
            tickprefix="$", tickformat=".2s"
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#0F0F11", bordercolor="rgba(16,185,129,0.2)",
            font=dict(family="Inter", size=12, color="#F8FAFC")
        ),
        showlegend=False,
    )

    if chart_type == "financials":
        fig_rev = go.Figure()
        fig_rev.add_trace(go.Scatter(
            x=dates, y=trend_data.get("revenue", []),
            mode='lines+markers', name='Revenue',
            line=dict(color=EMERALD, width=3, shape='spline', smoothing=1.15),
            marker=dict(size=5, color=EMERALD),
            fill='tozeroy', fillcolor='rgba(16,185,129,0.08)',
            hovertemplate='%{y:$,.0f}<extra></extra>'
        ))
        fig_rev.update_layout(**base_layout, height=280, template="plotly_dark",
            title=dict(text="REVENUE TREND", font=dict(size=11, color=MUTED), x=0.02))
        st.plotly_chart(fig_rev, use_container_width=True)

        fig_prof = go.Figure()
        fig_prof.add_trace(go.Scatter(
            x=dates, y=trend_data.get("profit", []),
            mode='lines+markers', name='Profit',
            line=dict(color=EMERALD, width=3, shape='spline', smoothing=1.15),
            marker=dict(size=5, color=EMERALD),
            fill='tozeroy', fillcolor='rgba(16,185,129,0.08)',
            hovertemplate='%{y:$,.0f}<extra></extra>'
        ))
        fig_prof.update_layout(**base_layout, height=280, template="plotly_dark",
            title=dict(text="PROFIT TREND", font=dict(size=11, color=MUTED), x=0.02))
        st.plotly_chart(fig_prof, use_container_width=True)
    else:
        prices = trend_data.get("price", [])
        is_positive = prices[-1] >= prices[0] if len(prices) >= 2 else True
        line_color = EMERALD if is_positive else CRIMSON
        fill_color = 'rgba(16,185,129,0.10)' if is_positive else 'rgba(239,68,68,0.08)'

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=prices,
            mode='lines', name='Price',
            line=dict(color=line_color, width=3, shape='spline', smoothing=1.2),
            fill='tozeroy', fillcolor=fill_color,
            hovertemplate='$%{y:.2f}<extra></extra>'
        ))
        fig.update_layout(**base_layout, height=320, template="plotly_dark",
            title=dict(text="6-MONTH PRICE ACTION", font=dict(size=11, color=MUTED), x=0.02),
            yaxis=dict(**base_layout['yaxis'], tickprefix="$", tickformat=".2f"))
        st.plotly_chart(fig, use_container_width=True)


def render_audit_trail(audit_text: str):
    """Renders the human-readable Audit Trace summary."""
    if not audit_text:
        return
        
    st.markdown(f"""
<div style="background: rgba(15, 23, 42, 0.4); 
            border: 1px solid rgba(16, 185, 129, 0.2); 
            border-radius: 12px; 
            padding: 1.5rem; 
            margin-bottom: 2rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);">
    <div style="color:{EMERALD}; font-size:0.75rem; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; margin-bottom:1.2rem; display:flex; align-items:center; gap:8px;">
        <span style="font-size:1.1rem;">🛡️</span> AGENT INTELLIGENCE TRACE
    </div>
    <div style="color:{BODY_TEXT}; font-size:0.92rem; line-height:1.8; font-family: 'Inter', sans-serif;">
        {audit_text}
    </div>
</div>
    """, unsafe_allow_html=True)


def render_ai_insights(insights: dict, fact_check_status: str = "PASS"):
    """Renders the High-Precision research report with Matrix and Landscape."""
    if "error" in insights:
        st.error(f"AI Generation Error: {insights['error']}")
        return

    # Extract High-Precision data
    summary = insights.get("executive_summary", insights.get("summary", ""))
    matrix = insights.get("financial_health_matrix", {})
    landscape = insights.get("competitive_landscape", [])
    signal = str(insights.get("signal", "HOLD")).upper()
    audit_trail = insights.get("audit_trail", "")

    if signal == "BUY":
        signal_class = "signal-buy"
        sig_color = EMERALD
    elif signal == "SELL":
        signal_class = "signal-sell"
        sig_color = CRIMSON
    else:
        signal_class = "signal-hold"
        sig_color = "#F59E0B"

    # ── Header & Badge ──
    badge_rgb = EMERALD_RGB if fact_check_status == "PASS" else CRIMSON_RGB
    badge_color = EMERALD if fact_check_status == "PASS" else CRIMSON
    badge_text = "✓ VERIFIED BY COMPLIANCE AGENT" if fact_check_status == "PASS" else "⚠ AUDIT LOG DISCREPANCY"
    
    st.markdown(f"""
<div class="insight-panel" style="position:relative; border-top:2px solid {sig_color}; padding:2rem; margin-top:2rem; background:{CARD_BG}; border-radius:12px; border:1px solid {BORDER}; box-shadow: 0 10px 40px rgba(0,0,0,0.35);">
    <span style="background:rgba({badge_rgb},0.15); color:{badge_color}; padding:4px 10px; border-radius:20px; font-weight:bold; font-size:0.75rem; float:right; margin-top:-0.5rem; border:1px solid rgba({badge_rgb},0.2);">{badge_text}</span>
    <h3 style="margin:0 0 1.5rem 0; color:{TEXT}; font-size:1.15rem; font-weight:700;">EXECUTIVE SUMMARY</h3>
    
    """, unsafe_allow_html=True)
    
    render_executive_summary(summary, signal)

    # ── Financial Health Matrix ──
    if matrix:
        st.markdown(f'<h4 style="color:{MUTED}; text-transform:uppercase; font-size:0.75rem; letter-spacing:0.1em; margin-bottom:1rem;">FINANCIAL HEALTH MATRIX</h4>', unsafe_allow_html=True)
        m_cols = st.columns(4)
        labels = ["Revenue", "Margins", "Solvency", "Efficiency"]
        keys = ["revenue", "margins", "solvency", "efficiency"]
        
        for col, label, key in zip(m_cols, labels, keys):
            item = matrix.get(key, {"val": "N/A", "status": "Unverified"})
            color = EMERALD if item.get("status") == "Verified" else MUTED
            col.markdown(f"""
<div style="background:rgba(255,255,255,0.02); padding:1rem; border-radius:8px; border:1px solid {BORDER}; text-align:center;">
    <div style="color:{MUTED}; font-size:0.65rem; font-weight:700; text-transform:uppercase;">{label}</div>
    <div style="color:{TEXT}; font-size:1.1rem; font-weight:800; margin:4px 0;">{item.get('val')}</div>
    <div style="color:{color}; font-size:0.55rem; font-weight:700;">● {item.get('status').upper()}</div>
</div>
            """, unsafe_allow_html=True)

    # ── Competitive Landscape ──
    if landscape:
        st.markdown(f'<h4 style="color:{MUTED}; text-transform:uppercase; font-size:0.75rem; letter-spacing:0.1em; margin:2rem 0 1rem 0;">COMPETITIVE LANDSCAPE</h4>', unsafe_allow_html=True)
        for peer in landscape:
            rel_color = EMERALD if peer.get("relationship") == "Direct Rival" else "#38BDF8"
            st.markdown(f"""
<div style="display:flex; justify-content:space-between; align-items:center; padding:0.8rem 1.2rem; background:rgba(15,23,42,0.3); border-radius:8px; border:1px solid {BORDER}; margin-bottom:0.6rem;">
    <div>
        <span style="color:{TEXT}; font-weight:700; font-size:0.9rem;">{peer.get('company')}</span>
        <span style="color:{rel_color}; font-size:0.65rem; font-weight:700; text-transform:uppercase; margin-left:8px; border:1px solid {rel_color}; padding:2px 6px; border-radius:4px;">{peer.get('relationship')}</span>
    </div>
    <div style="color:{BODY_TEXT}; font-size:0.8rem; font-style:italic;">{peer.get('metric_compare')}</div>
</div>
            """, unsafe_allow_html=True)

    # ── Audit Trail ──
    if audit_trail:
        st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
        render_audit_trail(audit_trail)

    # ── Copy Utility ──
    st.markdown("---")
    res_col1, res_col2 = st.columns([1, 1])
    with res_col1:
        if st.button("📋 Copy JSON Analysis", use_container_width=True):
            st.session_state.clipboard = json.dumps(insights, indent=2)
            st.success("JSON copied to context! (Use Ctrl+V)")
    with res_col2:
        st.markdown(f'<div style="text-align:right; color:{MUTED}; font-size:0.7rem; font-weight:600;">REPORT ID: {float(time.time()):.0f}</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_judge_panel(scores: dict):
    """Renders audit scores with 5-point discrete progress bars."""
    if "error" in scores and not scores.get("accuracy"):
        return

    st.markdown(f'<div style="color:{MUTED}; font-size:0.7rem; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; margin:1.5rem 0 0.8rem 0;">AUDIT SCORES</div>', unsafe_allow_html=True)

    dims = [
        ("Accuracy", scores.get("accuracy", 0), EMERALD),
        ("Completeness", scores.get("completeness", 0), EMERALD),
        ("Clarity", scores.get("clarity", 0), EMERALD),
        ("Confidence", scores.get("confidence", 0), "#F59E0B"),
    ]

    c1, c2, c3, c4 = st.columns(4)
    for col, (label, val, color) in zip([c1, c2, c3, c4], dims):
        # Ensure val is in 1-5 range
        if isinstance(val, (int, float)):
            display_val = max(1, min(5, int(val)))
        else:
            display_val = 1

        # Build 5 discrete segments
        segments_html = ""
        for i in range(1, 6):
            if i <= display_val:
                seg_color = color
                seg_opacity = "1"
            else:
                seg_color = "rgba(255,255,255,0.06)"
                seg_opacity = "1"
            segments_html += f'<div style="flex:1; height:6px; background:{seg_color}; border-radius:3px; opacity:{seg_opacity}; transition: background 0.4s ease;"></div>'

        col.markdown(f"""
<div class="judge-card">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem;">
        <span style="color:{MUTED}; font-size:0.65rem; text-transform:uppercase; letter-spacing:0.06em; font-weight:600;">{label}</span>
        <span style="color:{TEXT}; font-weight:700; font-size:1rem;">{display_val}<span style="color:{MUTED}; font-size:0.7rem; font-weight:400;">/5</span></span>
    </div>
    <div style="display:flex; gap:3px;">
        {segments_html}
    </div>
</div>
        """, unsafe_allow_html=True)


def render_news(news: list):
    """Renders clean, light-mode news stream cards."""
    st.markdown(f'<div style="color:{MUTED}; font-size:0.7rem; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; margin-bottom:1rem; margin-top:2rem;">LIVE NEWS STREAM</div>', unsafe_allow_html=True)

    if not news or len(news) == 0:
        st.info("No recent news available.")
        return

    for n in news:
        content = (n.get("content") or "").strip()
        # 1-line "key takeaway" = first sentence-ish
        takeaway = content.split(".")[0].strip()
        if takeaway and len(takeaway) > 110:
            takeaway = takeaway[:110].rsplit(" ", 1)[0] + "…"
        st.markdown(f"""
<div style="margin-bottom:1.1rem; padding:1.2rem; border:1px solid {BORDER}; border-radius:12px; background:{CARD_BG}; box-shadow: 0 8px 32px rgba(0,0,0,0.25); transition: transform 0.2s ease;">
    <div style="color:{TEXT}; font-size:0.92rem; font-weight:800; margin-bottom:0.35rem; line-height:1.35;">
        <a href="{n.get('url', '#')}" target="_blank" style="color:inherit; text-decoration:none;">{n.get('title')}</a>
    </div>
    <div style="color:{MUTED}; font-size:0.76rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.35rem;">Key takeaway</div>
    <div style="color:{BODY_TEXT}; font-size:0.85rem; line-height:1.55; margin-bottom:0.55rem;">{takeaway if takeaway else "Not available."}</div>
    <div style="color:{MUTED}; font-size:0.8rem; line-height:1.55;">{content}</div>
</div>
        """, unsafe_allow_html=True)
