from __future__ import annotations

from html import escape
from io import BytesIO
import json
import os
from pathlib import Path
from statistics import NormalDist

import pandas as pd
import streamlit as st
from streamlit.components.v1 import html as component_html

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ModuleNotFoundError:
    px = None
    go = None
    PLOTLY_AVAILABLE = False

from analytics import (
    aci214_process_classification,
    capability_metrics_table,
    interpretation_summary,
    aci_compliance,
    classify_risk,
    detect_abnormalities,
    export_report,
    positive_insights,
    risk_intelligence_table,
    prepare_data,
    read_excel_input,
    six_sigma_metrics,
    validate_columns,
)

page_domain = st.session_state.get("selected_quality_domain", "Construction Quality")

st.set_page_config(
    page_title=f"{page_domain} Analytics & Six Sigma Intelligence Platform",
    page_icon="C",
    layout="wide",
)

PLOTLY_TEMPLATE = "plotly_white"


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #edf7ff; --mint: #eefdf6; --card: rgba(255,255,255,.92); --card-solid: #ffffff;
            --line: #d7e7f5; --line-strong: #b9d7ec; --blue: #1d4ed8; --cyan: #0891b2;
            --teal: #0f766e; --green: #15803d; --amber: #b45309; --orange: #c2410c;
            --red: #dc2626; --text: #0f1f3a; --muted: #64748b; --soft: #f6fbff;
        }
        .stApp {
            background:
                radial-gradient(circle at 12% 0%, rgba(14,165,233,.22), transparent 28%),
                radial-gradient(circle at 92% 10%, rgba(34,197,94,.16), transparent 30%),
                linear-gradient(135deg, #f7fbff 0%, #eff8ff 44%, #f3fff8 100%);
            color: var(--text);
        }
        .block-container { padding-top: 1.1rem; padding-bottom: 2.2rem; max-width: 1780px; }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(255,255,255,.96), #eef8ff 62%, #eafcf5);
            border-right: 1px solid var(--line); box-shadow: 12px 0 36px rgba(29,78,216,.08);
        }
        [data-testid="stSidebar"] * { color: var(--text); }
        [data-testid="stSidebar"] [role="radiogroup"] label {
            border-radius: 10px; padding: 8px 10px; margin: 2px 0; transition: .16s ease;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:hover { background: #e8f4ff; }
        .st-key-domain_selector_shell {
            position: relative; overflow: hidden; margin: .85rem 0 1.1rem; padding: 1.2rem;
            border: 1px solid rgba(100,164,214,.46); border-radius: 22px;
            background:
                radial-gradient(circle at 8% 0%, rgba(14,165,233,.18), transparent 34%),
                radial-gradient(circle at 94% 100%, rgba(34,197,94,.13), transparent 32%),
                linear-gradient(145deg, rgba(255,255,255,.98), rgba(239,248,255,.96));
            box-shadow: 0 20px 50px rgba(15,58,95,.12), inset 0 1px 0 rgba(255,255,255,.96);
        }
        .domain-selector-kicker { color:#0284c7; font-size:.72rem; font-weight:950; letter-spacing:.13em; text-transform:uppercase; }
        .domain-selector-title { color:#0f2742; font-size:1.22rem; line-height:1.25; font-weight:950; margin:.18rem 0 .25rem; }
        .domain-selector-copy { color:#64748b; font-size:.88rem; margin-bottom:.85rem; }
        .st-key-domain_selector_shell [role="radiogroup"] {
            display:grid !important; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.72rem !important;
            align-items:stretch; width:100%;
        }
        .st-key-domain_selector_shell [role="radiogroup"] label {
            position:relative; min-height:76px; margin:0 !important; padding:1rem 1rem !important;
            display:flex !important; align-items:center !important; justify-content:flex-start;
            border:1px solid #d4e6f4; border-radius:16px; background:rgba(255,255,255,.92);
            box-shadow:0 8px 20px rgba(15,58,95,.07); cursor:pointer;
            transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease, background .18s ease;
        }
        .st-key-domain_selector_shell [role="radiogroup"] label:hover {
            transform:translateY(-3px); border-color:#38bdf8; background:#f7fcff;
            box-shadow:0 15px 28px rgba(14,116,144,.15);
        }
        .st-key-domain_selector_shell [role="radiogroup"] label:has(input:checked) {
            color:#fff !important; border-color:#0ea5e9;
            background:linear-gradient(135deg,#075985 0%,#0284c7 55%,#0f766e 100%);
            box-shadow:0 16px 32px rgba(2,132,199,.27), inset 0 1px 0 rgba(255,255,255,.25);
        }
        .st-key-domain_selector_shell [role="radiogroup"] label:has(input:checked) p { color:#fff !important; }
        .st-key-domain_selector_shell [role="radiogroup"] label p {
            margin:0 !important; color:#17324f; font-size:.93rem; line-height:1.25; font-weight:850;
        }
        .st-key-domain_selector_shell [role="radiogroup"] input { width:0 !important; height:0 !important; opacity:0 !important; position:absolute !important; }
        @media (max-width: 980px) { .st-key-domain_selector_shell [role="radiogroup"] { grid-template-columns:repeat(2,minmax(0,1fr)); } }
        @media (max-width: 640px) { .st-key-domain_selector_shell [role="radiogroup"] { grid-template-columns:1fr; } }
        .qc-logo {
            width: 66px; height: 66px; display: grid; place-items: center; border-radius: 18px;
            background: linear-gradient(145deg, #dff7ff, #d9fff0); color: #075985; font-weight: 950;
            border: 1px solid #a7d8f5; box-shadow: inset 0 0 0 1px rgba(255,255,255,.8), 0 16px 28px rgba(14,165,233,.16);
            margin-bottom: .85rem; letter-spacing: .02em;
        }
        .side-card {
            margin-top: 1.2rem; padding: 1rem; border-radius: 14px; border: 1px solid #c9e2f7;
            background: linear-gradient(150deg, #eff7ff, #e9fff6); box-shadow: 0 14px 28px rgba(15,23,42,.06);
            color: #173052; line-height: 1.45;
        }
        .top-shell {
            display: grid; grid-template-columns: minmax(420px, 1fr) auto; gap: 1rem; align-items: stretch;
            border: 1px solid rgba(185,215,236,.95); background: rgba(255,255,255,.82); border-radius: 18px;
            padding: 1.2rem; box-shadow: 0 22px 55px rgba(15,23,42,.10); margin: 0 0 1rem;
            backdrop-filter: blur(10px); position: relative; overflow: hidden;
        }
        .top-shell:before {
            content: ""; position: absolute; inset: 0 auto 0 0; width: 8px;
            background: linear-gradient(180deg, #2563eb, #06b6d4, #22c55e);
        }
        .brand-row { display: flex; align-items: center; gap: 1rem; min-width: 0; padding-left: .15rem; }
        .brand-mark {
            width: 58px; height: 58px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 16px;
            background: linear-gradient(145deg, #2563eb, #06b6d4); color: white; font-weight: 950;
            border: 1px solid rgba(255,255,255,.65); box-shadow: 0 18px 34px rgba(37,99,235,.22);
        }
        .hero-kicker { color: var(--cyan); font-size: .75rem; font-weight: 900; text-transform: uppercase; letter-spacing: .08em; margin-bottom: .24rem; }
        .hero-title { font-size: 1.78rem; font-weight: 950; color: var(--text); line-height: 1.12; margin: 0; }
        .hero-subtitle { color: #52657f; font-size: .95rem; margin-top: .45rem; line-height: 1.4; max-width: 780px; }
        .author-ribbon { display: inline-flex; align-items: center; gap: .45rem; margin-top: .75rem; padding: .48rem .78rem; border-radius: 999px; background: linear-gradient(90deg, #e0f2fe, #dcfce7); border: 1px solid #bae6fd; color: #0f3a5f; font-weight: 950; box-shadow: 0 10px 22px rgba(14,165,233,.12); }
        .author-ribbon span { color: #0369a1; }
        .author-card { margin-top: .85rem; padding: .85rem 1rem; border-radius: 14px; border: 1px solid #bae6fd; background: linear-gradient(135deg, #f0f9ff, #f0fdf4); box-shadow: 0 12px 24px rgba(14,165,233,.10); }
        .author-card small { display:block; color:#64748b; font-weight:800; text-transform:uppercase; letter-spacing:.06em; }
        .author-card b { display:block; color:#0f1f3a; font-size:1.05rem; margin-top:.16rem; }
        .top-pills { display: flex; flex-wrap: wrap; gap: .55rem; justify-content: flex-end; align-content: center; max-width: 560px; }
        .top-pill {
            border: 1px solid #cfe4f5; background: linear-gradient(180deg, #ffffff, #f3f9ff); border-radius: 12px;
            padding: .62rem .82rem; color: var(--text); font-weight: 850; font-size: .82rem; box-shadow: 0 8px 18px rgba(15,23,42,.05);
        }
        .top-pill.legend { background: #ffffff; min-width: 100%; text-align: center; }
        .upload-shell {
            display: grid; grid-template-columns: minmax(280px, .9fr) minmax(360px, 1.4fr); gap: 1rem; margin: 0 0 1rem;
        }
        .upload-card, .schema-card, .empty-state {
            border: 1px solid var(--line); border-radius: 16px; background: rgba(255,255,255,.86);
            box-shadow: 0 16px 38px rgba(15,23,42,.07); padding: 1rem;
        }
        .upload-card { background: linear-gradient(145deg, #ffffff, #edf8ff); }
        .upload-title { font-weight: 900; color: var(--text); font-size: 1rem; margin-bottom: .25rem; }
        .upload-copy { color: var(--muted); font-size: .88rem; margin-bottom: .8rem; }
        [data-testid="stFileUploader"] { background: transparent; }
        [data-testid="stFileUploader"] section {
            border: 1px dashed #93c5fd; border-radius: 14px; background: #f8fcff; padding: .9rem;
        }
        .empty-state {
            display: grid; grid-template-columns: 1fr auto; gap: 1rem; align-items: center;
            background: linear-gradient(135deg, #eef6ff, #f0fff7); border-color: #c7dff3; padding: 1.05rem 1.15rem;
        }
        .empty-state h3 { margin: 0 0 .25rem; font-size: 1.08rem; color: var(--text); }
        .empty-state p { margin: 0; color: #52657f; }
        .empty-badges { display: flex; flex-wrap: wrap; gap: .5rem; justify-content: flex-end; }
        .empty-badge { border-radius: 999px; background: #ffffff; border: 1px solid #d8e9f7; padding: .42rem .7rem; font-weight: 800; font-size: .78rem; color: #1e3a5f; }
        .panel {
            border: 1px solid var(--line); background: rgba(255,255,255,.93); border-radius: 14px;
            padding: 1rem; box-shadow: 0 14px 34px rgba(15,23,42,.08);
        }
        .kpi-card {
            min-height: 132px; border: 1px solid #cfe4f5; background: linear-gradient(150deg, #ffffff, #f5fbff 70%, #effdf6);
            border-radius: 14px; padding: 1rem; box-shadow: 0 16px 34px rgba(37,99,235,.09);
            position: relative; overflow: hidden;
        }
        .kpi-card:before { content: ""; position: absolute; width: 78px; height: 78px; right: -24px; top: -28px; background: radial-gradient(circle, rgba(14,165,233,.18), transparent 68%); }
        .kpi-card:after { content: ""; position: absolute; inset: auto 0 0 0; height: 4px; background: linear-gradient(90deg, #2563eb, #0891b2, #16a34a); opacity: .82; }
        .kpi-label, .small-label { color: var(--muted); font-size: .76rem; font-weight: 850; line-height: 1.25; }
        .kpi-value { color: var(--text); font-size: 1.48rem; font-weight: 950; line-height: 1.08; white-space: normal; overflow-wrap: anywhere; margin-top: .35rem; }
        .kpi-number { white-space: nowrap; }
        .kpi-unit { display: block; font-size: .92rem; font-weight: 900; margin-top: .12rem; }
        .kpi-chip { display: inline-block; padding: .25rem .62rem; margin-top: .65rem; border-radius: 999px; background: #dcfce7; color: var(--green); font-weight: 900; font-size: .72rem; line-height: 1.2; }
        .kpi-chip.amber { background: #fef3c7; color: var(--amber); }
        .kpi-chip.red { background: #fee2e2; color: var(--red); }
        .kpi-chip.review { background: #ffedd5; color: var(--orange); }
        .section-title { font-size: .92rem; font-weight: 950; text-transform: uppercase; color: var(--text); margin: .35rem 0 .7rem; letter-spacing: .035em; }
        .section-title:before { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: linear-gradient(135deg, #2563eb, #22c55e); margin-right: .5rem; vertical-align: 1px; }
        .risk-banner { border-left: 6px solid var(--green); background: #ffffff; border-radius: 14px; padding: 1rem; border: 1px solid var(--line); margin: .85rem 0; box-shadow: 0 14px 30px rgba(15,23,42,.07); }
        .risk-banner.amber { border-left-color: var(--amber); }
        .risk-banner.red { border-left-color: var(--red); }
        .risk-title { font-size: 1.1rem; font-weight: 950; color: var(--text); }
        .risk-copy { color: var(--muted); margin-top: .24rem; }
        .insight-card, .alert-card { border: 1px solid var(--line); background: #ffffff; border-radius: 14px; padding: .95rem; min-height: 100px; box-shadow: 0 12px 26px rgba(15,23,42,.06); }
        .insight-card { border-color: #b9f2ce; background: linear-gradient(145deg, #ffffff, #f0fdf4); }
        .alert-card { border-color: #fed7aa; background: linear-gradient(145deg, #ffffff, #fff7ed); }
        .small-value { color: var(--text); font-weight: 950; font-size: 1rem; margin-top: .32rem; }
        .summary-score { text-align: center; padding: .95rem; border-radius: 14px; background: linear-gradient(145deg, #eff6ff, #ecfeff); border: 1px solid var(--line); margin-bottom: .75rem; }
        .summary-score .score { font-size: 2.35rem; font-weight: 950; color: var(--blue); }
        .summary-line { display: flex; justify-content: space-between; border-top: 1px solid #eef2f7; padding: .48rem 0; color: var(--muted); }
        .summary-line b { color: var(--text); }
        .capability-tile { border: 1px solid var(--line); background: linear-gradient(145deg, #ffffff, #f8fbff); border-radius: 14px; padding: .9rem; margin-bottom: .75rem; box-shadow: 0 10px 22px rgba(15,23,42,.06); }
        .capability-value { font-size: 1.55rem; font-weight: 950; color: var(--blue); }
        .meter { height: 8px; background: #e2e8f0; border-radius: 999px; overflow: hidden; margin-top: .55rem; }
        .meter-fill { height: 100%; background: linear-gradient(90deg, #38bdf8, #16a34a); border-radius: 999px; }
        div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 14px; background: #ffffff; }
        .stTabs [data-baseweb="tab"] { background: #ffffff; border-radius: 10px 10px 0 0; border: 1px solid var(--line); color: var(--text); }
        .stDownloadButton button, .stFileUploader button, .stButton button { background: linear-gradient(90deg, #2563eb, #0891b2); color: white; border: 0; border-radius: 10px; font-weight: 900; }
        .print-report { display: none; } .report-preview { display: block !important; margin: 16px 0 24px; border-radius: 14px; overflow: hidden; box-shadow: 0 18px 40px rgba(15,23,42,.18); border: 1px solid #b7d7ef; } .report-preview .rdash { min-height: auto; }
        @media (max-width: 980px) { .top-shell, .upload-shell, .empty-state { grid-template-columns: 1fr; } .top-pills { justify-content: flex-start; } }
        @media print {
            @page { size: A4 landscape; margin: 10mm; }
            header, footer, [data-testid="stSidebar"], [data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton, .print-hide { display: none !important; }
            .stApp { background: #ffffff !important; }
            .print-report { display: block !important; color: #0f1d3d; font-family: Segoe UI, Arial, sans-serif; }
.print-chip { display: inline-block; margin-top: 8px; padding: 4px 8px; border-radius: 6px; background: #dcfce7; color: #15803d; font-size: 11px; font-weight: 800; }
            .print-chip.warn { background: #fef3c7; color: #b45309; }
            .print-chip.bad { background: #fee2e2; color: #dc2626; }
            .print-section-title { font-size: 15px; font-weight: 900; color: #071638; margin: 16px 0 8px; text-transform: uppercase; }
            .print-table { width: 100%; border-collapse: collapse; font-size: 11px; }
            .print-table th { background: #f3f7fc; color: #071638; text-align: left; }
            .print-table th, .print-table td { border: 1px solid #d9e8f5; padding: 6px; }
            .print-note { border-left: 5px solid #2563eb; padding: 10px 12px; background: #eff6ff; border-radius: 6px; margin-top: 10px; }
        }

        /* Enterprise light dashboard layout inspired by the supplied reference. */
        .stApp { background: #f8fbff !important; }
        .block-container { max-width: 1660px; padding-top: .8rem; }
        [data-testid="stSidebar"] { background: #ffffff !important; border-right: 1px solid #e5edf7; box-shadow: none; }
        .sidebar-brand { display:flex; align-items:center; gap:.75rem; margin:.25rem 0 1.25rem; color:#0b1d4d; font-weight:900; }
        .qc-logo { width:42px; height:42px; border-radius:10px; margin:0; background:linear-gradient(135deg,#e0f7ff,#ffffff); color:#1689d7; border:1px solid #d5e8f7; box-shadow:none; }
        [data-testid="stSidebar"] [role="radiogroup"] label { border-radius:8px; padding:10px 12px; color:#58709b; font-weight:800; }
        [data-testid="stSidebar"] [role="radiogroup"] label:first-of-type { background:#edf6ff; color:#1463ff; }
        .author-card, .side-card { box-shadow:none; border:1px solid #dce8f6; background:#f8fbff; }
        .top-shell.app-header { grid-template-columns:minmax(540px,1fr) auto; align-items:center; background:#ffffff; border-radius:0; border:0; border-bottom:1px solid #e5edf7; box-shadow:none; padding:1rem 1.25rem; margin:-.8rem 0 1rem; }
        .top-shell:before { display:none; }
        .brand-mark { width:40px; height:40px; border-radius:10px; background:linear-gradient(135deg,#e0f7ff,#ffffff); color:#1689d7; border:1px solid #d5e8f7; box-shadow:none; }
        .hero-title { font-size:1.55rem; color:#081747; letter-spacing:0; }
        .hero-subtitle { margin-top:.25rem; font-size:.9rem; color:#456080; }
        .signature { font-family:'Brush Script MT','Segoe Script',cursive; font-size:1.28rem; color:#1268ff; margin-left:.35rem; }
        .header-tools { align-items:center; max-width:none; flex-wrap:nowrap; }
        .top-pill { background:#ffffff; border:1px solid #dce8f6; box-shadow:none; color:#0b1d4d; }
        .avatar-pill { width:44px; height:44px; border-radius:999px; display:grid; place-items:center; color:white; background:#3b82f6; font-weight:900; box-shadow:0 10px 20px rgba(59,130,246,.18); }
        .upload-shell { grid-template-columns: 1.05fr 1.95fr; align-items:stretch; }
        .upload-card, .schema-card, .panel { background:#ffffff; border:1px solid #dce8f6; border-radius:10px; box-shadow:0 8px 18px rgba(18,35,77,.04); }
        [data-testid="stFileUploader"] section { border:1px dashed #89bfff; background:#fbfdff; border-radius:10px; }
        .kpi-card { min-height:112px; border-radius:10px; border:1px solid #dce8f6; background:#ffffff; box-shadow:0 8px 18px rgba(18,35,77,.045); padding:.85rem; }
        .kpi-card:before { display:none; }
        .kpi-card:after { height:0; }
        .kpi-label { color:#52678e; font-size:.73rem; }
        .kpi-value { font-size:1.22rem; color:#081747; }
        .kpi-unit { font-size:.76rem; color:#52678e; }
        .kpi-chip { margin-top:.5rem; border-radius:7px; font-size:.68rem; }
        .section-title { color:#0046b8; margin-top:.75rem; }
        div[data-testid="stPlotlyChart"] { border:1px solid #dce8f6; border-radius:10px; padding:.4rem; background:#ffffff; box-shadow:0 8px 18px rgba(18,35,77,.04); }
        .stDownloadButton button, .stButton button { border-radius:8px !important; box-shadow:none !important; background:#ffffff !important; color:#0b4fb3 !important; border:1px solid #d7e5f5 !important; }
        .stDownloadButton button:hover, .stButton button:hover { border-color:#8bbdff !important; background:#f2f8ff !important; }

        </style>
        """,
        unsafe_allow_html=True,
    )


def format_number(value: float, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.2f}{suffix}"


def status_label(chip: str, state: str = "green") -> str:
    chip_text = str(chip).lower()
    if state == "red" or chip_text in ["critical", "high"]:
        return "🔴 Critical"
    if chip_text == "review":
        return "🟠 Review"
    if chip_text in ["moderate risk", "moderate"]:
        return "🟡 Moderate Risk"
    if state == "amber" or chip_text in ["monitor", "capability"]:
        return "🟡 Monitor"
    if chip_text == "good":
        return "🟢 Good"
    return "🟢 Excellent"


def status_class(chip: str, state: str = "green") -> str:
    chip_text = str(chip).lower()
    if state == "red" or chip_text in ["critical", "high"]:
        return "red"
    if chip_text == "review":
        return "review"
    if state == "amber" or chip_text in ["monitor", "capability", "moderate risk", "moderate"]:
        return "amber"
    if state == "blue":
        return "blue"
    return ""


def risk_status_label(risk: str) -> str:
    return "🟢 Excellent" if risk == "Green" else "🟡 Monitor" if risk == "Amber" else "🔴 Critical"



def sigma_status(sigma_level: float) -> tuple[str, str]:
    if sigma_level is None or pd.isna(sigma_level):
        return "Review", "amber"
    if sigma_level >= 4.50:
        return "Excellent", "green"
    if sigma_level >= 3.00:
        return "Good", "green"
    if sigma_level >= 2.00:
        return "Monitor", "amber"
    return "Critical", "red"




def is_valid_number(value: float) -> bool:
    return value is not None and not pd.isna(value)


def complete_capability_metrics(metrics: dict) -> dict:
    metrics = dict(metrics)
    cp_missing = not is_valid_number(metrics.get("cp"))
    cpk_missing = not is_valid_number(metrics.get("cpk"))
    if not (cp_missing or cpk_missing):
        return metrics

    mean = metrics.get("mean")
    std = metrics.get("std_dev") or metrics.get("standard_deviation")
    lsl = metrics.get("calculated_lsl") if is_valid_number(metrics.get("calculated_lsl")) else metrics.get("lcl")
    usl = metrics.get("calculated_usl") if is_valid_number(metrics.get("calculated_usl")) else metrics.get("ucl")
    if not all(is_valid_number(v) for v in [mean, std, lsl, usl]) or float(std) <= 0 or float(usl) <= float(lsl):
        return metrics

    mean = float(mean)
    std = float(std)
    lsl = float(lsl)
    usl = float(usl)
    cpu = (usl - mean) / (3 * std)
    cpl = (mean - lsl) / (3 * std)
    cp = (usl - lsl) / (6 * std)
    cpk = min(cpu, cpl)
    metrics.update({
        "cp": cp,
        "cpu": cpu,
        "cpl": cpl,
        "cpk": cpk,
        "pp": metrics.get("pp") if is_valid_number(metrics.get("pp")) else cp,
        "ppu": metrics.get("ppu") if is_valid_number(metrics.get("ppu")) else cpu,
        "ppl": metrics.get("ppl") if is_valid_number(metrics.get("ppl")) else cpl,
        "ppk": metrics.get("ppk") if is_valid_number(metrics.get("ppk")) else cpk,
        "ppk_lower": metrics.get("ppk_lower") if is_valid_number(metrics.get("ppk_lower")) else cpl,
        "calculated_lsl": lsl,
        "calculated_usl": usl,
        "lcl": lsl,
        "ucl": usl,
        "usl": usl,
    })
    return metrics


def capability_pair_status(metrics: dict) -> tuple[str, str, str]:
    if is_valid_number(metrics.get("cp")) and is_valid_number(metrics.get("cpk")):
        chip, state = capability_status(metrics["cpk"])
        return f"{format_number(metrics['cp'])} / {format_number(metrics['cpk'])}", chip, state
    return "N/A", "Review", "amber"


def capability_status(value: float) -> tuple[str, str]:
    if value is None or pd.isna(value):
        return "Review", "amber"
    rounded = round(float(value), 2)
    if rounded < 1.00:
        return "Critical", "red"
    if rounded == 1.00:
        return "Moderate Risk", "amber"
    if rounded >= 1.33:
        return "Excellent", "green"
    return "Good", "green"


def status_color(state: str) -> str:
    return {
        "green": "#16a34a",
        "blue": "#2563eb",
        "amber": "#f59e0b",
        "red": "#dc2626",
        "review": "#f97316",
    }.get(state, "#64748b")


def labelled_status(label: str) -> str:
    return {
        "Excellent": "🟢 Excellent",
        "Good": "🟢 Good",
        "Monitor": "🟡 Monitor",
        "Moderate Risk": "🟡 Moderate Risk",
        "Review": "🟠 Review",
        "Critical": "🔴 Critical",
    }.get(label, "🟠 Review")

def aci_score_status(compliance_score: float, sigma_level: float) -> tuple[str, str]:
    if compliance_score >= 100:
        if not pd.isna(sigma_level) and sigma_level >= 3:
            return "Excellent", "green"
        return "Good", "green"
    if compliance_score >= 95:
        return "Good", "green"
    if compliance_score >= 90:
        return "Monitor", "amber"
    return "Critical", "red"

def percent_status_label(value: float) -> str:
    if value >= 95:
        return "🟢 Excellent"
    if value >= 90:
        return "🟢 Good"
    if value >= 80:
        return "🟡 Monitor"
    if value >= 70:
        return "🟠 Review"
    return "🔴 Critical"


def kpi_card(label: str, value: str, chip: str, state: str = "green") -> None:
    chip_class = status_class(chip, state)
    chip_text = status_label(chip, state)
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-chip {chip_class}">{chip_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def capability_tile(label: str, value: float, max_value: float, suffix: str = "") -> None:
    is_missing = value is None or pd.isna(value)
    shown = 0 if is_missing else float(value)
    value_text = "N/A" if is_missing else format_number(shown, suffix)
    status_text = "Formula UCL/LCL" if is_missing else percent_status_label(max(0, min(100, shown / max_value * 100)) if max_value else 0)
    pct = max(0, min(100, shown / max_value * 100)) if max_value and not is_missing else 0
    st.markdown(
        f"""
        <div class='capability-tile'>
            <div class='small-label'>{label}</div>
            <div class='capability-value'>{value_text}</div>
            <div class='meter'><div class='meter-fill' style='width:{pct:.0f}%'></div></div>
            <div class='small-label'>{status_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_plot(fig, fallback_data: pd.DataFrame | None = None, fallback_kind: str = "line") -> None:
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
        return
    if fallback_data is not None and not fallback_data.empty:
        if fallback_kind == "bar":
            st.bar_chart(fallback_data)
        else:
            st.line_chart(fallback_data)


def show_gauge_or_tile(label: str, value: float, max_value: float, suffix: str = "") -> None:
    if PLOTLY_AVAILABLE:
        show_plot(build_gauge(label, value, max_value, suffix))
    else:
        capability_tile(label, value, max_value, suffix)


def plot_layout(fig, height: int = 390):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        margin=dict(l=45, r=20, t=45, b=45),
        font=dict(color="#172033", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(gridcolor="#e2e8f0", zerolinecolor="#e2e8f0")
    fig.update_yaxes(gridcolor="#e2e8f0", zerolinecolor="#e2e8f0")
    return fig


def build_strength_trend(data: pd.DataFrame):
    if not PLOTLY_AVAILABLE:
        return None
    fig = px.line(
        data,
        x="test_date",
        y="test_average",
        markers=True,
        color="grade",
        hover_data=["supplier", "mix_id", "structure", "specified_strength"],
        title="Strength Trend Analysis (MPa)",
        color_discrete_sequence=["#2563eb", "#0891b2", "#16a34a", "#f59e0b", "#9333ea"],
    )
    fig.add_trace(go.Scatter(x=data["test_date"], y=data["specified_strength"], mode="lines", name="Target Strength", line=dict(color="#dc2626", dash="dash", width=2)))
    fig.update_layout(
        yaxis_title="Strength (MPa)",
        xaxis_title="Test Date",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_traces(marker=dict(size=4), line=dict(width=1.8))
    return plot_layout(fig, 285)


def build_control_chart(data: pd.DataFrame, metrics: dict):
    if not PLOTLY_AVAILABLE:
        return None
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=data["test_no"],
            y=data["test_average"],
            mode="lines+markers",
            name="Subgroup Average",
            line=dict(color="#1d4ed8", width=2),
            marker=dict(size=6, color="#1e40af"),
        )
    )

    cl = metrics.get("xbarbar", metrics.get("mean"))
    ucl = metrics.get("ucl")
    lcl = metrics.get("lcl")
    if not pd.isna(cl) and not pd.isna(ucl):
        sigma_zone = abs(float(ucl) - float(cl)) / 3
        zone_lines = [
            ("Upper Action Limit (+3 sigma)", cl + 3 * sigma_zone, "#dc2626", "dash", 2),
            ("Upper Warning Limit (+2 sigma)", cl + 2 * sigma_zone, "#f97316", "dot", 1),
            ("+1 sigma Guide", cl + sigma_zone, "#0891b2", "dot", 1),
            ("Center Line / Xbar", cl, "#06b6d4", "solid", 2),
            ("-1 sigma Guide", cl - sigma_zone, "#0891b2", "dot", 1),
            ("Lower Warning Limit (-2 sigma)", cl - 2 * sigma_zone, "#f97316", "dot", 1),
            ("Lower Action Limit (-3 sigma)", lcl if not pd.isna(lcl) else cl - 3 * sigma_zone, "#dc2626", "dash", 2),
        ]
        for name, value, color, dash, width in zone_lines:
            fig.add_hline(y=value, line_color=color, line_dash=dash, line_width=width, annotation_text=name)
    else:
        for name, value, color, dash in [("UCL", ucl, "#dc2626", "dash"), ("CL", cl, "#475569", "dot"), ("LCL", lcl, "#dc2626", "dash")]:
            if not pd.isna(value):
                fig.add_hline(y=value, line_color=color, line_dash=dash, annotation_text=name)

    if not pd.isna(metrics.get("lsl")):
        fig.add_hline(y=metrics["lsl"], line_color="#16a34a", line_dash="dashdot", annotation_text="LSL / f'c")
    fig.update_layout(
        title="SQC Control Chart with r*j Warning and Action Limits",
        xaxis_title="Test Number",
        yaxis_title="Average Strength (MPa)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return plot_layout(fig, 390)


def build_histogram(data: pd.DataFrame):
    if not PLOTLY_AVAILABLE:
        return None
    fig = px.histogram(data, x="test_average", nbins=24, marginal="box", title="Strength Distribution", color_discrete_sequence=["#0891b2"])
    fig.update_layout(xaxis_title="Test Average Strength (MPa)", yaxis_title="Count", showlegend=False)
    return plot_layout(fig, 350)


def build_comparison(data: pd.DataFrame, group_col: str, title: str):
    if not PLOTLY_AVAILABLE:
        return None
    grouped = data.groupby(group_col, as_index=False).agg(avg_strength=("test_average", "mean"), tests=("test_average", "count")).sort_values("avg_strength", ascending=False).head(12)
    fig = px.bar(
        grouped,
        x=group_col,
        y="avg_strength",
        text="tests",
        title=title,
        labels={"avg_strength": "Average Strength (MPa)", group_col: group_col.replace("_", " ").title()},
        color="avg_strength",
        color_continuous_scale=["#dbeafe", "#38bdf8", "#16a34a"],
    )
    fig.update_traces(texttemplate="%{text} tests", textposition="outside")
    fig.update_layout(yaxis_title="Average Strength (MPa)", coloraxis_showscale=False)
    return plot_layout(fig, 350)


def build_gauge(title: str, value: float, max_value: float, suffix: str = ""):
    if not PLOTLY_AVAILABLE:
        return None
    display_value = 0 if pd.isna(value) else value
    title_key = title.lower()
    if any(token in title_key for token in ["ppk", "cpk", "cp", "capability"]):
        _, gauge_state = capability_status(value)
        steps = [
            {"range": [0, 1.00], "color": "#fee2e2"},
            {"range": [1.00, 1.33], "color": "#fef3c7"},
            {"range": [1.33, max_value], "color": "#dcfce7"},
        ]
    elif "zbench" in title_key or "sigma" in title_key:
        _, gauge_state = sigma_status(value)
        steps = [
            {"range": [0, 2.00], "color": "#fee2e2"},
            {"range": [2.00, 3.00], "color": "#fef3c7"},
            {"range": [3.00, max_value], "color": "#dcfce7"},
        ]
    elif "cv" in title_key:
        gauge_state = "green" if not pd.isna(value) and value <= 8 else "amber" if not pd.isna(value) and value <= 10 else "red"
        steps = [
            {"range": [0, 8], "color": "#dcfce7"},
            {"range": [8, 10], "color": "#fef3c7"},
            {"range": [10, max_value], "color": "#fee2e2"},
        ]
    else:
        gauge_state = "green" if not pd.isna(value) and value >= 95 else "amber" if not pd.isna(value) and value >= 90 else "red"
        steps = [
            {"range": [0, 90], "color": "#fee2e2"},
            {"range": [90, 95], "color": "#fef3c7"},
            {"range": [95, max_value], "color": "#dcfce7"},
        ]
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=display_value,
        number={"suffix": suffix, "font": {"size": 34, "color": "#172033"}},
        title={"text": title, "font": {"size": 13, "color": "#334155"}},
        gauge={
            "axis": {"range": [0, max_value], "tickcolor": "#64748b"},
            "bar": {"color": status_color(gauge_state)},
            "bgcolor": "#ffffff",
            "borderwidth": 1,
            "bordercolor": "#d8e7f3",
            "steps": steps,
        },
    ))
    fig.update_layout(template=PLOTLY_TEMPLATE, height=245, paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=15, r=15, t=35, b=10))
    return fig

def build_compliance_heatmap(data: pd.DataFrame):
    if not PLOTLY_AVAILABLE:
        return None
    pivot = data.pivot_table(index="structure", columns="grade", values="aci_compliant", aggfunc="mean").fillna(0) * 100
    if pivot.empty:
        return None
    pivot = pivot.sort_index().head(10)
    fig = px.imshow(
        pivot,
        text_auto=".0f",
        aspect="auto",
        title="IS 456 Compliance Heat Map",
        color_continuous_scale=["#fee2e2", "#fef3c7", "#dcfce7"],
        zmin=80,
        zmax=100,
    )
    fig.update_traces(texttemplate="%{z:.0f}%")
    fig.update_layout(coloraxis_showscale=False, xaxis_title="Grade", yaxis_title="Structure")
    return plot_layout(fig, 420)


def render_executive_summary(metrics: dict, risk: tuple[str, str], compliance_score: float, analysed: pd.DataFrame) -> None:
    score = max(0, min(100, compliance_score))
    non_compliant = int((~analysed["aci_compliant"]).sum())
    chip_class = "red" if risk[0] == "Red" else "amber" if risk[0] == "Amber" else ""
    st.markdown(
        f"""
        <div class='panel'>
            <div class='summary-score'>
                <div class='small-label'>Overall Quality Score</div>
                <div class='score'>{score:.0f}%</div>
                <div class='kpi-chip {chip_class}'>{risk[0]}</div>
            </div>
            <div class='summary-line'><span>Sigma Level</span><b>{format_number(metrics['sigma_level'], ' sigma')}</b></div>
            <div class='summary-line'><span>Risk Index</span><b>{risk_status_label(risk[0])}</b></div>
            <div class='summary-line'><span>IS 456 Compliance</span><b>{format_number(compliance_score, '%')}</b></div>
            <div class='summary-line'><span>DPMO</span><b>{format_number(metrics.get('dpmo', metrics['ppm']))}</b></div>
            <div class='summary-line'><span>Yield</span><b>{format_number(metrics.get('yield_percent'), '%')}</b></div>
            <div class='summary-line'><span>Non-Compliant Tests</span><b>{non_compliant}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def print_dashboard_button(report_html: str | None = None, report_title: str = "Concrete Strength Dashboard Print") -> None:
    safe_report = json.dumps(report_html or "")
    safe_title = json.dumps(report_title)
    component_html(
        f"""
        <button id="printDash" style="
            background: linear-gradient(90deg, #2563eb, #0891b2);
            color: white;
            border: 0;
            border-radius: 8px;
            padding: 10px 16px;
            font-weight: 800;
            font-family: Segoe UI, Arial, sans-serif;
            cursor: pointer;
            box-shadow: 0 8px 18px rgba(37,99,235,.18);
        ">🖨️ Print Segmented Dashboard / Save PDF</button>
        <script>
        const reportHtml = {safe_report};
        document.getElementById('printDash').addEventListener('click', () => {{
            if (!reportHtml || reportHtml.trim().length <= 200) {{
                alert('Print report is not ready. Please wait for the dashboard analysis to finish.');
                return;
            }}
            const fullHtml = `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>${{{safe_title}}}</title>
</head>
<body>${{reportHtml}}
<script>
window.addEventListener('load', () => {{
    setTimeout(() => {{ window.focus(); window.print(); }}, 700);
}});
<\\/script>
</body>
</html>`;
            const blob = new Blob([fullHtml], {{ type: 'text/html' }});
            const url = URL.createObjectURL(blob);
            const win = window.open(url, '_blank', 'width=1200,height=850');
            if (!win) {{
                alert('Please allow pop-ups for this Hugging Face Space.');
                URL.revokeObjectURL(url);
                return;
            }}
            setTimeout(() => URL.revokeObjectURL(url), 60000);
        }});
        </script>
        """,
        height=52,
    )
def print_chip(status: str) -> str:
    klass = "bad" if status == "Red" else "warn" if status == "Amber" else ""
    return f"<span class='print-chip {klass}'>{risk_status_label(status)}</span>"


def render_print_report(analysed: pd.DataFrame, metrics: dict, risk: tuple[str, str], insights: dict, compliance_score: float, grade_label: str = '', visible: bool = False) -> str:
    grade_label = grade_label or (str(analysed["grade"].dropna().astype(str).iloc[0]) if "grade" in analysed.columns and not analysed["grade"].dropna().empty else "Selected Grade")
    non_compliant = int((~analysed["aci_compliant"]).sum())
    outliers = int(analysed["outlier"].sum())
    drops = int(analysed["sudden_drop"].sum())
    repeated = int(analysed["repeated_low_trend"].sum())
    high_variation = metrics["coefficient_of_variation"] > 10

    def dark_points(values, width=620, height=230, pad=28):
        series = pd.Series(values).dropna().astype(float).tail(80)
        if series.empty:
            return "", 0, 1
        lo = float(series.min())
        hi = float(series.max())
        if hi == lo:
            hi = lo + 1
        points = []
        for idx, val in enumerate(series):
            x = pad + idx / max(1, len(series) - 1) * (width - 2 * pad)
            y = height - pad - (float(val) - lo) / (hi - lo) * (height - 2 * pad)
            points.append(f"{x:.1f},{y:.1f}")
        return " ".join(points), lo, hi

    def dark_line_svg(width=660, height=235):
        pts, lo, hi = dark_points(analysed["test_average"], width, height)
        target = float(analysed["specified_strength"].median())
        target_y = height - 28 - (target - lo) / (hi - lo) * (height - 56)
        grid = "".join(f"<line x1='34' y1='{y}' x2='{width-28}' y2='{y}'/>" for y in [50, 90, 130, 170, 210])
        return f"<svg viewBox='0 0 {width} {height}' preserveAspectRatio='none'><g class='grid'>{grid}</g><line x1='34' y1='{target_y:.1f}' x2='{width-28}' y2='{target_y:.1f}' class='target'/><polyline points='{pts}' class='main-line'/><text x='36' y='22' class='axis'>{lo:.1f} - {hi:.1f} MPa</text><text x='{width-32}' y='{target_y-6:.1f}' text-anchor='end' class='target-text'>Target</text></svg>"

    def gauge_html(label: str, value: float, max_value: float, suffix=""):
        shown = 0 if pd.isna(value) else float(value)
        pct = max(0, min(100, shown / max_value * 100)) if max_value else 0
        label_key = label.lower()
        if any(token in label_key for token in ["ppk", "cpk", "cp"]):
            gauge_label, gauge_state = capability_status(value)
        elif "zbench" in label_key or "sigma" in label_key:
            gauge_label, gauge_state = sigma_status(value)
        elif "cv" in label_key:
            gauge_label, gauge_state = ("Good", "green") if not pd.isna(value) and value <= 8 else ("Monitor", "amber") if not pd.isna(value) and value <= 10 else ("Critical", "red")
        else:
            gauge_label, gauge_state = ("Excellent", "green") if not pd.isna(value) and value >= 95 else ("Monitor", "amber") if not pd.isna(value) and value >= 90 else ("Critical", "red")
        return f"<div class='rgauge'><svg viewBox='0 0 170 100'><path d='M25 82 A60 60 0 0 1 145 82' class='gbase'/><path d='M25 82 A60 60 0 0 1 145 82' class='gfill' style='stroke:{status_color(gauge_state)}' pathLength='100' stroke-dasharray='{pct:.0f} 100'/></svg><div class='gval'>{format_number(shown, suffix)}</div><div class='glabel'>{escape(label)}</div><div class='gstatus' style='color:{status_color(gauge_state)}'>{labelled_status(gauge_label)}</div></div>"

    def heatmap_html():
        pivot = analysed.pivot_table(index="structure", columns="grade", values="aci_compliant", aggfunc="mean").fillna(0).mul(100).head(7)
        if pivot.empty:
            return "<div class='muted'>No compliance data</div>"
        heads = "".join(f"<th>{escape(str(col))}</th>" for col in pivot.columns)
        rows = []
        for idx, row in pivot.iterrows():
            cells = [f"<td class='rowhead'>{escape(str(idx))[:26]}</td>"]
            for val in row:
                klass = "hgood" if float(val) >= 95 else "hwarn" if float(val) >= 90 else "hbad"
                cells.append(f"<td class='{klass}'>{float(val):.0f}%</td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        return f"<table class='rheat'><thead><tr><th>Structure</th>{heads}</tr></thead><tbody>{''.join(rows)}</tbody></table>"

    def bar_html():
        grouped = analysed.groupby("supplier")["test_average"].agg(["mean", "count"]).sort_values("mean", ascending=False).head(4)
        if grouped.empty:
            return "<div class='muted'>No supplier data</div>"
        max_mean = max(1, float(grouped["mean"].max()))
        rows = []
        for name, row in grouped.iterrows():
            pct = float(row["mean"]) / max_mean * 100
            rows.append(f"<div class='rbar'><span>{escape(str(name))[:18]}</span><div><i style='width:{pct:.0f}%'></i></div><b>{row['mean']:.1f}</b><em>{int(row['count'])}</em></div>")
        return "".join(rows)

    insight_items = list(insights.items())[:5]
    while len(insight_items) < 5:
        insight_items.append(("Opportunity", "N/A"))
    opportunity_cards = "".join(f"<div class='rop'><div class='opicon'>⌁</div><small>{escape(str(label))}</small><b>{escape(str(value))}</b></div>" for label, value in insight_items)

    status = risk_status_label(risk[0])
    aci_chip, _ = aci_score_status(compliance_score, metrics["sigma_level"])
    sigma_chip, _ = sigma_status(metrics["sigma_level"])
    sigma_print_status = labelled_status(sigma_chip)
    cpk_pair_value, cpk_pair_chip, _ = capability_pair_status(metrics)
    cpk_print_status = labelled_status(cpk_pair_chip)
    ppk_print_status = labelled_status(capability_status(metrics["ppk"])[0])
    aci_print_status = "Excellent" if aci_chip == "Excellent" else "Good" if aci_chip == "Good" else "Monitor" if aci_chip == "Monitor" else "Critical"
    risk_class = "critical" if risk[0] == "Red" else "monitor" if risk[0] == "Amber" else "excellent"
    kpi_cards = [
        ("28-Day Cubes Tested", f"{len(analysed):,}", "🟢 Excellent"),
        ("Average Strength (MPa)", format_number(metrics["mean"]), "🟢 Excellent"),
        ("Characteristic Strength (MPa)", format_number(metrics["lsl"]), "🟢 Excellent"),
        ("Capability Sigma", format_number(metrics["sigma_level"], " sigma"), sigma_print_status),
        ("Ppk (Lower)", format_number(metrics["ppk"]), ppk_print_status),
        ("Cp / Cpk", cpk_pair_value, cpk_print_status),
        ("DPMO", format_number(metrics.get("dpmo", metrics["ppm"])), "🟢 Excellent"),
        ("Yield", format_number(metrics.get("yield_percent"), "%"), "🟢 Excellent"),
        ("IS 456 Compliance Score", format_number(compliance_score, "%"), aci_print_status),
    ]
    kpi_html = "".join(f"<div class='rkpi'><small>{escape(label)}</small><b>{value}</b><span>{state}</span></div>" for label, value, state in kpi_cards)

    report_css = """
    <style>
    @page { size: A4 landscape; margin: 4mm; }
    * { box-sizing: border-box; }
    body { margin: 0; background: #061522; font-family: Segoe UI, Arial, sans-serif; color: #eaf6ff; }
    .rdash { width: 100%; min-height: 100vh; padding: 13px 16px 10px; background: radial-gradient(circle at 88% 10%, #123d59, transparent 28%), linear-gradient(135deg, #06101d, #08263b 55%, #030b13); }
    .rhead { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 10px; }
    .rbrand { display: flex; align-items: center; gap: 12px; }
    .rlogo { width: 52px; height: 52px; border-radius: 8px; display: grid; place-items: center; background: linear-gradient(145deg, #0ea5e9, #075985); color: white; font-weight: 900; box-shadow: inset 0 0 0 1px #38bdf8; }
    .rtitle { font-size: 24px; font-weight: 900; line-height: 1.05; color: #f8fbff; text-shadow: 0 1px 2px rgba(0,0,0,.45); }
    .rsub { color: #d7f3ff; font-size: 13px; margin-top: 3px; }
    .rpills { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
    .rpill { border: 1px solid #244d68; background: #091d2e; border-radius: 6px; padding: 7px 10px; color: #dff7ff; font-size: 12px; }
    .rkpis { display: grid; grid-template-columns: repeat(8, 1fr); gap: 8px; margin-bottom: 9px; }
    .rkpi, .rpanel, .rmini, .rop { background: linear-gradient(145deg, rgba(10,43,70,.96), rgba(5,22,38,.98)); border: 1px solid #1e4963; border-radius: 8px; box-shadow: 0 8px 20px rgba(0,0,0,.25); }
    .rkpi { min-height: 92px; padding: 10px 12px; }
    .rkpi small { display: block; color: #b6d7ea; font-size: 10.5px; min-height: 25px; }
    .rkpi b { display: block; color: white; font-size: 22px; line-height: 1.05; margin-top: 2px; }
    .rkpi span { display: inline-block; margin-top: 8px; padding: 3px 8px; border-radius: 5px; background: #063f28; color: #75ef7c; font-size: 11px; font-weight: 800; }
    .rgrid1 { display: grid; grid-template-columns: 1.34fr .9fr 1.05fr; gap: 9px; }
    .rgrid2 { display: grid; grid-template-columns: 1fr 1fr .78fr; gap: 9px; margin-top: 9px; }
    .rgrid3 { display: grid; grid-template-columns: 1.05fr 1fr; gap: 9px; margin-top: 9px; }
    .rpanel { padding: 10px 12px; min-height: 210px; }
    .ptitle { color: #eaf6ff; text-transform: uppercase; font-size: 13px; font-weight: 900; margin-bottom: 8px; }
    .legend { display: flex; gap: 14px; font-size: 11px; color: #c8e7f5; margin-bottom: 5px; }
    .legend i { display: inline-block; width: 18px; height: 3px; border-radius: 9px; margin-right: 4px; vertical-align: middle; }
    svg .grid line { stroke: #21485f; stroke-width: 1; }
    svg .main-line { fill: none; stroke: #29c7ff; stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
    svg .target { stroke: #ff514b; stroke-width: 1.7; stroke-dasharray: 7 5; }
    svg .target-text, svg .axis { fill: #b6d7ea; font-size: 12px; }
    .rgauge { text-align: center; min-height: 116px; }
    .rgauge svg { width: 100%; height: 72px; }
    .gbase { fill: none; stroke: #113249; stroke-width: 14; stroke-linecap: round; }
    .gfill { fill: none; stroke: #55d85a; stroke-width: 14; stroke-linecap: round; }
    .gval { color: white; font-weight: 900; font-size: 24px; margin-top: -8px; }
    .glabel { color: #d8edf8; font-size: 11px; }
    .gstatus { color: #75ef7c; font-size: 11px; font-weight: 800; }
    .gaugegrid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 5px; }
    table.rheat { width: 100%; border-collapse: collapse; font-size: 11px; }
    .rheat th, .rheat td { border: 1px solid #315873; padding: 5px 6px; text-align: center; }
    .rheat th { background: #0c2d44; color: #eaf6ff; }
    .rheat .rowhead { text-align: left; color: #d9f2ff; background: #082236; }
    .hgood { background: #196b2c; color: #eaffea; } .hwarn { background: #896312; color: #fff6cc; } .hbad { background: #9b2525; color: #ffe8e8; }
    .rbar { display: grid; grid-template-columns: 95px 1fr 45px 35px; gap: 8px; align-items: center; color: #dff7ff; font-size: 12px; margin: 10px 0; }
    .rbar div { height: 10px; background: #103247; border-radius: 20px; overflow: hidden; }
    .rbar i { display: block; height: 100%; background: linear-gradient(90deg, #2b7fff, #21d2ff); border-radius: 20px; }
    .rbar em { color: #8bdcf8; font-style: normal; }
    .riskrow { display: grid; grid-template-columns: 28px 1fr; gap: 8px; align-items: center; border-bottom: 1px solid #21485f; padding: 8px 0; color: #dff7ff; font-size: 12px; }
    .ricon { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; font-weight: 900; }
    .ok { background: #073f28; color: #7bf17f; } .warn { background: #4b3908; color: #ffd85a; } .critical { background: #4a1010; color: #ff7373; }
    .score { text-align: center; padding: 6px; }
    .donut { width: 132px; height: 132px; margin: 2px auto 8px; border-radius: 50%; display: grid; place-items: center; background: conic-gradient(#29c7ff var(--score), #123249 0); position: relative; box-shadow: 0 0 18px #0ea5e988; }
    .donut:after { content: ''; position: absolute; width: 94px; height: 94px; border-radius: 50%; background: #092034; }
    .donut b { position: relative; z-index: 1; color: white; font-size: 30px; }
    .sline { display: flex; justify-content: space-between; border-top: 1px solid #21485f; padding: 6px 0; color: #b6d7ea; font-size: 12px; }
    .sline b { color: #75ef7c; }
    .rminiwrap { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
    .rmini, .rop { min-height: 86px; padding: 10px; }
    .rmini small, .rop small { display: block; color: #c8e7f5; font-size: 11px; }
    .rmini b { display: block; color: #ffd85a; font-size: 20px; margin-top: 8px; }
    .rop { border-color: #166534; text-align: center; }
    .opicon { color: #75ef7c; font-size: 22px; }
    .rop b { display: block; color: white; font-size: 13px; margin-top: 6px; }
    .rfooter { margin-top: 10px; border-top: 1px solid #21485f; padding-top: 8px; display: flex; justify-content: space-between; color: #8bdcf8; font-size: 12px; }
    @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } .rdash { min-height: 200mm; } }
    </style>
    """
    wrapper_class = "print-report report-preview" if visible else "print-report"
    html = f"""
    <div class='{wrapper_class}'>
    {report_css}
    <div class='rdash'>
        <div class='rhead'>
            <div class='rbrand'><div class='rlogo'>QC</div><div><div class='rtitle'>Concrete Strength Analytics & Six Sigma Intelligence Platform</div><div class='rsub'>AI-Powered Concrete Quality Management | 28-day acceptance analytics</div></div></div>
            <div class='rpills'><div class='rpill'>Project: Concrete QC</div><div class='rpill'>{escape(str(grade_label))} Grade</div><div class='rpill'>{status}</div></div>
        </div>
        <div class='rkpis'>{kpi_html}</div>
        <div class='rgrid1'>
            <div class='rpanel'><div class='ptitle'>Strength Trend Analysis (MPa)</div><div class='legend'><span><i style='background:#29c7ff'></i>{escape(str(grade_label))}</span><span><i style='background:#ff514b'></i>Target Strength</span></div>{dark_line_svg()}</div>
            <div class='rpanel'><div class='ptitle'>Six Sigma Process Capability</div><div class='gaugegrid'>{gauge_html('Zbench', metrics['sigma_level'], 6, ' sigma')}{gauge_html('Ppk Lower', metrics['ppk'], 2.5)}{gauge_html('ACI', compliance_score, 100, '%')}{gauge_html('CV', metrics['coefficient_of_variation'], 15, '%')}</div></div>
            <div class='rpanel'><div class='ptitle'>IS 456 Compliance Heat Map</div>{heatmap_html()}</div>
        </div>
        <div class='rgrid2'>
            <div class='rpanel'><div class='ptitle'>Supplier Performance Comparison</div>{bar_html()}</div>
            <div class='rpanel'><div class='ptitle'>SQC Control Chart - {escape(str(grade_label))} Grade</div>{dark_line_svg(560, 220)}</div>
            <div class='rpanel'><div class='ptitle'>Executive Summary</div><div class='score'><div class='donut' style='--score:{compliance_score:.0f}%'><b>{compliance_score:.0f}%</b></div><div class='sline'><span>Sigma Level</span><b>{format_number(metrics['sigma_level'], ' sigma')}</b></div><div class='sline'><span>Risk Index</span><b>{status}</b></div><div class='sline'><span>DPMO</span><b>{format_number(metrics.get('dpmo', metrics['ppm']))}</b></div><div class='sline'><span>Yield</span><b>{format_number(metrics.get('yield_percent'), '%')}</b></div></div></div>
        </div>
        <div class='rgrid3'>
            <div class='rpanel'><div class='ptitle'>Risk Intelligence Engine</div><div class='riskrow'><div class='ricon ok'>✓</div><div>{escape(str(grade_label))} concrete 28-day set isolated and analysed.</div></div><div class='riskrow'><div class='ricon warn'>!</div><div>Coefficient of variation is {format_number(metrics['coefficient_of_variation'], '%')}.</div></div><div class='riskrow'><div class='ricon {'critical' if non_compliant else 'ok'}'>{'!' if non_compliant else '✓'}</div><div>Non-compliant tests detected: {non_compliant}.</div></div><div class='riskrow'><div class='ricon ok'>✓</div><div>Capability sigma (Zbench) is {format_number(metrics['sigma_level'], ' sigma')}; lower Ppk is {format_number(metrics['ppk'])}.</div></div></div>
            <div class='rpanel'><div class='ptitle'>Positive Opportunities</div><div class='rminiwrap'>{opportunity_cards}</div></div>
        </div>
        <div class='rpanel' style='margin-top:9px'><div class='ptitle'>Abnormality Detection</div><div class='rminiwrap'><div class='rmini'><small>Outlier Cube Strength</small><b>{outliers}</b><small>Tests flagged</small></div><div class='rmini'><small>High Variation</small><b>{'Yes' if high_variation else 'No'}</b><small>Process watch</small></div><div class='rmini'><small>Repeated Low Trend</small><b>{repeated}</b><small>Trend flags</small></div><div class='rmini'><small>Sudden Drop</small><b>{drops}</b><small>Drops detected</small></div><div class='rmini'><small>Non-Compliant</small><b>{non_compliant}</b><small>28-day tests</small></div></div></div>
        <div class='rfooter'><b>Digital Construction Intelligence</b><span>AI-Powered Concrete Quality Management Platform</span><span>SPC | AI/ML | Digital Twin | IoT Sensors | Cloud Analytics | Data Security</span></div>
    </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    return html

def show_sample_schema() -> None:
    with st.expander("Expected Excel columns and accepted formats"):
        st.write("The app accepts either a clean table or a formatted `CUBE COMPRESSIVE STRENGTH LOG` like Book1.xlsx. For a clean table, include `test_date`, `specified_strength`, and either `test_average` or cube columns. If grade is in sheet name, use names such as M10, M15, M20, M25, M30, M35, etc.")
        st.write("Optional fields: `supplier`, `mix_id`, `grade`, `structure`.")


def render_sidebar(active_domain: str) -> None:
    st.sidebar.markdown(f"""
        <div class='sidebar-brand'>
            <div class='qc-logo'>DQ</div>
            <div><b>DQIP<br>Digital Quality Intelligence Platform</b><small style='display:block;margin-top:.2rem'>{escape(active_domain)} workspace</small></div>
        </div>
    """, unsafe_allow_html=True)
    st.sidebar.radio(
        "Navigation",
        ["Domain Dashboard", "Data Management", "Evaluation", "Capability", "Compliance", "Risk Intelligence", "Abnormality Detection", "Corrective Actions", "Reports", "Settings"],
        label_visibility="collapsed",
    )
    st.sidebar.markdown("<div class='author-card'><small>Developed by</small><b>Janice Benita F</b></div>", unsafe_allow_html=True)
    st.sidebar.markdown(
        """
        <div class='side-card'>
            <b>Domain-adaptable quality engine</b><br>
            Select a domain to apply its dedicated schema, limits, evaluation reasons, corrective measures, and dashboard.
        </div>
        """,
        unsafe_allow_html=True,
    )
def render_alerts(analysed: pd.DataFrame, metrics: dict) -> None:
    items = [
        ("Outlier Cube Strength", f"{int(analysed['outlier'].sum())} tests flagged"),
        ("Sudden Strength Drop", f"{int(analysed['sudden_drop'].sum())} drops detected"),
        ("Repeated Low Trend", f"{int(analysed['repeated_low_trend'].sum())} trend flags"),
        ("High Variation", "Yes" if metrics["coefficient_of_variation"] > 10 else "No"),
    ]
    cols = st.columns(4)
    for col, (label, value) in zip(cols, items):
        with col:
            st.markdown(f"<div class='alert-card'><div class='small-label'>{label}</div><div class='small-value'>{value}</div></div>", unsafe_allow_html=True)


def render_insights(insights: dict) -> None:
    cols = st.columns(4)
    for col, (label, value) in zip(cols, insights.items()):
        with col:
            st.markdown(f"<div class='insight-card'><div class='small-label'>{label}</div><div class='small-value'>{value}</div></div>", unsafe_allow_html=True)


def build_domain_pdf_report(domain: str, summary: dict, capability: pd.DataFrame, risk_table: pd.DataFrame, standards: pd.DataFrame, exceptions: pd.DataFrame) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=12 * mm, leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"DQIP - {escape(domain)} Quality Evaluation Report", styles["Title"]), Spacer(1, 6)]
    story.append(Paragraph("Illustrative evaluation only. Non-concrete rules and numeric limits require independent validation before production use.", styles["BodyText"]))
    story.append(Spacer(1, 8))

    summary_rows = [["Metric", "Result"]] + [[str(key), str(value)] for key, value in summary.items()]
    summary_table = Table(summary_rows, colWidths=[65 * mm, 105 * mm])
    summary_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F3A5F")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.extend([summary_table, Spacer(1, 10)])

    def add_frame(title: str, frame: pd.DataFrame, max_rows: int = 20) -> None:
        story.append(Paragraph(title, styles["Heading2"]))
        safe = frame.head(max_rows).fillna("").astype(str)
        rows = [list(safe.columns)] + safe.values.tolist()
        table = Table(rows, repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D7E7F5")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.extend([table, Spacer(1, 8)])

    add_frame("Capability and Performance", capability)
    add_frame("Risk Intelligence", risk_table)
    add_frame("International Reference Framework", standards)
    if not exceptions.empty:
        report_columns = [column for column in ["Evaluation", "Evaluation_Reason", "Corrective_Measure"] if column in exceptions.columns]
        identifier = exceptions.columns[0]
        add_frame("Exceptions and Corrective Measures", exceptions[[identifier] + report_columns], 25)
    doc.build(story)
    return buffer.getvalue()


def render_domain_print_report(domain: str, summary: dict, capability: pd.DataFrame, risk_table: pd.DataFrame, standards: pd.DataFrame, exceptions: pd.DataFrame, data: pd.DataFrame, config: dict) -> str:
    values = pd.to_numeric(data[config["primary_value"]], errors="coerce").dropna().tail(80)
    width, height, pad = 720, 230, 34
    if values.empty:
        points = ""
        lo, hi = 0.0, 1.0
    else:
        lo, hi = float(values.min()), float(values.max())
        if hi == lo:
            hi = lo + 1
        points = " ".join(
            f"{pad + index / max(1, len(values) - 1) * (width - 2 * pad):.1f},{height - pad - (float(value) - lo) / (hi - lo) * (height - 2 * pad):.1f}"
            for index, value in enumerate(values)
        )
    grid = "".join(f"<line x1='{pad}' y1='{y}' x2='{width-pad}' y2='{y}'/>" for y in [45, 85, 125, 165, 205])
    chart = f"<svg viewBox='0 0 {width} {height}' preserveAspectRatio='none'><g class='grid'>{grid}</g><polyline points='{points}' class='main-line'/><text x='{pad}' y='22' class='axis'>{lo:.3f} to {hi:.3f}</text></svg>"

    def html_table(frame: pd.DataFrame, columns: list[str] | None = None, limit: int = 20) -> str:
        shown = frame.head(limit)
        if columns:
            shown = shown[[column for column in columns if column in shown.columns]]
        if shown.empty:
            return "<div class='empty'>No records</div>"
        heads = "".join(f"<th>{escape(str(column))}</th>" for column in shown.columns)
        rows = "".join("<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>" for row in shown.fillna("").values.tolist())
        return f"<table><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody></table>"

    kpis = [
        ("Records Evaluated", summary["Records evaluated"]),
        ("Observed Yield", summary["Yield"]),
        ("Flagged Records", summary["Flagged records"]),
        ("Sigma Level", summary["Sigma level"]),
        ("DPMO", summary["DPMO"]),
        ("Overall Cpk/Ppk", summary["Overall Cpk/Ppk"]),
        ("Risk Classification", summary["Risk classification"]),
    ]
    kpi_html = "".join(f"<div class='kpi'><small>{escape(str(label))}</small><b>{escape(str(value))}</b></div>" for label, value in kpis)
    standards_html = "".join(f"<div class='standard'><b>{escape(str(row['Standard']))}</b><span>{escape(str(row['Application']))}</span></div>" for _, row in standards.iterrows())
    exception_columns = [data.columns[0], "Evaluation_Reason", "Corrective_Measure"]
    return f"""
    <style>
      *{{box-sizing:border-box}} body{{margin:0;background:#061b2c;color:#eef8ff;font-family:Segoe UI,Arial,sans-serif}} .report{{padding:18px;max-width:1180px;margin:auto}}
      .head{{display:flex;justify-content:space-between;align-items:center;padding:16px 18px;border:1px solid #24516d;border-radius:12px;background:#0b3047}} .head h1{{margin:0;font-size:25px}} .head p{{margin:5px 0 0;color:#9ed9f4}}
      .badge{{padding:9px 14px;border-radius:8px;background:#0e4665;border:1px solid #2b6b8e;font-weight:800}} .kpis{{display:grid;grid-template-columns:repeat(7,1fr);gap:9px;margin:12px 0}}
      .kpi{{min-height:94px;padding:12px;border:1px solid #24516d;border-radius:10px;background:#08253a}} .kpi small{{display:block;color:#a8cce0;font-weight:700;min-height:32px}} .kpi b{{display:block;font-size:21px;margin-top:5px;color:#fff}}
      .grid2{{display:grid;grid-template-columns:1.2fr 1fr;gap:12px}} .panel{{padding:14px;border:1px solid #24516d;border-radius:10px;background:#08253a;margin-bottom:12px;break-inside:avoid}} .panel h2{{font-size:15px;text-transform:uppercase;color:#7dd3fc;margin:0 0 10px}}
      svg{{width:100%;height:245px}} svg .grid line{{stroke:#17455f;stroke-width:1}} .main-line{{fill:none;stroke:#38bdf8;stroke-width:3}} .axis{{fill:#a8cce0;font-size:13px}}
      table{{width:100%;border-collapse:collapse;font-size:11px}} th{{background:#0e4665;color:#fff;text-align:left}} th,td{{border:1px solid #24516d;padding:7px;vertical-align:top}} tr:nth-child(even){{background:#0a2b40}}
      .standards{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}} .standard{{padding:10px;border:1px solid #24516d;border-radius:8px;background:#0a2b40}} .standard b,.standard span{{display:block}} .standard span{{color:#b7d7e8;margin-top:4px;font-size:12px}}
      .notice{{padding:10px;border-left:5px solid #f59e0b;background:#3a2a12;color:#fde7b0;margin:10px 0;border-radius:7px}} .empty{{color:#9abbd0}} @media print{{@page{{size:landscape;margin:8mm}} body{{print-color-adjust:exact;-webkit-print-color-adjust:exact}} .report{{max-width:none;padding:0}}}}
    </style>
    <div class='report'>
      <div class='head'><div><h1>DQIP {escape(domain)} Quality Intelligence</h1><p>Domain-specific evaluation, capability, risk, and corrective-action report</p></div><div class='badge'>{escape(str(summary['Risk classification']))} Risk</div></div>
      <div class='notice'>Illustrative non-concrete evaluation. Validate the domain rules, limits, and reference framework before production use.</div>
      <div class='kpis'>{kpi_html}</div>
      <div class='grid2'><div class='panel'><h2>{escape(config['primary_label'])} Trend Analysis</h2>{chart}</div><div class='panel'><h2>Executive Risk Intelligence</h2>{html_table(risk_table, limit=8)}</div></div>
      <div class='panel'><h2>Capability and Performance Calculation List</h2>{html_table(capability)}</div>
      <div class='panel'><h2>International Reference Framework</h2><div class='standards'>{standards_html}</div><p>{escape(config['standards_note'])}</p></div>
      <div class='panel'><h2>Exception Reasons and Corrective Measures</h2>{html_table(exceptions, exception_columns, 30)}</div>
    </div>
    """


def render_domain_intelligence(domain: str, data: pd.DataFrame, config: dict) -> None:
    value_column = config["primary_value"]
    date_column = config["date_column"]
    group_column = config["group_column"]
    values = pd.to_numeric(data[value_column], errors="coerce")
    valid_values = values.dropna()
    mean = float(valid_values.mean()) if not valid_values.empty else 0.0
    std = float(valid_values.std(ddof=1)) if len(valid_values) > 1 else 0.0
    cv = abs(std / mean * 100) if mean else 0.0
    total = len(data)
    defects = int((~data["Evaluated_Status"]).sum())
    opportunities = max(int(config.get("opportunities", 1)), 1)
    dpo = defects / max(total * opportunities, 1)
    dpmo = dpo * 1_000_000
    yield_rate = 1 - defects / max(total, 1)
    sigma_level = 6.0 if dpo <= 0 else max(0.0, min(6.0, NormalDist().inv_cdf(max(1e-9, 1 - dpo)) + 1.5))
    ucl = mean + 3 * std
    lcl = mean - 3 * std
    uwl = mean + 2 * std
    lwl = mean - 2 * std
    control_flags = int(((values > ucl) | (values < lcl)).sum()) if std else 0

    capability_rows = []
    capability_values = []
    for spec in config["capability_specs"]:
        series = pd.to_numeric(data[spec["value"]], errors="coerce").dropna()
        spec_mean = float(series.mean()) if not series.empty else 0.0
        spec_std = float(series.std(ddof=1)) if len(series) > 1 else 0.0
        lsl = float(pd.to_numeric(data[spec["lsl"]], errors="coerce").median()) if spec.get("lsl") else None
        usl = float(pd.to_numeric(data[spec["usl"]], errors="coerce").median()) if spec.get("usl") else None
        cp = (usl - lsl) / (6 * spec_std) if spec_std and lsl is not None and usl is not None else None
        cpu = (usl - spec_mean) / (3 * spec_std) if spec_std and usl is not None else None
        cpl = (spec_mean - lsl) / (3 * spec_std) if spec_std and lsl is not None else None
        sides = [value for value in [cpu, cpl] if value is not None]
        cpk = min(sides) if sides else None
        capability_values.extend([value for value in [cp, cpk] if value is not None])
        status = "Not estimable" if cpk is None else "Excellent" if cpk >= 1.33 else "Capable" if cpk >= 1.0 else "Needs improvement"
        capability_rows.append({"Characteristic": spec["label"], "Mean": round(spec_mean, 4), "Std Dev": round(spec_std, 4), "LSL": lsl, "USL": usl, "Cp": None if cp is None else round(cp, 4), "Cpk/Ppk": None if cpk is None else round(cpk, 4), "Status": status})
    capability = pd.DataFrame(capability_rows)
    overall_cpk = min(capability_values) if capability_values else None
    risk_level = "Critical" if yield_rate < 0.90 else "High" if yield_rate < 0.95 else "Monitor" if defects or control_flags else "Low"

    st.markdown("##### Capability and Six Sigma intelligence")
    metric_cols = st.columns(7)
    metric_cols[0].metric("Yield", f"{yield_rate:.2%}")
    metric_cols[1].metric("Sigma level", f"{sigma_level:.2f}")
    metric_cols[2].metric("DPMO", f"{dpmo:,.0f}")
    metric_cols[3].metric("Overall Cpk/Ppk", "N/A" if overall_cpk is None else f"{overall_cpk:.2f}")
    metric_cols[4].metric("Mean", f"{mean:.3f}")
    metric_cols[5].metric("CV", f"{cv:.2f}%")
    metric_cols[6].metric("Risk", risk_level)

    if PLOTLY_AVAILABLE and not valid_values.empty:
        chart_data = data.copy()
        chart_data[date_column] = pd.to_datetime(chart_data[date_column], errors="coerce")
        control = go.Figure()
        control.add_trace(go.Scatter(x=chart_data[date_column], y=values, name=value_column, mode="lines+markers"))
        for label, level, color, dash in [("Center", mean, "#1d4ed8", "solid"), ("UWL", uwl, "#f59e0b", "dot"), ("LWL", lwl, "#f59e0b", "dot"), ("UCL", ucl, "#dc2626", "dash"), ("LCL", lcl, "#dc2626", "dash")]:
            control.add_hline(y=level, line_color=color, line_dash=dash, annotation_text=label)
        control.update_layout(title=f"{config['primary_label']} Shewhart-style control chart", yaxis_title=config["primary_label"], template=PLOTLY_TEMPLATE)
        distribution = px.histogram(chart_data, x=value_column, marginal="box", title=f"{config['primary_label']} distribution")
        chart_cols = st.columns(2)
        chart_cols[0].plotly_chart(control, use_container_width=True, key=f"{domain}_control")
        chart_cols[1].plotly_chart(distribution, use_container_width=True, key=f"{domain}_distribution")

    st.markdown("##### Capability calculation list")
    st.dataframe(capability, use_container_width=True, hide_index=True)

    missing = int(data[config["required_numeric"]].isna().any(axis=1).sum()) if config.get("required_numeric") else 0
    risk_table = pd.DataFrame([
        {"Signal": "Specification compliance", "Calculated value": f"{yield_rate:.2%} yield; {defects} flagged", "Interpretation": "Uploaded limits and domain rules applied.", "Status": "Good" if defects == 0 else "Review"},
        {"Signal": "Process capability", "Calculated value": "N/A" if overall_cpk is None else f"Minimum Cpk/Ppk={overall_cpk:.3f}", "Interpretation": "Capability is descriptive and requires a stable process and approved limits.", "Status": "Good" if overall_cpk is not None and overall_cpk >= 1.33 else "Monitor"},
        {"Signal": "Sigma / defects", "Calculated value": f"{sigma_level:.3f} sigma; DPMO={dpmo:,.0f}", "Interpretation": "Observed defect opportunity performance.", "Status": "Good" if sigma_level >= 4 else "Monitor"},
        {"Signal": "Variation", "Calculated value": f"CV={cv:.2f}%", "Interpretation": "Relative variation of the primary quality characteristic.", "Status": "Good" if cv <= 10 else "Monitor"},
        {"Signal": "Control chart", "Calculated value": f"{control_flags} beyond 3-sigma limits", "Interpretation": "Shewhart-style statistical signals require process investigation.", "Status": "Good" if control_flags == 0 else "Review"},
        {"Signal": "Data quality", "Calculated value": f"{missing} incomplete numeric rows", "Interpretation": "Missing values reduce confidence in evaluation.", "Status": "Good" if missing == 0 else "Review"},
        {"Signal": "Overall risk", "Calculated value": risk_level, "Interpretation": "Use the highest-severity specification, control, and data-quality signal.", "Status": risk_level},
    ])
    st.markdown("##### Risk intelligence and interpretation")
    st.dataframe(risk_table, use_container_width=True, hide_index=True)

    abnormalities = st.columns(4)
    abnormalities[0].metric("Specification failures", defects)
    abnormalities[1].metric("Beyond control limits", control_flags)
    abnormalities[2].metric("Incomplete records", missing)
    abnormalities[3].metric("Process variation", "High" if cv > 10 else "Controlled")

    group_summary = data.groupby(group_column, dropna=False)["Evaluated_Status"].agg(["count", "mean"]).reset_index()
    best_group = str(group_summary.sort_values(["mean", "count"], ascending=[False, False]).iloc[0][group_column]) if not group_summary.empty else "N/A"
    opportunity_cols = st.columns(3)
    opportunity_cols[0].success(f"Best-performing {group_column}: {best_group}")
    opportunity_cols[1].success(f"Primary mean: {mean:.3f}; standard deviation: {std:.3f}")
    opportunity_cols[2].success(f"Observed yield: {yield_rate:.2%}")

    standards = pd.DataFrame(config["standards"])
    st.markdown("##### International reference framework")
    st.dataframe(standards, use_container_width=True, hide_index=True, column_config={"Official source": st.column_config.LinkColumn("Official source")})
    st.caption(config["standards_note"])

    exceptions = data.loc[~data["Evaluated_Status"]].copy()
    summary = {"Domain": domain, "Records evaluated": total, "Yield": f"{yield_rate:.2%}", "Flagged records": defects, "Sigma level": f"{sigma_level:.3f}", "DPMO": f"{dpmo:,.0f}", "Overall Cpk/Ppk": "N/A" if overall_cpk is None else f"{overall_cpk:.3f}", "Risk classification": risk_level}
    pdf = build_domain_pdf_report(domain, summary, capability, risk_table, standards, exceptions)
    segmented_report_html = render_domain_print_report(domain, summary, capability, risk_table, standards, exceptions, data, config)
    action_cols = st.columns([1, 1, 1, 1.5])
    action_cols[0].download_button("Export evaluated CSV", data=data.to_csv(index=False).encode("utf-8"), file_name=f"{domain.replace(' ', '_')}_evaluated.csv", mime="text/csv", key=f"{domain}_csv_export")
    action_cols[1].download_button("Download PDF report", data=pdf, file_name=f"{domain.replace(' ', '_')}_quality_report.pdf", mime="application/pdf", key=f"{domain}_pdf_export")
    with action_cols[3]:
        print_dashboard_button(segmented_report_html, f"{domain} Quality Dashboard Print")
    report_state_key = f"show_{domain.replace(' ', '_')}_report"
    report_is_visible = st.session_state.get(report_state_key, False)
    report_button_label = "Hide report" if report_is_visible else "Display report"
    if action_cols[2].button(report_button_label, key=f"{domain}_display_report"):
        st.session_state[report_state_key] = not report_is_visible
        report_is_visible = not report_is_visible

    if report_is_visible:
        st.markdown(f"##### {domain} executive report")
        report_colour = "#dcfce7" if risk_level == "Low" else "#ffedd5" if risk_level in ["Monitor", "High"] else "#fee2e2"
        report_border = "#16a34a" if risk_level == "Low" else "#f59e0b" if risk_level in ["Monitor", "High"] else "#dc2626"
        st.markdown(
            f"""
            <div style='padding:1rem 1.2rem;border:1px solid {report_border};border-left:6px solid {report_border};border-radius:14px;background:{report_colour};margin-bottom:1rem;'>
                <div style='font-size:.82rem;color:#52657f;font-weight:800;text-transform:uppercase;'>Executive conclusion</div>
                <div style='font-size:1.15rem;font-weight:900;color:#0f1f3a;margin:.25rem 0;'>Risk classification: {risk_level}</div>
                <div style='color:#334155;'>{total:,} records were evaluated using the {escape(domain)} domain profile. Observed yield was {yield_rate:.2%}, with {defects} record(s) flagged and an estimated sigma level of {sigma_level:.3f}.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        report_metrics = st.columns(4)
        report_metrics[0].metric("Records evaluated", f"{total:,}")
        report_metrics[1].metric("Observed yield", f"{yield_rate:.2%}")
        report_metrics[2].metric("Flagged records", defects)
        report_metrics[3].metric("Overall Cpk/Ppk", "N/A" if overall_cpk is None else f"{overall_cpk:.3f}")
        st.markdown("**Key findings and interpretation**")
        st.dataframe(risk_table, use_container_width=True, hide_index=True)
        st.markdown("**Applicable international reference framework**")
        st.dataframe(standards, use_container_width=True, hide_index=True, column_config={"Official source": st.column_config.LinkColumn("Official source")})
        st.caption(config["standards_note"])
        if exceptions.empty:
            st.success("No exception or corrective-action records were generated.")
        else:
            st.markdown("**Exception reasons and recommended corrective measures**")
            identifier = exceptions.columns[0]
            st.dataframe(exceptions[[identifier, "Evaluation_Reason", "Corrective_Measure"]], use_container_width=True, hide_index=True)


def render_non_concrete_dashboard(domain: str, source_data: pd.DataFrame) -> None:
    """Render an illustrative, domain-specific evaluation dashboard."""
    data = source_data.copy()
    quality_config = {}
    st.markdown(f"#### {domain} evaluation dashboard")

    if domain == "Manufacturing":
        for column in ["Nominal_mm", "LSL_mm", "USL_mm", "Diameter_mm"]:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        data["Inspection_Date"] = pd.to_datetime(data["Inspection_Date"], errors="coerce")
        data["Evaluated_Status"] = data["Diameter_mm"].between(data["LSL_mm"], data["USL_mm"]) & data["Diameter_mm"].notna()
        data["Evaluation_Reason"] = "Diameter is within the specified tolerance."
        data["Corrective_Measure"] = "Continue routine process monitoring."
        data.loc[data["Diameter_mm"] < data["LSL_mm"], "Evaluation_Reason"] = "Measured diameter is below the lower specification limit (undersize)."
        data.loc[data["Diameter_mm"] < data["LSL_mm"], "Corrective_Measure"] = "Segregate the part; verify tool offset and calibration; inspect tool wear; remeasure after correction."
        data.loc[data["Diameter_mm"] > data["USL_mm"], "Evaluation_Reason"] = "Measured diameter is above the upper specification limit (oversize)."
        data.loc[data["Diameter_mm"] > data["USL_mm"], "Corrective_Measure"] = "Segregate the part; inspect tool wear and machine settings; correct the process before restart."
        data.loc[data["Diameter_mm"].isna(), "Evaluation_Reason"] = "Diameter result is missing or non-numeric."
        data.loc[data["Diameter_mm"].isna(), "Corrective_Measure"] = "Correct the inspection record and repeat the measurement with a calibrated instrument."
        quality_config = {"primary_value": "Diameter_mm", "primary_label": "Diameter (mm)", "date_column": "Inspection_Date", "group_column": "Machine", "required_numeric": ["Nominal_mm", "LSL_mm", "USL_mm", "Diameter_mm"], "opportunities": 1, "capability_specs": [{"label": "Diameter", "value": "Diameter_mm", "lsl": "LSL_mm", "usl": "USL_mm"}], "standards": [{"Standard": "ISO 22514-2:2026", "Application": "Process capability and performance statistics for continuous characteristics", "Official source": "https://www.iso.org/standard/88883.html"}, {"Standard": "ISO 7870-2:2023", "Application": "Shewhart control-chart approach and process signals", "Official source": "https://www.iso.org/standard/78859.html"}], "standards_note": "LSL and USL must come from the approved drawing, specification, or control plan; ISO statistical standards do not create the product tolerance."}
        conforming = int(data["Evaluated_Status"].sum())
        metrics = st.columns(4)
        metrics[0].metric("Parts inspected", f"{len(data):,}")
        metrics[1].metric("First-pass yield", f"{conforming / max(len(data), 1):.1%}")
        metrics[2].metric("Mean diameter", f"{data['Diameter_mm'].mean():.3f} mm")
        metrics[3].metric("Out of tolerance", int((~data["Evaluated_Status"]).sum()))
        if PLOTLY_AVAILABLE:
            trend = go.Figure()
            trend.add_trace(go.Scatter(x=data["Inspection_Date"], y=data["Diameter_mm"], name="Measured diameter", mode="lines+markers"))
            trend.add_trace(go.Scatter(x=data["Inspection_Date"], y=data["USL_mm"], name="USL", line=dict(color="#dc2626", dash="dash")))
            trend.add_trace(go.Scatter(x=data["Inspection_Date"], y=data["LSL_mm"], name="LSL", line=dict(color="#f59e0b", dash="dash")))
            trend.update_layout(title="Diameter trend against engineering tolerances", yaxis_title="Diameter (mm)", template=PLOTLY_TEMPLATE)
            machine = data.groupby("Machine", dropna=False)["Evaluated_Status"].mean().mul(100).reset_index(name="Conformance_pct")
            by_group = px.bar(machine, x="Machine", y="Conformance_pct", title="Conformance by machine", labels={"Conformance_pct": "Conformance (%)"})
            chart_cols = st.columns(2)
            chart_cols[0].plotly_chart(trend, use_container_width=True, key="manufacturing_trend")
            chart_cols[1].plotly_chart(by_group, use_container_width=True, key="manufacturing_machine")

    elif domain == "Laboratory QA":
        for column in ["Lower_Limit", "Upper_Limit", "pH_Result"]:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        data["Test_Date"] = pd.to_datetime(data["Test_Date"], errors="coerce")
        data["Evaluated_Status"] = data["pH_Result"].between(data["Lower_Limit"], data["Upper_Limit"]) & data["pH_Result"].notna()
        data["Evaluation_Reason"] = "pH result is within the stated laboratory acceptance limits."
        data["Corrective_Measure"] = "Report the result and continue routine quality-control monitoring."
        data.loc[data["pH_Result"] < data["Lower_Limit"], "Evaluation_Reason"] = "pH result is below the stated lower acceptance limit."
        data.loc[data["pH_Result"] > data["Upper_Limit"], "Evaluation_Reason"] = "pH result is above the stated upper acceptance limit."
        data.loc[~data["Evaluated_Status"], "Corrective_Measure"] = "Initiate an OOS review; verify calibration and controls; repeat according to the approved method; investigate the sample and batch."
        quality_config = {"primary_value": "pH_Result", "primary_label": "Laboratory pH", "date_column": "Test_Date", "group_column": "Instrument_ID", "required_numeric": ["Lower_Limit", "Upper_Limit", "pH_Result"], "opportunities": 1, "capability_specs": [{"label": "pH result", "value": "pH_Result", "lsl": "Lower_Limit", "usl": "Upper_Limit"}], "standards": [{"Standard": "ISO/IEC 17025:2017", "Application": "Laboratory competence, impartiality, and consistent operation", "Official source": "https://www.iso.org/standard/66912.html"}, {"Standard": "ISO 10523:2008", "Application": "Method for determination of pH in water matrices", "Official source": "https://www.iso.org/standard/51994.html"}, {"Standard": "ISO 7870-2:2023", "Application": "Shewhart-style statistical monitoring", "Official source": "https://www.iso.org/standard/78859.html"}], "standards_note": "Acceptance limits must be defined by the validated method, customer, regulation, or specification; ISO/IEC 17025 does not prescribe a universal pH acceptance range."}
        metrics = st.columns(4)
        metrics[0].metric("Tests evaluated", f"{len(data):,}")
        metrics[1].metric("Within limits", f"{data['Evaluated_Status'].mean():.1%}")
        metrics[2].metric("Mean pH result", f"{data['pH_Result'].mean():.2f}")
        metrics[3].metric("OOS results", int((~data["Evaluated_Status"]).sum()))
        if PLOTLY_AVAILABLE:
            trend = go.Figure()
            trend.add_trace(go.Scatter(x=data["Test_Date"], y=data["pH_Result"], name="pH result", mode="lines+markers"))
            trend.add_trace(go.Scatter(x=data["Test_Date"], y=data["Upper_Limit"], name="Upper limit", line=dict(color="#dc2626", dash="dash")))
            trend.add_trace(go.Scatter(x=data["Test_Date"], y=data["Lower_Limit"], name="Lower limit", line=dict(color="#f59e0b", dash="dash")))
            trend.update_layout(title="Laboratory pH results against acceptance limits", yaxis_title="pH", template=PLOTLY_TEMPLATE)
            instrument = data.groupby("Instrument_ID", dropna=False)["Evaluated_Status"].agg(["count", "mean"]).reset_index()
            instrument["Conformance_pct"] = instrument["mean"] * 100
            by_group = px.bar(instrument, x="Instrument_ID", y="Conformance_pct", title="Conformance by instrument", labels={"Conformance_pct": "Conformance (%)"})
            chart_cols = st.columns(2)
            chart_cols[0].plotly_chart(trend, use_container_width=True, key="laboratory_trend")
            chart_cols[1].plotly_chart(by_group, use_container_width=True, key="laboratory_instrument")

    elif domain == "Healthcare":
        for column in ["Waiting_Time_min", "Service_Time_min", "Target_Max_min"]:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        data["Visit_Date"] = pd.to_datetime(data["Visit_Date"], errors="coerce")
        data["Evaluated_Status"] = (data["Waiting_Time_min"] <= data["Target_Max_min"]) & data["Waiting_Time_min"].notna()
        data["Evaluation_Reason"] = "Waiting time met the stated operational target."
        data["Corrective_Measure"] = "Continue routine service monitoring."
        data.loc[data["Waiting_Time_min"] > data["Target_Max_min"], "Evaluation_Reason"] = "Waiting time exceeded the stated operational target."
        data.loc[data["Waiting_Time_min"] > data["Target_Max_min"], "Corrective_Measure"] = "Review staffing and queue allocation; identify the bottleneck; adjust scheduling and monitor the next service period."
        data.loc[data["Waiting_Time_min"].isna(), "Evaluation_Reason"] = "Waiting-time value is missing or non-numeric."
        data.loc[data["Waiting_Time_min"].isna(), "Corrective_Measure"] = "Correct the operational record before using it for performance decisions."
        quality_config = {"primary_value": "Waiting_Time_min", "primary_label": "Waiting time (min)", "date_column": "Visit_Date", "group_column": "Department", "required_numeric": ["Waiting_Time_min", "Service_Time_min", "Target_Max_min"], "opportunities": 1, "capability_specs": [{"label": "Waiting time", "value": "Waiting_Time_min", "usl": "Target_Max_min"}], "standards": [{"Standard": "ISO 7101:2023", "Application": "Quality-management requirements for healthcare organizations", "Official source": "https://www.iso.org/standard/81647.html"}, {"Standard": "ISO 7870-2:2023", "Application": "Statistical monitoring of operational process measures", "Official source": "https://www.iso.org/standard/78859.html"}], "standards_note": "ISO 7101 requires monitoring and improvement but does not establish a universal waiting-time limit. Target_Max_min must be an organization-approved operational target."}
        metrics = st.columns(4)
        metrics[0].metric("Visits evaluated", f"{len(data):,}")
        metrics[1].metric("Waiting target met", f"{data['Evaluated_Status'].mean():.1%}")
        metrics[2].metric("Average waiting time", f"{data['Waiting_Time_min'].mean():.1f} min")
        metrics[3].metric("Target breaches", int((~data["Evaluated_Status"]).sum()))
        if PLOTLY_AVAILABLE:
            trend = go.Figure()
            trend.add_trace(go.Scatter(x=data["Visit_Date"], y=data["Waiting_Time_min"], name="Waiting time", mode="lines+markers"))
            trend.add_trace(go.Scatter(x=data["Visit_Date"], y=data["Target_Max_min"], name="Target maximum", line=dict(color="#dc2626", dash="dash")))
            trend.update_layout(title="Patient-service waiting time trend", yaxis_title="Minutes", template=PLOTLY_TEMPLATE)
            department = data.groupby("Department", dropna=False)[["Waiting_Time_min", "Service_Time_min"]].mean().reset_index()
            by_group = px.bar(department, x="Department", y=["Waiting_Time_min", "Service_Time_min"], barmode="group", title="Average time by department", labels={"value": "Minutes", "variable": "Measure"})
            chart_cols = st.columns(2)
            chart_cols[0].plotly_chart(trend, use_container_width=True, key="healthcare_trend")
            chart_cols[1].plotly_chart(by_group, use_container_width=True, key="healthcare_department")

    elif domain == "Pharmaceuticals":
        numeric_columns = ["Assay_LSL_pct", "Assay_USL_pct", "Dissolution_Min_pct", "Assay_pct", "Dissolution_pct"]
        for column in numeric_columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        data["Test_Date"] = pd.to_datetime(data["Test_Date"], errors="coerce")
        assay_pass = data["Assay_pct"].between(data["Assay_LSL_pct"], data["Assay_USL_pct"])
        dissolution_pass = data["Dissolution_pct"] >= data["Dissolution_Min_pct"]
        data["Evaluated_Status"] = assay_pass & dissolution_pass & data["Assay_pct"].notna() & data["Dissolution_pct"].notna()
        data["Evaluation_Reason"] = "Assay and dissolution meet the stated illustrative specifications."
        data["Corrective_Measure"] = "Continue the approved batch-review workflow."
        data.loc[data["Assay_pct"] < data["Assay_LSL_pct"], "Evaluation_Reason"] = "Assay is below the stated lower specification limit."
        data.loc[data["Assay_pct"] > data["Assay_USL_pct"], "Evaluation_Reason"] = "Assay is above the stated upper specification limit."
        data.loc[data["Dissolution_pct"] < data["Dissolution_Min_pct"], "Evaluation_Reason"] = "Dissolution is below the stated minimum requirement."
        data.loc[~data["Evaluated_Status"], "Corrective_Measure"] = "Place the batch on hold; initiate the approved OOS investigation; verify method, standards, equipment, and manufacturing records before disposition."
        quality_config = {"primary_value": "Assay_pct", "primary_label": "Assay (%)", "date_column": "Test_Date", "group_column": "Product", "required_numeric": numeric_columns, "opportunities": 2, "capability_specs": [{"label": "Assay", "value": "Assay_pct", "lsl": "Assay_LSL_pct", "usl": "Assay_USL_pct"}, {"label": "Dissolution", "value": "Dissolution_pct", "lsl": "Dissolution_Min_pct"}], "standards": [{"Standard": "ICH Q6A", "Application": "Specifications, test procedures, and acceptance criteria for drug substances/products", "Official source": "https://database.ich.org/sites/default/files/Q6A%20Guideline.pdf"}, {"Standard": "ISO 7870-2:2023", "Application": "Shewhart-style process monitoring", "Official source": "https://www.iso.org/standard/78859.html"}], "standards_note": "Assay and dissolution criteria must be justified and approved for the specific product and method under ICH Q6A; the sample limits are not universal release specifications."}
        metrics = st.columns(4)
        metrics[0].metric("Batches evaluated", f"{len(data):,}")
        metrics[1].metric("Illustrative release rate", f"{data['Evaluated_Status'].mean():.1%}")
        metrics[2].metric("Mean assay", f"{data['Assay_pct'].mean():.2f}%")
        metrics[3].metric("Batches flagged", int((~data["Evaluated_Status"]).sum()))
        if PLOTLY_AVAILABLE:
            assay = go.Figure()
            assay.add_trace(go.Scatter(x=data["Test_Date"], y=data["Assay_pct"], name="Assay", mode="lines+markers"))
            assay.add_trace(go.Scatter(x=data["Test_Date"], y=data["Assay_USL_pct"], name="Assay USL", line=dict(color="#dc2626", dash="dash")))
            assay.add_trace(go.Scatter(x=data["Test_Date"], y=data["Assay_LSL_pct"], name="Assay LSL", line=dict(color="#f59e0b", dash="dash")))
            assay.update_layout(title="Assay trend against release specifications", yaxis_title="Assay (%)", template=PLOTLY_TEMPLATE)
            product = data.groupby("Product", dropna=False)[["Assay_pct", "Dissolution_pct"]].mean().reset_index()
            by_group = px.bar(product, x="Product", y=["Assay_pct", "Dissolution_pct"], barmode="group", title="Mean assay and dissolution by product", labels={"value": "Percent", "variable": "Quality measure"})
            chart_cols = st.columns(2)
            chart_cols[0].plotly_chart(assay, use_container_width=True, key="pharmaceutical_assay")
            chart_cols[1].plotly_chart(by_group, use_container_width=True, key="pharmaceutical_product")

    elif domain == "Environmental Monitoring":
        numeric_columns = ["pH_LSL", "pH_USL", "Turbidity_Max_NTU", "Chlorine_LSL_mgL", "Chlorine_USL_mgL", "pH_Result", "Turbidity_NTU", "Chlorine_mgL"]
        for column in numeric_columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        data["Sample_Date"] = pd.to_datetime(data["Sample_Date"], errors="coerce")
        ph_pass = data["pH_Result"].between(data["pH_LSL"], data["pH_USL"])
        turbidity_pass = data["Turbidity_NTU"] <= data["Turbidity_Max_NTU"]
        chlorine_pass = data["Chlorine_mgL"].between(data["Chlorine_LSL_mgL"], data["Chlorine_USL_mgL"])
        data["Evaluated_Status"] = ph_pass & turbidity_pass & chlorine_pass
        data["Evaluation_Reason"] = "pH, turbidity, and residual chlorine meet the stated monitoring limits."
        data["Corrective_Measure"] = "Continue routine monitoring."
        data.loc[~ph_pass, "Evaluation_Reason"] = "pH is outside the stated monitoring range."
        data.loc[~ph_pass, "Corrective_Measure"] = "Resample; verify the pH instrument; inspect dosing and treatment controls; investigate the affected location."
        data.loc[~turbidity_pass, "Evaluation_Reason"] = "Turbidity exceeds the stated maximum limit."
        data.loc[~turbidity_pass, "Corrective_Measure"] = "Resample; inspect filtration and treatment performance; investigate the source of elevated solids."
        data.loc[~chlorine_pass, "Evaluation_Reason"] = "Residual chlorine is outside the stated monitoring range."
        data.loc[~chlorine_pass, "Corrective_Measure"] = "Resample; verify the chlorine method; inspect dosing and contact time; correct treatment controls as approved."
        quality_config = {"primary_value": "pH_Result", "primary_label": "Water pH", "date_column": "Sample_Date", "group_column": "Location", "required_numeric": numeric_columns, "opportunities": 3, "capability_specs": [{"label": "pH", "value": "pH_Result", "lsl": "pH_LSL", "usl": "pH_USL"}, {"label": "Turbidity", "value": "Turbidity_NTU", "usl": "Turbidity_Max_NTU"}, {"label": "Residual chlorine", "value": "Chlorine_mgL", "lsl": "Chlorine_LSL_mgL", "usl": "Chlorine_USL_mgL"}], "standards": [{"Standard": "WHO Guidelines for Drinking-water Quality", "Application": "Risk-based framework and basis for locally relevant water-quality standards", "Official source": "https://www.who.int/teams/environment-climate-change-and-health/water-sanitation-and-health/water-safety-and-quality/drinking-water-quality-guidelines"}, {"Standard": "ISO 10523:2008", "Application": "Determination of pH", "Official source": "https://www.iso.org/standard/51994.html"}, {"Standard": "ISO 7027-1:2016", "Application": "Quantitative determination of turbidity", "Official source": "https://www.iso.org/standard/62801.html"}], "standards_note": "WHO guidance supports locally relevant regulations and water-safety plans. Uploaded limits must match the applicable national regulation and approved monitoring plan."}
        metrics = st.columns(4)
        metrics[0].metric("Samples evaluated", f"{len(data):,}")
        metrics[1].metric("All parameters compliant", f"{data['Evaluated_Status'].mean():.1%}")
        metrics[2].metric("Mean turbidity", f"{data['Turbidity_NTU'].mean():.2f} NTU")
        metrics[3].metric("Samples flagged", int((~data["Evaluated_Status"]).sum()))
        if PLOTLY_AVAILABLE:
            ph_chart = go.Figure()
            ph_chart.add_trace(go.Scatter(x=data["Sample_Date"], y=data["pH_Result"], name="pH", mode="lines+markers"))
            ph_chart.add_trace(go.Scatter(x=data["Sample_Date"], y=data["pH_USL"], name="pH USL", line=dict(color="#dc2626", dash="dash")))
            ph_chart.add_trace(go.Scatter(x=data["Sample_Date"], y=data["pH_LSL"], name="pH LSL", line=dict(color="#f59e0b", dash="dash")))
            ph_chart.update_layout(title="Environmental pH monitoring trend", yaxis_title="pH", template=PLOTLY_TEMPLATE)
            location = data.groupby("Location", dropna=False)["Evaluated_Status"].mean().mul(100).reset_index(name="Compliance_pct")
            by_group = px.bar(location, x="Location", y="Compliance_pct", title="Full-parameter compliance by location", labels={"Compliance_pct": "Compliance (%)"})
            chart_cols = st.columns(2)
            chart_cols[0].plotly_chart(ph_chart, use_container_width=True, key="environmental_ph")
            chart_cols[1].plotly_chart(by_group, use_container_width=True, key="environmental_location")

    data["Evaluation"] = data["Evaluated_Status"].map({True: "Pass", False: "Flagged"})
    exceptions = data.loc[~data["Evaluated_Status"]]
    if exceptions.empty:
        st.success("No exceptions were identified by this illustrative evaluation rule.")
    else:
        st.error(f"{len(exceptions)} record(s) require review under this illustrative evaluation rule.")
        st.dataframe(exceptions, use_container_width=True, height=220)
    with st.expander("View complete evaluated dataset"):
        st.dataframe(data, use_container_width=True, height=320)
    render_domain_intelligence(domain, data, quality_config)


def render_cross_domain_profiles() -> str:
    profiles = [
        {
            "name": "Construction Quality",
            "icon": "🏗️",
            "status": "Active analytics module",
            "purpose": "Concrete cube-strength compliance, capability, risk, and Six Sigma intelligence.",
            "fields": "Test date · Grade · Specified strength · Measured strength · Supplier · Batch",
            "rule": "IS 456 and grade-aware concrete-quality rules",
        },
        {
            "name": "Manufacturing",
            "icon": "🏭",
            "status": "Model-ready profile",
            "purpose": "Dimensional inspection, process capability, defect detection, and line comparison.",
            "fields": "Inspection date · Line · Part number · Nominal · Measured value · LSL · USL",
            "rule": "Configurable engineering tolerances and control limits",
            "sample_file": "Manufacturing_Sample_60.csv",
            "required_columns": ["Part_ID", "Inspection_Date", "Shift", "Machine", "Operator", "Nominal_mm", "LSL_mm", "USL_mm", "Diameter_mm", "Status"],
        },
        {
            "name": "Laboratory QA",
            "icon": "🔬",
            "status": "Model-ready profile",
            "purpose": "Analytical results, instrument performance, control-limit monitoring, and exceptions.",
            "fields": "Analysis date · Instrument · Analyte · Result · Unit · Lower limit · Upper limit",
            "rule": "Method-specific acceptance and laboratory control limits",
            "sample_file": "Laboratory_QA_Sample_60.csv",
            "required_columns": ["Sample_ID", "Test_Date", "Batch", "Analyst", "Instrument_ID", "Lower_Limit", "Upper_Limit", "pH_Result", "Status"],
        },
        {
            "name": "Healthcare",
            "icon": "🏥",
            "status": "Operational model profile",
            "purpose": "De-identified service-quality indicators such as waiting time and data completeness.",
            "fields": "Encounter date · Facility · Department · Wait time · Target · Quality flag",
            "rule": "Approved operational targets; not for clinical decisions",
            "sample_file": "Healthcare_Sample_60.csv",
            "required_columns": ["Visit_ID", "Visit_Date", "Shift", "Department", "Waiting_Time_min", "Service_Time_min", "Target_Max_min", "Status"],
        },
        {
            "name": "Pharmaceuticals",
            "icon": "💊",
            "status": "Model-ready profile",
            "purpose": "Batch assay, specification compliance, release-quality trends, and exception review.",
            "fields": "Test date · Product · Batch · Assay · Lower specification · Upper specification",
            "rule": "Product and method-specific approved specifications",
            "sample_file": "Pharmaceuticals_Sample_60.csv",
            "required_columns": ["Sample_ID", "Test_Date", "Batch_No", "Product", "Assay_LSL_pct", "Assay_USL_pct", "Dissolution_Min_pct", "Assay_pct", "Dissolution_pct", "Status"],
        },
        {
            "name": "Environmental Monitoring",
            "icon": "🌱",
            "status": "Model-ready profile",
            "purpose": "Water, air, or site measurements compared with configurable monitoring limits.",
            "fields": "Collection date · Site · Parameter · Value · Unit · Lower limit · Upper limit",
            "rule": "Parameter-specific regulatory or organizational limits",
            "sample_file": "Environmental_Sample_60.csv",
            "required_columns": ["Sample_ID", "Sample_Date", "Location", "pH_LSL", "pH_USL", "Turbidity_Max_NTU", "Chlorine_LSL_mgL", "Chlorine_USL_mgL", "pH_Result", "Turbidity_NTU", "Chlorine_mgL", "Status"],
        },
    ]

    st.markdown("### DQIP cross-domain quality profiles")
    st.caption("The same quality-intelligence core can be configured through domain-specific schemas, units, limits, and rule sets.")
    st.warning("Important: Except for Concrete Quality data, all other domain datasets are samples and have not been validated. They are provided only for model testing and demonstration.")

    domain_icons = {profile["name"]: profile["icon"] for profile in profiles}
    with st.container(key="domain_selector_shell"):
        st.markdown(
            """
            <div class='domain-selector-kicker'>Enterprise workspace selector</div>
            <div class='domain-selector-title'>Choose your quality-intelligence domain</div>
            <div class='domain-selector-copy'>Launch a dedicated schema, evaluation engine, standards framework, corrective-action model, and executive dashboard.</div>
            """,
            unsafe_allow_html=True,
        )
        selected_domain = st.radio(
            "Select quality domain",
            options=[profile["name"] for profile in profiles],
            format_func=lambda name: f"{domain_icons[name]}  {name}",
            horizontal=True,
            label_visibility="collapsed",
            key="selected_quality_domain",
        )
    for profile in profiles:
        if profile["name"] != selected_domain:
            continue
        with st.container():
            left, middle, right = st.columns([1.25, 1.55, 1.2])
            with left:
                st.markdown(f"**{profile['status']}**")
                st.write(profile["purpose"])
            with middle:
                st.markdown("**Model input schema**")
                st.write(profile["fields"])
            with right:
                st.markdown("**Acceptance model**")
                st.write(profile["rule"])

            if "sample_file" in profile:
                sample_path = Path(__file__).with_name("sample_data") / profile["sample_file"]
                uploaded_csv = st.file_uploader(
                    f"Upload {profile['name']} CSV file",
                    type=["csv"],
                    key=f"csv_upload_{profile['sample_file']}",
                    help="The uploaded CSV replaces this tab's preloaded sample for the current session.",
                )

                if uploaded_csv is None and not sample_path.is_file():
                    st.error(f"The preloaded sample file '{profile['sample_file']}' could not be found.")
                    continue

                csv_source = uploaded_csv if uploaded_csv is not None else sample_path
                try:
                    domain_data = pd.read_csv(csv_source)
                except Exception as exc:
                    st.error("Could not read this CSV file. Confirm that it is a valid comma-separated file with a header row.")
                    st.caption(str(exc))
                    continue

                missing_columns = [column for column in profile["required_columns"] if column not in domain_data.columns]
                if missing_columns:
                    st.error("CSV schema validation failed. Missing columns: " + ", ".join(missing_columns))
                else:
                    source_label = uploaded_csv.name if uploaded_csv is not None else f"Preloaded sample: {profile['sample_file']}"
                    st.caption(source_label)
                    render_non_concrete_dashboard(profile["name"], domain_data)

                if sample_path.is_file():
                    st.download_button(
                        f"Download {profile['name']} sample CSV",
                        data=sample_path.read_bytes(),
                        file_name=profile["sample_file"],
                        mime="text/csv",
                        key=f"csv_download_{profile['sample_file']}",
                    )

    st.info("Construction Quality is the validated analysis workflow. Each non-concrete dashboard performs a domain-specific illustrative evaluation, but its thresholds, rules, reasons, corrective measures, and results require independent validation before production use.")
    return selected_domain


inject_css()
active_domain = st.session_state.get("selected_quality_domain", "Construction Quality")
render_sidebar(active_domain)

if os.environ.get("DQIP_STORYTELLING_CHILD") != "1":
    st.sidebar.markdown("---")
    st.sidebar.markdown("### AI Storytelling Studio")
    st.sidebar.caption("Record a narrated 1080p demonstration of the complete DQIP cross-domain workflow.")
    if st.sidebar.button("Generate AI Demo Video", type="primary", use_container_width=True, key="generate_ai_demo_video"):
        try:
            from storytelling import generate_demo_video
            with st.status("Generating the AI storytelling video…", expanded=True) as generation_status:
                st.write("Creating Indian-English female narration and scene timings…")
                st.write("Launching an isolated recording session and automating the application…")
                st.write("Rendering subtitles, music ducking, H.264 video, and AAC audio…")
                artifacts = generate_demo_video(Path(__file__).resolve().parent)
                st.session_state["storytelling_artifacts"] = {
                    "video": str(artifacts.video),
                    "subtitles": str(artifacts.subtitles),
                    "voice": str(artifacts.voice),
                }
                generation_status.update(label="AI demo video generated successfully", state="complete", expanded=False)
        except Exception as exc:
            st.sidebar.error("Video generation could not be completed.")
            st.sidebar.exception(exc)

    generated = st.session_state.get("storytelling_artifacts", {})
    generated_files = {name: Path(path) for name, path in generated.items() if Path(path).is_file()}
    if "video" in generated_files:
        st.sidebar.video(generated_files["video"].read_bytes())
        st.sidebar.download_button("Download demo_storytelling_video.mp4", generated_files["video"].read_bytes(), "demo_storytelling_video.mp4", "video/mp4", use_container_width=True)
    if "subtitles" in generated_files:
        st.sidebar.download_button("Download subtitles (SRT)", generated_files["subtitles"].read_bytes(), "demo_storytelling_video.srt", "application/x-subrip", use_container_width=True)
    if "voice" in generated_files:
        st.sidebar.download_button("Download narration (WAV)", generated_files["voice"].read_bytes(), "voice.wav", "audio/wav", use_container_width=True)

st.markdown(
    f"""
    <div class='top-shell app-header'>
        <div class='brand-row'>
            <div class='brand-mark'>DQ</div>
            <div>
                <div class='hero-title'>DQIP — Digital Quality Intelligence Platform</div>
                <div class='hero-subtitle'>{escape(active_domain)} workspace · Developed by <span class='signature'>Janice Benita F.</span></div>
            </div>
        </div>
        <div class='top-pills header-tools'>
            <div class='top-pill'>Domain: {escape(active_domain)}</div>
            <div class='top-pill'>Rule-aware</div>
            <div class='top-pill'>Quality + Six Sigma</div>
            <div class='avatar-pill'>JB</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

selected_domain = render_cross_domain_profiles()

if selected_domain != "Construction Quality":
    st.stop()

st.markdown("### Construction quality analytics workspace")

st.markdown("<div class='upload-shell'>", unsafe_allow_html=True)
upload_left, upload_right = st.columns([1.0, 1.7])
with upload_left:
    st.markdown("<div class='upload-card'><div class='upload-title'>Upload cube strength workbook</div><div class='upload-copy'>Accepted formats: XLSX and XLS. The analysis uses 28-day results only and supports grade-wise IS 456 evaluation for M10, M15, M20, M25, M30, M35 and higher grades.</div>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload concrete cube strength Excel file", type=["xlsx", "xls"], label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)
with upload_right:
    st.markdown("<div class='schema-card'>", unsafe_allow_html=True)
    show_sample_schema()
    st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

sample_file = Path(__file__).with_name("SQC Data.xls")
excel_source = uploaded if uploaded is not None else sample_file

if uploaded is None and not sample_file.is_file():
    st.error("The preloaded sample file 'SQC Data.xls' could not be found. Please upload an Excel workbook.")
    st.stop()

try:
    if uploaded is None:
        st.info("Sample data is preloaded for testing. Upload your own workbook above to replace it.")
        st.caption(f"Preloaded sample: {sample_file.name} ({sample_file.stat().st_size / 1024:.1f} KB)")
    else:
        st.caption(f"Uploaded file detected: {uploaded.name} ({uploaded.size / 1024:.1f} KB)")
    raw, import_message = read_excel_input(excel_source)
except Exception as exc:
    st.error("Could not read the Excel file.")
    st.exception(exc)
    st.info("For Hugging Face Spaces, rebuild/restart the Space after uploading the updated requirements.txt, analytics.py, app.py, and Dockerfile. XLSX needs openpyxl; XLS needs xlrd.")
    st.stop()

valid, missing, mapping = validate_columns(raw)
if not valid:
    st.error("Column validation failed.")
    st.write("Missing or insufficient fields:", ", ".join(missing))
    st.stop()

st.markdown(
    f"""
    <style>
        .block-container {{ padding-top: 0.85rem !important; }}
    </style>
    <div id='results-dashboard-anchor'></div>
    <div class='panel' style='padding:.7rem .9rem; margin-bottom:.75rem; border-left:5px solid #16a34a;'>
        <b style='color:#15803d'>Evaluation complete.</b>
        <span style='color:#52657f'> {import_message}</span>
        <span style='float:right; color:#0f3a5f; font-weight:900;'>Developed by Janice Benita F</span>
    </div>
    """,
    unsafe_allow_html=True,
)
data_all = prepare_data(raw, mapping)
if data_all.empty:
    st.error("No valid rows remain after parsing dates and numeric strength values.")
    st.stop()

grade_options = sorted([grade for grade in data_all["grade"].dropna().astype(str).unique() if grade and grade.lower() != "nan"])
if not grade_options:
    grade_options = ["All grades"]

st.markdown("<div class='section-title'>Select Grade for Separate Evaluation</div>", unsafe_allow_html=True)
selected_grade = st.radio(
    "Grade view",
    grade_options,
    horizontal=True,
    label_visibility="collapsed",
    key="selected_grade_view",
)

data = data_all[data_all["grade"].astype(str) == selected_grade].copy() if selected_grade != "All grades" else data_all.copy()
data = data.sort_values("test_date").reset_index(drop=True)
data["test_no"] = range(1, len(data) + 1)
if data.empty:
    st.error(f"No valid 28-day records found for selected grade {selected_grade}.")
    st.stop()

st.caption(
    f"Evaluating grade {selected_grade} separately: {len(data)} completed 28-day tests. "
    f"Other grades remain available through the grade selector above."
)

analysed = aci_compliance(data)
metrics = complete_capability_metrics(six_sigma_metrics(analysed))
st.caption(
    f"SQC capability limits for {selected_grade}: LCL = {format_number(metrics['lcl'], ' MPa')}, "
    f"UCL/USL = {format_number(metrics['ucl'], ' MPa')}. Cp/Cpk use these calculated limits."
)
analysed = detect_abnormalities(analysed, metrics)
risk = classify_risk(analysed, metrics)
insights = positive_insights(analysed)

compliance_score = float(analysed["aci_compliant"].mean() * 100) if len(analysed) else 0
risk_class = risk[0].lower()
chip_state = "green" if risk[0] == "Green" else "amber" if risk[0] == "Amber" else "red"
aci_chip, aci_state = aci_score_status(compliance_score, metrics["sigma_level"])
sigma_chip, sigma_state = sigma_status(metrics["sigma_level"])

report_html = render_print_report(analysed, metrics, risk, insights, compliance_score, selected_grade)
report = export_report(analysed, metrics, risk, insights, all_data=data_all)
with st.container():
    st.markdown("<div class='print-hide'>", unsafe_allow_html=True)
    action_cols = st.columns([1.0, 1.0, 1.25, 3.75])
    with action_cols[0]:
        st.download_button(
            "Export",
            data=report,
            file_name="concrete_cube_strength_analysed_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with action_cols[1]:
        print_dashboard_button(report_html)
    with action_cols[2]:
        preview_label = "Hide Report" if st.session_state.get("show_report_preview", False) else "Display Report"
        if st.button(preview_label, key="toggle_report_preview", use_container_width=True):
            new_preview_state = not st.session_state.get("show_report_preview", False)
            st.session_state["show_report_preview"] = new_preview_state
            st.session_state["scroll_to_report_preview"] = new_preview_state
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
kpi_items = [
    ("Average Strength (28d)", f"<span class='kpi-number'>{format_number(metrics['mean'])}</span><span class='kpi-unit'>MPa</span>", "Excellent", "green"),
    ("Compliance Rate", f"<span class='kpi-number'>{format_number(compliance_score)}</span><span class='kpi-unit'>%</span>", aci_chip, aci_state),
    ("Sigma Level", f"<span class='kpi-number'>{format_number(metrics['sigma_level'])}</span><span class='kpi-unit'>sigma</span>", sigma_chip, sigma_state),
    ("Ppk (Overall)", format_number(metrics["ppk"]), *capability_status(metrics["ppk"])),
    ("Total Tests", f"{len(analysed):,}", "Good", "green"),
    ("Cp / Cpk", *capability_pair_status(metrics)),
    ("DPMO", f"<span class='kpi-number'>{format_number(metrics.get('dpmo', metrics['ppm']))}</span>", "Low" if metrics.get("dpmo", metrics["ppm"]) < 6210 else "High", "green" if metrics.get("dpmo", metrics["ppm"]) < 6210 else "red"),
    ("Yield", f"<span class='kpi-number'>{format_number(metrics.get('yield_percent'))}</span><span class='kpi-unit'>%</span>", "Excellent" if metrics.get("yield_percent", 0) >= 99.38 else "Good", "green"),
]
kpi_cols = st.columns(len(kpi_items))
for col, (label, value, chip, state) in zip(kpi_cols, kpi_items):
    with col:
        kpi_card(label, value, chip, state)

main_left, main_mid, main_right = st.columns([0.82, 1.45, 1.0])
with main_left:
    st.markdown("<div class='section-title'>Strength Trend Analysis</div>", unsafe_allow_html=True)
    show_plot(build_strength_trend(analysed), analysed.set_index("test_date")[["test_average", "specified_strength"]])
with main_mid:
    st.markdown("<div class='section-title'>Six Sigma Process Capability</div>", unsafe_allow_html=True)
    g1, g2 = st.columns(2)
    with g1:
        show_gauge_or_tile("Zbench", metrics["sigma_level"], 6)
    with g2:
        show_gauge_or_tile("Ppk", metrics["ppk"], 2.5)
    g3, g4 = st.columns(2)
    with g3:
        if not is_valid_number(metrics.get("cpk")):
            capability_tile("Cp/Cpk", None, 2.5, "")
        else:
            show_gauge_or_tile("Cpk", metrics["cpk"], 2.5)
    with g4:
        show_gauge_or_tile("ACI", compliance_score, 100, "%")
with main_right:
    st.markdown("<div class='section-title'>IS 456 Compliance Heat Map</div>", unsafe_allow_html=True)
    heatmap_fallback = analysed.groupby("structure")["aci_compliant"].mean().mul(100).sort_values(ascending=False).head(10).to_frame("Compliance %")
    show_plot(build_compliance_heatmap(analysed), heatmap_fallback, "bar")

chart_left, chart_mid, chart_right = st.columns([1.0, 1.0, 0.86])
with chart_left:
    st.markdown("<div class='section-title'>Supplier Performance Comparison</div>", unsafe_allow_html=True)
    supplier_fallback = analysed.groupby("supplier")["test_average"].mean().sort_values(ascending=False).head(12).to_frame()
    show_plot(build_comparison(analysed, "supplier", "Supplier Comparison"), supplier_fallback, "bar")
with chart_mid:
    st.markdown("<div class='section-title'>SQC Control Chart</div>", unsafe_allow_html=True)
    show_plot(build_control_chart(analysed, metrics), analysed.set_index("test_no")[["test_average"]])
with chart_right:
    st.markdown("<div class='section-title'>Executive Summary</div>", unsafe_allow_html=True)
    render_executive_summary(metrics, risk, compliance_score, analysed)

risk_engine = risk_intelligence_table(analysed, metrics, risk, compliance_score)
st.markdown("<div class='section-title'>Risk Intelligence Engine</div>", unsafe_allow_html=True)
st.dataframe(risk_engine, use_container_width=True, hide_index=True)

st.markdown("<div class='section-title'>Risk Classification and Interpretation</div>", unsafe_allow_html=True)
bullets = interpretation_summary(analysed, metrics, risk, compliance_score)[:5]
bullet_html = "".join(f"<li>{escape(item)}</li>" for item in bullets)
st.markdown(
    f"""
    <div class='panel'>
        <div class='risk-banner {risk_class}' style='margin-bottom:.8rem'>
            <div class='risk-title'>Risk Classification: {risk[0]}</div>
            <div class='risk-copy'>{risk[1]}</div>
        </div>
        <ul style='margin:0; padding-left:1.1rem; color:#24364f; line-height:1.55'>{bullet_html}</ul>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<div class='section-title'>Abnormality Detection</div>", unsafe_allow_html=True)
render_alerts(analysed, metrics)

st.markdown("<div class='section-title'>Positive Opportunities</div>", unsafe_allow_html=True)
render_insights(insights)

st.markdown("<div class='section-title'>Concrete Statistics and Process Classification according to ACI 214R-02</div>", unsafe_allow_html=True)
aci214_table = aci214_process_classification(analysed)
st.dataframe(aci214_table, use_container_width=True, hide_index=True)

st.markdown("<div class='section-title'>Capability and SQC Calculation List</div>", unsafe_allow_html=True)
capability_table = capability_metrics_table(metrics)
st.dataframe(capability_table, use_container_width=True, hide_index=True)

if st.session_state.get("show_report_preview", False):
    st.markdown("<div id='dashboard-report-preview'></div><div class='section-title'>Dashboard Report Preview</div>", unsafe_allow_html=True)
    render_print_report(analysed, metrics, risk, insights, compliance_score, selected_grade, visible=True)
    if st.session_state.pop("scroll_to_report_preview", False):
        component_html(
            """
            <script>
            setTimeout(() => {
                const target = window.parent.document.getElementById('dashboard-report-preview');
                if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 250);
            </script>
            """,
            height=0,
        )

st.markdown("<div class='section-title'>Detailed Analytics</div>", unsafe_allow_html=True)
tab1, tab2, tab3, tab4 = st.tabs(["Histogram", "Mix ID Comparison", "IS 456 Compliance", "Data Preview"])
with tab1:
    show_plot(build_histogram(analysed), analysed[["test_average"]])
with tab2:
    mix_fallback = analysed.groupby("mix_id")["test_average"].mean().sort_values(ascending=False).head(12).to_frame()
    show_plot(build_comparison(analysed, "mix_id", "Mix ID Comparison"), mix_fallback, "bar")
with tab3:
    st.dataframe(analysed[["test_no", "test_date", "specified_strength", "test_average", "moving_avg_4", "is456_required_4_avg", "minimum_allowed_test_avg", "four_test_avg_ok", "single_test_ok", "is456_compliant"]], use_container_width=True)
with tab4:
    st.dataframe(analysed, use_container_width=True)
