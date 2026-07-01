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
# Compare-cities multiselect can exceed 3 cities, so extend beyond CITY_PALETTE.
CITY_COMPARE_PALETTE = CITY_PALETTE + TYPE_PALETTE

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


@st.cache_data(show_spinner=False)
def load_locations() -> pd.DataFrame:
    """Lat/lon per city, from the existing dim_location mart (no model changes)."""
    return _get_con().execute(
        "select location_id, latitude, longitude from marts.dim_location"
    ).df()


@st.cache_data(show_spinner=False)
def load_forecast() -> pd.DataFrame:
    """Latest forecast snapshot per city/date, from the existing staging view
    (stg_forecast_daily isn't promoted to a mart yet, so we dedupe here instead
    of touching the dbt layer)."""
    return _get_con().execute("""
        select location_id, city_name, country_code, date,
               temperature_2m_max, temperature_2m_min, temperature_2m_mean,
               precipitation_sum, rain_sum, snowfall_sum,
               wind_speed_10m_max, extracted_at
        from staging.stg_forecast_daily
        qualify row_number() over (
            partition by location_id, date order by extracted_at desc
        ) = 1
        order by city_name, date
    """).df()


# ─── Pure helpers (no Streamlit calls — safe to define before page renders) ──

def aqi_label(aqi: float) -> str:
    """European AQI qualitative label: 0–20 Good · 20–40 Fair · 40–60 Moderate · 60–80 Poor · 80+ Very Poor."""
    if aqi < 20:  return "Good"
    if aqi < 40:  return "Fair"
    if aqi < 60:  return "Moderate"
    if aqi < 80:  return "Poor"
    return "Very Poor"


# ─── Load data (with graceful error) ─────────────────────────────────────────
try:
    summary_df    = load_summary()
    daily_df      = load_daily()
    locations_df  = load_locations()
    forecast_df   = load_forecast()
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

/* On image overlays the semi-transparent tinted badges are hard to read —
   switch to solid fill with white text so they always pop over photos. */
