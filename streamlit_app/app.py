import base64
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    layout="wide",
    page_title="Weather Holiday Recommender",
    page_icon="🌤️",
    initial_sidebar_state="collapsed",
)

# ─── Paths ────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
DB_PATH = _HERE.parent / "weather.duckdb"
ASSETS_DIR = _HERE / "assets" / "cities"
HERO_PATH = _HERE / "assets" / "hero.jpg"

# ─── Constants ────────────────────────────────────────────────────────────────
HOLIDAY_TYPES = [
    "Beach & Sun",
    "Nature & Hiking",
    "City Break",
    "Cultural & Sightseeing",
    "Wellness & Slow Travel",
    "Extreme Sports",
]

HOLIDAY_META = {
    "Beach & Sun": {
        "score_col": "beach_score",
        "flag_col": "is_beach_destination",
        "thresholds": "Apparent temp > 27°C · rain < 5 mm · wind < 30 km/h",
        "score_desc": "Weighted score: avg temp above 15°C (50 pts) + low rain-day frequency (30 pts) + avg wind below 60 km/h (20 pts). Temperatures are **actual** mean °C from Open-Meteo.",
        "pill_icon": "☀️",
    },
    "Nature & Hiking": {
        "score_col": "hiking_score",
        "flag_col": "is_hiking_destination",
        "thresholds": "Temp 10–22°C · rain < 15 mm · AQI < 30",
        "score_desc": "Weighted score: proximity to 15°C mean temp (50 pts) + clean air — European AQI below 150 (50 pts).",
        "pill_icon": "⛰️",
    },
    "City Break": {
        "score_col": "city_break_score",
        "flag_col": "is_city_break_destination",
        "thresholds": "Temp 15–28°C · rain < 10 mm · AQI < 50",
        "score_desc": "Weighted score: % of comfortable days — 18–25°C actual temp, rain < 5 mm, wind < 40 km/h (50 pts) + clean air AQI < 100 (30 pts) + low heavy-rain frequency (20 pts).",
        "pill_icon": "🏙️",
    },
    "Cultural & Sightseeing": {
        "score_col": "cultural_score",
        "flag_col": "is_cultural_destination",
        "thresholds": "Temp 15–25°C · rain < 8 mm · AQI < 40 · wind < 25 km/h",
        "score_desc": "Weighted score: proximity to 20°C actual temp (40 pts) + low rain-day frequency (25 pts) + clean air AQI < 80 (20 pts) + calm wind below 50 km/h (15 pts).",
        "pill_icon": "🏛️",
    },
    "Wellness & Slow Travel": {
        "score_col": "wellness_score",
        "flag_col": "is_wellness_destination",
        "thresholds": "Temp 18–25°C · rain < 8 mm · AQI < 25 · wind < 20 km/h",
        "score_desc": "Weighted score: proximity to 21.5°C actual temp (35 pts) + very low rain frequency (25 pts) + pristine air AQI < 50 (25 pts) + very calm wind below 40 km/h (15 pts).",
        "pill_icon": "🌿",
    },
    "Extreme Sports": {
        "score_col": "extreme_sports_score",
        "flag_col": "is_extreme_sports_destination",
        "thresholds": "Wind > 30 km/h · rain < 10 mm  (kitesurfing · paragliding · surfing)",
        "score_desc": "Weighted score: avg wind speed up to 40 km/h (60 pts) + peak wind speed up to 80 km/h (40 pts). Wind is the feature here.",
        "pill_icon": "🌬️",
    },
}

CITY_CLIMATE_ZONE = {
    "Tenerife":   "Canary Islands",
    "Tarifa":     "Mediterranean coast",
    "Barcelona":  "Mediterranean",
    "Lisbon":     "Atlantic coast",
    "Dubrovnik":  "Adriatic coast",
    "Rhodes":     "Eastern Mediterranean",
    "Nice":       "French Riviera",
    "Chamonix":   "Alpine",
    "Bergen":     "Nordic fjords",
    "Reykjavik":  "Subarctic",
    "Prague":     "Continental",
    "Amsterdam":  "Northern European",
}

ZONE_GRADIENTS = {
    "Canary Islands":       "linear-gradient(135deg,#FF8C42 0%,#4FC3D9 100%)",
    "Mediterranean coast":  "linear-gradient(135deg,#14B8A6 0%,#4FC3D9 100%)",
    "Mediterranean":        "linear-gradient(135deg,#4FC3D9 0%,#14B8A6 100%)",
    "Atlantic coast":       "linear-gradient(135deg,#14B8A6 0%,#0E3A4D 100%)",
    "Adriatic coast":       "linear-gradient(135deg,#4FC3D9 0%,#14B8A6 100%)",
    "Eastern Mediterranean":"linear-gradient(135deg,#FFC83D 0%,#14B8A6 100%)",
    "French Riviera":       "linear-gradient(135deg,#FF6B5B 0%,#4FC3D9 100%)",
    "Alpine":               "linear-gradient(135deg,#0E3A4D 0%,#6B8794 100%)",
    "Nordic fjords":        "linear-gradient(135deg,#0E3A4D 0%,#14B8A6 100%)",
    "Subarctic":            "linear-gradient(135deg,#6B8794 0%,#0E3A4D 100%)",
    "Continental":          "linear-gradient(135deg,#6B8794 0%,#4FC3D9 100%)",
    "Northern European":    "linear-gradient(135deg,#0E3A4D 0%,#6B8794 100%)",
}

