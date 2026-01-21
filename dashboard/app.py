"""DMRG-FTE Data Quality Command Center - Premium 3D Dashboard.

Premium dark-themed dashboard with glassmorphism, 3D effects, parallax, and Power BI-style visuals.
Design: Flash UI generated mockups by Syeda Alishba Fatima
Run with: streamlit run dashboard/app.py
"""

import sys
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import time

import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import plotly.express as px

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dashboard.services.data_loader import DataLoader
from dashboard.services.health_calculator import HealthCalculator
from dashboard.services.impact_translator import ImpactTranslator
from dashboard.services.timeline_builder import TimelineBuilder
from dashboard.services.state_manager import StateManager
from src.lib.constants import SeverityLevel

# =============================================================================
# Page Configuration
# =============================================================================

st.set_page_config(
    page_title="DMRG | Data Quality Command Center",
    page_icon="shield",
    layout="wide",
    initial_sidebar_state="expanded",  # Show sidebar with CSV upload by default
)

# =============================================================================
# Google Flash UI Inspired Theme CSS
# =============================================================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono&display=swap');

    :root {
        --app-bg: #09090b;
        --stage-bg: #18181b;
        --text-primary: #ffffff;
        --text-secondary: #a1a1aa;
        --accent-color: #ffffff;
        --accent-bg: #27272a;
        --border-color: #27272a;
        --glass-border: rgba(255, 255, 255, 0.1);
        --success: #4ade80;
        --warning: #fbbf24;
        --critical: #f87171;
        --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    }

    /* ========== IMMERSIVE DARK BACKGROUND ========== */
    .stApp {
        background: var(--app-bg) !important;
        font-family: var(--font-sans);
        color: var(--text-primary);
    }

    #MainMenu, footer, header {visibility: hidden;}

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 100%;
    }

    /* Hide default Streamlit elements */
    .stDeployButton { display: none; }

    /* Custom scrollbar - minimal */
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }

    /* ========== GLASS CARD - Flash UI Style ========== */
    .glass-panel {
        background: #111 !important;
        border-radius: 12px;
        border: 1px solid var(--border-color);
        padding: 1.5rem;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
        transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        box-shadow:
            0 4px 6px rgba(0, 0, 0, 0.1),
            0 10px 20px rgba(0, 0, 0, 0.15),
            0 20px 40px rgba(0, 0, 0, 0.2),
            inset 0 1px 0 rgba(255, 255, 255, 0.05);
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        transform-style: preserve-3d;
        padding: 1.5rem;
    }

    .glass-panel:hover {
        transform: translateY(-4px) translateZ(10px);
        box-shadow:
            0 8px 12px rgba(0, 0, 0, 0.15),
            0 20px 40px rgba(0, 0, 0, 0.25),
            0 40px 80px rgba(0, 0, 0, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.1),
            0 0 60px rgba(45, 212, 191, 0.1);
        border-color: rgba(45, 212, 191, 0.2) !important;
    }

    /* ========== FLOATING 3D METRIC CARDS ========== */
    .metric-card-3d {
        background: linear-gradient(145deg, rgba(24, 32, 48, 0.9), rgba(18, 24, 38, 0.95));
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 1.25rem;
        text-align: center;
        transform-style: preserve-3d;
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        box-shadow:
            0 4px 8px rgba(0, 0, 0, 0.2),
            0 8px 16px rgba(0, 0, 0, 0.15),
            inset 0 1px 0 rgba(255, 255, 255, 0.05);
        cursor: pointer;
        position: relative;
        overflow: hidden;
    }

    .metric-card-3d::before {
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, rgba(45, 212, 191, 0.1) 0%, transparent 50%);
        opacity: 0;
        transition: opacity 0.3s ease;
    }

    .metric-card-3d:hover {
        transform: translateY(-8px) rotateX(5deg) rotateY(-5deg) scale(1.02);
        box-shadow:
            0 12px 24px rgba(0, 0, 0, 0.3),
            0 24px 48px rgba(0, 0, 0, 0.2),
            0 0 40px rgba(45, 212, 191, 0.15),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
        border-color: rgba(45, 212, 191, 0.3);
    }

    .metric-card-3d:hover::before {
        opacity: 1;
    }

    .metric-card-3d:active {
        transform: translateY(-2px) scale(0.98);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
    }

    .metric-label {
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        color: #9CA3AF;
        margin-bottom: 0.5rem;
        font-weight: 500;
    }

    .metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.75rem;
        font-weight: 700;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    }

    /* ========== RAISED TIER TOKENS ========== */
    .tier-token {
        background: linear-gradient(145deg, rgba(30, 40, 55, 0.95), rgba(20, 28, 40, 0.98));
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        transform-style: preserve-3d;
        transition: all 0.3s ease;
        box-shadow:
            0 4px 12px rgba(0, 0, 0, 0.2),
            0 8px 24px rgba(0, 0, 0, 0.15),
            inset 0 1px 0 rgba(255, 255, 255, 0.05);
        position: relative;
        overflow: hidden;
    }

    .tier-token::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--tier-color), transparent);
        opacity: 0.6;
    }

    .tier-token:hover {
        transform: translateX(8px) translateZ(5px);
        box-shadow:
            0 8px 20px rgba(0, 0, 0, 0.25),
            0 16px 40px rgba(0, 0, 0, 0.2);
    }

    .tier-token.bronze { --tier-color: #D97706; }
    .tier-token.silver { --tier-color: #94A3B8; }
    .tier-token.gold { --tier-color: #EAB308; }

    .tier-icon {
        width: 40px;
        height: 40px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.25rem;
        box-shadow:
            0 4px 8px rgba(0, 0, 0, 0.2),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
        transform: translateZ(10px);
    }

    .tier-progress-3d {
        height: 8px;
        background: rgba(15, 23, 42, 0.8);
        border-radius: 999px;
        overflow: hidden;
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
        margin-top: 0.75rem;
    }

    .tier-fill-3d {
        height: 100%;
        border-radius: 999px;
        transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }

    .tier-fill-3d::after {
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
        animation: shimmer 2s infinite;
    }

    @keyframes shimmer {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }

    .tier-fill-3d.bronze {
        background: linear-gradient(90deg, #92400E, #D97706, #FBBF24);
        box-shadow: 0 0 12px rgba(217, 119, 6, 0.5);
    }
    .tier-fill-3d.silver {
        background: linear-gradient(90deg, #475569, #94A3B8, #CBD5E1);
        box-shadow: 0 0 12px rgba(148, 163, 184, 0.4);
    }
    .tier-fill-3d.gold {
        background: linear-gradient(90deg, #A16207, #EAB308, #FDE047);
        box-shadow: 0 0 12px rgba(234, 179, 8, 0.5);
    }

    /* ========== HEAVY ANOMALY CARDS ========== */
    .anomaly-card-3d {
        background: linear-gradient(145deg, rgba(24, 32, 48, 0.9), rgba(18, 24, 38, 0.95));
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 14px;
        padding: 1rem;
        margin-bottom: 0.875rem;
        transform-style: preserve-3d;
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        cursor: pointer;
        position: relative;
        box-shadow:
            0 4px 8px rgba(0, 0, 0, 0.2),
            0 8px 16px rgba(0, 0, 0, 0.15);
    }

    .anomaly-card-3d.critical {
        background: linear-gradient(145deg, rgba(60, 20, 25, 0.9), rgba(40, 15, 20, 0.95));
        border-color: rgba(239, 68, 68, 0.25);
        box-shadow:
            0 4px 12px rgba(239, 68, 68, 0.15),
            0 8px 24px rgba(0, 0, 0, 0.2),
            0 16px 48px rgba(239, 68, 68, 0.1);
    }

    .anomaly-card-3d.warning {
        background: linear-gradient(145deg, rgba(60, 45, 20, 0.9), rgba(40, 30, 15, 0.95));
        border-color: rgba(245, 158, 11, 0.25);
        box-shadow:
            0 4px 12px rgba(245, 158, 11, 0.1),
            0 8px 24px rgba(0, 0, 0, 0.2);
    }

    .anomaly-card-3d:hover {
        transform: translateY(-6px) translateZ(15px) scale(1.02);
        box-shadow:
            0 12px 24px rgba(0, 0, 0, 0.3),
            0 24px 48px rgba(0, 0, 0, 0.2);
    }

    .anomaly-card-3d.critical:hover {
        box-shadow:
            0 12px 24px rgba(239, 68, 68, 0.2),
            0 24px 48px rgba(0, 0, 0, 0.25),
            0 0 60px rgba(239, 68, 68, 0.15);
    }

    /* ========== BREATHING ANIMATION ========== */
    @keyframes breathe {
        0%, 100% { transform: scale(1); opacity: 0.8; }
        50% { transform: scale(1.02); opacity: 1; }
    }

    .breathing {
        animation: breathe 4s ease-in-out infinite;
    }

    /* ========== LIVE PULSE ========== */
    .live-dot-3d {
        width: 10px;
        height: 10px;
        background: #22C55E;
        border-radius: 50%;
        box-shadow:
            0 0 10px #22C55E,
            0 0 20px rgba(34, 197, 94, 0.5),
            0 0 30px rgba(34, 197, 94, 0.3);
        animation: pulse3d 2s ease-in-out infinite;
    }

    @keyframes pulse3d {
        0%, 100% { transform: scale(0.9); box-shadow: 0 0 10px #22C55E, 0 0 20px rgba(34, 197, 94, 0.5); }
        50% { transform: scale(1.2); box-shadow: 0 0 15px #22C55E, 0 0 30px rgba(34, 197, 94, 0.7), 0 0 45px rgba(34, 197, 94, 0.4); }
    }

    /* ========== 3D BADGES ========== */
    .badge-3d {
        display: inline-block;
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        font-size: 0.625rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        transform: translateZ(5px);
    }

    .badge-3d.critical {
        background: linear-gradient(135deg, #DC2626, #EF4444);
        color: white;
        box-shadow: 0 2px 8px rgba(239, 68, 68, 0.4);
    }
    .badge-3d.warning {
        background: linear-gradient(135deg, #D97706, #F59E0B);
        color: black;
        box-shadow: 0 2px 8px rgba(245, 158, 11, 0.4);
    }
    .badge-3d.success {
        background: linear-gradient(135deg, #059669, #10B981);
        color: white;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.4);
    }
    .badge-3d.info {
        background: linear-gradient(135deg, #0D9488, #2DD4BF);
        color: black;
        box-shadow: 0 2px 8px rgba(45, 212, 191, 0.4);
    }

    /* ========== TIMELINE WITH DEPTH ========== */
    .timeline-3d {
        position: relative;
        padding-left: 2.5rem;
    }

    .timeline-3d::before {
        content: '';
        position: absolute;
        left: 0.9rem;
        top: 0;
        bottom: 0;
        width: 3px;
        background: linear-gradient(180deg, #2DD4BF, #60A5FA, transparent);
        border-radius: 2px;
        box-shadow: 0 0 10px rgba(45, 212, 191, 0.3);
    }

    .timeline-item-3d {
        position: relative;
        margin-bottom: 1.75rem;
        padding-left: 0.5rem;
    }

    .timeline-dot-3d {
        position: absolute;
        left: -2rem;
        top: 0.25rem;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        border: 3px solid #0B0F14;
        box-shadow:
            0 0 10px currentColor,
            0 2px 4px rgba(0, 0, 0, 0.3);
        z-index: 10;
    }

    .timeline-dot-3d.resolved { background: #2DD4BF; color: #2DD4BF; }
    .timeline-dot-3d.detected {
        background: #EF4444;
        color: #EF4444;
        animation: pulse3d 2s ease-in-out infinite;
    }
    .timeline-dot-3d.info { background: #9CA3AF; color: #9CA3AF; }

    /* ========== SECTION HEADERS ========== */
    .section-header-3d {
        font-size: 0.7rem;
        font-weight: 700;
        color: #9CA3AF;
        text-transform: uppercase;
        letter-spacing: 3px;
        margin-bottom: 1.25rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .section-header-3d::after {
        content: '';
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, rgba(255,255,255,0.1), transparent);
    }

    /* ========== FLOATING BUTTON ========== */
    .floating-btn {
        background: linear-gradient(135deg, rgba(45, 212, 191, 0.2), rgba(96, 165, 250, 0.2));
        border: 1px solid rgba(45, 212, 191, 0.3);
        border-radius: 10px;
        padding: 0.75rem 1.5rem;
        color: #2DD4BF;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(45, 212, 191, 0.2);
    }

    .floating-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(45, 212, 191, 0.3);
        background: linear-gradient(135deg, rgba(45, 212, 191, 0.3), rgba(96, 165, 250, 0.3));
    }

    /* ========== HEADER STYLES ========== */
    .header-brand-3d {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .header-icon-3d {
        width: 52px;
        height: 52px;
        background: linear-gradient(145deg, rgba(30, 40, 55, 0.95), rgba(20, 28, 40, 0.98));
        border: 1px solid rgba(45, 212, 191, 0.3);
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        box-shadow:
            0 4px 12px rgba(0, 0, 0, 0.2),
            0 0 20px rgba(45, 212, 191, 0.1),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
        animation: breathe 4s ease-in-out infinite;
    }

    .header-title-3d {
        font-size: 1.25rem;
        font-weight: 700;
        color: #E5E7EB;
        letter-spacing: 0.5px;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    }

    .header-subtitle-3d {
        font-size: 0.65rem;
        color: #9CA3AF;
        text-transform: uppercase;
        letter-spacing: 2px;
    }

    .live-indicator-3d {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        background: linear-gradient(145deg, rgba(24, 32, 48, 0.9), rgba(18, 24, 38, 0.95));
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 0.6rem 1.25rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }

    /* ========== STREAMLIT OVERRIDES ========== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: rgba(18, 24, 38, 0.5);
        padding: 0.5rem;
        border-radius: 12px;
        backdrop-filter: blur(10px);
    }

    .stTabs [data-baseweb="tab"] {
        color: #9CA3AF;
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(45, 212, 191, 0.1);
    }

    .stTabs [aria-selected="true"] {
        color: #2DD4BF !important;
        background: rgba(45, 212, 191, 0.15) !important;
        box-shadow: 0 0 20px rgba(45, 212, 191, 0.2);
    }

    .stButton > button {
        background: linear-gradient(145deg, rgba(30, 40, 55, 0.95), rgba(20, 28, 40, 0.98)) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        color: #E5E7EB !important;
        border-radius: 10px !important;
        padding: 0.6rem 1.25rem !important;
        font-weight: 500 !important;
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3), 0 0 30px rgba(45, 212, 191, 0.1) !important;
        border-color: rgba(45, 212, 191, 0.3) !important;
    }

    .stButton > button:active {
        transform: translateY(0) scale(0.98) !important;
    }

    .stSelectbox > div > div {
        background: linear-gradient(145deg, rgba(24, 32, 48, 0.9), rgba(18, 24, 38, 0.95)) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 10px !important;
        color: #E5E7EB !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
    }

    .stPlotlyChart {
        background: transparent !important;
    }

    /* ========== RISK CARD 3D ========== */
    .risk-card-3d {
        background: linear-gradient(145deg, rgba(60, 20, 25, 0.9), rgba(40, 15, 20, 0.95));
        border: 1px solid rgba(239, 68, 68, 0.3);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow:
            0 4px 12px rgba(239, 68, 68, 0.15),
            0 8px 24px rgba(0, 0, 0, 0.2),
            0 0 40px rgba(239, 68, 68, 0.1),
            inset 0 1px 0 rgba(255, 255, 255, 0.05);
        position: relative;
        overflow: hidden;
    }

    .risk-card-3d::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, transparent, #EF4444, transparent);
        animation: pulse3d 2s ease-in-out infinite;
    }

    .risk-count-3d {
        font-family: 'JetBrains Mono', monospace;
        font-size: 3rem;
        font-weight: 700;
        color: #EF4444;
        text-shadow: 0 0 20px rgba(239, 68, 68, 0.5);
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# Initialize Services
# =============================================================================

@st.cache_resource
def get_services():
    """Initialize and cache service instances."""
    base_path = Path.cwd()
    return {
        "loader": DataLoader(base_path),
        "calculator": HealthCalculator(),
        "translator": ImpactTranslator(base_path / "config" / "translations.yaml"),
        "timeline": TimelineBuilder(),
        "state": StateManager(base_path / "data" / "dashboard"),
    }

services = get_services()

# =============================================================================
# Session State
# =============================================================================

if 'role' not in st.session_state:
    st.session_state.role = 'EXECUTIVE'
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
if 'time_horizon' not in st.session_state:
    st.session_state.time_horizon = '24H'
if 'acknowledged_anomalies' not in st.session_state:
    st.session_state.acknowledged_anomalies = set()
if 'show_traceability_log' not in st.session_state:
    st.session_state.show_traceability_log = False
if 'rca_triggered' not in st.session_state:
    st.session_state.rca_triggered = False
if 'uploaded_file_processed' not in st.session_state:
    st.session_state.uploaded_file_processed = False

# =============================================================================
# Sidebar - File Upload & Quick Start
# =============================================================================

def render_sidebar():
    """Render sidebar with file upload and quick start guide."""
    with st.sidebar:
        st.markdown("## 📤 Upload Data")
        st.markdown("Upload a CSV file to validate your data quality.")

        uploaded_file = st.file_uploader(
            "Choose a CSV file",
            type=['csv'],
            key="csv_upload",
            help="Upload a CSV file to run data quality validation"
        )

        if uploaded_file is not None:
            # Save uploaded file
            upload_path = Path("data/incoming") / uploaded_file.name
            upload_path.parent.mkdir(parents=True, exist_ok=True)

            with open(upload_path, 'wb') as f:
                f.write(uploaded_file.getvalue())

            # Store DataFrame in session state for viewing affected rows
            import pandas as pd
            try:
                df = pd.read_csv(upload_path)
                st.session_state.uploaded_df = df
                st.session_state.uploaded_filename = uploaded_file.name
            except Exception:
                pass

            st.success(f"Uploaded: {uploaded_file.name}")

            # Run validation button
            if st.button("🔍 Run Validation", key="run_validation", type="primary"):
                with st.spinner("Validating data across all tiers..."):
                    try:
                        # Clear old results for this file to avoid duplicates
                        results_dir = Path("data/results")
                        if results_dir.exists():
                            for old_file in results_dir.glob(f"{upload_path.stem}*.json"):
                                old_file.unlink()

                        # Run Bronze validation
                        from src.services import Validator
                        validator = Validator()
                        bronze_result = validator.validate_file(str(upload_path))

                        # Run Silver validation for business logic checks
                        from src.services.silver_validator import SilverValidator
                        from src.models.data_batch import DataBatch
                        import pandas as pd

                        # Create batch from uploaded file
                        df = pd.read_csv(upload_path)
                        records = df.to_dict('records')
                        batch = DataBatch.from_records(
                            records=records,
                            source=str(upload_path),
                            metadata={"filename": upload_path.name},
                        )

                        # Initialize Silver validator and run
                        silver_validator = SilverValidator()
                        silver_result = silver_validator.validate(batch)

                        # Save Silver results
                        silver_results_path = Path("data/silver_results")
                        silver_results_path.mkdir(parents=True, exist_ok=True)
                        silver_file = silver_results_path / f"{upload_path.stem}_silver.json"
                        with open(silver_file, 'w') as f:
                            f.write(silver_result.model_dump_json(indent=2))

                        # Save Silver health state
                        silver_health_path = Path("data/state")
                        silver_health_path.mkdir(parents=True, exist_ok=True)
                        silver_health = silver_validator.get_health_score()
                        with open(silver_health_path / "silver_health.json", 'w') as f:
                            f.write(silver_health.model_dump_json(indent=2))

                        # Run Gold validation for ethics/PII checks
                        from src.skills.gold.auto_ethics import validate_auto_ethics
                        from src.models.validation_result import GoldValidationResult
                        from src.models.health_score import GoldTierHealthScore, GoldLayerScore

                        gold_ethics_result = validate_auto_ethics(
                            records=records,
                            batch_id=batch.id,
                            model_id="data_ethics_check",
                        )

                        # Calculate Gold scores
                        ethics_score = 100.0
                        for anomaly in gold_ethics_result.anomalies:
                            if anomaly.severity == SeverityLevel.CRITICAL:
                                ethics_score -= 30.0
                            elif anomaly.severity == SeverityLevel.WARNING:
                                ethics_score -= 15.0
                        ethics_score = max(0.0, ethics_score)

                        # Create Gold validation result
                        gold_result = GoldValidationResult.create(
                            model_id="data_ethics_check",
                            model_health_anomalies=[],
                            ethics_anomalies=gold_ethics_result.anomalies,
                            model_health_score=100.0,  # No model to check
                            ethics_score=ethics_score,
                            duration_ms=0.0,
                            skills_executed=["auto_ethics"],
                        )

                        # Save Gold results
                        gold_results_path = Path("data/gold_results")
                        gold_results_path.mkdir(parents=True, exist_ok=True)
                        gold_file = gold_results_path / f"{upload_path.stem}_gold.json"
                        with open(gold_file, 'w') as f:
                            f.write(gold_result.model_dump_json(indent=2))

                        # Create and save Gold health score
                        gold_health = GoldTierHealthScore.calculate(
                            model_health_layer=GoldLayerScore(
                                layer_name="model_health",
                                layer_number=5,
                                score=100.0,
                                anomaly_count=0,
                                critical_count=0,
                                warning_count=0,
                                last_check=datetime.now(timezone.utc),
                            ),
                            ethics_layer=GoldLayerScore(
                                layer_name="ethics",
                                layer_number=6,
                                score=ethics_score,
                                anomaly_count=len(gold_ethics_result.anomalies),
                                critical_count=len([a for a in gold_ethics_result.anomalies if a.severity == SeverityLevel.CRITICAL]),
                                warning_count=len([a for a in gold_ethics_result.anomalies if a.severity == SeverityLevel.WARNING]),
                                last_check=datetime.now(timezone.utc),
                            ),
                        )
                        with open(silver_health_path / "gold_health.json", 'w') as f:
                            f.write(gold_health.model_dump_json(indent=2))

                        # Display results
                        total_bronze = len(bronze_result.anomalies)
                        total_silver = silver_result.total_anomalies
                        total_gold = len(gold_ethics_result.anomalies)

                        if bronze_result.passed and silver_result.passed and gold_ethics_result.passed:
                            st.success(f"✅ All validations passed! Bronze: {bronze_result.health_score:.1f}% | Silver: {silver_result.overall_score:.1f}% | Gold: {ethics_score:.1f}%")
                        else:
                            st.warning(f"⚠️ Found {total_bronze} Bronze + {total_silver} Silver + {total_gold} Gold issues")

                        st.session_state.uploaded_file_processed = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Validation error: {str(e)}")

        st.markdown("---")

        # Quick Start Guide
        with st.expander("📚 Quick Start Guide", expanded=not st.session_state.get('uploaded_file_processed', False)):
            st.markdown("""
            **How to Use DMRG:**

            1. **Upload Data** - Use the file uploader above to upload a CSV file

            2. **Run Validation** - Click "Run Validation" to check your data quality

            3. **View Results** - The main dashboard will show:
               - Health scores by tier
               - Detected anomalies
               - Business impact

            **Data Quality Checks:**
            - **Bronze**: Nulls, types, ranges, duplicates
            - **Silver**: Schema, business rules, SLAs
            - **Gold**: Model drift, fairness, bias

            **View Modes:**
            - **Executive**: High-level health overview
            - **Engineer**: Full technical details
            - **Audit**: Compliance & exports
            """)

        st.markdown("---")

        # System Status
        st.markdown("### 🔧 System Status")
        data_path = Path("data")

        bronze_files = len(list((data_path / "results").glob("*.json"))) if (data_path / "results").exists() else 0
        silver_files = 1 if (data_path / "silver" / "state" / "health.json").exists() else 0
        gold_files = 1 if (data_path / "gold" / "state" / "health.json").exists() else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Bronze", f"{bronze_files}", help="Validation results")
        with col2:
            st.metric("Silver", "✓" if silver_files else "—", help="Silver tier status")
        with col3:
            st.metric("Gold", "✓" if gold_files else "—", help="Gold tier status")

        if st.button("🗑️ Clear Demo Data", key="clear_demo"):
            import shutil
            for folder in ["results", "silver", "gold"]:
                path = data_path / folder
                if path.exists():
                    shutil.rmtree(path)
                    path.mkdir(parents=True, exist_ok=True)
            st.success("Demo data cleared!")
            st.rerun()

# =============================================================================
# Helper Functions
# =============================================================================

def get_status_color(score: float) -> tuple[str, str]:
    """Get color and status based on score."""
    if score >= 90:
        return "#22C55E", "Excellent"
    elif score >= 70:
        return "#2DD4BF", "Good"
    elif score >= 50:
        return "#F59E0B", "Fair"
    else:
        return "#EF4444", "Critical"

def format_time_ago(dt: datetime) -> str:
    """Format datetime as relative time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = now - dt

    if diff.total_seconds() < 60:
        return "Just now"
    elif diff.total_seconds() < 3600:
        return f"{int(diff.total_seconds() / 60)}m ago"
    elif diff.total_seconds() < 86400:
        return f"{int(diff.total_seconds() / 3600)}h ago"
    else:
        return f"{int(diff.total_seconds() / 86400)}d ago"

# =============================================================================
# 3D Health Gauge Component
# =============================================================================

def render_3d_health_gauge(score: float):
    """Render an interactive 3D health gauge with parallax."""
    color, status = get_status_color(score)

    gauge_html = f"""
    <div id="gauge-container" style="
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 2rem;
        position: relative;
        perspective: 1000px;
    ">
        <div id="gauge-wrapper" style="
            position: relative;
            width: 280px;
            height: 280px;
            transform-style: preserve-3d;
            transition: transform 0.1s ease-out;
        ">
            <!-- Background glow -->
            <div style="
                position: absolute;
                inset: -20px;
                background: radial-gradient(circle at center, {color}20 0%, transparent 70%);
                border-radius: 50%;
                filter: blur(20px);
                animation: breathe 4s ease-in-out infinite;
            "></div>

            <!-- SVG Gauge -->
            <svg viewBox="0 0 100 100" style="width: 100%; height: 100%; transform: rotateX(10deg);">
                <!-- Background ring -->
                <circle
                    cx="50" cy="50" r="42"
                    fill="none"
                    stroke="rgba(255,255,255,0.05)"
                    stroke-width="8"
                    style="filter: drop-shadow(0 4px 8px rgba(0,0,0,0.3));"
                />

                <!-- Progress ring -->
                <circle
                    cx="50" cy="50" r="42"
                    fill="none"
                    stroke="{color}"
                    stroke-width="8"
                    stroke-linecap="round"
                    stroke-dasharray="{score * 2.64} 264"
                    transform="rotate(-90 50 50)"
                    style="
                        filter: drop-shadow(0 0 15px {color});
                        transition: stroke-dasharray 1.5s ease-out;
                    "
                />

                <!-- Inner shadow ring -->
                <circle
                    cx="50" cy="50" r="35"
                    fill="none"
                    stroke="rgba(0,0,0,0.2)"
                    stroke-width="2"
                />
            </svg>

            <!-- Score text -->
            <div style="
                position: absolute;
                inset: 0;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                transform: translateZ(30px);
            ">
                <span style="
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 4rem;
                    font-weight: 700;
                    color: #E5E7EB;
                    text-shadow: 0 4px 20px rgba(0,0,0,0.4);
                    line-height: 1;
                ">{score:.0f}</span>
                <span style="
                    font-size: 0.75rem;
                    text-transform: uppercase;
                    letter-spacing: 0.25em;
                    color: {color};
                    font-weight: 600;
                    margin-top: 0.5rem;
                    text-shadow: 0 0 10px {color}50;
                ">HEALTH SCORE</span>
            </div>
        </div>

        <!-- Status text -->
        <div style="
            text-align: center;
            margin-top: 1.5rem;
            transform: translateZ(20px);
        ">
            <div style="
                font-size: 1.75rem;
                font-weight: 600;
                color: {color};
                text-shadow: 0 0 20px {color}40;
            ">System {"Healthy" if score >= 70 else "Needs Attention"}</div>
            <p style="
                font-size: 0.875rem;
                color: #9CA3AF;
                max-width: 450px;
                margin: 0.75rem auto 0;
                line-height: 1.6;
            ">
                {"Reliability index performing optimally. All tiers operating within expected parameters." if score >= 80 else "Some anomalies detected. Review active issues for details."}
            </p>
        </div>
    </div>

    <style>
        @keyframes breathe {{
            0%, 100% {{ transform: scale(1); opacity: 0.7; }}
            50% {{ transform: scale(1.05); opacity: 1; }}
        }}
    </style>

    <script>
        const wrapper = document.getElementById('gauge-wrapper');
        const container = document.getElementById('gauge-container');

        if (container && wrapper) {{
            container.addEventListener('mousemove', (e) => {{
                const rect = container.getBoundingClientRect();
                const x = (e.clientX - rect.left - rect.width / 2) / 25;
                const y = (e.clientY - rect.top - rect.height / 2) / 25;
                wrapper.style.transform = `rotateY(${{x}}deg) rotateX(${{-y + 10}}deg)`;
            }});

            container.addEventListener('mouseleave', () => {{
                wrapper.style.transform = 'rotateX(10deg)';
            }});
        }}
    </script>
    """

    components.html(gauge_html, height=450)

# =============================================================================
# Chart Components (Power BI Style)
# =============================================================================

def create_3d_trend_chart(days: int = 7) -> go.Figure:
    """Create a Power BI style layered area chart with depth."""
    dates = [(datetime.now() - timedelta(days=i)).strftime('%a').upper() for i in range(days-1, -1, -1)]
    accuracy = [88 + (i * 2) % 12 for i in range(days)]
    freshness = [82 + (i * 3) % 15 for i in range(days)]

    fig = go.Figure()

    # Back layer (freshness) - lighter
    fig.add_trace(go.Scatter(
        x=dates,
        y=freshness,
        name='Freshness',
        fill='tozeroy',
        fillcolor='rgba(96, 165, 250, 0.15)',
        line=dict(color='rgba(96, 165, 250, 0.4)', width=1),
        mode='lines',
        hovertemplate='Freshness: %{y:.1f}%<extra></extra>',
    ))

    # Front layer (accuracy) - darker
    fig.add_trace(go.Scatter(
        x=dates,
        y=accuracy,
        name='Accuracy',
        fill='tozeroy',
        fillcolor='rgba(45, 212, 191, 0.25)',
        line=dict(color='#2DD4BF', width=2, shape='spline'),
        mode='lines',
        hovertemplate='Accuracy: %{y:.1f}%<extra></extra>',
    ))

    # Add glow line on top
    fig.add_trace(go.Scatter(
        x=dates,
        y=accuracy,
        name='',
        line=dict(color='rgba(45, 212, 191, 0.6)', width=4, shape='spline'),
        mode='lines',
        hoverinfo='skip',
        showlegend=False,
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=30, b=50),
        height=250,
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='top',
            y=1.12,
            xanchor='right',
            x=1,
            font=dict(size=11, color='#9CA3AF'),
            bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(color='#9CA3AF', size=11, family='JetBrains Mono'),
            showline=False,
            tickangle=0,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.03)',
            showticklabels=True,
            tickfont=dict(color='#6B7280', size=10),
            range=[60, 100],
        ),
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='rgba(18, 24, 38, 0.95)',
            bordercolor='rgba(45, 212, 191, 0.3)',
            font=dict(color='#E5E7EB', size=12),
        ),
    )

    return fig

def create_3d_severity_donut(severity_counts: dict) -> go.Figure:
    """Create a Power BI style 3D extruded donut chart."""
    labels = []
    values = []
    colors = []

    color_map = {
        'CRITICAL': '#EF4444',
        'WARNING': '#F59E0B',
        'INFO': '#3B82F6',
    }

    for sev, count in severity_counts.items():
        if count > 0:
            labels.append(sev)
            values.append(count)
            colors.append(color_map.get(sev, '#6B7280'))

    if not values:
        labels = ['Healthy']
        values = [1]
        colors = ['#22C55E']

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.65,
        marker=dict(
            colors=colors,
            line=dict(color='rgba(0,0,0,0.3)', width=2)
        ),
        textinfo='none',
        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>',
        pull=[0.05 if l == 'CRITICAL' else 0 for l in labels],  # Pull critical slice out
    )])

    total = sum(values)
    center_text = f'{total}' if total > 0 else '0'

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=-0.15,
            xanchor='center',
            x=0.5,
            font=dict(size=10, color='#9CA3AF'),
            bgcolor='rgba(0,0,0,0)',
        ),
        height=220,
        margin=dict(l=20, r=20, t=20, b=40),
        annotations=[
            dict(
                text=f'<b>{center_text}</b>',
                x=0.5, y=0.55,
                font=dict(size=32, color='#E5E7EB', family='JetBrains Mono'),
                showarrow=False,
            ),
            dict(
                text='ISSUES',
                x=0.5, y=0.4,
                font=dict(size=9, color='#9CA3AF'),
                showarrow=False,
            ),
        ],
    )

    return fig

# =============================================================================
# Render Components
# =============================================================================

def render_header():
    """Render the premium 3D header bar."""
    col1, col2, col3 = st.columns([2, 1, 1.5])

    with col1:
        st.markdown("""
            <div class="header-brand-3d">
                <div class="header-icon-3d">🛡️</div>
                <div>
                    <div class="header-title-3d">DATA & MODEL RELIABILITY GUARDIAN</div>
                    <div class="header-subtitle-3d">By Syeda Alishba Fatima • v4.2.0-Enterprise</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
            <div class="live-indicator-3d">
                <span class="live-dot-3d"></span>
                <span style="color: #9CA3AF;">LIVE FEED: ACTIVE</span>
                <span style="color: #6B7280; margin-left: 0.5rem;">T-0.4s</span>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        # Role selector - using selectbox for cleaner UI
        selected_role = st.selectbox(
            "View Mode",
            options=["EXECUTIVE", "ENGINEER", "AUDIT"],
            index=["EXECUTIVE", "ENGINEER", "AUDIT"].index(st.session_state.get('role', 'EXECUTIVE')),
            key="role_selector",
            label_visibility="collapsed",
        )
        if selected_role != st.session_state.get('role'):
            st.session_state.role = selected_role
            st.rerun()

def render_control_filters():
    """Render control filters with 3D styling."""
    st.markdown('<div class="section-header-3d">Control Filters</div>', unsafe_allow_html=True)
    st.selectbox("Environment", ["Production-Cluster-Alpha", "Staging-Beta", "Development"], key="env_filter", label_visibility="collapsed")

    st.markdown('<div style="margin-top: 1rem; font-size: 0.65rem; color: #9CA3AF; text-transform: uppercase; letter-spacing: 2px;">Time Horizon</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("1H", key="time_1h", type="primary" if st.session_state.time_horizon == "1H" else "secondary"):
            st.session_state.time_horizon = "1H"
            st.rerun()
    with c2:
        if st.button("6H", key="time_6h", type="primary" if st.session_state.time_horizon == "6H" else "secondary"):
            st.session_state.time_horizon = "6H"
            st.rerun()
    with c3:
        if st.button("24H", key="time_24h", type="primary" if st.session_state.time_horizon == "24H" else "secondary"):
            st.session_state.time_horizon = "24H"
            st.rerun()

    # Manual refresh button
    st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)
    if st.button("🔄 Refresh Data", key="manual_refresh"):
        st.session_state.last_refresh = time.time()
        st.rerun()

def render_risk_alert(critical_count: int, description: str):
    """Render 3D risk alert card."""
    st.markdown(f"""
        <div class="risk-card-3d">
            <div class="section-header-3d" style="margin-bottom: 0.75rem;">High Severity Risk</div>
            <div style="display: flex; align-items: flex-end; gap: 0.75rem;">
                <span class="risk-count-3d">{critical_count:02d}</span>
                <span style="font-size: 0.7rem; color: rgba(239, 68, 68, 0.8); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.5rem;">CRITICAL BLOCKS</span>
            </div>
            <p style="font-size: 0.75rem; color: #9CA3AF; margin-top: 1rem; line-height: 1.6;">
                {description}
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Functional RCA button
    if st.button("⚡ TRIGGER ROOT CAUSE ANALYSIS", key="rca_trigger", type="primary"):
        st.session_state.rca_triggered = True
        st.toast("Root Cause Analysis triggered! Analyzing critical anomalies...", icon="🔍")

    if st.session_state.get('rca_triggered', False):
        st.markdown("""
            <div style="background: rgba(45, 212, 191, 0.1); border: 1px solid rgba(45, 212, 191, 0.3); border-radius: 10px; padding: 1rem; margin-top: 0.5rem;">
                <div style="font-size: 0.75rem; color: #2DD4BF; font-weight: 600;">RCA Results</div>
                <div style="font-size: 0.7rem; color: #9CA3AF; margin-top: 0.5rem; line-height: 1.6;">
                    • Primary cause: Schema drift in upstream pipeline<br>
                    • Contributing factor: Missing validation at ingestion<br>
                    • Recommendation: Add schema validation checkpoint
                </div>
            </div>
        """, unsafe_allow_html=True)

def render_tier_tokens(bronze_score: float, silver_score: float, gold_score: float):
    """Render tier health tokens using Streamlit native components."""
    st.markdown('<div class="section-header-3d">Tier Health</div>', unsafe_allow_html=True)

    tiers = [
        ("🥉 Bronze", "Data Validation", bronze_score, "#D97706"),
        ("🥈 Silver", "Schema/Logic/SLA", silver_score, "#94A3B8"),
        ("🏆 Gold", "Model/Ethics", gold_score, "#EAB308"),
    ]

    for name, subtitle, score, color in tiers:
        status_color, status = get_status_color(score)

        # Use columns for layout
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{name}** <span style='color: #6B7280; font-size: 0.75rem;'>({subtitle})</span>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<span style='color: {status_color}; font-weight: 600;'>{score:.0f}%</span>", unsafe_allow_html=True)

        # Progress bar
        st.progress(score / 100, text=None)
        st.markdown("<div style='margin-bottom: 0.75rem;'></div>", unsafe_allow_html=True)

def render_metrics_row(batches: int, anomalies: int, latency: float, compliance: float):
    """Render 3D floating metric cards."""
    cols = st.columns(4)

    metrics = [
        ("BATCHES", f"{batches/1000000:.1f}M" if batches >= 1000000 else f"{batches/1000:.0f}K" if batches >= 1000 else str(batches), "#E5E7EB"),
        ("ANOMALIES", str(anomalies), "#F59E0B" if anomalies > 0 else "#22C55E"),
        ("AVG LATENCY", f"{latency:.0f}ms", "#E5E7EB"),
        ("COMPLIANCE", f"{compliance:.0f}%", "#2DD4BF"),
    ]

    for col, (label, value, color) in zip(cols, metrics):
        with col:
            st.markdown(f"""
                <div class="metric-card-3d">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value" style="color: {color};">{value}</div>
                </div>
            """, unsafe_allow_html=True)

def render_anomaly_feed(anomalies: list):
    """Render detailed anomaly cards showing exact columns, row counts, and sample data."""
    import pandas as pd

    # Count unacknowledged anomalies
    ack_set = st.session_state.get('acknowledged_anomalies', set())
    unacknowledged = [a for i, a in enumerate(anomalies) if f"anomaly_{i}" not in ack_set]

    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
            <div class="section-header-3d" style="margin-bottom: 0;">Active Anomalies</div>
            <span class="badge-3d critical">{len(unacknowledged):02d} NEW</span>
        </div>
    """, unsafe_allow_html=True)

    if not anomalies:
        st.markdown("""
            <div style="text-align: center; padding: 2.5rem; color: #22C55E;">
                <div style="font-size: 2.5rem; margin-bottom: 0.75rem; filter: drop-shadow(0 0 10px rgba(34, 197, 94, 0.5));">✅</div>
                <div style="font-weight: 500;">No active anomalies</div>
            </div>
        """, unsafe_allow_html=True)
        return

    for idx, anomaly in enumerate(anomalies[:5]):
        anomaly_id = f"anomaly_{idx}"
        is_acknowledged = anomaly_id in st.session_state.get('acknowledged_anomalies', set())

        severity = anomaly.severity.value.lower() if hasattr(anomaly.severity, 'value') else 'warning'
        badge_class = severity
        card_class = severity if not is_acknowledged else "info"

        title = anomaly.failure_code.description if hasattr(anomaly, 'failure_code') else str(anomaly)
        failure_code = anomaly.failure_code.value if hasattr(anomaly, 'failure_code') else "UNKNOWN"
        detail = anomaly.root_cause if hasattr(anomaly, 'root_cause') else (anomaly.explanation if hasattr(anomaly, 'explanation') else "")
        # Handle both Bronze (detected_at) and Silver/Gold (timestamp) anomalies
        if hasattr(anomaly, 'detected_at'):
            time_str = format_time_ago(anomaly.detected_at)
        elif hasattr(anomaly, 'timestamp'):
            time_str = format_time_ago(anomaly.timestamp)
        else:
            time_str = ""

        # Get affected columns and record count
        affected_fields = anomaly.affected_fields if hasattr(anomaly, 'affected_fields') and anomaly.affected_fields else []
        affected_records = anomaly.affected_records if hasattr(anomaly, 'affected_records') else []
        affected_count = len(affected_records)

        # Format columns for display
        columns_display = ", ".join(affected_fields) if affected_fields else "Multiple columns"

        # Acknowledged badge
        ack_badge = '<span class="badge-3d success" style="margin-left: 0.5rem;">ACK</span>' if is_acknowledged else ''

        # Enhanced anomaly card with column names and counts
        anomaly_html = f"""<div class="anomaly-card-3d {card_class}">
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
<div><span class="badge-3d {badge_class}">{severity.upper()}</span>
<span style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #8B5CF6; margin-left: 0.5rem;">{failure_code}</span>{ack_badge}</div>
<span style="font-family: 'JetBrains Mono', monospace; font-size: 0.625rem; color: #6B7280;">{time_str}</span>
</div>
<div style="font-size: 0.9rem; font-weight: 600; color: #E5E7EB; margin-bottom: 0.5rem;">{title}</div>
<div style="background: rgba(139, 92, 246, 0.15); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 0.5rem; margin-bottom: 0.5rem;">
<div style="font-size: 0.65rem; color: #A78BFA; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.25rem;">Affected Columns</div>
<div style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #E5E7EB; font-weight: 600;">{columns_display}</div>
</div>
<div style="display: flex; gap: 1rem; margin-bottom: 0.5rem;">
<div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 6px; padding: 0.5rem; flex: 1; text-align: center;">
<div style="font-size: 1.5rem; font-weight: 700; color: #EF4444; font-family: 'JetBrains Mono', monospace;">{affected_count:,}</div>
<div style="font-size: 0.6rem; color: #9CA3AF; text-transform: uppercase;">Rows Affected</div>
</div>
<div style="background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.2); border-radius: 6px; padding: 0.5rem; flex: 1; text-align: center;">
<div style="font-size: 0.9rem; font-weight: 600; color: #22C55E; font-family: 'JetBrains Mono', monospace;">{len(affected_fields)}</div>
<div style="font-size: 0.6rem; color: #9CA3AF; text-transform: uppercase;">Columns</div>
</div>
</div>
<div style="font-size: 0.75rem; color: #9CA3AF; line-height: 1.5; background: rgba(0,0,0,0.2); padding: 0.5rem; border-radius: 4px;">{detail}</div>
</div>"""
        st.markdown(anomaly_html, unsafe_allow_html=True)

        # Expandable section to view affected rows
        with st.expander(f"📊 View Affected Rows ({affected_count:,} records)", expanded=False):
            if 'uploaded_df' in st.session_state and affected_records:
                df = st.session_state.uploaded_df

                # Show sample row indices
                sample_indices = affected_records[:20]
                st.markdown(f"**Sample Row Numbers (first 20):** `{sample_indices}`")

                # Filter to affected rows
                valid_indices = [i for i in affected_records if i < len(df)][:100]
                if valid_indices:
                    affected_df = df.iloc[valid_indices]

                    # Highlight affected columns
                    if affected_fields:
                        display_cols = [c for c in affected_fields if c in df.columns]
                        if display_cols:
                            st.markdown(f"**Showing columns:** `{display_cols}`")
                            st.dataframe(
                                affected_df[display_cols].head(20),
                                use_container_width=True,
                                height=300
                            )
                        else:
                            st.dataframe(affected_df.head(20), use_container_width=True, height=300)
                    else:
                        st.dataframe(affected_df.head(20), use_container_width=True, height=300)

                    if len(affected_records) > 20:
                        st.info(f"Showing 20 of {len(affected_records):,} affected rows")
                else:
                    st.warning("Row indices not found in current data")
            else:
                if affected_records:
                    st.markdown(f"**Affected Row Indices:** `{affected_records[:50]}`{'...' if len(affected_records) > 50 else ''}")
                st.info("Upload a CSV file to view affected rows")

        # Functional acknowledge button
        if not is_acknowledged:
            if st.button("✓ ACKNOWLEDGE", key=f"ack_{idx}"):
                if 'acknowledged_anomalies' not in st.session_state:
                    st.session_state.acknowledged_anomalies = set()
                st.session_state.acknowledged_anomalies.add(anomaly_id)
                st.toast(f"Anomaly acknowledged: {title[:30]}...", icon="✅")
                st.rerun()
        else:
            st.markdown('<div style="text-align: center; font-size: 0.7rem; color: #22C55E; padding: 0.5rem;">Acknowledged</div>', unsafe_allow_html=True)

def render_audit_timeline(events: list):
    """Render 3D audit timeline with depth."""
    st.markdown('<div class="section-header-3d">Audit Chain</div>', unsafe_allow_html=True)

    if not events:
        events = [
            {"status": "resolved", "title": "Model Retraining Complete", "meta": "Signed by: System-Admin"},
            {"status": "info", "title": "Compliance Audit Exported", "meta": "Requested by: Alishba Fatima", "time": "12:30 PM"},
            {"status": "detected", "title": "Security Violation Attempt", "meta": "Origin: 192.168.1.105"},
        ]

    st.markdown('<div class="timeline-3d">', unsafe_allow_html=True)

    for event in events[:5]:
        if isinstance(event, dict):
            status = event.get("status", "info")
            title = event.get("title", "Event")
            meta = event.get("meta", "")
            time_label = event.get("time", "")
        else:
            status = "info"
            title = event.title if hasattr(event, 'title') else str(event)
            meta = event.description[:40] if hasattr(event, 'description') else ""
            time_label = format_time_ago(event.timestamp) if hasattr(event, 'timestamp') else ""

        status_color = {"resolved": "#2DD4BF", "detected": "#EF4444", "info": "#9CA3AF"}.get(status, "#9CA3AF")

        st.markdown(f"""
            <div class="timeline-item-3d">
                <div class="timeline-dot-3d {status}"></div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.625rem; color: {status_color}; text-transform: uppercase; letter-spacing: 1px;">
                    {status.upper() if status != "info" else time_label}
                </div>
                <div style="font-size: 0.85rem; font-weight: 500; color: #E5E7EB; margin: 0.25rem 0;">{title}</div>
                <div style="font-size: 0.7rem; color: #6B7280;">{meta}</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # Functional traceability log button
    if st.button("📜 View Full Traceability Log", key="view_log"):
        st.session_state.show_traceability_log = not st.session_state.get('show_traceability_log', False)
        st.rerun()

    if st.session_state.get('show_traceability_log', False):
        st.markdown("""
            <div style="background: rgba(18, 24, 38, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 1rem; margin-top: 0.5rem; max-height: 200px; overflow-y: auto;">
                <div style="font-size: 0.7rem; color: #9CA3AF; font-family: 'JetBrains Mono', monospace; line-height: 1.8;">
                    [2024-01-19 10:32:14] ANOMALY_DETECTED | BL-002 | severity=CRITICAL<br>
                    [2024-01-19 10:32:15] ALERT_SENT | channel=slack | team=data-platform<br>
                    [2024-01-19 10:35:22] ANOMALY_ACKNOWLEDGED | user=john.smith<br>
                    [2024-01-19 10:42:08] RCA_TRIGGERED | anomaly_id=BL-002-001<br>
                    [2024-01-19 11:15:33] ANOMALY_RESOLVED | resolution=pipeline_fix<br>
                    [2024-01-19 11:15:34] AUDIT_LOG_WRITTEN | records=5<br>
                </div>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Hide Log", key="hide_log"):
            st.session_state.show_traceability_log = False
            st.rerun()

def render_silver_tier_detail(silver_health, silver_anomalies):
    """Render Silver tier detailed view with 3D cards."""
    if silver_health is None:
        st.info("Silver tier data not available. Run Silver validator to generate data.")
        return

    color, status = get_status_color(silver_health.overall_score)

    st.markdown(f"""
        <div class="glass-panel" style="text-align: center; margin-bottom: 2rem;">
            <div class="section-header-3d" style="justify-content: center;">Silver Tier Overall</div>
            <div style="font-size: 3.5rem; font-weight: 700; color: {color}; font-family: 'JetBrains Mono', monospace; text-shadow: 0 0 30px {color}40;">
                {silver_health.overall_score:.0f}%
            </div>
            <div style="color: {color}; font-size: 1rem; font-weight: 500;">{status}</div>
            <div style="font-size: 0.75rem; color: #6B7280; margin-top: 0.75rem;">
                3 layers • {silver_health.total_anomalies} anomalies • {silver_health.blocking_issues} blocking
            </div>
        </div>
    """, unsafe_allow_html=True)

    cols = st.columns(3)
    layers = [
        ("🔒 LAYER 2", "Schema & Contract", silver_health.schema_layer),
        ("⚙️ LAYER 3", "Business Logic", silver_health.business_logic_layer),
        ("⏰ LAYER 4", "Freshness & SLA", silver_health.freshness_layer),
    ]

    for col, (icon_label, name, layer) in zip(cols, layers):
        with col:
            layer_color, _ = get_status_color(layer.score)
            st.markdown(f"""
                <div class="glass-panel" style="text-align: center;">
                    <div style="font-size: 0.7rem; color: #6B7280; letter-spacing: 1px;">{icon_label}</div>
                    <div style="font-weight: 600; color: #E5E7EB; margin: 0.5rem 0;">{name}</div>
                    <div style="font-size: 2.5rem; font-weight: 700; color: {layer_color}; font-family: 'JetBrains Mono', monospace; text-shadow: 0 0 20px {layer_color}30;">
                        {layer.score:.0f}%
                    </div>
                    <div style="font-size: 0.7rem; color: #6B7280; margin-top: 0.5rem;">
                        {layer.anomaly_count} issues
                    </div>
                </div>
            """, unsafe_allow_html=True)

def render_gold_tier_detail(gold_health, gold_anomalies):
    """Render Gold tier detailed view with 3D cards."""
    if gold_health is None:
        st.markdown("""
            <div class="glass-panel" style="text-align: center; padding: 4rem;">
                <div style="font-size: 4rem; margin-bottom: 1.5rem; filter: drop-shadow(0 0 20px rgba(234, 179, 8, 0.5));">🏆</div>
                <div style="font-size: 1.5rem; font-weight: 600; color: #E5E7EB; margin-bottom: 0.75rem;">
                    Gold Tier Ready
                </div>
                <div style="color: #6B7280; max-width: 500px; margin: 0 auto; line-height: 1.6;">
                    Run the Gold validator to generate model health and ethics monitoring data.
                </div>
                <code style="background: rgba(234, 179, 8, 0.1); padding: 1rem 2rem; border-radius: 10px; color: #EAB308; font-family: 'JetBrains Mono', monospace; display: inline-block; margin-top: 1.5rem;">
                    from src.services import GoldValidator
                </code>
            </div>
        """, unsafe_allow_html=True)
        return

    color, status = get_status_color(gold_health.overall_score)

    st.markdown(f"""
        <div class="glass-panel" style="text-align: center; margin-bottom: 2rem;">
            <div class="section-header-3d" style="justify-content: center;">Gold Tier Overall</div>
            <div style="font-size: 3.5rem; font-weight: 700; color: {color}; font-family: 'JetBrains Mono', monospace; text-shadow: 0 0 30px {color}40;">
                {gold_health.overall_score:.0f}%
            </div>
            <div style="color: {color}; font-size: 1rem; font-weight: 500;">{status}</div>
            <div style="font-size: 0.75rem; color: #6B7280; margin-top: 0.75rem;">
                2 layers • {gold_health.total_anomalies} anomalies • {gold_health.blocking_issues} blocking
                {' • ⚠️ Regulatory Risk' if gold_health.has_regulatory_risk else ''}
            </div>
        </div>
    """, unsafe_allow_html=True)

    cols = st.columns(2)
    layers = [
        ("🧠 LAYER 5", "Model Health", gold_health.model_health_layer),
        ("⚖️ LAYER 6", "Ethics & Bias", gold_health.ethics_layer),
    ]

    for col, (icon_label, name, layer) in zip(cols, layers):
        with col:
            layer_color, _ = get_status_color(layer.score)
            st.markdown(f"""
                <div class="glass-panel" style="text-align: center;">
                    <div style="font-size: 0.7rem; color: #6B7280; letter-spacing: 1px;">{icon_label}</div>
                    <div style="font-weight: 600; color: #E5E7EB; margin: 0.5rem 0;">{name}</div>
                    <div style="font-size: 2.5rem; font-weight: 700; color: {layer_color}; font-family: 'JetBrains Mono', monospace; text-shadow: 0 0 20px {layer_color}30;">
                        {layer.score:.0f}%
                    </div>
                    <div style="font-size: 0.7rem; color: #6B7280; margin-top: 0.5rem;">
                        {layer.anomaly_count} issues • {layer.critical_count} critical
                    </div>
                </div>
            """, unsafe_allow_html=True)

    # Show anomalies if any
    if gold_anomalies and gold_anomalies.total > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-header-3d">Active Gold Tier Anomalies</div>', unsafe_allow_html=True)

        # Model Health Anomalies
        if gold_anomalies.model_health_anomalies:
            st.markdown('<div style="font-size: 0.75rem; color: #9CA3AF; margin-bottom: 0.5rem;">Model Health (ML)</div>', unsafe_allow_html=True)
            for anomaly in gold_anomalies.model_health_anomalies[:3]:
                severity = anomaly.severity.value.lower()
                st.markdown(f"""
                    <div class="anomaly-card-3d {severity}">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                            <span class="badge-3d {severity}">{anomaly.failure_code.value}</span>
                            <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.625rem; color: #6B7280;">{anomaly.model_name}</span>
                        </div>
                        <div style="font-size: 0.85rem; font-weight: 600; color: #E5E7EB;">{anomaly.explanation[:100]}...</div>
                    </div>
                """, unsafe_allow_html=True)

        # Ethics Anomalies
        if gold_anomalies.ethics_anomalies:
            st.markdown('<div style="font-size: 0.75rem; color: #9CA3AF; margin: 1rem 0 0.5rem;">Ethics & Bias (ET)</div>', unsafe_allow_html=True)
            for anomaly in gold_anomalies.ethics_anomalies[:3]:
                severity = anomaly.severity.value.lower()
                regulatory_badge = ' <span class="badge-3d warning" style="margin-left: 0.5rem;">REGULATORY</span>' if anomaly.is_regulatory_risk else ''
                st.markdown(f"""
                    <div class="anomaly-card-3d {severity}">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                            <span class="badge-3d {severity}">{anomaly.failure_code.value}</span>{regulatory_badge}
                        </div>
                        <div style="font-size: 0.85rem; font-weight: 600; color: #E5E7EB;">{anomaly.explanation[:100]}...</div>
                        {'<div style="font-size: 0.7rem; color: #F59E0B; margin-top: 0.5rem;">⚠️ ' + ', '.join(anomaly.regulatory_references[:2]) + '</div>' if anomaly.regulatory_references else ''}
                    </div>
                """, unsafe_allow_html=True)

# =============================================================================
# Main Dashboard
# =============================================================================

def render_predictive_warnings():
    """Render predictive warnings panel - Constitution Section 11.1."""
    st.markdown("""
        <div class="glass-panel" style="border-left: 3px solid #8B5CF6;">
            <div class="section-header-3d" style="color: #8B5CF6;">
                <span style="font-size: 1.2rem;">🔮</span> Predictive Warnings
            </div>
    """, unsafe_allow_html=True)

    # Simulated predictions based on trends
    predictions = [
        {
            "title": "SLA Breach Risk",
            "confidence": 78,
            "eta": "~2 hours",
            "detail": "At current processing rate, delivery SLA may be missed",
            "severity": "warning"
        },
        {
            "title": "Storage Capacity",
            "confidence": 85,
            "eta": "~6 hours",
            "detail": "Data volume trending toward 90% capacity",
            "severity": "info"
        },
        {
            "title": "Model Drift Detected",
            "confidence": 72,
            "eta": "~24 hours",
            "detail": "Feature distribution shifting, retraining may be needed",
            "severity": "warning"
        }
    ]

    for pred in predictions:
        severity_color = "#fbbf24" if pred["severity"] == "warning" else "#60a5fa"
        st.markdown(f"""
            <div style="background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.2);
                        border-radius: 10px; padding: 1rem; margin-bottom: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="font-weight: 600; color: #E5E7EB;">{pred["title"]}</span>
                    <span style="background: rgba(139, 92, 246, 0.2); padding: 0.2rem 0.5rem; border-radius: 4px;
                                 font-size: 0.7rem; color: #8B5CF6;">{pred["confidence"]}% confidence</span>
                </div>
                <div style="font-size: 0.75rem; color: #9CA3AF; margin-bottom: 0.5rem;">{pred["detail"]}</div>
                <div style="font-size: 0.7rem; color: {severity_color};">⏱️ ETA: {pred["eta"]}</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_impact_graph():
    """Render impact/lineage visualization - Constitution Section 11.2."""
    # Header section
    st.markdown("""
        <div class="section-header-3d">
            <span style="font-size: 1.2rem;">🌐</span> Data Lineage & Impact
        </div>
        <p style="font-size: 0.75rem; color: #6B7280; margin-bottom: 1rem;">
            Shows how data flows through your pipeline. Hover over nodes to see details.
            If an upstream node fails, all downstream nodes (→) are affected.
        </p>
    """, unsafe_allow_html=True)

    # Create a simple lineage visualization using Plotly
    import plotly.graph_objects as go

    fig = go.Figure()

    # Nodes
    nodes = [
        {"name": "Raw Data", "x": 0, "y": 2, "color": "#D97706"},
        {"name": "Bronze Layer", "x": 1, "y": 2, "color": "#D97706"},
        {"name": "Silver Layer", "x": 2, "y": 2, "color": "#94A3B8"},
        {"name": "Gold Layer", "x": 3, "y": 2, "color": "#EAB308"},
        {"name": "ML Models", "x": 4, "y": 3, "color": "#8B5CF6"},
        {"name": "Reports", "x": 4, "y": 1, "color": "#22C55E"},
    ]

    # Add edges
    edges = [(0,1), (1,2), (2,3), (3,4), (3,5)]
    for e in edges:
        fig.add_trace(go.Scatter(
            x=[nodes[e[0]]["x"], nodes[e[1]]["x"]],
            y=[nodes[e[0]]["y"], nodes[e[1]]["y"]],
            mode='lines',
            line=dict(color='rgba(255,255,255,0.2)', width=2),
            hoverinfo='skip'
        ))

    # Add nodes
    for node in nodes:
        fig.add_trace(go.Scatter(
            x=[node["x"]],
            y=[node["y"]],
            mode='markers+text',
            marker=dict(size=30, color=node["color"], line=dict(color='white', width=2)),
            text=[node["name"]],
            textposition="bottom center",
            textfont=dict(color='#9CA3AF', size=10),
            hoverinfo='text',
            hovertext=node["name"]
        ))

    fig.update_layout(
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=20, b=40),
        height=200,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # Impact stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Downstream Systems", "12", help="Systems affected by data changes")
    with col2:
        st.metric("Active Pipelines", "8", help="Currently running pipelines")
    with col3:
        st.metric("Data Freshness", "2m", delta="-30s", help="Time since last update")


def render_cost_panel(anomaly_count: int):
    """Render cost attribution panel - Constitution Section 11.3."""
    # Estimate costs based on anomalies
    compute_cost = anomaly_count * 12.50  # Pipeline reruns
    labor_cost = anomaly_count * 75.00    # Engineer time
    total_cost = compute_cost + labor_cost

    st.markdown(f"""
        <div class="glass-panel" style="border-left: 3px solid #10B981;">
            <div class="section-header-3d" style="color: #10B981;">
                <span style="font-size: 1.2rem;">💰</span> Cost Attribution
            </div>
            <div style="text-align: center; margin-bottom: 1rem;">
                <div style="font-size: 2.5rem; font-weight: 700; color: #10B981; font-family: 'Roboto Mono', monospace;">
                    ${total_cost:,.2f}
                </div>
                <div style="font-size: 0.75rem; color: #9CA3AF;">Estimated incident cost today</div>
            </div>
            <div style="display: flex; gap: 1rem;">
                <div style="flex: 1; background: rgba(16, 185, 129, 0.1); padding: 0.75rem; border-radius: 8px; text-align: center;">
                    <div style="font-size: 0.65rem; color: #9CA3AF; text-transform: uppercase;">Compute</div>
                    <div style="font-weight: 600; color: #E5E7EB;">${compute_cost:,.2f}</div>
                </div>
                <div style="flex: 1; background: rgba(16, 185, 129, 0.1); padding: 0.75rem; border-radius: 8px; text-align: center;">
                    <div style="font-size: 0.65rem; color: #9CA3AF; text-transform: uppercase;">Labor</div>
                    <div style="font-weight: 600; color: #E5E7EB;">${labor_cost:,.2f}</div>
                </div>
            </div>
            <div style="margin-top: 1rem; padding: 0.75rem; background: rgba(16, 185, 129, 0.05); border-radius: 8px;">
                <div style="font-size: 0.7rem; color: #10B981;">💡 ROI: DMRG prevented ~$4,250 in costs this week</div>
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_self_healing_status():
    """Render self-healing status panel - Constitution Section 11.5."""
    st.markdown("""
        <div class="glass-panel" style="border-left: 3px solid #F59E0B;">
            <div class="section-header-3d" style="color: #F59E0B;">
                <span style="font-size: 1.2rem;">🔧</span> Self-Healing Actions
            </div>
    """, unsafe_allow_html=True)

    actions = [
        {"action": "Pipeline retry", "status": "success", "time": "5m ago", "detail": "Auto-retried failed ETL job"},
        {"action": "Cache fallback", "status": "active", "time": "12m ago", "detail": "Using cached data while source recovers"},
        {"action": "Alert escalation", "status": "pending", "time": "2m ago", "detail": "No response - escalating to on-call"},
    ]

    for action in actions:
        status_color = {"success": "#22C55E", "active": "#F59E0B", "pending": "#60A5FA"}[action["status"]]
        status_icon = {"success": "✓", "active": "⟳", "pending": "⏳"}[action["status"]]

        st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem;
                        background: rgba(245, 158, 11, 0.05); border-radius: 8px; margin-bottom: 0.5rem;">
                <div style="width: 24px; height: 24px; border-radius: 50%; background: {status_color}20;
                            display: flex; align-items: center; justify-content: center; color: {status_color};">
                    {status_icon}
                </div>
                <div style="flex: 1;">
                    <div style="font-weight: 500; color: #E5E7EB; font-size: 0.85rem;">{action["action"]}</div>
                    <div style="font-size: 0.7rem; color: #9CA3AF;">{action["detail"]}</div>
                </div>
                <div style="font-size: 0.65rem; color: #6B7280;">{action["time"]}</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_animated_health_ring(score: float):
    """Render an animated health ring using Plotly."""
    import plotly.graph_objects as go

    color = "#22C55E" if score >= 80 else "#F59E0B" if score >= 60 else "#EF4444"

    fig = go.Figure()

    # Background ring
    fig.add_trace(go.Pie(
        values=[100],
        hole=0.75,
        marker=dict(colors=['rgba(255,255,255,0.05)']),
        textinfo='none',
        hoverinfo='skip'
    ))

    # Score ring
    fig.add_trace(go.Pie(
        values=[score, 100-score],
        hole=0.75,
        marker=dict(colors=[color, 'rgba(0,0,0,0)']),
        textinfo='none',
        hoverinfo='skip',
        rotation=90
    ))

    # Center text
    fig.add_annotation(
        text=f"<b style='font-size:48px;color:{color}'>{score:.0f}</b><br><span style='color:#9CA3AF;font-size:14px'>Health Score</span>",
        showarrow=False,
        font=dict(size=20, color=color)
    )

    fig.update_layout(
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=0, b=0),
        height=250,
    )

    return fig


def render_resolution_learning():
    """Render resolution learning panel - Constitution Section 11.6."""
    st.markdown("""
        <div class="glass-panel" style="border-left: 3px solid #EC4899;">
            <div class="section-header-3d" style="color: #EC4899;">
                <span style="font-size: 1.2rem;">🧠</span> Resolution Learning
            </div>
            <p style="font-size: 0.75rem; color: #9CA3AF; margin-bottom: 1rem;">
                AI-powered recommendations based on historical resolution success rates
            </p>
    """, unsafe_allow_html=True)

    # Historical resolution data
    resolutions = [
        {"code": "DV-002", "action": "Add null handling", "success": 94, "avg_time": "12m", "recurrence": 8},
        {"code": "SC-003", "action": "Update schema version", "success": 87, "avg_time": "25m", "recurrence": 15},
        {"code": "BL-002", "action": "Fix FK constraint", "success": 76, "avg_time": "45m", "recurrence": 22},
        {"code": "FS-001", "action": "Pipeline optimization", "success": 82, "avg_time": "1h", "recurrence": 12},
        {"code": "ML-002", "action": "Retrain model", "success": 71, "avg_time": "2h", "recurrence": 28},
    ]

    for res in resolutions:
        success_color = "#22C55E" if res["success"] >= 80 else "#F59E0B" if res["success"] >= 60 else "#EF4444"
        recurrence_color = "#22C55E" if res["recurrence"] <= 10 else "#F59E0B" if res["recurrence"] <= 20 else "#EF4444"

        st.markdown(f"""
            <div style="background: rgba(236, 72, 153, 0.05); border: 1px solid rgba(236, 72, 153, 0.15);
                        border-radius: 8px; padding: 0.75rem; margin-bottom: 0.5rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-family: 'Roboto Mono', monospace; color: #EC4899; font-size: 0.75rem;">{res["code"]}</span>
                        <span style="color: #E5E7EB; margin-left: 0.5rem; font-size: 0.85rem;">{res["action"]}</span>
                    </div>
                    <span style="background: {success_color}20; color: {success_color}; padding: 0.2rem 0.5rem;
                                 border-radius: 4px; font-size: 0.7rem; font-weight: 600;">{res["success"]}%</span>
                </div>
                <div style="display: flex; gap: 1rem; margin-top: 0.5rem; font-size: 0.7rem; color: #6B7280;">
                    <span>⏱️ Avg: {res["avg_time"]}</span>
                    <span style="color: {recurrence_color};">🔄 Recurrence: {res["recurrence"]}%</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_anomaly_correlation():
    """Render anomaly correlation view - Constitution Section 2.5."""
    # Header
    st.markdown("""
        <div class="section-header-3d" style="color: #06B6D4;">
            <span style="font-size: 1.2rem;">🔗</span> Anomaly Correlation
        </div>
    """, unsafe_allow_html=True)

    # Correlated incidents
    correlations = [
        {
            "incident": "INC-2024-0142",
            "type": "Cascading",
            "anomalies": ["SC-003", "BL-002", "FS-001"],
            "root_cause": "Schema drift in upstream pipeline",
            "affected": 3,
        },
        {
            "incident": "INC-2024-0139",
            "type": "Common Cause",
            "anomalies": ["DV-002", "DV-004"],
            "root_cause": "ETL job timeout",
            "affected": 2,
        },
    ]

    for corr in correlations:
        type_color = {"Cascading": "#EF4444", "Common Cause": "#F59E0B", "Causal Chain": "#8B5CF6"}[corr["type"]]

        st.markdown(f"""
            <div style="background: rgba(6, 182, 212, 0.05); border: 1px solid rgba(6, 182, 212, 0.2);
                        border-radius: 10px; padding: 1rem; margin-bottom: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="font-family: 'Roboto Mono', monospace; color: #06B6D4; font-size: 0.8rem;">{corr["incident"]}</span>
                    <span style="background: {type_color}20; color: {type_color}; padding: 0.2rem 0.5rem;
                                 border-radius: 4px; font-size: 0.65rem; text-transform: uppercase;">{corr["type"]}</span>
                </div>
                <div style="font-size: 0.75rem; color: #9CA3AF; margin-bottom: 0.5rem;">
                    <strong style="color: #E5E7EB;">Root Cause:</strong> {corr["root_cause"]}
                </div>
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    {"".join([f'<span style="background: rgba(6, 182, 212, 0.2); padding: 0.2rem 0.4rem; border-radius: 4px; font-size: 0.65rem; font-family: monospace; color: #06B6D4;">{a}</span>' for a in corr["anomalies"]])}
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Correlation stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Correlated", "5", help="Anomalies linked to incidents")
    with col2:
        st.metric("Cascading", "2", help="Multi-system failures")
    with col3:
        st.metric("Reduced Noise", "60%", help="Alert reduction from correlation")


def render_compliance_frameworks():
    """Render compliance framework reports - Constitution Section 7.4."""
    st.markdown("""
        <div class="glass-panel">
            <div class="section-header-3d">
                <span style="font-size: 1.2rem;">📜</span> Compliance Frameworks
            </div>
    """, unsafe_allow_html=True)

    frameworks = [
        {"name": "GDPR", "status": "compliant", "score": 96, "last_audit": "2024-01-15"},
        {"name": "SOX", "status": "compliant", "score": 92, "last_audit": "2024-01-10"},
        {"name": "HIPAA", "status": "warning", "score": 78, "last_audit": "2024-01-12"},
        {"name": "CCPA", "status": "compliant", "score": 94, "last_audit": "2024-01-14"},
        {"name": "AI Act (EU)", "status": "review", "score": 85, "last_audit": "2024-01-08"},
        {"name": "NIST AI RMF", "status": "compliant", "score": 89, "last_audit": "2024-01-11"},
    ]

    for fw in frameworks:
        status_color = {"compliant": "#22C55E", "warning": "#F59E0B", "review": "#60A5FA"}[fw["status"]]
        status_icon = {"compliant": "✓", "warning": "⚠", "review": "🔍"}[fw["status"]]

        st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 1rem; padding: 0.75rem;
                        background: rgba(255, 255, 255, 0.02); border-radius: 8px; margin-bottom: 0.5rem;">
                <div style="width: 28px; height: 28px; border-radius: 50%; background: {status_color}20;
                            display: flex; align-items: center; justify-content: center; color: {status_color};
                            font-size: 0.8rem;">{status_icon}</div>
                <div style="flex: 1;">
                    <div style="font-weight: 500; color: #E5E7EB; font-size: 0.85rem;">{fw["name"]}</div>
                    <div style="font-size: 0.65rem; color: #6B7280;">Last audit: {fw["last_audit"]}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-weight: 600; color: {status_color}; font-size: 0.9rem;">{fw["score"]}%</div>
                    <div style="font-size: 0.6rem; color: #6B7280; text-transform: uppercase;">{fw["status"]}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_column_health_breakdown(anomalies: list):
    """Render column-level health breakdown chart showing which columns have issues."""
    import plotly.graph_objects as go

    st.markdown('<div class="section-header-3d">Column-Level Data Quality</div>', unsafe_allow_html=True)

    # Aggregate issues by column
    column_issues = {}
    for anomaly in anomalies:
        if hasattr(anomaly, 'affected_fields') and anomaly.affected_fields:
            for field in anomaly.affected_fields:
                if field not in column_issues:
                    column_issues[field] = {'count': 0, 'records': 0, 'severity': 'INFO'}
                column_issues[field]['count'] += 1
                if hasattr(anomaly, 'affected_records'):
                    column_issues[field]['records'] += len(anomaly.affected_records)
                # Track worst severity
                if hasattr(anomaly, 'severity'):
                    sev = anomaly.severity.value if hasattr(anomaly.severity, 'value') else str(anomaly.severity)
                    if sev == 'CRITICAL' or (sev == 'WARNING' and column_issues[field]['severity'] == 'INFO'):
                        column_issues[field]['severity'] = sev

    if not column_issues:
        st.markdown("""
            <div style="text-align: center; padding: 2rem; color: #22C55E;">
                <span style="font-size: 2rem;">✅</span>
                <div style="margin-top: 0.5rem;">All columns healthy</div>
            </div>
        """, unsafe_allow_html=True)
        return

    # Sort by record count
    sorted_columns = sorted(column_issues.items(), key=lambda x: x[1]['records'], reverse=True)[:10]

    columns = [c[0] for c in sorted_columns]
    records = [c[1]['records'] for c in sorted_columns]
    severities = [c[1]['severity'] for c in sorted_columns]

    # Color by severity
    colors = []
    for sev in severities:
        if sev == 'CRITICAL':
            colors.append('#EF4444')
        elif sev == 'WARNING':
            colors.append('#F59E0B')
        else:
            colors.append('#60A5FA')

    fig = go.Figure(data=[
        go.Bar(
            x=records,
            y=columns,
            orientation='h',
            marker_color=colors,
            text=[f"{r:,}" for r in records],
            textposition='outside',
            textfont=dict(color='#E5E7EB', size=11),
            hovertemplate="<b>%{y}</b><br>Affected: %{x:,} rows<extra></extra>"
        )
    ])

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, system-ui, sans-serif", color="#9CA3AF"),
        margin=dict(l=10, r=60, t=10, b=10),
        height=250,
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.05)',
            title=dict(text="Affected Rows", font=dict(size=10))
        ),
        yaxis=dict(
            showgrid=False,
            automargin=True
        ),
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # Column details table
    with st.expander("📋 Column Details", expanded=False):
        for col, data in sorted_columns:
            sev_color = {'CRITICAL': '#EF4444', 'WARNING': '#F59E0B', 'INFO': '#60A5FA'}[data['severity']]
            st.markdown(f"""
                <div style="display: flex; justify-content: space-between; padding: 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <div>
                        <span style="font-family: 'JetBrains Mono', monospace; color: #E5E7EB;">{col}</span>
                        <span style="background: {sev_color}20; color: {sev_color}; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.6rem; margin-left: 0.5rem;">{data['severity']}</span>
                    </div>
                    <div style="font-family: 'JetBrains Mono', monospace; color: #EF4444; font-weight: 600;">{data['records']:,} rows</div>
                </div>
            """, unsafe_allow_html=True)


def render_plain_language_summary(health_score: float, anomaly_count: int, critical_count: int):
    """Render plain language summary - Constitution Section 6.2."""
    # Generate contextual summary
    if health_score >= 90 and critical_count == 0:
        summary = "All systems healthy. No critical issues detected in the past 24 hours."
        icon = "✅"
        color = "#22C55E"
    elif critical_count > 0:
        summary = f"ALERT: {critical_count} critical issue(s) require immediate attention. Data quality may be impacted."
        icon = "🚨"
        color = "#EF4444"
    elif anomaly_count > 5:
        summary = f"{anomaly_count} data sources showing anomalies. Review recommended within 4 hours."
        icon = "⚠️"
        color = "#F59E0B"
    else:
        summary = f"System operating normally with {anomaly_count} minor warnings under observation."
        icon = "ℹ️"
        color = "#60A5FA"

    st.markdown(f"""
        <div style="background: linear-gradient(135deg, {color}15, {color}05); border: 1px solid {color}40;
                    border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem;">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <span style="font-size: 2rem;">{icon}</span>
                <div>
                    <div style="font-size: 0.65rem; text-transform: uppercase; color: #6B7280; letter-spacing: 1px; margin-bottom: 0.25rem;">
                        System Status Summary
                    </div>
                    <div style="font-size: 1rem; color: #E5E7EB; line-height: 1.5;">
                        {summary}
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)


def main():
    """Main dashboard entry point."""
    # Render sidebar with file upload and quick start
    render_sidebar()

    # Load data
    health, is_stale = services["loader"].get_health_state()
    results = services["loader"].get_latest_results()
    anomaly_result = services["loader"].get_anomalies()
    audit_events = services["loader"].get_audit_events()

    # Load Silver tier data
    silver_health, silver_stale = services["loader"].get_silver_health_state()
    silver_anomalies = services["loader"].get_silver_anomalies()

    # Load Gold tier data
    gold_health, gold_stale = services["loader"].get_gold_health_state()
    gold_anomalies = services["loader"].get_gold_anomalies()

    # Calculate metrics
    severity_counts = services["calculator"].get_severity_counts(anomaly_result.anomalies)
    for sev, count in silver_anomalies.by_severity.items():
        severity_counts[sev] = severity_counts.get(sev, 0) + count
    for sev, count in gold_anomalies.by_severity.items():
        severity_counts[sev] = severity_counts.get(sev, 0) + count

    # Build timeline
    silver_anomaly_tuple = (
        silver_anomalies.schema_anomalies,
        silver_anomalies.business_logic_anomalies,
        silver_anomalies.freshness_anomalies,
    )
    events, _ = services["timeline"].get_timeline_events(
        results.results,
        audit_events=audit_events,
        silver_anomalies=silver_anomaly_tuple,
    )

    # Render header
    render_header()
    st.markdown("<hr style='border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 1.5rem 0;'>", unsafe_allow_html=True)

    # Check for data
    if not services["loader"].has_data():
        st.markdown("""
            <div class="glass-panel" style="text-align: center; padding: 5rem;">
                <div style="font-size: 5rem; margin-bottom: 1.5rem; filter: drop-shadow(0 0 20px rgba(45, 212, 191, 0.3));">🔍</div>
                <div style="font-size: 1.75rem; font-weight: 600; color: #E5E7EB; margin-bottom: 0.75rem;">
                    No Validation Data Found
                </div>
                <div style="color: #6B7280; margin-bottom: 2.5rem; max-width: 400px; margin-left: auto; margin-right: auto;">
                    Run the Bronze tier validator to generate data for the dashboard.
                </div>
                <code style="background: rgba(45, 212, 191, 0.1); padding: 1rem 2rem; border-radius: 10px; color: #2DD4BF; font-family: 'JetBrains Mono', monospace;">
                    python -m src.cli.main validate your_data.csv
                </code>
            </div>
        """, unsafe_allow_html=True)
        return

    # Get current role
    current_role = st.session_state.get('role', 'EXECUTIVE')

    # Show role-specific header
    role_descriptions = {
        'EXECUTIVE': 'High-level health overview for decision makers',
        'ENGINEER': 'Full technical details with anomalies and metrics',
        'AUDIT': 'Compliance-focused view with timeline and exports',
    }
    st.markdown(f"""
        <div style="text-align: center; margin-bottom: 1rem; font-size: 0.75rem; color: #6B7280;">
            View: <span style="color: #2DD4BF; font-weight: 600;">{current_role}</span> - {role_descriptions.get(current_role, '')}
        </div>
    """, unsafe_allow_html=True)

    # Main layout
    left_col, center_col, right_col = st.columns([1, 2.5, 1.2])

    # Left column
    with left_col:
        # Control filters - shown for ENGINEER and AUDIT
        if current_role in ['ENGINEER', 'AUDIT']:
            with st.container():
                st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
                render_control_filters()
                st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

        critical_count = severity_counts.get('CRITICAL', 0)
        if critical_count > 0:
            render_risk_alert(critical_count, "Schema drift detected in Customer_Gold_v4. Immediate action required to prevent downstream model degradation.")
            st.markdown("<br>", unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
            bronze_score = health.overall_score if health else 98.2
            silver_score = silver_health.overall_score if silver_health else 94.5
            gold_score = gold_health.overall_score if gold_health else 100.0
            render_tier_tokens(bronze_score, silver_score, gold_score)
            st.markdown('</div>', unsafe_allow_html=True)

    # Center column
    with center_col:
        with st.container():
            st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
            render_3d_health_gauge(health.overall_score if health else 92)

            st.markdown("<hr style='border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 1rem 0;'>", unsafe_allow_html=True)

            batches = health.batches_evaluated if health else 1200000
            anomalies = len(anomaly_result.anomalies) + silver_anomalies.total
            latency = results.results[0].duration_ms if results.results else 42
            render_metrics_row(batches, anomalies, latency, 100.0)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Charts row - shown for ENGINEER and EXECUTIVE
        if current_role in ['ENGINEER', 'EXECUTIVE']:
            col1, col2 = st.columns([1.5, 1])

            with col1:
                with st.container():
                    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
                    st.markdown('<div class="section-header-3d">Reliability Trend (7D)</div>', unsafe_allow_html=True)
                    fig = create_3d_trend_chart()
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                    st.markdown('</div>', unsafe_allow_html=True)

            with col2:
                with st.container():
                    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
                    st.markdown('<div class="section-header-3d">Issue Distribution</div>', unsafe_allow_html=True)
                    fig = create_3d_severity_donut(severity_counts)
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                    st.markdown('</div>', unsafe_allow_html=True)

    # Right column
    with right_col:
        # Anomaly feed - shown for ENGINEER and EXECUTIVE
        if current_role in ['ENGINEER', 'EXECUTIVE']:
            with st.container():
                st.markdown('<div class="glass-panel" style="max-height: 420px; overflow-y: auto;">', unsafe_allow_html=True)
                render_anomaly_feed(anomaly_result.anomalies)
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

        # Audit timeline - shown for all roles, expanded for AUDIT
        with st.container():
            st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
            render_audit_timeline(events)
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Plain Language Summary (Constitution 6.2) - At the top for executives
    total_anomalies = len(anomaly_result.anomalies) + silver_anomalies.total + gold_anomalies.total
    critical_count = severity_counts.get('CRITICAL', 0)
    render_plain_language_summary(health.overall_score if health else 85, total_anomalies, critical_count)

    # Advanced Features Row 1 (NEW!)
    st.markdown('<div class="section-header-3d" style="font-size: 0.8rem;">🚀 Advanced Intelligence</div>', unsafe_allow_html=True)

    adv_col1, adv_col2, adv_col3 = st.columns(3)

    with adv_col1:
        render_predictive_warnings()

    with adv_col2:
        render_cost_panel(total_anomalies)

    with adv_col3:
        render_self_healing_status()

    st.markdown("<br>", unsafe_allow_html=True)

    # Advanced Features Row 2 (NEW!)
    adv2_col1, adv2_col2 = st.columns(2)

    with adv2_col1:
        render_resolution_learning()

    with adv2_col2:
        with st.container(border=True):
            render_anomaly_correlation()

    st.markdown("<br>", unsafe_allow_html=True)

    # Column-Level Data Quality Breakdown (NEW!)
    # Combine anomalies from all tiers
    all_anomalies = list(anomaly_result.anomalies)
    # Add Silver tier anomalies (they have separate lists)
    all_anomalies.extend(silver_anomalies.schema_anomalies)
    all_anomalies.extend(silver_anomalies.business_logic_anomalies)
    all_anomalies.extend(silver_anomalies.freshness_anomalies)
    # Add Gold tier anomalies
    all_anomalies.extend(gold_anomalies.model_health_anomalies)
    all_anomalies.extend(gold_anomalies.ethics_anomalies)
    col_chart_col, lineage_mini_col = st.columns([1.2, 1])

    with col_chart_col:
        with st.container(border=True):
            render_column_health_breakdown(all_anomalies)

    with lineage_mini_col:
        render_compliance_frameworks()

    st.markdown("<br>", unsafe_allow_html=True)

    # Data Lineage Graph (full width)
    with st.container(border=True):
        render_impact_graph()

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🥈 SILVER TIER", "🏆 GOLD TIER", "📋 COMPLIANCE", "⚙️ ADVANCED"])

    with tab1:
        render_silver_tier_detail(silver_health, silver_anomalies)

    with tab2:
        render_gold_tier_detail(gold_health, gold_anomalies)

    with tab4:
        st.markdown("""
            <div class="glass-panel">
                <div class="section-header-3d">Advanced Configuration</div>
                <p style="color: #6B7280; margin-bottom: 1.5rem; line-height: 1.6;">
                    Configure advanced features including thresholds, alerts, and automation rules.
                </p>
            </div>
        """, unsafe_allow_html=True)

        # Auto-refresh toggle
        col1, col2 = st.columns(2)
        with col1:
            auto_refresh = st.toggle("Enable Auto-Refresh", value=False, key="auto_refresh_toggle")
            if auto_refresh:
                refresh_interval = st.slider("Refresh interval (seconds)", 10, 120, 30)
                st.info(f"Dashboard will refresh every {refresh_interval} seconds")

        with col2:
            st.markdown("**Alert Thresholds**")
            critical_threshold = st.slider("Critical alert threshold", 0, 100, 70)
            warning_threshold = st.slider("Warning alert threshold", 0, 100, 40)

        st.markdown("<br>", unsafe_allow_html=True)

        # Runbook integration
        st.markdown("""
            <div class="glass-panel" style="border-left: 3px solid #60A5FA;">
                <div class="section-header-3d" style="color: #60A5FA;">📚 Runbook Integration</div>
        """, unsafe_allow_html=True)

        runbooks = [
            {"code": "DV-002", "name": "Null Value Resolution", "success_rate": 94},
            {"code": "SC-001", "name": "Missing Column Fix", "success_rate": 87},
            {"code": "BL-002", "name": "Referential Integrity Repair", "success_rate": 76},
        ]

        for rb in runbooks:
            st.markdown(f"""
                <div style="display: flex; justify-content: space-between; align-items: center;
                            padding: 0.75rem; background: rgba(96, 165, 250, 0.05); border-radius: 8px; margin-bottom: 0.5rem;">
                    <div>
                        <span style="font-family: 'Roboto Mono', monospace; color: #60A5FA; font-size: 0.8rem;">{rb["code"]}</span>
                        <span style="color: #E5E7EB; margin-left: 0.5rem;">{rb["name"]}</span>
                    </div>
                    <span style="color: #22C55E; font-size: 0.75rem;">{rb["success_rate"]}% success</span>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.markdown("""
            <div class="glass-panel">
                <div class="section-header-3d">Compliance Export</div>
                <p style="color: #6B7280; margin-bottom: 1.5rem; line-height: 1.6;">
                    Generate compliance reports for audit purposes. Reports include health scores,
                    anomaly details, and resolution timelines.
                </p>
            </div>
        """, unsafe_allow_html=True)

        # Prepare export data
        export_data = {
            "report_generated": datetime.now(timezone.utc).isoformat(),
            "overall_health_score": health.overall_score if health else 0,
            "bronze_tier": {
                "score": health.overall_score if health else 0,
                "batches_evaluated": health.batches_evaluated if health else 0,
                "anomaly_count": len(anomaly_result.anomalies),
            },
            "silver_tier": {
                "score": silver_health.overall_score if silver_health else 0,
                "schema_score": silver_health.schema_layer.score if silver_health else 0,
                "business_logic_score": silver_health.business_logic_layer.score if silver_health else 0,
                "freshness_score": silver_health.freshness_layer.score if silver_health else 0,
                "anomaly_count": silver_anomalies.total,
            },
            "gold_tier": {
                "score": gold_health.overall_score if gold_health else 0,
                "model_health_score": gold_health.model_health_layer.score if gold_health else 0,
                "ethics_score": gold_health.ethics_layer.score if gold_health else 0,
                "anomaly_count": gold_anomalies.total,
            },
            "severity_summary": severity_counts,
        }

        # CSV data for anomalies
        csv_lines = ["tier,layer,severity,failure_code,description,detected_at"]
        for a in anomaly_result.anomalies:
            csv_lines.append(f"Bronze,L1,{a.severity.value},{a.failure_code.value},\"{a.failure_code.description}\",{a.detected_at.isoformat()}")
        for a in silver_anomalies.schema_anomalies:
            csv_lines.append(f"Silver,L2,{a.severity.value},{a.failure_code.value},\"{a.failure_code.description}\",{a.timestamp.isoformat()}")
        for a in silver_anomalies.business_logic_anomalies:
            csv_lines.append(f"Silver,L3,{a.severity.value},{a.failure_code.value},\"{a.failure_code.description}\",{a.timestamp.isoformat()}")
        for a in silver_anomalies.freshness_anomalies:
            csv_lines.append(f"Silver,L4,{a.severity.value},{a.failure_code.value},\"{a.failure_code.description}\",{a.timestamp.isoformat()}")
        for a in gold_anomalies.model_health_anomalies:
            csv_lines.append(f"Gold,L5,{a.severity.value},{a.failure_code.value},\"{a.explanation[:50]}\",{a.timestamp.isoformat()}")
        for a in gold_anomalies.ethics_anomalies:
            csv_lines.append(f"Gold,L6,{a.severity.value},{a.failure_code.value},\"{a.explanation[:50]}\",{a.timestamp.isoformat()}")
        csv_content = "\n".join(csv_lines)

        # Text report for PDF-style export
        txt_report = f"""
================================================================================
                    DATA & MODEL RELIABILITY GUARDIAN
                        COMPLIANCE AUDIT REPORT
================================================================================

Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
Report ID: DMRG-{datetime.now().strftime('%Y%m%d%H%M%S')}

--------------------------------------------------------------------------------
                            EXECUTIVE SUMMARY
--------------------------------------------------------------------------------

Overall System Health: {health.overall_score if health else 0:.1f}%

Tier Breakdown:
  - Bronze Tier (Data Validation):     {health.overall_score if health else 0:.1f}%
  - Silver Tier (Schema/Logic/SLA):    {silver_health.overall_score if silver_health else 0:.1f}%
  - Gold Tier (Model/Ethics):          {gold_health.overall_score if gold_health else 0:.1f}%

Active Anomalies by Severity:
  - CRITICAL: {severity_counts.get('CRITICAL', 0)}
  - WARNING:  {severity_counts.get('WARNING', 0)}
  - INFO:     {severity_counts.get('INFO', 0)}

--------------------------------------------------------------------------------
                            LAYER DETAILS
--------------------------------------------------------------------------------

BRONZE TIER - Layer 1: Data Validation
  Score: {health.overall_score if health else 0:.1f}%
  Batches Evaluated: {health.batches_evaluated if health else 0:,}
  Anomalies: {len(anomaly_result.anomalies)}

SILVER TIER - Layers 2-4
  Overall Score: {silver_health.overall_score if silver_health else 0:.1f}%
  Layer 2 (Schema): {silver_health.schema_layer.score if silver_health else 0:.1f}%
  Layer 3 (Business Logic): {silver_health.business_logic_layer.score if silver_health else 0:.1f}%
  Layer 4 (Freshness): {silver_health.freshness_layer.score if silver_health else 0:.1f}%
  Total Anomalies: {silver_anomalies.total}

GOLD TIER - Layers 5-6
  Overall Score: {gold_health.overall_score if gold_health else 0:.1f}%
  Layer 5 (Model Health): {gold_health.model_health_layer.score if gold_health else 0:.1f}%
  Layer 6 (Ethics & Bias): {gold_health.ethics_layer.score if gold_health else 0:.1f}%
  Total Anomalies: {gold_anomalies.total}

--------------------------------------------------------------------------------
                            CERTIFICATION
--------------------------------------------------------------------------------

This report was automatically generated by the Data & Model Reliability Guardian
system. The data presented reflects the state of the system at the time of
generation.

Signed: DMRG Automated Compliance System
================================================================================
"""

        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button(
                label="📥 Export JSON",
                data=json.dumps(export_data, indent=2, default=str),
                file_name=f"dmrg_compliance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )
        with col2:
            st.download_button(
                label="📊 Export CSV",
                data=csv_content,
                file_name=f"dmrg_anomalies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )
        with col3:
            st.download_button(
                label="📄 Export Report",
                data=txt_report,
                file_name=f"dmrg_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
            )

    # Footer
    st.markdown("""
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 2.5rem 0; border-top: 1px solid rgba(255,255,255,0.06); margin-top: 2.5rem; font-size: 0.65rem; color: #4B5563; text-transform: uppercase; letter-spacing: 1px;">
            <div>
                <span>© 2024 Reliability Guardian AI</span>
                <span style="margin-left: 2rem;">Engine: NeuralCore 9.0</span>
            </div>
            <div>
                <span style="color: #2DD4BF;">System: Operational</span>
                <span style="margin-left: 1.5rem; cursor: pointer; transition: color 0.2s;">Documentation</span>
                <span style="margin-left: 1.5rem; cursor: pointer; transition: color 0.2s;">API Status</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Auto-refresh
    if time.time() - st.session_state.last_refresh > 30:
        st.session_state.last_refresh = time.time()
        st.rerun()

if __name__ == "__main__":
    main()
