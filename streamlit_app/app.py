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
HERE = Path(__file__).parent
DB_PATH = HERE.parent / "weather.duckdb"
ASSETS_DIR = HERE / "assets" / "cities"
HERO_PATH = HERE / "assets" / "hero.jpg"

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

SCORE_COMPONENTS = {
    "Beach & Sun": [
        ("Temperature",   lambda r: min(max(r["avg_temp_c"] - 15, 0), 20) / 20 * 50,  50),
        ("Low Rain",      lambda r: (1 - r["heavy_rain_days"] / max(r["total_days"], 1)) * 30, 30),
        ("Low Wind",      lambda r: max(1 - r["avg_wind_speed_kmh"] / 60, 0) * 20,    20),
    ],
    "Nature & Hiking": [
        ("Mild Temp",     lambda r: max(1 - abs(r["avg_temp_c"] - 15) / 20, 0) * 50,  50),
        ("Clean Air",     lambda r: (1 - min(r["avg_aqi"] / 150, 1)) * 50,            50),
    ],
    "City Break": [
        ("Comfort Days",  lambda r: r["comfortable_day_pct"] / 100 * 50,              50),
        ("Air Quality",   lambda r: (1 - min(r["avg_aqi"] / 100, 1)) * 30,            30),
        ("Low Rain",      lambda r: (1 - r["heavy_rain_days"] / max(r["total_days"], 1)) * 20, 20),
    ],
    "Extreme Sports": [
        ("Avg Wind",      lambda r: min(r["avg_wind_speed_kmh"] / 40, 1) * 60,        60),
        ("Peak Wind",     lambda r: min(r["max_wind_speed_kmh"] / 80, 1) * 40,        40),
    ],
    "Cultural & Sightseeing": [
        ("Mild Temp",     lambda r: max(1 - abs(r["avg_temp_c"] - 20) / 10, 0) * 40,  40),
        ("Low Rain",      lambda r: (1 - r["heavy_rain_days"] / max(r["total_days"], 1)) * 25, 25),
        ("Clean Air",     lambda r: max(1 - r["avg_aqi"] / 80, 0) * 20,               20),
        ("Low Wind",      lambda r: max(1 - r["avg_wind_speed_kmh"] / 50, 0) * 15,    15),
    ],
    "Wellness & Slow Travel": [
        ("Mild Temp",     lambda r: max(1 - abs(r["avg_temp_c"] - 21.5) / 7, 0) * 35, 35),
        ("Low Rain",      lambda r: (1 - r["heavy_rain_days"] / max(r["total_days"], 1)) * 25, 25),
        ("Clean Air",     lambda r: max(1 - r["avg_aqi"] / 50, 0) * 25,               25),
        ("Low Wind",      lambda r: max(1 - r["avg_wind_speed_kmh"] / 40, 0) * 15,    15),
    ],
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
    "Mediterranean coast":  "linear-gradient(135deg,#218208 0%,#4FC3D9 100%)",
    "Mediterranean":        "linear-gradient(135deg,#4FC3D9 0%,#218208 100%)",
    "Atlantic coast":       "linear-gradient(135deg,#218208 0%,#0E3A4D 100%)",
    "Adriatic coast":       "linear-gradient(135deg,#4FC3D9 0%,#218208 100%)",
    "Eastern Mediterranean":"linear-gradient(135deg,#FFC83D 0%,#218208 100%)",
    "French Riviera":       "linear-gradient(135deg,#FF6B5B 0%,#4FC3D9 100%)",
    "Alpine":               "linear-gradient(135deg,#0E3A4D 0%,#6B8794 100%)",
    "Nordic fjords":        "linear-gradient(135deg,#0E3A4D 0%,#218208 100%)",
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
CITY_PALETTE  = ["#218208", "#FF6B5B", "#0E3A4D"]
TYPE_PALETTE  = ["#4FC3D9", "#FFC83D", "#94A3B8", "#F97316", "#A78BFA", "#EC4899"]

SORT_OPTIONS = {
    "Warmest":  ("avg_temp_c",                 False),
    "Driest":   ("avg_daily_precipitation_mm", True),
    "Rainiest": ("avg_daily_precipitation_mm", False),
    "Calmest":  ("avg_wind_speed_kmh",         True),
    "Snowfall": ("snow_days",                  False),
    "Best air": ("avg_aqi",                    True),
}

RADAR_CATS = [
    ("Beach & Sun",     "beach_score"),
    ("Nature & Hiking", "hiking_score"),
    ("City Break",      "city_break_score"),
    ("Extreme Sports",  "extreme_sports_score"),
    ("Cultural",        "cultural_score"),
    ("Wellness",        "wellness_score"),
]


# ─── Image helpers ────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _img_b64(path_str: str) -> str:
    p = Path(path_str)
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


HERO_IMAGE = _img_b64(str(HERO_PATH))

CITY_IMAGES: dict[str, str] = {
    city.lower(): _img_b64(str(ASSETS_DIR / f"{city.lower()}.jpg"))
    for city in CITY_CLIMATE_ZONE
}




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



# ─── Load data (with graceful error) ─────────────────────────────────────────
try:
    summary_df = load_summary()
    daily_df   = load_daily()
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
    background-color: #FFFFFF !important;
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
    color: rgba(255,255,255,0.72);
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
    background: #218208;
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
    height: 340px;
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
    overflow: hidden;
}
.featured-eyebrow {
    font-family: 'Poppins', sans-serif;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #218208;
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
.badge-top    { background: rgba(33,130,8,.18); color: #218208; border: 2px solid rgba(33,130,8,.4); }
.badge-good   { background: rgba(33,130,8,.12); color: #218208; border: 1px solid rgba(33,130,8,.3); }
.badge-low    { background: rgba(107,135,148,.10); color: #6B8794; border: 1px solid rgba(107,135,148,.25); }

/* ── Widget focus overrides (Streamlit / BaseWeb) ──────────────────── */
div[data-baseweb="select"] > div:focus-within {
    border-color: #218208 !important;
    box-shadow: 0 0 0 3px rgba(33,130,8,.12) !important;
}
[data-baseweb="menu"] [aria-selected="true"] {
    background-color: rgba(33,130,8,.12) !important;
}
[data-baseweb="menu"] li:hover {
    background-color: rgba(33,130,8,.08) !important;
}
[data-baseweb="tag"] {
    background-color: rgba(33,130,8,.15) !important;
    color: #218208 !important;
}

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
    height: 300px;
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
    color: #218208;
    border-bottom: 2px solid #218208;
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
.footer a { color: #218208; text-decoration: none; }
.footer a:hover { text-decoration: underline; }

/* ── Filter card — override st.container(border=True) styling ─────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #E2E8F0 !important;
    border-radius: 14px !important;
    box-shadow: 0 2px 12px rgba(14,58,77,.08) !important;
    background: #FFFFFF !important;
    padding: 24px 28px 20px 28px !important;
    margin-bottom: 28px !important;
}

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
.filter-section-label {
    font-family: 'Poppins', sans-serif;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin: 0 0 6px 0;
    padding-bottom: 6px;
    border-bottom: 2px solid currentColor;
    opacity: 0.9;
}
.chart-title {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    color: #0E3A4D;
    margin-bottom: 4px;
}
</style>
""", unsafe_allow_html=True)


# ─── Hero ────────────────────────────────────────────────────────────────────
hero_style = (
    f"background-image: linear-gradient(120deg, rgba(14,58,77,.92) 0%, "
    f"rgba(33,130,8,.55) 100%), url('data:image/jpeg;base64,{HERO_IMAGE}');"
    if HERO_IMAGE else
    "background-image: linear-gradient(120deg, #0E3A4D 0%, #218208 100%);"
)

hero_pills = "".join(
    f'<span class="hero-pill">{m["pill_icon"]} {ht}</span>'
    for ht, m in HOLIDAY_META.items()
)

data_date = (
    daily_df["date"].max().strftime("%d %b %Y") if not daily_df.empty else "—"
)

st.markdown(f"""
<div class="hero-wrapper" style="{hero_style}">
  <p class="hero-eyebrow">OPEN-METEO · DBT · DUCKDB · 12 EUROPEAN DESTINATIONS</p>
  <h1 class="hero-title">Find your perfect-weather escape</h1>
  <div class="hero-underline"></div>
  <p class="hero-subtitle">
    Pick a holiday style and we rank 12 destinations by how often
    the weather matches your ideal conditions.
  </p>
  <div class="hero-pills">{hero_pills}</div>
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
for state_key, default_value in [
    ("filter_mode",  "holiday"),
    ("holiday_type", HOLIDAY_TYPES[0]),
    ("sort_attr",    list(SORT_OPTIONS.keys())[0]),
]:
    if state_key not in st.session_state:
        st.session_state[state_key] = default_value

# Guard: sort_attr may be stale if SORT_OPTIONS changed
if st.session_state.sort_attr not in SORT_OPTIONS:
    st.session_state.sort_attr = list(SORT_OPTIONS.keys())[0]


def _activate_holiday():
    st.session_state.filter_mode = "holiday"
    st.session_state.holiday_type = st.session_state["_ht_select"]
    st.session_state["_dest_country"] = "All countries"
    st.session_state["_dest_cities"] = []


def _activate_sort():
    st.session_state.filter_mode = "sort"
    st.session_state.sort_attr = st.session_state["_sort_select"]
    st.session_state["_dest_country"] = "All countries"
    st.session_state["_dest_cities"] = []


def _on_dest_country_change():
    """Switch to destination mode; clear city selection when country changes."""
    st.session_state.filter_mode = "destination"
    st.session_state["_dest_cities"] = []


def _on_dest_city_change():
    st.session_state.filter_mode = "destination"


# ─── Filter card (3 mutually-exclusive sections) ────────────────────────────
with st.container(border=True):
    filter_mode = st.session_state.filter_mode
    holiday_col, sort_col, destination_col = st.columns([2, 2, 3], gap="large")

    # ── Holiday type ─────────────────────────────────────────
    with holiday_col:
        holiday_tab_active    = filter_mode == "holiday"
        holiday_label_color = "#218208" if holiday_tab_active else "#94A3B8"
        st.markdown(
            f'<p class="filter-section-label" style="color:{holiday_label_color};">'
            'Holiday type</p>',
            unsafe_allow_html=True,
        )
        holiday_type_index = (
            HOLIDAY_TYPES.index(st.session_state.holiday_type)
            if st.session_state.holiday_type in HOLIDAY_TYPES else 0
        )
        st.selectbox(
            "Holiday type",
            HOLIDAY_TYPES,
            index=holiday_type_index,
            key="_ht_select",
            label_visibility="collapsed",
            on_change=_activate_holiday,
        )

    # ── Attribute ───────────────────────────────────────────
    with sort_col:
        sort_tab_active    = filter_mode == "sort"
        sort_label_color = "#218208" if sort_tab_active else "#94A3B8"
        st.markdown(
            f'<p class="filter-section-label" style="color:{sort_label_color};">'
            'Attribute</p>',
            unsafe_allow_html=True,
        )
        sort_option_names = list(SORT_OPTIONS.keys())
        sort_option_index  = (
            sort_option_names.index(st.session_state.sort_attr)
            if st.session_state.sort_attr in sort_option_names else 0
        )
        st.selectbox(
            "Attribute",
            sort_option_names,
            index=sort_option_index,
            key="_sort_select",
            label_visibility="collapsed",
            on_change=_activate_sort,
        )

    # ── Destination ─────────────────────────────────────────
    with destination_col:
        destination_tab_active    = filter_mode == "destination"
        destination_label_color = "#218208" if destination_tab_active else "#94A3B8"
        st.markdown(
            f'<p class="filter-section-label" style="color:{destination_label_color};">'
            'Destination</p>',
            unsafe_allow_html=True,
        )
        country_options = ["All countries"] + sorted(
            summary_df["country"].unique().tolist()
        )
        selected_country = st.selectbox(
            "Country",
            country_options,
            key="_dest_country",
            on_change=_on_dest_country_change,
        )
        available_cities = (
            sorted(summary_df["city_name"].unique().tolist())
            if selected_country == "All countries"
            else sorted(
                summary_df.loc[
                    summary_df["country"] == selected_country, "city_name"
                ].unique().tolist()
            )
        )
        st.multiselect(
            "Cities (leave blank for all)",
            available_cities,
            key="_dest_cities",
            on_change=_on_dest_city_change,
        )


# ─── Filtering & ranking ──────────────────────────────────────────────────────
filter_mode          = st.session_state.filter_mode
selected_type = st.session_state.holiday_type
meta          = HOLIDAY_META[selected_type]
score_col     = meta["score_col"]
flag_col      = meta["flag_col"]

# Destination mode: filter by country / cities
if filter_mode == "destination":
    selected_country   = st.session_state.get("_dest_country", "All countries")
    selected_cities = st.session_state.get("_dest_cities", [])
    filtered_destinations = summary_df.copy()
    if selected_country != "All countries":
        filtered_destinations = filtered_destinations[filtered_destinations["country"] == selected_country].copy()
    if selected_cities:
        filtered_destinations = filtered_destinations[filtered_destinations["city_name"].isin(selected_cities)].copy()
else:
    filtered_destinations = summary_df.copy()

if filtered_destinations.empty:
    st.warning("No destinations match your filters. Try widening the selection.")
    st.stop()

filtered_daily = daily_df[daily_df["city_name"].isin(filtered_destinations["city_name"])].copy()


# ─── Results strip ────────────────────────────────────────────────────────────
if filter_mode == "holiday":
    results_heading = selected_type
elif filter_mode == "sort":
    results_heading = f"Sorted by {st.session_state.sort_attr}"
else:
    selected_country = st.session_state.get("_dest_country", "All countries")
    results_heading = f"Destination — {selected_country}" if selected_country != "All countries" else "Destination"

st.markdown(
    f'<p class="results-title">{results_heading} &nbsp;·&nbsp; '
    f'{len(filtered_destinations)} destinations</p>',
    unsafe_allow_html=True,
)

# Badge legend
st.markdown(
    '<div class="badge-legend">'
    '<span><span class="bl-dot" style="background:#218208;"></span>Top match = highest score</span>'
    '<span><span class="bl-dot" style="background:#218208;"></span>Recommended = meets threshold</span>'
    '<span><span class="bl-dot" style="background:#6B8794;"></span>Not ideal = below threshold</span>'
    '</div>',
    unsafe_allow_html=True,
)


# ─── Sort & rank ─────────────────────────────────────────────────────────────
if filter_mode == "sort":
    sort_column, sort_ascending = SORT_OPTIONS[st.session_state.sort_attr]
else:
    sort_column, sort_ascending = score_col, False  # highest score first

ranked = (
    filtered_destinations
    .sort_values(sort_column, ascending=sort_ascending)
    .reset_index(drop=True)
)
ranked["rank"] = ranked.index + 1

top = ranked.iloc[0]
top_score = float(top[score_col])
top_city_zone  = CITY_CLIMATE_ZONE.get(top["city_name"], "")


# ─── Score colour helper ──────────────────────────────────────────────────────
def score_color(score: float) -> str:
    if score >= 75:
        return "#218208"
    if score >= 40:
        return "#FFC83D"
    return "#6B8794"


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ─── Featured best-match card ────────────────────────────────────────────────
st.markdown('<div style="margin-top:20px;margin-bottom:4px;">', unsafe_allow_html=True)

featured_left, featured_right = st.columns([5, 3], gap="medium")
with featured_left:
    city_image = CITY_IMAGES.get(top["city_name"].lower(), "")
    if city_image:
        image_html = (
            f'<img src="data:image/jpeg;base64,{city_image}" alt="{top["city_name"]}" '
            f'style="width:100%;height:100%;object-fit:cover;object-position:center;display:block;">'
        )
    else:
        zone = top.get("climate_zone", "Mediterranean")
        grad = ZONE_GRADIENTS.get(zone, "linear-gradient(135deg,#218208,#0E3A4D)")
        image_html = f'<div style="width:100%;height:100%;background:{grad};"></div>'

    st.markdown(f"""
<div class="featured-card">
  <div class="featured-photo" style="min-height:260px;">
    {image_html}
    <div class="featured-photo-scrim"></div>
  </div>
  <div class="featured-info">
    <p class="featured-eyebrow">✦ BEST MATCH FOR {selected_type.upper()}</p>
    <p class="featured-city">{top["city_name"]}</p>
    <p class="featured-zone">{top_city_zone} · {top["country"]}</p>
    <span class="badge badge-top">🏆 Top match</span>
    <div style="margin-top:16px;">
      <div class="chip">☀️ {top['avg_temp_c']:.1f}°C avg temp</div>&nbsp;
      <div class="chip">🌧️ {top['avg_daily_precipitation_mm']:.1f} mm/day rain</div>&nbsp;
      <div class="chip">💨 {top['avg_wind_speed_kmh']:.1f} km/h wind</div>&nbsp;
      <div class="chip">🌫️ AQI {top['avg_aqi']:.0f}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

with featured_right:
    gauge_color = score_color(top_score)
    active_components    = SCORE_COMPONENTS.get(selected_type, [])
    top_city_row  = top.to_dict()

    # Map each component to (actual-value-fn, "what makes a good score")
    component_descriptions = {
        "Temperature":  (lambda r: f"avg {r['avg_temp_c']:.1f}°C",
                         "ideal: ≥15°C, best at 35°C+"),
        "Mild Temp":    (lambda r: f"avg {r['avg_temp_c']:.1f}°C",
                         "ideal: 15°C, score falls ±20°C away"),
        "Low Rain":     (lambda r: f"{r['heavy_rain_days']:.0f} heavy-rain days",
                         "0 heavy-rain days = max score"),
        "Clean Air":    (lambda r: f"AQI {r['avg_aqi']:.0f}",
                         "AQI 0 = best, 150+ = zero pts"),
        "Air Quality":  (lambda r: f"AQI {r['avg_aqi']:.0f}",
                         "AQI 0 = best, 100+ = zero pts"),
        "Comfort Days": (lambda r: f"{r['comfortable_day_pct']:.1f}% of days",
                         "mild temp + low rain + calm wind"),
        "Avg Wind":     (lambda r: f"avg {r['avg_wind_speed_kmh']:.1f} km/h",
                         "40+ km/h = max pts (sports ideal)"),
        "Peak Wind":    (lambda r: f"max {r['max_wind_speed_kmh']:.1f} km/h",
                         "80+ km/h = max pts"),
        "Low Wind":     (lambda r: f"avg {r['avg_wind_speed_kmh']:.1f} km/h",
                         "below 40–60 km/h = better score"),
    }

    # Build hover tooltip — one block per score component
    hover_text = (
        f"<b>{selected_type} — {top['city_name']}: "
        f"{top_score:.1f} / 100</b><br><br>"
    )
    for component_name, score_fn, max_points in active_components:
        points_earned  = round(min(max(score_fn(top_city_row), 0), max_points), 1)
        percent_earned  = round(points_earned / max_points * 100)
        description_fn, component_desc = component_descriptions.get(component_name, (lambda r: "", ""))
        actual_value = description_fn(top_city_row)
        hover_text += (
            f"<b>{component_name}</b>  →  "
            f"{points_earned:.1f} / {max_points} pts  ({percent_earned}%)<br>"
            f"<i>{actual_value}  ·  {component_desc}</i><br><br>"
        )
    hover_text += (
        f"<br><b>Recommended if:</b> {meta['thresholds']}<br>"
        f"<i>{meta['score_desc']}</i>"
    )
    hover_text += "<extra></extra>"

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=top_score,
        number={"suffix": " / 100",
                "font": {"size": 28, "color": "#0E3A4D", "family": "Poppins"}},
        title={"text": f"<b>{selected_type}</b><br>Weather Score",
               "font": {"size": 13, "color": "#6B8794", "family": "Inter"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#E2E8F0",
                     "tickfont": {"size": 10}},
            "bar": {"color": gauge_color, "thickness": 0.28},
            "bgcolor": "#F7FAFC",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 40],  "color": "#FEE2E2"},
                {"range": [40, 75], "color": "#FEF3C7"},
                {"range": [75, 100], "color": "#CCFBF1"},
            ],
            "threshold": {
                "line": {"color": gauge_color, "width": 3},
                "thickness": 0.8,
                "value": top_score,
            },
        },
    ))

    # Invisible full-area scatter — triggers rich hover anywhere over the gauge
    fig_gauge.add_trace(go.Scatter(
        x=[0.5], y=[0.35],
        mode="markers",
        marker=dict(size=280, opacity=0, color="rgba(0,0,0,0)"),
        hovertemplate=hover_text,
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#218208",
            font=dict(size=11, family="Inter", color="#0E3A4D"),
            align="left",
        ),
        showlegend=False,
        xaxis="x",
        yaxis="y",
    ))
    fig_gauge.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=10, r=10, t=50, b=10),
        height=340,
        xaxis=dict(visible=False, range=[0, 1], fixedrange=True,
                   zeroline=False, showgrid=False),
        yaxis=dict(visible=False, range=[0, 1], fixedrange=True,
                   zeroline=False, showgrid=False),
    )
    st.markdown(
        '<div style="background:#FFFFFF;border-radius:14px;'
        'box-shadow:0 2px 12px rgba(14,58,77,.08);">',
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig_gauge, use_container_width=True)
    st.caption("ℹ️ Hover over the gauge to see the score breakdown.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)


# ─── Top 3 cards + radar (inline) ──────────────────────────────────────────────────────────────────────────────
top_3_cities = ranked.head(3)

cards_col, radar_col = st.columns([5, 3], gap="medium")

with cards_col:
    st.markdown(
        f'<p class="section-heading" style="margin-top:0;">'
        f'Showing top 3 of {len(ranked)} for {selected_type}</p>',
        unsafe_allow_html=True,
    )
    grid_cols = st.columns(min(len(top_3_cities), 3), gap="small")
    for col, (_, r) in zip(grid_cols, top_3_cities.iterrows()):
        with col:
            city_name  = r["city_name"]
            city_score  = float(r[score_col])
            meets_threshold  = bool(r[flag_col])
            is_best_match   = r["rank"] == 1

            if is_best_match:
                badge_html = '<span class="badge badge-top">🏆 Top match</span>'
            elif meets_threshold:
                badge_html = '<span class="badge badge-good">✓ Recommended</span>'
            else:
                badge_html = '<span class="badge badge-low">Not ideal</span>'

            fill_color = score_color(city_score)
            score_bar_pct   = f"{city_score:.0f}%"

            city_image = CITY_IMAGES.get(city_name.lower(), "")
            if city_image:
                card_image_html = (
                    f'<div class="card-photo" style="height:190px;">'
                    f'<img src="data:image/jpeg;base64,{city_image}" alt="{city_name}">'
                    f'<div class="card-photo-scrim"></div>'
                    f'<div class="card-overlay">'
                    f'<p class="card-city-name">{city_name}</p>'
                    f'<p class="card-zone">'
                    f'{r.get("climate_zone", "")} · {r["country"]}'
                    f'</p>'
                    f'{badge_html}'
                    f'</div></div>'
                )
            else:
                zone = r.get("climate_zone", "Mediterranean")
                grad = ZONE_GRADIENTS.get(
                    zone, "linear-gradient(135deg,#218208,#0E3A4D)"
                )
                card_image_html = (
                    f'<div class="card-photo" style="height:190px;'
                    f'background:{grad};">'
                    f'<div class="card-photo-scrim"></div>'
                    f'<div class="card-overlay">'
                    f'<p class="card-city-name">{city_name}</p>'
                    f'<p class="card-zone">'
                    f'{r.get("climate_zone", "")} · {r["country"]}'
                    f'</p>'
                    f'{badge_html}'
                    f'</div></div>'
                )

            aqi_display = f"{r['avg_aqi']:.0f}" if pd.notna(r["avg_aqi"]) else "—"
            st.markdown(f"""
<div class="dest-card">
  {card_image_html}
  <div class="score-section">
<div class="score-label-row">
  <span class="score-label">Score</span>
  <span class="score-value">{city_score:.0f} / 100</span>
</div>
<div class="score-track">
  <div class="score-fill" style="width:{score_bar_pct};background:{fill_color};"></div>
</div>
  </div>
  <div class="metric-chips">
<span class="chip" title="Actual mean temperature">☀️ {r['avg_temp_c']:.1f}°C</span>
<span class="chip" title="Average daily rainfall">🌧️ {r['avg_daily_precipitation_mm']:.1f} mm</span>
<span class="chip" title="Average wind speed">💨 {r['avg_wind_speed_kmh']:.1f} km/h</span>
<span class="chip" title="Average European AQI">🌫️ AQI {aqi_display}</span>
  </div>
</div>
""", unsafe_allow_html=True)

with radar_col:
    st.markdown(
        '<p class="section-heading" style="margin-top:0;">'
        'City profiles — all holiday types</p>',
        unsafe_allow_html=True,
    )
    radar_city_names = ranked["city_name"].head(3).tolist()
    radar_data     = filtered_destinations[filtered_destinations["city_name"].isin(radar_city_names)].copy()

    radar_labels = [c[0] for c in RADAR_CATS]
    radar_score_cols   = [c[1] for c in RADAR_CATS]

    fig_radar = go.Figure()
    for city_index, city_name in enumerate(radar_city_names):
        city_row = radar_data[radar_data["city_name"] == city_name]
        if city_row.empty:
            continue
        city_row = city_row.iloc[0]
        radar_scores = [float(city_row[col_name]) for col_name in radar_score_cols]
        closed_scores = radar_scores + [radar_scores[0]]
        closed_labels = radar_labels + [radar_labels[0]]
        city_color  = CITY_PALETTE[city_index % len(CITY_PALETTE)]
        fill_color = hex_to_rgba(city_color, 0.12)
        fig_radar.add_trace(go.Scatterpolar(
            r=closed_scores,
            theta=closed_labels,
            fill="toself",
            fillcolor=fill_color,
            line=dict(color=city_color, width=2),
            name=city_name,
            hovertemplate="%{theta}: %{r:.1f}/100<extra>" + city_name + "</extra>",
        ))

    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[25, 50, 75, 100],
                tickfont=dict(size=8, family="Inter", color="#6B8794"),
                gridcolor="#E2E8F0",
                linecolor="#E2E8F0",
            ),
            angularaxis=dict(
                tickfont=dict(size=12, family="Inter", color="#0E3A4D"),
                gridcolor="#E2E8F0",
                linecolor="#E2E8F0",
            ),
            bgcolor="#FFFFFF",
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.14,
            xanchor="center", x=0.5,
            font=dict(size=10, family="Inter"),
        ),
        height=300,
        margin=dict(l=20, r=20, t=5, b=48),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
    )
    st.plotly_chart(fig_radar, use_container_width=True)



# ─── Daily weather section ────────────────────────────────────────────────────
st.markdown('<p class="section-heading">Daily weather trends</p>', unsafe_allow_html=True)

chart_cities = ranked["city_name"].head(3).tolist()
chart_data = filtered_daily[filtered_daily["city_name"].isin(chart_cities)].copy()

legend_style = dict(orientation="h", yanchor="bottom", y=1.02,
                  xanchor="right", x=1, font=dict(size=11, family="Inter"))
chart_layout = dict(margin=dict(l=0, r=0, t=10, b=0), height=340,
                     plot_bgcolor="#FFFFFF", legend=legend_style)

temp_col, precip_col = st.columns(2, gap="medium")

with temp_col:
    st.markdown(
        '<p class="chart-title">'
        'Temperature range (°C) — min / mean / max'
        '</p>',
        unsafe_allow_html=True,
    )
    if not chart_data.empty:
        fig_temp = go.Figure()
        for city_index, city_name in enumerate(chart_cities):
            daily_data    = chart_data[chart_data["city_name"] == city_name].sort_values("date")
            city_color = CITY_PALETTE[city_index % len(CITY_PALETTE)]
            fill_color  = hex_to_rgba(city_color, 0.15)
            fig_temp.add_trace(go.Scatter(
                x=daily_data["date"], y=daily_data["temperature_2m_max"],
                mode="lines", line=dict(width=0),
                showlegend=False, name=f"{city_name} max",
            ))
            fig_temp.add_trace(go.Scatter(
                x=daily_data["date"], y=daily_data["temperature_2m_min"],
                mode="lines", line=dict(width=0),
                fill="tonexty", fillcolor=fill_color,
                showlegend=False, name=f"{city_name} min",
            ))
            fig_temp.add_trace(go.Scatter(
                x=daily_data["date"], y=daily_data["temperature_2m_mean"],
                mode="lines", line=dict(color=city_color, width=2),
                name=city_name,
            ))
        fig_temp.update_layout(
            **chart_layout,
            template="plotly_white",
            yaxis_title="Temp (°C)",
            xaxis_title="",
        )
        st.plotly_chart(fig_temp, use_container_width=True)

with precip_col:
    st.markdown(
        '<p class="chart-title">'
        'Daily precipitation (mm)'
        '</p>',
        unsafe_allow_html=True,
    )
    if not chart_data.empty:
        fig_precip = px.bar(
            chart_data,
            x="date",
            y="precipitation_sum",
            color="city_name",
            barmode="overlay",
            opacity=0.65,
            color_discrete_sequence=CITY_PALETTE,
            labels={"date": "", "precipitation_sum": "Precipitation (mm)", "city_name": "City"},
            template="plotly_white",
        )
        fig_precip.update_layout(**chart_layout)
        st.plotly_chart(fig_precip, use_container_width=True)

wind_col, snow_col = st.columns(2, gap="medium")

with wind_col:
    st.markdown(
        '<p class="chart-title">'
        'Max wind speed (km/h)'
        '</p>',
        unsafe_allow_html=True,
    )
    if not chart_data.empty:
        fig_wind = px.line(
            chart_data,
            x="date",
            y="wind_speed_10m_max",
            color="city_name",
            color_discrete_sequence=CITY_PALETTE,
            labels={"date": "", "wind_speed_10m_max": "Max Wind (km/h)", "city_name": "City"},
            template="plotly_white",
        )
        fig_wind.update_traces(line_width=2)
        fig_wind.update_layout(**chart_layout)
        st.plotly_chart(fig_wind, use_container_width=True)

with snow_col:
    st.markdown(
        '<p class="chart-title">'
        'Daily snowfall (cm)'
        '</p>',
        unsafe_allow_html=True,
    )
    if not chart_data.empty:
        fig_snow = px.bar(
            chart_data,
            x="date",
            y="snowfall_sum",
            color="city_name",
            barmode="overlay",
            opacity=0.65,
            color_discrete_sequence=CITY_PALETTE,
            labels={"date": "", "snowfall_sum": "Snowfall (cm)", "city_name": "City"},
            template="plotly_white",
        )
        fig_snow.update_layout(**chart_layout)
        st.plotly_chart(fig_snow, use_container_width=True)

# All-scores comparison chart
st.markdown(
    '<p style="font-family:Inter;font-weight:600;color:#0E3A4D;margin:20px 0 8px 0;">'
    'All holiday-type scores compared'
    '</p>',
    unsafe_allow_html=True,
)
all_scores = filtered_destinations.melt(
    id_vars=["city_name"],
    value_vars=SCORE_COLS,
    var_name="activity",
    value_name="score",
)
all_scores["activity"] = all_scores["activity"].map(SCORE_LABELS)
all_scores["label"] = all_scores["city_name"].apply(
    lambda c: c + " (" + filtered_destinations.loc[filtered_destinations["city_name"] == c, "country"].values[0][:3] + ")"
)
fig_all = px.bar(
    all_scores,
    x="label",
    y="score",
    color="activity",
    barmode="group",
    color_discrete_sequence=TYPE_PALETTE,
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
st.markdown(
    f'<div class="footer">'
    f'<span>Source: Open-Meteo · Built with dbt + DuckDB · '
    f'Model: <code>marts.mart_destination_weather_summary</code></span>'
    f'<span>Data as of {data_date} · '
    f'<a href="assets/cities/ATTRIBUTIONS.md">Image attributions</a></span>'
    f'</div>',
    unsafe_allow_html=True,
)