SCORE_COLS = [
    "beach_score", "hiking_score", "city_break_score",
    "cultural_score", "wellness_score", "extreme_sports_score",
]
SCORE_LABELS = {
    "beach_score":          "Beach & Sun",
    "hiking_score":         "Nature & Hiking",
    "city_break_score":     "City Break",
    "cultural_score":       "Cultural",
    "wellness_score":       "Wellness",
    "extreme_sports_score": "Extreme Sports",
}
COASTAL_PALETTE = ["#FF6B5B", "#14B8A6", "#4FC3D9", "#FFC83D", "#6B8794", "#0E3A4D"]

SORT_OPTIONS = {
    "Score":    ("score_col",            False),
    "Warmest":  ("avg_temp_c",           False),
    "Driest":   ("avg_daily_precipitation_mm", True),
    "Calmest":  ("avg_wind_speed_kmh",   True),
    "Best air": ("avg_aqi",              True),
}


# ─── Image helpers ────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _img_b64(path_str: str) -> str:
    p = Path(path_str)
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


_HERO_B64 = _img_b64(str(HERO_PATH))

_CITY_B64: dict[str, str] = {
    city.lower(): _img_b64(str(ASSETS_DIR / f"{city.lower()}.jpg"))
    for city in CITY_CLIMATE_ZONE
}


def _card_img(city_name: str, height: str = "200px") -> str:
    b64 = _CITY_B64.get(city_name.lower(), "")
    if b64:
        return (
            f'<div style="width:100%;height:{height};overflow:hidden;flex-shrink:0;">'
            f'<img src="data:image/jpeg;base64,{b64}" alt="{city_name}" '
            f'loading="lazy" style="width:100%;height:100%;'
            f'object-fit:cover;object-position:center;display:block;">'
            f'</div>'
        )
    zone = CITY_CLIMATE_ZONE.get(city_name, "Mediterranean")
    grad = ZONE_GRADIENTS.get(zone, "linear-gradient(135deg,#14B8A6,#0E3A4D)")
    icons = {"Alpine": "⛰️", "Subarctic": "❄️", "Nordic fjords": "🏔️",
             "Continental": "🏙️", "Northern European": "🌧️"}
    ico = icons.get(zone, "🌊")
    return (
        f'<div style="width:100%;height:{height};background:{grad};'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-size:3rem;flex-shrink:0;">{ico}</div>'
    )


# ─── Data loading ─────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _get_con():
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_data(show_spinner=False)
def load_summary() -> pd.DataFrame:
    df = _get_con().execute(
        "select * from marts.mart_destination_weather_summary"
    ).df()
    df["avg_aqi"] = df["avg_aqi"].fillna(50.0)
    # Cultural & Wellness: use mart columns if present (after dbt build),
    # otherwise compute from existing metrics using the same formula.
    if "cultural_score" not in df.columns:
        df["cultural_score"] = df.apply(lambda r: round(min(100.0, max(0.0,
            max(1 - abs(r["avg_temp_c"] - 20.0) / 10.0, 0) * 40
            + (1 - r["heavy_rain_days"] / max(r["total_days"], 1)) * 25
            + max(1 - r["avg_aqi"] / 80.0, 0) * 20
            + max(1 - r["avg_wind_speed_kmh"] / 50.0, 0) * 15
        )), 1), axis=1)
    if "wellness_score" not in df.columns:
        df["wellness_score"] = df.apply(lambda r: round(min(100.0, max(0.0,
            max(1 - abs(r["avg_temp_c"] - 21.5) / 7.0, 0) * 35
            + (1 - r["heavy_rain_days"] / max(r["total_days"], 1)) * 25
            + max(1 - r["avg_aqi"] / 50.0, 0) * 25
            + max(1 - r["avg_wind_speed_kmh"] / 40.0, 0) * 15
        )), 1), axis=1)
    if "is_cultural_destination" not in df.columns:
        df["is_cultural_destination"] = (
            df["avg_temp_c"].between(14, 26)
            & (df["avg_daily_precipitation_mm"] < 8)
            & (df["avg_aqi"] < 50)
            & (df["avg_wind_speed_kmh"] < 30)
        )
    if "is_wellness_destination" not in df.columns:
        df["is_wellness_destination"] = (
            df["avg_temp_c"].between(17, 26)
            & (df["avg_daily_precipitation_mm"] < 8)
            & (df["avg_aqi"] < 35)
            & (df["avg_wind_speed_kmh"] < 25)
        )
    df["climate_zone"] = df["city_name"].map(CITY_CLIMATE_ZONE)
    return df