.card-overlay .badge-top  { background: #218208; color: #FFFFFF; border-color: transparent; }
.card-overlay .badge-good { background: rgba(33,130,8,.80); color: #FFFFFF; border-color: transparent; }
.card-overlay .badge-low  { background: rgba(14,58,77,.60);  color: #FFFFFF; border-color: transparent; }

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
    min-height: 280px;
    height: auto;
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

/* ── Bordered containers — override st.container(border=True) styling ─── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #E2E8F0 !important;
    border-radius: 14px !important;
    box-shadow: 0 2px 12px rgba(14,58,77,.08) !important;
    background: #FFFFFF !important;
    padding: 24px 28px 20px 28px !important;
    margin-bottom: 28px !important;
}

/* ── Filter bar — lighter, single-row variant of the bordered card ────── */
[data-testid="stVerticalBlockBorderWrapper"].st-key-filter_bar,
.st-key-filter_bar [data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 10px !important;
    box-shadow: 0 1px 6px rgba(14,58,77,.05) !important;
    padding: 14px 22px !important;
    margin-bottom: 24px !important;
}
.st-key-filter_bar .filter-section-label {
    margin-bottom: 4px;
    padding-bottom: 3px;
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

/* ── 7-day forecast strip ─────────────────────────────────────────────── */
.forecast-strip {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}
.forecast-card {
    flex: 1;
    min-width: 96px;
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    box-shadow: 0 2px 10px rgba(14,58,77,.06);
    padding: 14px 8px 12px 8px;
    text-align: center;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.forecast-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(14,58,77,.12);
}
.forecast-card.is-today {
    border: 1.5px solid #218208;
    background: rgba(33,130,8,.04);
}
.forecast-day {
    font-family: 'Poppins', sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #0E3A4D;
    margin-bottom: 1px;
}
.forecast-date {
    font-family: 'Inter', sans-serif;
    font-size: 0.68rem;
    color: #94A3B8;
    margin-bottom: 8px;
}
.forecast-icon {
    font-size: 1.9rem;
    line-height: 1.2;
    margin-bottom: 4px;
}
.forecast-cond {
    font-family: 'Inter', sans-serif;
    font-size: 0.68rem;
    color: #6B8794;
    margin-bottom: 8px;
}
.forecast-temp {
    font-family: 'Poppins', sans-serif;
    font-size: 0.92rem;
    font-weight: 700;
    color: #0E3A4D;
}
.forecast-temp .lo {
    color: #94A3B8;
    font-weight: 500;
}
.forecast-rain {
    font-family: 'Inter', sans-serif;
    font-size: 0.66rem;
    color: #4FC3D9;
    margin-top: 4px;
}

/* ── KPI stat row ──────────────────────────────────────────────────────── */
.kpi-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin: 16px 0 24px 0;
}
.kpi-card {
    flex: 1;
    min-width: 140px;
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    box-shadow: 0 2px 10px rgba(14,58,77,.06);
    padding: 14px 18px;
}
.kpi-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6B8794;
    margin-bottom: 4px;
}
.kpi-value {
    font-family: 'Poppins', sans-serif;
    font-size: 1.3rem;
    font-weight: 700;
    color: #0E3A4D;
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
    ("filter_mode",  None),
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
    st.session_state["_sort_select"] = None
    st.session_state["_dest_country"] = []
    st.session_state["_dest_cities"] = []


def _activate_sort():
    st.session_state.filter_mode = "sort"
    st.session_state.sort_attr = st.session_state["_sort_select"]
    st.session_state["_ht_select"] = None
    st.session_state["_dest_country"] = []
    st.session_state["_dest_cities"] = []


def _on_dest_country_change():
    st.session_state.filter_mode = "destination"
    st.session_state["_ht_select"] = None
    st.session_state["_sort_select"] = None
    st.session_state["_dest_cities"] = []


def _on_dest_city_change():
    st.session_state.filter_mode = "destination"
    st.session_state["_ht_select"] = None
    st.session_state["_sort_select"] = None


# ─── Filter bar (single row, 4 equal controls) ───────────────────────────────
with st.container(border=True, key="filter_bar"):
    filter_mode = st.session_state.filter_mode
    holiday_tab_active      = filter_mode == "holiday"
    sort_tab_active         = filter_mode == "sort"
    destination_tab_active  = filter_mode == "destination"

    def _label_color(active: bool) -> str:
        return "#218208" if active else "#94A3B8"

    holiday_col, sort_col, country_col, cities_col = st.columns(
        [1.6, 1.6, 1.9, 1.9], gap="medium"
    )

    # ── Holiday type ─────────────────────────────────────────
    with holiday_col:
        st.markdown(
            f'<p class="filter-section-label" style="color:{_label_color(holiday_tab_active)};">'
            'Holiday type</p>',
            unsafe_allow_html=True,
        )
        holiday_type_index = (
            HOLIDAY_TYPES.index(st.session_state.holiday_type)
            if filter_mode == "holiday"
            and st.session_state.holiday_type in HOLIDAY_TYPES
            else None
        )
        st.selectbox(
            "Holiday type",
            HOLIDAY_TYPES,
            index=holiday_type_index,
            placeholder="Select holiday type",
            key="_ht_select",
            label_visibility="collapsed",
            on_change=_activate_holiday,
        )

    # ── Attribute ───────────────────────────────────────────
    with sort_col:
        st.markdown(
            f'<p class="filter-section-label" style="color:{_label_color(sort_tab_active)};">'
            'Attribute</p>',
            unsafe_allow_html=True,
        )
        sort_option_names = list(SORT_OPTIONS.keys())
        sort_option_index = (
            sort_option_names.index(st.session_state.sort_attr)
            if filter_mode == "sort"
            and st.session_state.sort_attr in sort_option_names
            else None
        )
        st.selectbox(
            "Attribute",
            sort_option_names,
            index=sort_option_index,
            placeholder="Select attribute",
            key="_sort_select",
            label_visibility="collapsed",
            on_change=_activate_sort,
        )

    # ── Country ──────────────────────────────────────────────
    with country_col:
        st.markdown(
            f'<p class="filter-section-label" style="color:{_label_color(destination_tab_active)};">'
            'Country</p>',
            unsafe_allow_html=True,
        )
        country_options = sorted(summary_df["country"].unique().tolist())
        selected_countries = st.multiselect(
            "Country (leave blank for all)",
            country_options,
            key="_dest_country",
            label_visibility="collapsed",
            placeholder="All countries",
            on_change=_on_dest_country_change,
        )

    # ── Cities ───────────────────────────────────────────────
    with cities_col:
        st.markdown(
            f'<p class="filter-section-label" style="color:{_label_color(destination_tab_active)};">'
            'Cities</p>',
            unsafe_allow_html=True,
        )
        available_cities = (
            sorted(summary_df["city_name"].unique().tolist())
            if not selected_countries
            else sorted(
                summary_df.loc[
                    summary_df["country"].isin(selected_countries), "city_name"
                ].unique().tolist()
            )
        )
        st.multiselect(
            "Cities (leave blank for all)",
            available_cities,
            key="_dest_cities",
            label_visibility="collapsed",
            placeholder="All cities",
            on_change=_on_dest_city_change,
        )

st.caption(
    "💡 Country and Cities support multiple selections — pick more than one "
    "to compare destinations side by side."
)


# ─── Filtering & ranking ──────────────────────────────────────────────────────
filter_mode          = st.session_state.filter_mode
selected_type = st.session_state.holiday_type
meta          = HOLIDAY_META[selected_type]
score_col     = meta["score_col"]
flag_col      = meta["flag_col"]

# Destination mode: filter by country / cities
if filter_mode == "destination":
    selected_countries = st.session_state.get("_dest_country", [])
    selected_cities = st.session_state.get("_dest_cities", [])
    filtered_destinations = summary_df.copy()
    if selected_countries:
        filtered_destinations = filtered_destinations[filtered_destinations["country"].isin(selected_countries)].copy()
    if selected_cities:
        filtered_destinations = filtered_destinations[filtered_destinations["city_name"].isin(selected_cities)].copy()
else:
    filtered_destinations = summary_df.copy()

if filtered_destinations.empty:
    st.warning("No destinations match your filters. Try widening the selection.")
    st.stop()

filtered_daily = daily_df[daily_df["city_name"].isin(filtered_destinations["city_name"])].copy()

# ─── Sort & rank config (needed by KPI row below) ────────────────────────────
if filter_mode == "sort":
    sort_column, sort_ascending = SORT_OPTIONS[st.session_state.sort_attr]
elif filter_mode == "holiday":
    sort_column, sort_ascending = score_col, False
else:
    sort_column, sort_ascending = "city_name", True  # alphabetical when no filter


# ─── Results strip ────────────────────────────────────────────────────────────
if filter_mode == "holiday":
    results_heading = selected_type
elif filter_mode == "sort":
    results_heading = f"Sorted by {st.session_state.sort_attr}"
elif filter_mode == "destination":
    selected_countries = st.session_state.get("_dest_country", [])
    results_heading = (
        f"Destination — {', '.join(selected_countries)}"
        if selected_countries else "Destination"
    )
else:
    results_heading = "All destinations"

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

# ─── KPI stat row (current filtered selection) ───────────────────────────────
kpi_avg_temp   = filtered_destinations["avg_temp_c"].mean()
kpi_avg_aqi    = filtered_destinations["avg_aqi"].mean()
kpi_days       = int(filtered_destinations["total_days"].max())
kpi_n_dest     = len(filtered_destinations)

if filter_mode == "holiday":
    kpi_best_score = filtered_destinations[score_col].max()
    kpi3_label = f"🏆 Best {selected_type} score"
    kpi3_value = f"{kpi_best_score:.0f} / 100"
elif filter_mode == "sort":
    sort_val = filtered_destinations[sort_column]
    best_val = sort_val.min() if sort_ascending else sort_val.max()
    kpi3_label = f"{'↓' if sort_ascending else '↑'} Best {st.session_state.sort_attr}"
    kpi3_value = f"{best_val:.1f}"
else:
    kpi3_label = "🗺️ Destinations"
    kpi3_value = str(kpi_n_dest)

st.markdown(f"""
<div class="kpi-row">
  <div class="kpi-card">
    <div class="kpi-label">☀️ Avg temp</div>
    <div class="kpi-value">{kpi_avg_temp:.1f}°C</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">🌫️ Avg AQI</div>
    <div class="kpi-value">{kpi_avg_aqi:.0f} <span style="font-size:0.75rem;font-weight:500;color:#6B8794;">({aqi_label(kpi_avg_aqi)})</span></div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">{kpi3_label}</div>
    <div class="kpi-value">{kpi3_value}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">📅 Days of data</div>
    <div class="kpi-value">{kpi_days}</div>
  </div>
</div>
""", unsafe_allow_html=True)


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


# ─── Forecast icon helper ──────────────────────────────────────────────────────
# stg_forecast_daily has no weather_code (sky condition) field, only precip /
# snow / wind / temp, so the icon is an estimate derived from those — not a
# true cloud-cover read. Flagged to the user in the UI caption.
def forecast_icon(row: pd.Series) -> tuple[str, str]:
    if row["snowfall_sum"] > 0:
        return "❄️", "Snow"
    if row["rain_sum"] >= 5 or row["precipitation_sum"] >= 5:
        return "🌧️", "Rain"
    if row["rain_sum"] > 0 or row["precipitation_sum"] > 0:
        return "🌦️", "Showers"
    if row["wind_speed_10m_max"] >= 45:
        return "🌬️", "Windy"
    return "☀️", "Clear"


# ─── Shared Plotly theme — keeps gridlines/fonts consistent with the rest ──
# of the page (gauge + radar already styled this way; trend/heatmap/map charts
# used to fall back to Plotly defaults, which is what made them look bolted on).
CHART_FONT = dict(family="Inter", size=11, color="#0E3A4D")


def themed(fig: go.Figure, **layout_kwargs) -> go.Figure:
    fig.update_xaxes(gridcolor="#E2E8F0", linecolor="#E2E8F0", zerolinecolor="#E2E8F0",
                      tickfont=dict(family="Inter", size=10, color="#6B8794"))
    fig.update_yaxes(gridcolor="#E2E8F0", linecolor="#E2E8F0", zerolinecolor="#E2E8F0",
                      tickfont=dict(family="Inter", size=10, color="#6B8794"))
    fig.update_layout(font=CHART_FONT, paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                       **layout_kwargs)
    return fig


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
    <p class="featured-eyebrow">✦ {'TOP DESTINATION' if filter_mode == 'destination' else f'SORTED BY {st.session_state.sort_attr.upper()}' if filter_mode == 'sort' else f'BEST MATCH FOR {selected_type.upper()}'}</p>
    <p class="featured-city">{top["city_name"]}</p>
    <p class="featured-zone">{top_city_zone} · {top["country"]}</p>
    <span class="badge badge-top">🏆 Top match</span>
    <div style="margin-top:16px;">
      <div class="chip">☀️ {top['avg_temp_c']:.1f}°C avg temp</div>&nbsp;
      <div class="chip">🌧️ {top['avg_daily_precipitation_mm']:.1f} mm/day rain</div>&nbsp;
      <div class="chip">💨 {top['avg_wind_speed_kmh']:.1f} km/h wind</div>&nbsp;
      <div class="chip">🌫️ AQI {top['avg_aqi']:.0f} ({aqi_label(top['avg_aqi'])})</div>
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
    fig_gauge.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=10, r=10, t=50, b=10),
        height=340,

    )
    st.markdown(
        '<div style="background:#FFFFFF;border-radius:14px;'
        'box-shadow:0 2px 12px rgba(14,58,77,.08);">',
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

    # Plain-English verdict: identify the strongest and weakest components
    if active_components:
        _comp_scores = [
            (name, round(min(max(fn(top_city_row), 0), mx), 1), mx)
            for name, fn, mx in active_components
        ]
        _best  = max(_comp_scores, key=lambda x: x[1] / x[2])
        _worst = min(_comp_scores, key=lambda x: x[1] / x[2])
        _best_pct  = round(_best[1]  / _best[2]  * 100)
        _worst_pct = round(_worst[1] / _worst[2] * 100)
        st.markdown(
            f'<p style="font-family:Inter,sans-serif;font-size:0.8rem;'
            f'color:#6B8794;padding:0 4px 8px 4px;margin:0;">'
            f'<b style="color:#0E3A4D;">Strong:</b> {_best[0]} ({_best_pct}% of max pts)'
            f' &nbsp;·&nbsp; '
            f'<b style="color:#0E3A4D;">Held back by:</b> {_worst[0]} ({_worst_pct}% of max pts)'
            f'</p>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)


# ─── 7-day forecast strip (top match city) ───────────────────────────────────
top_forecast = (
    forecast_df[forecast_df["location_id"] == top["location_id"]]
    .sort_values("date")
    .head(7)
)

if not top_forecast.empty:
    forecast_extracted = top_forecast["extracted_at"].max()
    extracted_dt = pd.to_datetime(forecast_extracted)
    extracted_label = extracted_dt.strftime("%d %b %Y") if pd.notna(forecast_extracted) else "—"

    # Staleness: how many days since the forecast was pulled
    days_stale = (pd.Timestamp.now(tz=extracted_dt.tzinfo) - extracted_dt).days if pd.notna(forecast_extracted) else 0

    st.markdown(
        f'<p class="section-heading" style="margin-top:0;">'
        f'Forecast — {top["city_name"]} '
        f'<span style="font-size:0.75rem;font-weight:400;color:#6B8794;">'
        f'(as of {extracted_label})</span></p>',
        unsafe_allow_html=True,
    )

    if days_stale > 2:
        st.warning(
            f"⚠️ This forecast was pulled {days_stale} days ago ({extracted_label}). "
            "Re-run `uv run python scripts/extract_open_meteo.py` then `uv run dbt build` to refresh.",
            icon=None,
        )

    forecast_cards_html = []
    for _, frow in top_forecast.iterrows():
        icon, condition = forecast_icon(frow)
        # Always show the real date — never label a past date as "Today"
        day_label = frow["date"].strftime("%a")
        date_label = frow["date"].strftime("%d %b")
        today_class = " is-today" if frow["date"].date() == extracted_dt.date() else ""
        if today_class:
            day_label = "Extracted"
        rain_html = (
            f'<div class="forecast-rain">💧 {frow["precipitation_sum"]:.1f} mm</div>'
            if frow["precipitation_sum"] > 0 else ""
        )
        forecast_cards_html.append(f"""
<div class="forecast-card{today_class}">
  <div class="forecast-day">{day_label}</div>
  <div class="forecast-date">{date_label}</div>
  <div class="forecast-icon">{icon}</div>
  <div class="forecast-cond">{condition}</div>
  <div class="forecast-temp">{frow['temperature_2m_max']:.0f}°<span class="lo"> / {frow['temperature_2m_min']:.0f}°</span></div>
  {rain_html}
</div>""")
    st.markdown(
        f'<div class="forecast-strip">{"".join(forecast_cards_html)}</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "ℹ️ Icons estimated from forecasted rain/snow/wind (no sky-condition code available). "
        "Highlighted card = date of extraction."
    )


# ─── Top 3 cards + radar (inline) ──────────────────────────────────────────────────────────────────────────────
top_3_cities = ranked.head(3)

# "Compare cities" sync strategy
# ─────────────────────────────
# We only auto-reset when the pool of AVAILABLE cities actually changes
# (i.e. the user changed the top filter). Between resets the user can freely
# add/remove cities from compare — we never override their edits mid-session.
# Tracking _ranked_key_for_compare (the frozenset of cities at last reset) lets
# us detect "filter changed" without fighting the user's in-session edits.

_dest_cities_picked = (
    st.session_state.get("_dest_cities", [])
    if filter_mode == "destination"
    else []
)

# Default: mirror dest-selected cities exactly; else top-3 of ranked view
if _dest_cities_picked:
    default_compare = [c for c in _dest_cities_picked if c in ranked["city_name"].values]
else:
    default_compare = ranked["city_name"].head(3).tolist()

# Include ranking context so compare resets when holiday type or sort changes,
# not only when the pool of available cities changes.
_curr_ranked_key = (
    frozenset(ranked["city_name"]),
    filter_mode,
    selected_type,
    st.session_state.sort_attr,
)
_prev_ranked_key = st.session_state.get("_ranked_key_for_compare", None)
_current_compare = set(st.session_state.get("_compare_cities", []))
_ranked_city_set = frozenset(ranked["city_name"])

_need_reset = (
    "_compare_cities" not in st.session_state                   # first load
    or not _current_compare.issubset(_ranked_city_set)          # stale city
    or _prev_ranked_key != _curr_ranked_key                     # context changed
)
if _need_reset:
    st.session_state["_compare_cities"] = default_compare
    st.session_state["_ranked_key_for_compare"] = _curr_ranked_key

_cmp_col, _ = st.columns([3, 2])
with _cmp_col:
    compare_cities = st.multiselect(
        "Compare cities (radar + daily trends below)",
        ranked["city_name"].tolist(),
        key="_compare_cities",
    )
if not compare_cities:
    compare_cities = default_compare

cards_col, radar_col = st.columns([5, 3], gap="medium")

_SORT_COL_UNIT = {
    "avg_temp_c": "°C", "avg_daily_precipitation_mm": "mm/day",
    "avg_wind_speed_kmh": "km/h", "snow_days": " days", "avg_aqi": " AQI",
}
_RANK_MEDALS = {1: "🥇 #1", 2: "🥈 #2", 3: "🥉 #3"}

with cards_col:
    if filter_mode == "holiday":
        _top3_heading = f"Top 3 for {selected_type}"
    elif filter_mode == "sort":
        _top3_heading = f"Top 3 — {st.session_state.sort_attr}"
    elif filter_mode == "destination":
        _top3_heading = f"Showing {min(len(top_3_cities), 3)} of {len(ranked)}"
    else:
        _top3_heading = f"All {len(ranked)} destinations (select a filter to rank)"
    st.markdown(
        f'<p class="section-heading" style="margin-top:0;">{_top3_heading}</p>',
        unsafe_allow_html=True,
    )
    grid_cols = st.columns(min(len(top_3_cities), 3), gap="small")
    for col, (_, r) in zip(grid_cols, top_3_cities.iterrows()):
        with col:
            city_name = r["city_name"]
            is_best_match = r["rank"] == 1

            if filter_mode == "sort":
                sort_val = float(r[sort_column])
                sort_unit = _SORT_COL_UNIT.get(sort_column, "")
                card_score_label = st.session_state.sort_attr
                card_score_value = f"{sort_val:.1f}{sort_unit}"
                rank_pct = max(0, 100 - (r["rank"] - 1) / max(len(ranked) - 1, 1) * 100)
                fill_color = score_color(rank_pct)
                score_bar_pct = f"{rank_pct:.0f}%"
                _rank_int = int(r["rank"])
                _medal = _RANK_MEDALS.get(_rank_int, f"#{_rank_int}")
                badge_html = f'<span class="badge badge-top">{_medal}</span>'
            elif filter_mode == "holiday":
                city_score = float(r[score_col])
                meets_threshold = bool(r[flag_col])
                card_score_label = "Score"
                card_score_value = f"{city_score:.0f} / 100"
                fill_color = score_color(city_score)
                score_bar_pct = f"{city_score:.0f}%"
                if is_best_match:
                    badge_html = '<span class="badge badge-top">🏆 Top match</span>'
                elif meets_threshold:
                    badge_html = '<span class="badge badge-good">✓ Recommended</span>'
                else:
                    badge_html = '<span class="badge badge-low">Not ideal</span>'
            else:
                city_score = float(r[score_col])
                card_score_label = "Score"
                card_score_value = f"{city_score:.0f} / 100"
                fill_color = "#94A3B8"
                score_bar_pct = f"{city_score:.0f}%"
                badge_html = f'<span class="badge badge-low">#{int(r["rank"])}</span>'

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

            aqi_display = (
                f"{r['avg_aqi']:.0f} ({aqi_label(r['avg_aqi'])})"
                if pd.notna(r["avg_aqi"]) else "—"
            )
            st.markdown(f"""
<div class="dest-card">
  {card_image_html}
  <div class="score-section">
<div class="score-label-row">
  <span class="score-label">{card_score_label}</span>
  <span class="score-value">{card_score_value}</span>
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
    bar_city_names = compare_cities
    bar_data = filtered_destinations[
        filtered_destinations["city_name"].isin(bar_city_names)
    ].copy()

    bar_labels = [c[0] for c in RADAR_CATS]
    bar_score_cols = [c[1] for c in RADAR_CATS]

    fig_hbar = go.Figure()
    for city_index, city_name in enumerate(bar_city_names):
        city_row = bar_data[bar_data["city_name"] == city_name]
        if city_row.empty:
            continue
        city_row = city_row.iloc[0]
        scores = [float(city_row[col]) for col in bar_score_cols]
        city_color = CITY_COMPARE_PALETTE[city_index % len(CITY_COMPARE_PALETTE)]
        fig_hbar.add_trace(go.Bar(
            name=city_name,
            y=bar_labels,
            x=scores,
            orientation="h",
            marker_color=city_color,
            opacity=0.85,
            hovertemplate="%{y}: %{x:.1f}/100<extra>" + city_name + "</extra>",
        ))

    themed(
        fig_hbar,
        barmode="group",
        height=320,
        margin=dict(l=0, r=0, t=40, b=10),
        xaxis=dict(range=[0, 100], title="Score (0–100)"),
        yaxis=dict(autorange="reversed"),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left", x=0,
            font=dict(size=10, family="Inter"),
        ),
        showlegend=True,
    )
    st.plotly_chart(fig_hbar, use_container_width=True, config={"displayModeBar": False})


# ─── Map view ─────────────────────────────────────────────────────────────────
map_data = filtered_destinations.merge(locations_df, on="location_id", how="left")

if filter_mode == "sort":
    _map_color_col = sort_column
    _map_heading   = f"Map view — {st.session_state.sort_attr}"
    _map_scale     = (
        ["#218208", "#4FC3D9", "#D0EEF4"] if sort_ascending
        else ["#D0EEF4", "#4FC3D9", "#218208"]
    )
    _map_range     = [map_data[sort_column].min(), map_data[sort_column].max()]
    _map_cb_title  = sort_column.replace("_", " ")
    _map_hover     = {"country": True, "avg_temp_c": ":.1f", sort_column: ":.1f",
                      "latitude": False, "longitude": False}
    _map_labels    = {sort_column: st.session_state.sort_attr}
    _map_caption   = (
        f"ℹ️ Color = {sort_column.replace('_', ' ')} ({st.session_state.sort_attr}). "
        f"Bubble size = {selected_type} score."
    )
else:
    _map_color_col = score_col
    _map_heading   = f"Map view — {selected_type}"
    _map_scale     = ["#D0EEF4", "#4FC3D9", "#218208"]
    _map_range     = [0, 100]
    _map_cb_title  = f"{selected_type}<br>score"
    _map_hover     = {"country": True, "avg_temp_c": ":.1f", score_col: ":.1f",
                      "latitude": False, "longitude": False}
    _map_labels    = {score_col: f"{selected_type} score"}
    _map_caption   = f"ℹ️ Bubble size & color = {selected_type} score for the current filter."

st.markdown(
    f'<p class="section-heading">{_map_heading}</p>',
    unsafe_allow_html=True,
)

with st.container(border=True, key="map_card"):
    fig_map = px.scatter_map(
        map_data,
        lat="latitude",
        lon="longitude",
        color=_map_color_col,
        size=score_col,
        size_max=22,
        hover_name="city_name",
        text="city_name",
        hover_data=_map_hover,
        color_continuous_scale=_map_scale,
        range_color=_map_range,
        labels=_map_labels,
        map_style="open-street-map",
        zoom=3.2,
        center={"lat": 50, "lon": 8},
    )
    fig_map.update_traces(
        marker=dict(opacity=0.85),
        textposition="top center",
        mode="markers+text",
    )
    fig_map.update_layout(
        height=460,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#FFFFFF",
        font=CHART_FONT,
        coloraxis_colorbar=dict(title=_map_cb_title, thickness=12),
    )
    st.plotly_chart(fig_map, use_container_width=True, config={"scrollZoom": True})
    st.caption(_map_caption)


# ─── Conditions breakdown ─────────────────────────────────────────────────────
_compare_subtitle = " · ".join(compare_cities) if compare_cities else ""

conditions_data = filtered_destinations[
    filtered_destinations["city_name"].isin(compare_cities)
].copy()

if not conditions_data.empty:
    conditions_data = conditions_data.copy()

    scatter_col, cards_col = st.columns([3, 2], gap="large")

    with scatter_col:
        st.markdown(
            f'<p class="section-heading" style="margin-top:0;">Conditions breakdown'
            f'<span style="font-size:0.78rem;font-weight:400;color:#6B8794;margin-left:10px;">{_compare_subtitle}</span>'
            f'</p>',
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            # Scatter: x = avg temp, y = avg AQI, bubble size = comfortable day %,
            # color = avg daily precipitation. Immediately shows which cities are
            # warm/clean/dry (bottom-right, large bubble) vs cool/rainy/polluted.
            bubble_sizes = (conditions_data["comfortable_day_pct"] / 100 * 60 + 10).tolist()

            fig_cond = go.Figure()
            for idx, (_, r) in enumerate(conditions_data.iterrows()):
                city_color = CITY_COMPARE_PALETTE[idx % len(CITY_COMPARE_PALETTE)]
                fig_cond.add_trace(go.Scatter(
                    x=[r["avg_temp_c"]],
                    y=[r["avg_aqi"]],
                    mode="markers+text",
                    name=r["city_name"],
                    text=[r["city_name"]],
                    textposition="top center",
                    textfont=dict(size=11, family="Inter", color="#0E3A4D"),
                    marker=dict(
                        size=bubble_sizes[idx],
                        color=city_color,
                        opacity=0.82,
                        line=dict(width=2, color="#FFFFFF"),
                    ),
                    hovertemplate=(
                        f"<b>{r['city_name']}</b><br>"
                        f"Avg temp: {r['avg_temp_c']:.1f}°C<br>"
                        f"Avg AQI: {r['avg_aqi']:.0f} ({aqi_label(r['avg_aqi'])})<br>"
                        f"Comfortable days: {r['comfortable_day_pct']:.0f}%<br>"
                        f"Avg rain: {r['avg_daily_precipitation_mm']:.1f} mm/day"
                        "<extra></extra>"
                    ),
                ))

            themed(
                fig_cond,
                height=320,
                margin=dict(l=0, r=0, t=10, b=0),
                showlegend=False,
                xaxis=dict(title="Avg temperature (°C)"),
                yaxis=dict(title="Avg AQI ↑ cleaner air", autorange="reversed"),
            )
            st.plotly_chart(fig_cond, use_container_width=True)
            st.caption("Bubble size = % comfortable days · Bottom-right = warm & clean air")

    with cards_col:
        st.markdown(
            '<p class="section-heading" style="margin-top:0;">City weather profile</p>',
            unsafe_allow_html=True,
        )
        for _, r in conditions_data.iterrows():
            aqi_color = "#218208" if r["avg_aqi"] < 30 else "#FFC83D" if r["avg_aqi"] < 60 else "#FF6B5B"
            st.markdown(f"""
<div class="kpi-card" style="margin-bottom:10px;">
  <div style="font-family:'Poppins',sans-serif;font-size:0.85rem;font-weight:700;color:#0E3A4D;margin-bottom:8px;">{r['city_name']}</div>
  <div style="display:flex;gap:16px;flex-wrap:wrap;">
    <div><div class="kpi-label">Temp range</div><div style="font-family:'Poppins',sans-serif;font-size:0.9rem;font-weight:700;color:#0E3A4D;">{r['min_temp_c']:.0f}° – {r['max_temp_c']:.0f}°C</div></div>
    <div><div class="kpi-label">Comfortable</div><div style="font-family:'Poppins',sans-serif;font-size:0.9rem;font-weight:700;color:#218208;">{r['comfortable_day_pct']:.0f}%</div></div>
    <div><div class="kpi-label">Avg AQI</div><div style="font-family:'Poppins',sans-serif;font-size:0.9rem;font-weight:700;color:{aqi_color};">{r['avg_aqi']:.0f} <span style="font-size:0.72rem;font-weight:500;">({aqi_label(r['avg_aqi'])})</span></div></div>
    <div><div class="kpi-label">Avg rain</div><div style="font-family:'Poppins',sans-serif;font-size:0.9rem;font-weight:700;color:#0E3A4D;">{r['avg_daily_precipitation_mm']:.1f} mm</div></div>
  </div>
</div>
""", unsafe_allow_html=True)


# ─── Daily weather section ────────────────────────────────────────────────────
st.markdown(
    f'<p class="section-heading">Daily weather trends'
    f'<span style="font-size:0.78rem;font-weight:400;color:#6B8794;margin-left:10px;">{_compare_subtitle}</span>'
    f'</p>',
    unsafe_allow_html=True,
)

chart_cities = compare_cities
chart_data = filtered_daily[filtered_daily["city_name"].isin(chart_cities)].copy()

legend_style = dict(orientation="h", yanchor="bottom", y=1.02,
                  xanchor="right", x=1, font=dict(size=11, family="Inter"))
chart_layout = dict(margin=dict(l=0, r=0, t=10, b=0), height=380, legend=legend_style)

_has_snow = not chart_data.empty and chart_data["snowfall_sum"].sum() > 0
_tab_labels = ["🌡️ Temperature", "🌧️ Precipitation", "💨 Wind"]
if _has_snow:
    _tab_labels.append("❄️ Snow")
_tabs = st.tabs(_tab_labels)
temp_tab, precip_tab, wind_tab = _tabs[0], _tabs[1], _tabs[2]
snow_tab = _tabs[3] if _has_snow else None

with temp_tab:
    with st.container(border=True):
        st.markdown(
            '<p class="chart-title">Temperature range (°C) — min / mean / max</p>',
            unsafe_allow_html=True,
        )
        if not chart_data.empty:
            fig_temp = go.Figure()
            for city_index, city_name in enumerate(chart_cities):
                daily_data = chart_data[chart_data["city_name"] == city_name].sort_values("date")
                city_color = CITY_COMPARE_PALETTE[city_index % len(CITY_COMPARE_PALETTE)]
                fill_color = hex_to_rgba(city_color, 0.15)
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
            themed(fig_temp, **chart_layout, yaxis_title="Temp (°C)", xaxis_title="")
            st.plotly_chart(fig_temp, use_container_width=True)
        else:
            st.info("No data for the selected cities.")

with precip_tab:
    with st.container(border=True):
        st.markdown(
            '<p class="chart-title">Daily precipitation (mm)</p>',
            unsafe_allow_html=True,
        )
        if not chart_data.empty:
            fig_precip = px.bar(
                chart_data, x="date", y="precipitation_sum", color="city_name",
                barmode="overlay", opacity=0.65,
                color_discrete_sequence=CITY_COMPARE_PALETTE,
                labels={"date": "", "precipitation_sum": "Precipitation (mm)", "city_name": "City"},
            )
            themed(fig_precip, **chart_layout)
            st.plotly_chart(fig_precip, use_container_width=True)
        else:
            st.info("No data for the selected cities.")

with wind_tab:
    with st.container(border=True):
        st.markdown(
            '<p class="chart-title">Max wind speed (km/h)</p>',
            unsafe_allow_html=True,
        )
        if not chart_data.empty:
            fig_wind = px.line(
                chart_data, x="date", y="wind_speed_10m_max", color="city_name",
                color_discrete_sequence=CITY_COMPARE_PALETTE,
                labels={"date": "", "wind_speed_10m_max": "Max Wind (km/h)", "city_name": "City"},
            )
            fig_wind.update_traces(line_width=2)
            themed(fig_wind, **chart_layout)
            st.plotly_chart(fig_wind, use_container_width=True)
        else:
            st.info("No data for the selected cities.")

if snow_tab is not None:
    with snow_tab:
        with st.container(border=True):
            st.markdown(
                '<p class="chart-title">Daily snowfall (cm)</p>',
                unsafe_allow_html=True,
            )
            fig_snow = px.bar(
                chart_data, x="date", y="snowfall_sum", color="city_name",
                barmode="overlay", opacity=0.65,
                color_discrete_sequence=CITY_COMPARE_PALETTE,
                labels={"date": "", "snowfall_sum": "Snowfall (cm)", "city_name": "City"},
            )
            themed(fig_snow, **chart_layout)
            st.plotly_chart(fig_snow, use_container_width=True)

# All-scores heatmap
st.markdown(
    '<p class="section-heading">All holiday-type scores compared</p>',
    unsafe_allow_html=True,
)
with st.container(border=True):
    heat_source = filtered_destinations.set_index("city_name")[SCORE_COLS].rename(columns=SCORE_LABELS)
    heat_city_order = [c for c in ranked["city_name"] if c in heat_source.index]
    heat_source = heat_source.loc[heat_city_order]

    # Color by per-column rank (not raw score) so each holiday-type column
    # always has one clear dark-green winner, regardless of score clustering.
    n_cities_heat = len(heat_source)
    rank_df = heat_source.rank(ascending=False, method="first").astype(int)

    def _ordinal(n: int) -> str:
        return f"{n}{'st' if n==1 else 'nd' if n==2 else 'rd' if n==3 else 'th'}"

    # Build hover text: "Dubrovnik · City Break: 67 pts — 5th of 12"
    hover_text = [
        [
            f"<b>{heat_source.index[i]} · {col}</b><br>"
            f"Score: {heat_source.values[i, j]:.0f} / 100<br>"
            f"Ranking: {_ordinal(rank_df.values[i, j])} of {n_cities_heat}"
            for j, col in enumerate(heat_source.columns)
        ]
        for i in range(n_cities_heat)
    ]

    # Cell label: trophy for #1 in column, plain score otherwise
    cell_text = [
        [
            f"🏆{heat_source.values[i, j]:.0f}" if rank_df.values[i, j] == 1
            else f"{heat_source.values[i, j]:.0f}"
            for j in range(len(heat_source.columns))
        ]
        for i in range(n_cities_heat)
    ]

    # z = normalised rank 0→1 (0 = best = dark green, 1 = worst = light)
    norm_rank = (rank_df - 1) / max(n_cities_heat - 1, 1)

    fig_heat = go.Figure(data=go.Heatmap(
        z=norm_rank.values,
        x=heat_source.columns.tolist(),
        y=heat_source.index.tolist(),
        zmin=0, zmax=1,
        colorscale=[[0, "#218208"], [0.4, "#4FC3D9"], [1, "#F0F9FF"]],
        text=cell_text,
        texttemplate="%{text}",
        textfont=dict(size=11, family="Inter", color="#0E3A4D"),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_text,
        showscale=False,
        xgap=4, ygap=4,
    ))
    themed(
        fig_heat,
        height=max(320, 32 * len(heat_source) + 80),
        margin=dict(l=0, r=0, t=10, b=10),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig_heat, use_container_width=True)
    st.caption("ℹ️ Color shows rank within each holiday type — 🏆 = best city for that category. Hover for score + rank.")


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
