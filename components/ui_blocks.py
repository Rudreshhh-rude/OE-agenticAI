import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ═══════════════════════════════════════════════════════════════
#  COMPONENT LIBRARY — Glass-Box Professional UI
# ═══════════════════════════════════════════════════════════════

# ── Color Constants (Institutional Dark Mode) ──
EMERALD = "#10B981"
CRIMSON = "#EF4444"
ACCENT  = "#10B981"       # Switched from Blue to Emerald
CARD_BG = "#111827"
BORDER  = "rgba(255,255,255,0.08)"
MUTED   = "#94A3B8"
TEXT    = "#F9FAFB"
SUBTLE  = "#64748B"
BODY_TEXT = "#E2E8F0"


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


def render_ai_insights(insights: dict, fact_check_status: str = "PASS"):
    """Renders the Glass-Box research report panel with prominent verification badge."""
    if "error" in insights:
        st.error(f"AI Generation Error: {insights['error']}")
        return

    # Optional UI-only enhancements (computed in app.py)
    confidence_pct = insights.get("_confidence_pct")
    reasons = insights.get("_reasons") if isinstance(insights.get("_reasons"), list) else []

    # ── Extract signal from nested or flat structure ──
    if "executive_verdict" in insights and isinstance(insights["executive_verdict"], dict):
        signal = insights["executive_verdict"].get("signal", "HOLD").upper()
        summary = insights["executive_verdict"].get("justification", "")
    else:
        signal = insights.get("signal", "HOLD").upper()
        summary = insights.get("summary", "")

    fundamental_health = insights.get("fundamental_health", "No fundamental health analysis provided.")
    historical_trends = insights.get("historical_trends", "No historical trends analysis provided.")
    catalysts_headwinds = insights.get("catalysts_headwinds", "No catalysts or headwinds provided.")

    if signal == "BUY":
        signal_class = "signal-buy"
    elif signal == "SELL":
        signal_class = "signal-sell"
    else:
        signal_class = "signal-hold"

    safe_summary = str(summary).replace('\n', ' ')
    safe_fund_health = str(fundamental_health).replace('\n', '<br/>')
    safe_hist_trends = str(historical_trends).replace('\n', '<br/>')
    safe_cat_head = str(catalysts_headwinds).replace('\n', '<br/>')

    if fact_check_status == "PASS":
        badge_html = f'<span style="background:rgba(22,163,74,0.15); color:{EMERALD}; padding:4px 10px; border-radius:20px; font-weight:bold; font-size:0.75rem; float:right; margin-top:-0.5rem; border:1px solid rgba(22,163,74,0.2);">✓ VERIFIED BY CRITIQUE AGENT</span>'
    else:
        badge_html = f'<span style="background:rgba(239,68,68,0.15); color:{CRIMSON}; padding:4px 10px; border-radius:20px; font-weight:bold; font-size:0.75rem; float:right; margin-top:-0.5rem; border:1px solid rgba(239,68,68,0.2);">⚠ CRITIQUE FAILED</span>'

    conf_line = f' <span style="color:{MUTED}; font-weight:700;">(Confidence: {int(confidence_pct)}%)</span>' if isinstance(confidence_pct, (int, float)) else ""
    reasons_html = ""
    if reasons:
        bullets = "".join([f"<li style='margin:6px 0; color:{BODY_TEXT};'>{r}</li>" for r in reasons[:3]])
        # IMPORTANT: no leading indentation, otherwise Streamlit Markdown may render this as a code block
        reasons_html = (
            f'<div style="margin-top: 12px;">'
            f'<div style="color:{MUTED}; font-size:0.7rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:6px;">Why this signal</div>'
            f'<ul style="margin: 0 0 0 18px; padding: 0;">{bullets}</ul>'
            f"</div>"
        )

    st.markdown(f"""<div class="insight-panel" style="position:relative; border-top:2px solid {ACCENT}; padding:2rem; margin-top:2rem; background:{CARD_BG}; border-radius:12px; border:1px solid {BORDER}; box-shadow: 0 10px 40px rgba(0,0,0,0.35);">
    {badge_html}
    <h3 style="margin:0 0 1.5rem 0; color:{TEXT}; font-size:1.15rem; font-weight:700; padding-top:0.3rem;">EXECUTIVE VERDICT</h3>
    <div style="background:rgba(15,23,42,0.4); border-left:4px solid {ACCENT}; padding:1.2rem 1.4rem; border-radius:6px; margin-bottom:2rem; border:1px solid {BORDER};">
        <p style="color:{BODY_TEXT}; font-size:0.92rem; line-height:1.7; margin:0;">{safe_summary}</p>
        <div style="margin-top: 1.2rem; border-top:1px solid {BORDER}; padding-top:0.8rem;">
            <span style="font-size:0.7rem; font-weight:700; color:{MUTED}; text-transform:uppercase; margin-right:8px;">Signal:</span>
            <span class="signal-badge {signal_class}" style="padding:0.4rem 1.2rem; font-size:0.8rem; font-weight:700; border-radius:30px;">{signal}</span>{conf_line}
        </div>
        {reasons_html}
    </div>
    <h4 style="color:{MUTED}; text-transform:uppercase; font-size:0.7rem; letter-spacing:0.1em; margin-bottom:0.7rem; padding-bottom:0.4rem; border-bottom:1px solid #E2E8F0; margin-top:1.5rem;">FUNDAMENTAL HEALTH</h4>
    <p style="color:{BODY_TEXT}; font-size:0.92rem; line-height:1.7; margin-bottom:2rem;">{safe_fund_health}</p>
    <h4 style="color:{MUTED}; text-transform:uppercase; font-size:0.7rem; letter-spacing:0.1em; margin-bottom:0.7rem; padding-bottom:0.4rem; border-bottom:1px solid #E2E8F0;">HISTORICAL TRENDS</h4>
    <p style="color:{BODY_TEXT}; font-size:0.92rem; line-height:1.7; margin-bottom:2rem;">{safe_hist_trends}</p>
    <h4 style="color:{MUTED}; text-transform:uppercase; font-size:0.7rem; letter-spacing:0.1em; margin-bottom:0.7rem; padding-bottom:0.4rem; border-bottom:1px solid #E2E8F0;">CATALYSTS & HEADWINDS</h4>
    <p style="color:{BODY_TEXT}; font-size:0.92rem; line-height:1.7; margin-bottom:1rem;">{safe_cat_head}</p>
</div>""", unsafe_allow_html=True)


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