@st.cache_data(show_spinner=False)
def load_daily() -> pd.DataFrame:
    return _get_con().execute(
        "select * from marts.fct_city_weather_day order by city_name, date"
    ).df()


@st.cache_data(show_spinner=False)
def load_locations() -> pd.DataFrame:
    return _get_con().execute(
        "select city_name, latitude, longitude from marts.dim_location"
    ).df()


# ─── Load data (with graceful error) ─────────────────────────────────────────
try:
    summary_df = load_summary()
    daily_df   = load_daily()
    loc_df     = load_locations()
    _data_ok   = True
except Exception as _e:
    st.error(
        f"**Could not connect to weather.duckdb** — run `uv run dbt build` first.\n\n"
        f"Error: `{_e}`"
    )
    st.stop()


# ─── CSS — ONE block ─────────────────────────────────────────────────────────
# All custom styles live here. Fonts scoped to text elements only;
# Material icon font explicitly restored so Streamlit icon ligatures work.
st.markdown("""
<style>
/* ── Google Fonts ─────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap');

/* ── Restore Material icon ligatures (DO NOT use global * override) ────── */
[data-testid="stIconMaterial"],
span[class*="material-symbols"],
span[class*="material-icons"] {
    font-family: 'Material Symbols Outlined','Material Symbols Rounded','Material Icons' !important;
}

/* ── Font scoping — headings and body text only, not global * ─────────── */
h1, h2, h3, h4, h5, h6,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4 {
    font-family: 'Poppins', sans-serif !important;
    color: #0E3A4D;
}
p, li,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li,
label, .stButton button, .stSelectbox label,
.stMultiSelect label, .stRadio label {
    font-family: 'Inter', sans-serif;
}

/* ── App background ───────────────────────────────────────────────────── */
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
    background-color: #F7FAFC !important;
}

/* ── Remove top padding so hero sits flush ────────────────────────────── */
[data-testid="stMainBlockContainer"] {
    padding-top: 0 !important;
}

/* ── Collapse sidebar toggle ──────────────────────────────────────────── */
[data-testid="stSidebarCollapsedControl"] {
    display: none;
}

/* ── Hero wrapper — full-bleed trick: left+transform pushes to vp edge ── */
.hero-wrapper {
    position: relative;
    left: 50%;
    transform: translateX(-50%);
    width: 100vw;
    min-height: 440px;
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    padding: 64px 5vw 0 5vw;
    box-sizing: border-box;
    overflow: hidden;
}
.hero-eyebrow {
    font-family: 'Poppins', sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: rgba(255,107,91,0.92);
    margin-bottom: 14px;
}
.hero-title {
    font-family: 'Poppins', sans-serif !important;
    font-size: clamp(2rem, 4vw, 3.2rem);
    font-weight: 800;
    color: #FFFFFF !important;
    line-height: 1.12;
    text-shadow: 0 1px 14px rgba(14,58,77,.45);
    margin: 0 0 10px 0;
}
.hero-underline {
    width: 64px;
    height: 4px;
    background: #FF6B5B;
    border-radius: 2px;
    margin: 0 0 20px 0;
}
.hero-subtitle {
    font-family: 'Inter', sans-serif;
    font-size: 1.08rem;
    color: rgba(255,255,255,0.82);
    max-width: 560px;
    line-height: 1.55;
    margin-bottom: 32px;
}
.hero-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 32px;
}
.hero-pill {
    font-family: 'Inter', sans-serif;
    font-size: 0.82rem;
    font-weight: 600;
    color: #FFFFFF;
    background: rgba(255,255,255,0.14);
    border: 1px solid rgba(255,255,255,0.32);
    border-radius: 999px;
    padding: 6px 16px;
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    white-space: nowrap;
    cursor: default;
    transition: background 0.2s;
}
.hero-pill:hover {
    background: rgba(255,255,255,0.24);
}
.hero-stats {
    font-family: 'Inter', sans-serif;
    font-size: 0.82rem;
    color: rgba(255,255,255,0.65);
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
    margin-bottom: 0;
    padding-bottom: 48px;
}
.hero-stats span { white-space: nowrap; }
.hero-stat-dot {
    color: rgba(255,255,255,0.3);
    margin: 0 -8px;
}

/* ── SVG wave divider ─────────────────────────────────────────────────── */
.hero-wave {
    display: block;
    position: relative;
    left: 50%;
    transform: translateX(-50%);
    width: 100vw;
    line-height: 0;
    margin-top: -2px;
    overflow: hidden;
}
.hero-wave svg { display: block; width: 100%; }

/* ── Filter card ──────────────────────────────────────────────────────── */
.filter-card {
    background: #FFFFFF;
    border-radius: 14px;
    box-shadow: 0 2px 12px rgba(14,58,77,.08);
    padding: 24px 28px 20px 28px;
    margin-bottom: 28px;
}
.filter-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: #6B8794;
    margin-bottom: 10px;
}

/* ── Holiday-type selector buttons ───────────────────────────────────── */
/* Active state: coral fill */
div[data-testid="stButton"] button[kind="primary"] {
    background-color: #FF6B5B !important;
    color: #FFFFFF !important;
    border-color: #FF6B5B !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
    padding: 8px 6px !important;
    transition: transform 0.15s, box-shadow 0.15s !important;
}
div[data-testid="stButton"] button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(255,107,91,.35) !important;
}
/* Inactive: white with border */
div[data-testid="stButton"] button[kind="secondary"] {
    background-color: #FFFFFF !important;
    color: #0E3A4D !important;
    border: 1.5px solid #E2E8F0 !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    white-space: nowrap !important;
    padding: 8px 6px !important;
    transition: border-color 0.15s, color 0.15s !important;
}
div[data-testid="stButton"] button[kind="secondary"]:hover {
    border-color: #FF6B5B !important;
    color: #FF6B5B !important;
}

/* ── Coral primary CTA button ─────────────────────────────────────────── */
.cta-btn button {
    background-color: #FF6B5B !important;
    color: #FFFFFF !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    padding: 10px 0 !important;
    width: 100% !important;
    border: none !important;
    transition: transform 0.15s, box-shadow 0.15s !important;
}
.cta-btn button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(255,107,91,.4) !important;
}

/* ── Results strip ────────────────────────────────────────────────────── */
.results-strip {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 8px;
    flex-wrap: wrap;
}
.results-title {
    font-family: 'Poppins', sans-serif;
    font-size: 1.15rem;
    font-weight: 700;
    color: #0E3A4D;
    flex: 1;
    min-width: 160px;
}
.badge-legend {
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    color: #6B8794;
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    align-items: center;
}
.bl-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 4px;
    vertical-align: middle;
}

/* ── Featured card ────────────────────────────────────────────────────── */
.featured-card {
    background: #FFFFFF;
    border-radius: 14px;
    box-shadow: 0 4px 20px rgba(14,58,77,.12);
    overflow: hidden;
    margin-bottom: 28px;
    display: flex;
    min-height: 260px;
}
.featured-photo {
    flex: 0 0 42%;
    position: relative;
    overflow: hidden;
}
.featured-photo img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
    display: block;
}
.featured-photo-scrim {
    position: absolute;
    inset: 0;
    background: linear-gradient(to right, rgba(14,58,77,.60), rgba(14,58,77,.10));
}
.featured-info {
    flex: 1;
    padding: 28px 28px 24px 28px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.featured-eyebrow {
    font-family: 'Poppins', sans-serif;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #FF6B5B;
    margin-bottom: 8px;
}
.featured-city {
    font-family: 'Poppins', sans-serif;
    font-size: 1.75rem;
    font-weight: 800;
    color: #0E3A4D;
    line-height: 1.1;
    margin-bottom: 4px;
}
.featured-zone {
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem;
    color: #6B8794;
    margin-bottom: 14px;
}

/* ── Recommendation badges ────────────────────────────────────────────── */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: 'Inter', sans-serif;
    font-size: 0.74rem;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    white-space: nowrap;
}
.badge-top    { background: rgba(255,107,91,.12); color: #FF6B5B; border: 1px solid rgba(255,107,91,.3); }
.badge-good   { background: rgba(20,184,166,.12); color: #14B8A6; border: 1px solid rgba(20,184,166,.3); }
.badge-low    { background: rgba(107,135,148,.10); color: #6B8794; border: 1px solid rgba(107,135,148,.25); }

/* ── Score bar (for grid cards) ───────────────────────────────────────── */
.score-section {
    padding: 12px 16px 8px 16px;
}
.score-label-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 6px;
}
.score-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6B8794;
}
.score-value {
    font-family: 'Poppins', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: #0E3A4D;
}
.score-track {
    width: 100%;
    height: 8px;
    background: #E2E8F0;
    border-radius: 4px;
    overflow: hidden;
}
.score-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.4s ease;
}

/* ── Destination card (3-up grid) ────────────────────────────────────── */
.dest-card {
    background: #FFFFFF;
    border-radius: 14px;
    box-shadow: 0 2px 12px rgba(14,58,77,.08);
    overflow: hidden;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    cursor: default;
    height: 100%;
}
.dest-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 28px rgba(14,58,77,.14);
}
.dest-card:hover .card-photo img {
    transform: scale(1.04);
}
.card-photo {
    position: relative;
    overflow: hidden;
}
.card-photo img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
    display: block;
    transition: transform 0.35s ease;
}
.card-photo-scrim {
    position: absolute;
    inset: 0;
    background: linear-gradient(to top, rgba(14,58,77,.85) 0%, rgba(14,58,77,.15) 55%, transparent 100%);
}
.card-overlay {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 14px 14px 12px 14px;
}
.card-city-name {
    font-family: 'Poppins', sans-serif;
    font-size: 1.05rem;
    font-weight: 700;
    color: #FFFFFF;
    margin-bottom: 2px;
    text-shadow: 0 1px 4px rgba(0,0,0,.3);
}
.card-zone {
    font-family: 'Inter', sans-serif;
    font-size: 0.74rem;
    color: rgba(255,255,255,0.78);
    margin-bottom: 6px;
}

/* ── Metric chips ─────────────────────────────────────────────────────── */
.metric-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 10px 14px 14px 14px;
}
.chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    font-weight: 500;
    color: #0E3A4D;
    background: #F7FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 999px;
    padding: 3px 10px;
    white-space: nowrap;
}

/* ── Tab styling ─────────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem;
    font-weight: 600;
    color: #6B8794;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    color: #FF6B5B;
    border-bottom: 2px solid #FF6B5B;
}

/* ── Footer ──────────────────────────────────────────────────────────── */
.footer {
    margin-top: 48px;
    padding: 20px 0 28px 0;
    border-top: 1px solid #E2E8F0;
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    color: #6B8794;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
}
.footer a { color: #14B8A6; text-decoration: none; }
.footer a:hover { text-decoration: underline; }

/* ── Utilities ────────────────────────────────────────────────────────── */
.mt-0 { margin-top: 0 !important; }
.mb-16 { margin-bottom: 16px; }
.section-heading {
    font-family: 'Poppins', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: #0E3A4D;
    margin: 28px 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #E2E8F0;
}
</style>
""", unsafe_allow_html=True)


# ─── Hero ────────────────────────────────────────────────────────────────────
_hero_style = (
    f"background-image: linear-gradient(120deg, rgba(14,58,77,.92) 0%, "
    f"rgba(20,184,166,.55) 100%), url('data:image/jpeg;base64,{_HERO_B64}');"
    if _HERO_B64 else
    "background-image: linear-gradient(120deg, #0E3A4D 0%, #14B8A6 100%);"
)

_pills_html = "".join(
    f'<span class="hero-pill">{m["pill_icon"]} {ht}</span>'
    for ht, m in HOLIDAY_META.items()
)

_max_date_str = (
    daily_df["date"].max().strftime("%d %b %Y") if not daily_df.empty else "—"
)

st.markdown(f"""
<div class="hero-wrapper" style="{_hero_style}">
  <p class="hero-eyebrow">OPEN-METEO · DBT · DUCKDB · 12 EUROPEAN DESTINATIONS</p>
  <h1 class="hero-title">Find your perfect-weather escape</h1>
  <div class="hero-underline"></div>
  <p class="hero-subtitle">
    Pick a holiday style and we rank 12 destinations by how often
    the weather matches your ideal conditions.
  </p>
  <div class="hero-pills">{_pills_html}</div>
  <div class="hero-stats">
    <span>🗺️ 12 destinations</span>
    <span class="hero-stat-dot">·</span>
    <span>🌍 4 climate zones</span>
    <span class="hero-stat-dot">·</span>
    <span>📅 {len(daily_df) // max(summary_df["city_name"].nunique(), 1)} days of data</span>
    <span class="hero-stat-dot">·</span>
    <span>🔮 7-day forecast included</span>
  </div>
</div>
""", unsafe_allow_html=True)

# SVG wave divider
st.markdown("""
<div class="hero-wave">
  <svg viewBox="0 0 1440 56" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M0,32 C360,64 1080,0 1440,32 L1440,56 L0,56 Z" fill="#F7FAFC"/>
  </svg>
</div>
""", unsafe_allow_html=True)


# ─── Session state ────────────────────────────────────────────────────────────
if "holiday_type" not in st.session_state:
    st.session_state.holiday_type = HOLIDAY_TYPES[0]


# ─── Filter card ─────────────────────────────────────────────────────────────
st.markdown('<div class="filter-card">', unsafe_allow_html=True)

st.markdown('<p class="filter-label">Holiday type</p>', unsafe_allow_html=True)
btn_cols = st.columns(6, gap="small")
for col, ht in zip(btn_cols, HOLIDAY_TYPES):
    with col:
        is_active = st.session_state.holiday_type == ht
        if st.button(
            ht,
            key=f"ht_{ht}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.holiday_type = ht
            st.rerun()

st.markdown("<div style='margin-top:16px;'>", unsafe_allow_html=True)

filter_cols = st.columns([3, 4, 2], gap="medium")
with filter_cols[0]:
    all_countries = ["All countries"] + sorted(summary_df["country"].unique().tolist())
    selected_country = st.selectbox(
        "Country",
        options=all_countries,
        label_visibility="visible",
    )
with filter_cols[1]:
    if selected_country == "All countries":
        city_options = sorted(summary_df["city_name"].unique().tolist())
    else:
        city_options = sorted(
            summary_df.loc[summary_df["country"] == selected_country, "city_name"]
            .unique().tolist()
        )
    selected_cities = st.multiselect(
        "City (leave blank for all)",
        options=city_options,
        label_visibility="visible",
    )
with filter_cols[2]:
    st.markdown("<div class='cta-btn' style='margin-top:24px;'>", unsafe_allow_html=True)
    if st.button("🔍 Find destinations", use_container_width=True):
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)  # close .filter-card


# ─── Filtering & ranking ──────────────────────────────────────────────────────
selected_type = st.session_state.holiday_type
meta = HOLIDAY_META[selected_type]
score_col = meta["score_col"]
flag_col  = meta["flag_col"]

# Apply country filter
if selected_country == "All countries":
    filt_df = summary_df.copy()
else:
    filt_df = summary_df[summary_df["country"] == selected_country].copy()

# Apply city filter
if selected_cities:
    filt_df = filt_df[filt_df["city_name"].isin(selected_cities)].copy()

if filt_df.empty:
    st.warning("No destinations match your filters. Try widening the selection.")
    st.stop()

# Apply daily filter to match
filt_daily = daily_df[daily_df["city_name"].isin(filt_df["city_name"])].copy()


# ─── Results strip ────────────────────────────────────────────────────────────
res_l, res_r = st.columns([5, 2], gap="medium")
with res_l:
    st.markdown(
        f'<p class="results-title">{selected_type} — {len(filt_df)} destinations</p>',
        unsafe_allow_html=True,
    )
with res_r:
    sort_key = st.selectbox(
        "Sort by",
        options=list(SORT_OPTIONS.keys()),
        label_visibility="visible",
        key="sort_by",
    )

# Badge legend
st.markdown(
    '<div class="badge-legend">'
    '<span><span class="bl-dot" style="background:#FF6B5B;"></span>Top match = highest score</span>'
    '<span><span class="bl-dot" style="background:#14B8A6;"></span>Recommended = meets threshold</span>'
    '<span><span class="bl-dot" style="background:#6B8794;"></span>Not ideal = below threshold</span>'
    '</div>',
    unsafe_allow_html=True,
)

# Score method popover
with st.popover("ℹ️ How the score works"):
    st.markdown(
        f"**Score = 0–100** — a weighted composite of weather metrics "
        f"computed across all days in the data period.  \n\n"
        f"**{selected_type}** thresholds (from README):  \n"
        f">{meta['thresholds']}  \n\n"
        f"{meta['score_desc']}  \n\n"
        f"Temperatures are **actual mean °C** (`temperature_2m_mean`) from Open-Meteo."
    )


# ─── Sort & rank ─────────────────────────────────────────────────────────────
_sort_field, _sort_asc = SORT_OPTIONS[sort_key]
if _sort_field == "score_col":
    _sort_field = score_col

ranked = (
    filt_df
    .sort_values(_sort_field, ascending=_sort_asc)
    .reset_index(drop=True)
)
ranked["rank"] = ranked.index + 1

top = ranked.iloc[0]
top_score = float(top[score_col])
top_zone  = CITY_CLIMATE_ZONE.get(top["city_name"], "")


# ─── Score colour helper ──────────────────────────────────────────────────────
def _score_color(score: float) -> str:
    if score >= 75:
        return "#14B8A6"
    if score >= 40:
        return "#FFC83D"
    return "#6B8794"


# ─── Featured best-match card ────────────────────────────────────────────────
st.markdown('<div style="margin-top:20px;margin-bottom:4px;">', unsafe_allow_html=True)

fc_l, fc_r = st.columns([5, 3], gap="medium")
with fc_l:
    b64 = _CITY_B64.get(top["city_name"].lower(), "")
    if b64:
        _img_tag = (
            f'<img src="data:image/jpeg;base64,{b64}" alt="{top["city_name"]}" '
            f'style="width:100%;height:100%;object-fit:cover;object-position:center;display:block;">'
        )
    else:
        zone = top.get("climate_zone", "Mediterranean")
        grad = ZONE_GRADIENTS.get(zone, "linear-gradient(135deg,#14B8A6,#0E3A4D)")
        _img_tag = f'<div style="width:100%;height:100%;background:{grad};"></div>'

    badge_cls = "badge-top"
    badge_txt = "🏆 Top match"

    st.markdown(f"""
<div class="featured-card">
  <div class="featured-photo" style="min-height:260px;">
    {_img_tag}
    <div class="featured-photo-scrim"></div>
  </div>
  <div class="featured-info">
    <p class="featured-eyebrow">✦ BEST MATCH FOR {selected_type.upper()}</p>
    <p class="featured-city">{top["city_name"]}</p>
    <p class="featured-zone">{top_zone} · {top["country"]}</p>
    <span class="badge {badge_cls}">{badge_txt}</span>
    <div style="margin-top:16px;">
      <div class="chip">☀️ {top['avg_temp_c']:.1f}°C avg temp</div>&nbsp;
      <div class="chip">🌧️ {top['avg_daily_precipitation_mm']:.1f} mm/day rain</div>&nbsp;
      <div class="chip">💨 {top['avg_wind_speed_kmh']:.1f} km/h wind</div>&nbsp;
      <div class="chip">🌫️ AQI {top['avg_aqi']:.0f}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

with fc_r:
    # Plotly gauge for the featured card score
    _fc_color = _score_color(top_score)
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=top_score,
        number={"suffix": " / 100", "font": {"size": 28, "color": "#0E3A4D",
                                              "family": "Poppins"}},
        title={"text": f"<b>{selected_type}</b><br>Weather Score",
               "font": {"size": 13, "color": "#6B8794", "family": "Inter"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#E2E8F0",
                     "tickfont": {"size": 10}},
            "bar": {"color": _fc_color, "thickness": 0.28},
            "bgcolor": "#F7FAFC",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 40],  "color": "#FEE2E2"},
                {"range": [40, 75], "color": "#FEF3C7"},
                {"range": [75, 100],"color": "#CCFBF1"},
            ],
            "threshold": {
                "line": {"color": _fc_color, "width": 3},
                "thickness": 0.8,
                "value": top_score,
            },
        },
    ))
    fig_gauge.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=20, r=20, t=40, b=20),
        height=240,
    )
    st.markdown(
        '<div style="background:#FFFFFF;border-radius:14px;'
        'box-shadow:0 2px 12px rgba(14,58,77,.08);padding:8px;margin-top:0;">',
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig_gauge, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)


# ─── Tabs: Destinations | Map ────────────────────────────────────────────────
tab_cards, tab_map = st.tabs(["📍 Destinations", "🗺️ Map"])


# ── Cards tab ────────────────────────────────────────────────────────────────
with tab_cards:
    if len(ranked) == 0:
        st.info("No destinations match the current filters.")
    else:
        rows = [ranked.iloc[i : i + 3] for i in range(0, len(ranked), 3)]
        for row_df in rows:
            grid_cols = st.columns(3, gap="medium")
            for col, (_, r) in zip(grid_cols, row_df.iterrows()):
                with col:
                    city_nm  = r["city_name"]
                    score_v  = float(r[score_col])
                    is_flag  = bool(r[flag_col])
                    is_top   = r["rank"] == 1

                    if is_top:
                        badge_html = '<span class="badge badge-top">🏆 Top match</span>'
                    elif is_flag:
                        badge_html = '<span class="badge badge-good">✓ Recommended</span>'
                    else:
                        badge_html = '<span class="badge badge-low">Not ideal</span>'

                    fill_color = _score_color(score_v)
                    fill_pct   = f"{score_v:.0f}%"

                    b64 = _CITY_B64.get(city_nm.lower(), "")
                    if b64:
                        _img_html = (
                            f'<div class="card-photo" style="height:190px;">'
                            f'<img src="data:image/jpeg;base64,{b64}" alt="{city_nm}">'
                            f'<div class="card-photo-scrim"></div>'
                            f'<div class="card-overlay">'
                            f'<p class="card-city-name">{city_nm}</p>'
                            f'<p class="card-zone">'
                            f'{r.get("climate_zone", "")} · {r["country"]}'
                            f'</p>'
                            f'{badge_html}'
                            f'</div></div>'
                        )
                    else:
                        zone = r.get("climate_zone", "Mediterranean")
                        grad = ZONE_GRADIENTS.get(
                            zone, "linear-gradient(135deg,#14B8A6,#0E3A4D)"
                        )
                        _img_html = (
                            f'<div class="card-photo" style="height:190px;'
                            f'background:{grad};">'
                            f'<div class="card-photo-scrim"></div>'
                            f'<div class="card-overlay">'
                            f'<p class="card-city-name">{city_nm}</p>'
                            f'<p class="card-zone">'
                            f'{r.get("climate_zone", "")} · {r["country"]}'
                            f'</p>'
                            f'{badge_html}'
                            f'</div></div>'
                        )

                    aqi_val = f"{r['avg_aqi']:.0f}" if pd.notna(r["avg_aqi"]) else "—"
                    st.markdown(f"""
<div class="dest-card">
  {_img_html}
  <div class="score-section">
    <div class="score-label-row">
      <span class="score-label">Score</span>
      <span class="score-value">{score_v:.0f} / 100</span>
    </div>
    <div class="score-track">
      <div class="score-fill" style="width:{fill_pct};background:{fill_color};"></div>
    </div>
  </div>
  <div class="metric-chips">
    <span class="chip" title="Actual mean temperature">☀️ {r['avg_temp_c']:.1f}°C</span>
    <span class="chip" title="Average daily rainfall">🌧️ {r['avg_daily_precipitation_mm']:.1f} mm</span>
    <span class="chip" title="Average wind speed">💨 {r['avg_wind_speed_kmh']:.1f} km/h</span>
    <span class="chip" title="Average European AQI">🌫️ AQI {aqi_val}</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Map tab ───────────────────────────────────────────────────────────────────
with tab_map:
    try:
        import pydeck as pdk

        map_df = ranked.merge(loc_df, on="city_name", how="left")
        map_df["score_val"] = map_df[score_col].fillna(0)
        map_df["radius"] = (map_df["score_val"] / 100 * 60_000 + 20_000).astype(int)

        def _score_rgb(s: float):
            if s >= 75:
                return [20, 184, 166]
            if s >= 40:
                return [255, 200, 61]
            return [107, 135, 148]

        map_df["color"] = map_df["score_val"].apply(_score_rgb)
        map_df["tooltip_text"] = (
            map_df["city_name"] + " · " + map_df["score_val"].apply(lambda v: f"{v:.0f}/100")
        )

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position="[longitude, latitude]",
            get_color="color",
            get_radius="radius",
            opacity=0.75,
            pickable=True,
            filled=True,
        )
        view = pdk.ViewState(
            latitude=map_df["latitude"].mean(),
            longitude=map_df["longitude"].mean(),
            zoom=3.8,
            pitch=0,
        )
        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=view,
                tooltip={"text": "{tooltip_text}"},
                map_style="mapbox://styles/mapbox/light-v10",
            ),
            use_container_width=True,
        )
        st.caption(
            "Marker size and colour reflect weather score for the selected holiday type. "
            "Teal = high score · Amber = mid · Grey = low."
        )
    except ImportError:
        st.info("Install pydeck (`uv add pydeck`) to enable the map tab.")
    except Exception as _map_err:
        st.warning(f"Map could not render: {_map_err}")


# ─── Daily weather section ────────────────────────────────────────────────────
st.markdown('<p class="section-heading">Daily weather trends</p>', unsafe_allow_html=True)

top3_cities = ranked["city_name"].head(3).tolist()
all_city_opts = sorted(filt_daily["city_name"].unique().tolist())

daily_city_sel = st.multiselect(
    "Cities to compare (default: top 3 by score)",
    options=all_city_opts,
    default=[c for c in top3_cities if c in all_city_opts],
    key="daily_city_sel",
)
if not daily_city_sel:
    daily_city_sel = top3_cities[:3]

chart_df = filt_daily[filt_daily["city_name"].isin(daily_city_sel)].copy()

ch_l, ch_r = st.columns(2, gap="medium")

with ch_l:
    st.markdown(
        '<p style="font-family:Inter;font-weight:600;color:#0E3A4D;margin-bottom:4px;">'
        'Actual mean temperature (°C)'
        '</p>',
        unsafe_allow_html=True,
    )
    if not chart_df.empty:
        fig_temp = px.line(
            chart_df,
            x="date",
            y="temperature_2m_mean",
            color="city_name",
            color_discrete_sequence=COASTAL_PALETTE,
            labels={"date": "", "temperature_2m_mean": "Mean Temp (°C)", "city_name": "City"},
            template="plotly_white",
        )
        fig_temp.update_traces(line_width=2)
        fig_temp.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            height=280,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(size=11, family="Inter")),
            plot_bgcolor="#FFFFFF",
        )
        st.plotly_chart(fig_temp, use_container_width=True)

with ch_r:
    st.markdown(
        '<p style="font-family:Inter;font-weight:600;color:#0E3A4D;margin-bottom:4px;">'
        'Daily precipitation (mm)'
        '</p>',
        unsafe_allow_html=True,
    )
    if not chart_df.empty:
        fig_precip = px.bar(
            chart_df,
            x="date",
            y="precipitation_sum",
            color="city_name",
            barmode="overlay",
            opacity=0.6,
            color_discrete_sequence=COASTAL_PALETTE,
            labels={"date": "", "precipitation_sum": "Precipitation (mm)", "city_name": "City"},
            template="plotly_white",
        )
        fig_precip.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            height=280,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(size=11, family="Inter")),
            plot_bgcolor="#FFFFFF",
        )
        st.plotly_chart(fig_precip, use_container_width=True)

# All-scores comparison chart
st.markdown(
    '<p style="font-family:Inter;font-weight:600;color:#0E3A4D;margin:20px 0 8px 0;">'
    'All holiday-type scores compared'
    '</p>',
    unsafe_allow_html=True,
)
all_scores = filt_df.melt(
    id_vars=["city_name"],
    value_vars=SCORE_COLS,
    var_name="activity",
    value_name="score",
)
all_scores["activity"] = all_scores["activity"].map(SCORE_LABELS)
all_scores["label"] = all_scores["city_name"].apply(
    lambda c: c + " (" + filt_df.loc[filt_df["city_name"] == c, "country"].values[0][:3] + ")"
)
fig_all = px.bar(
    all_scores,
    x="label",
    y="score",
    color="activity",
    barmode="group",
    color_discrete_sequence=COASTAL_PALETTE,
    labels={"label": "", "score": "Score (0–100)", "activity": "Holiday Type"},
    template="plotly_white",
)
fig_all.update_layout(
    xaxis_tickangle=-25,
    yaxis_range=[0, 100],
    height=340,
    margin=dict(l=0, r=0, t=20, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(size=11, family="Inter")),
    plot_bgcolor="#FFFFFF",
)
st.plotly_chart(fig_all, use_container_width=True)


# ─── Footer ───────────────────────────────────────────────────────────────────
_max_date_footer = (
    daily_df["date"].max().strftime("%d %b %Y") if not daily_df.empty else "—"
)
st.markdown(
    f'<div class="footer">'
    f'<span>Source: Open-Meteo · Built with dbt + DuckDB · '
    f'Model: <code>marts.mart_destination_weather_summary</code></span>'
    f'<span>Data as of {_max_date_footer} · '
    f'<a href="assets/cities/ATTRIBUTIONS.md">Image attributions</a></span>'
    f'</div>',
    unsafe_allow_html=True,
)
