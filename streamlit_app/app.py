import duckdb
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Weather Holiday Recommender",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] > .main {
    background-color: #F7F9FC;
}
[data-testid="stSidebar"] {
    background-color: #1E2A3B;
}
[data-testid="stSidebar"] * {
    color: #E5EAF2 !important;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stMultiSelect label {
    color: #9BAEC8 !important;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.kpi-row {
    display: flex;
    gap: 16px;
    margin-bottom: 24px;
}
.kpi-card {
    flex: 1;
    background: #FFFFFF;
    border-radius: 10px;
    padding: 20px 24px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
    border-top: 3px solid #1A56DB;
}
.kpi-card.green  { border-top-color: #057A55; }
.kpi-card.amber  { border-top-color: #C27803; }
.kpi-card.purple { border-top-color: #6B21A8; }
.kpi-label {
    font-size: 11px;
    color: #6B7280;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 6px;
}
.kpi-value {
    font-size: 30px;
    font-weight: 700;
    color: #111827;
    line-height: 1.1;
}
.kpi-sub {
    font-size: 12px;
    color: #9CA3AF;
    margin-top: 4px;
}
.section-header {
    font-size: 15px;
    font-weight: 600;
    color: #374151;
    margin: 20px 0 10px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid #E5E7EB;
}
.recommend-box {
    background: #ECFDF5;
    border: 1px solid #A7F3D0;
    border-radius: 8px;
    padding: 14px 18px;
    color: #065F46;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 16px;
}
.warn-box {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-radius: 8px;
    padding: 14px 18px;
    color: #92400E;
    font-size: 14px;
    margin-bottom: 16px;
}
.page-header {
    padding: 10px 0 6px 0;
    margin-bottom: 4px;
}
.page-title {
    font-size: 26px;
    font-weight: 700;
    color: #111827;
    margin: 0;
}
.page-subtitle {
    font-size: 13px;
    color: #6B7280;
    margin-top: 4px;
}
.holiday-badge {
    display: inline-block;
    background: #EBF0FF;
    color: #1A56DB;
    font-size: 13px;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 20px;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

DB_PATH = "weather.duckdb"

CHART_TEMPLATE = "plotly_white"
COLOR_SEQ = px.colors.qualitative.Set2

HOLIDAY_TYPES = {
    "Beach & Sun": {
        "score_col": "beach_score",
        "flag_col": "is_beach_destination",
        "readme_profile": (
            "Apparent temp > 27°C · rain < 5 mm · wind < 30 km/h"
        ),
        "score_desc": (
            "**50 pts** — avg temp above 15°C (capped at 35°C)  \n"
            "**30 pts** — low heavy-rain day frequency  \n"
            "**20 pts** — avg wind speed below 60 km/h"
        ),
        "flag_rule": (
            "avg temp > 22°C **and** heavy-rain days < 15%"
        ),
        "accent": "#C27803",
    },
    "Nature & Hiking": {
        "score_col": "hiking_score",
        "flag_col": "is_hiking_destination",
        "readme_profile": (
            "Temp 10–22°C · rain < 15 mm · AQI < 30"
        ),
        "score_desc": (
            "**50 pts** — avg temp close to 15°C  \n"
            "**50 pts** — clean air: European AQI below 150"
        ),
        "flag_rule": "avg temp 8–18°C **and** avg AQI < 60",
        "accent": "#057A55",
    },
    "City Break": {
        "score_col": "city_break_score",
        "flag_col": "is_city_break_destination",
        "readme_profile": (
            "Temp 15–28°C · rain < 10 mm · AQI < 50"
        ),
        "score_desc": (
            "**50 pts** — % of comfortable days "
            "(18–25°C, rain < 5 mm, wind < 40 km/h)  \n"
            "**30 pts** — European AQI below 100  \n"
            "**20 pts** — low heavy-rain day frequency"
        ),
        "flag_rule": (
            "comfortable-day % > 40% **and** avg AQI < 75"
        ),
        "accent": "#1A56DB",
    },
    "Extreme Sports": {
        "score_col": "extreme_sports_score",
        "flag_col": "is_extreme_sports_destination",
        "readme_profile": (
            "Wind > 30 km/h · rain < 10 mm "
            "(kitesurfing · paragliding · surfing)"
        ),
        "score_desc": (
            "**60 pts** — average wind speed (max at 40 km/h)  \n"
            "**40 pts** — peak wind speed (max at 80 km/h)"
        ),
        "flag_rule": "avg wind speed > 30 km/h",
        "accent": "#C81E1E",
    },
}

SCORE_LABEL_MAP = {
    "beach_score": "Beach & Sun",
    "hiking_score": "Nature & Hiking",
    "city_break_score": "City Break",
    "extreme_sports_score": "Extreme Sports",
}

CITY_CLIMATE_ZONE = {
    "Tenerife": "Canary Islands",
    "Tarifa": "Mediterranean coast",
    "Barcelona": "Mediterranean",
    "Lisbon": "Atlantic coast",
    "Dubrovnik": "Adriatic coast",
    "Rhodes": "Eastern Mediterranean",
    "Nice": "French Riviera",
    "Chamonix": "Alpine",
    "Bergen": "Nordic fjords",
    "Reykjavik": "Subarctic",
    "Prague": "Continental",
    "Amsterdam": "Northern European",
}


@st.cache_resource
def get_connection():
    return duckdb.connect(DB_PATH, read_only=True)


@st.cache_data
def load_summary():
    return get_connection().execute(
        "select * from marts.mart_destination_weather_summary"
    ).df()


@st.cache_data
def load_daily():
    return get_connection().execute(
        "select * from marts.fct_city_weather_day"
        " order by city_name, date"
    ).df()


summary_df = load_summary()
daily_df = load_daily()

# ── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.markdown(
    "<div style='padding:24px 0 8px 0;'>"
    "<span style='font-size:20px;font-weight:700;"
    "color:#FFFFFF;letter-spacing:-0.3px;'>"
    "Holiday Recommender</span>"
    "<div style='font-size:12px;color:#9BAEC8;margin-top:4px;'>"
    "Weather-based destination guide"
    "</div></div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")

holiday_type = st.sidebar.selectbox(
    "Holiday type",
    options=list(HOLIDAY_TYPES.keys()),
)
ht = HOLIDAY_TYPES[holiday_type]

st.sidebar.markdown("&nbsp;")

all_countries = sorted(summary_df["country"].unique().tolist())
selected_countries = st.sidebar.multiselect(
    "Filter by country",
    options=all_countries,
    default=all_countries,
)
if not selected_countries:
    st.sidebar.warning("Select at least one country.")
    selected_countries = all_countries

filt_summary = summary_df[
    summary_df["country"].isin(selected_countries)
].copy()
filt_daily = daily_df[
    daily_df["city_name"].isin(filt_summary["city_name"].tolist())
].copy()

st.sidebar.markdown("---")
st.sidebar.markdown(
    "<div style='font-size:11px;color:#6B7280;padding:4px 0;'>"
    "Source: Open-Meteo API · Built with dbt + DuckDB"
    "</div>",
    unsafe_allow_html=True,
)

# ── Page header ──────────────────────────────────────────────────────────────
st.markdown(
    "<div class='page-header'>"
    "<div class='page-title'>Weather Holiday Recommender</div>"
    "<div class='page-subtitle'>"
    "Based on weather, which destination is best "
    "for your type of holiday?"
    "</div></div>",
    unsafe_allow_html=True,
)

score_col = ht["score_col"]
flag_col = ht["flag_col"]

ranked = (
    filt_summary[[
        "city_name", "country", score_col, flag_col,
        "avg_temp_c", "comfortable_day_pct", "heavy_rain_days",
        "avg_wind_speed_kmh", "avg_aqi", "total_days",
    ]]
    .sort_values(score_col, ascending=False)
    .reset_index(drop=True)
)
ranked["rank"] = ranked.index + 1
ranked["climate_zone"] = ranked["city_name"].map(CITY_CLIMATE_ZONE)

top = ranked.iloc[0]
n_countries = len(selected_countries)
n_cities = len(ranked)
recommended = ranked[ranked[flag_col]]["city_name"].tolist()
top_zone = CITY_CLIMATE_ZONE.get(top["city_name"], "")
top_score_str = f"{top[score_col]:.0f}"
top_temp_str = f"{top['avg_temp_c']:.1f}"
rec_text = ", ".join(recommended) if recommended else "—"

# ── KPI row ──────────────────────────────────────────────────────────────────
st.markdown(
    f"""
<div class='kpi-row'>
  <div class='kpi-card'>
    <div class='kpi-label'>Selected scope</div>
    <div class='kpi-value'>{n_countries} countries</div>
    <div class='kpi-sub'>{n_cities} destinations</div>
  </div>
  <div class='kpi-card green'>
    <div class='kpi-label'>Top destination — {holiday_type}</div>
    <div class='kpi-value'>{top["city_name"]}</div>
    <div class='kpi-sub'>{top["country"]} · {top_zone}</div>
  </div>
  <div class='kpi-card amber'>
    <div class='kpi-label'>Best score</div>
    <div class='kpi-value'>{top_score_str} / 100</div>
    <div class='kpi-sub'>Avg temp {top_temp_str} °C</div>
  </div>
  <div class='kpi-card purple'>
    <div class='kpi-label'>Recommended cities</div>
    <div class='kpi-value'>{len(recommended)}</div>
    <div class='kpi-sub'>{rec_text}</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "Destination Ranking",
    "Daily Weather",
    "Metric Definitions",
])

# ── Tab 1: Destination Ranking ───────────────────────────────────────────────
with tab1:
    st.markdown(
        f"<div class='holiday-badge'>{holiday_type} — "
        f"{ht['readme_profile']}</div>",
        unsafe_allow_html=True,
    )

    col_chart, col_table = st.columns([3, 2], gap="large")

    with col_chart:
        st.markdown(
            "<div class='section-header'>Score ranking</div>",
            unsafe_allow_html=True,
        )
        fig_rank = px.bar(
            ranked.sort_values(score_col),
            x=score_col,
            y="city_name",
            orientation="h",
            color=score_col,
            color_continuous_scale=[
                [0, "#FEE2E2"], [0.5, "#FEF3C7"], [1, "#D1FAE5"]
            ],
            range_color=[0, 100],
            text=score_col,
            labels={
                "city_name": "",
                score_col: f"{holiday_type} Score",
            },
            template=CHART_TEMPLATE,
        )
        fig_rank.update_traces(
            texttemplate="%{text:.0f}",
            textposition="outside",
            marker_line_width=0,
        )
        fig_rank.update_layout(
            xaxis=dict(range=[0, 108], showgrid=False, title=""),
            yaxis=dict(tickfont=dict(size=13)),
            showlegend=False,
            coloraxis_showscale=False,
            margin=dict(l=0, r=40, t=10, b=10),
            height=380,
            plot_bgcolor="white",
        )
        st.plotly_chart(fig_rank, use_container_width=True)

    with col_table:
        st.markdown(
            "<div class='section-header'>Key metrics</div>",
            unsafe_allow_html=True,
        )
        col_map = {
            "rank": "#",
            "city_name": "City",
            "country": "Country",
            score_col: "Score",
            flag_col: "Recommended",
            "avg_temp_c": "Avg °C",
            "comfortable_day_pct": "Comfortable %",
            "heavy_rain_days": "Rain Days",
            "avg_aqi": "AQI",
        }
        st.dataframe(
            ranked[list(col_map.keys())].rename(columns=col_map),
            hide_index=True,
            use_container_width=True,
            height=370,
        )

    st.markdown(
        "<div class='section-header'>All activity scores compared</div>",
        unsafe_allow_html=True,
    )
    all_scores = filt_summary.melt(
        id_vars=["city_name"],
        value_vars=list(SCORE_LABEL_MAP.keys()),
        var_name="activity",
        value_name="score",
    )
    all_scores["activity"] = all_scores["activity"].map(SCORE_LABEL_MAP)
    all_scores["city_name"] = all_scores["city_name"].apply(
        lambda c: c + " (" + (
            filt_summary.loc[
                filt_summary["city_name"] == c, "country"
            ].values[0][:2]
        ) + ")"
    )
    fig_all = px.bar(
        all_scores,
        x="city_name",
        y="score",
        color="activity",
        barmode="group",
        color_discrete_sequence=COLOR_SEQ,
        labels={
            "city_name": "",
            "score": "Score (0–100)",
            "activity": "Holiday Type",
        },
        template=CHART_TEMPLATE,
    )
    fig_all.update_layout(
        xaxis_tickangle=-25,
        yaxis_range=[0, 100],
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=0, r=0, t=40, b=10),
        height=340,
    )
    st.plotly_chart(fig_all, use_container_width=True)


# ── Tab 2: Daily Weather ─────────────────────────────────────────────────────
with tab2:
    n_rows = len(filt_daily)
    n_cits = filt_daily["city_name"].nunique()
    st.caption(
        f"`marts.fct_city_weather_day` — one row per city per day "
        f"· {n_rows:,} rows · {n_cits} cities"
    )

    col_left, col_right = st.columns(2, gap="medium")

    with col_left:
        st.markdown(
            "<div class='section-header'>Daily mean temperature (°C)</div>",
            unsafe_allow_html=True,
        )
        fig_temp = px.line(
            filt_daily,
            x="date",
            y="temperature_2m_mean",
            color="city_name",
            color_discrete_sequence=COLOR_SEQ,
            labels={
                "date": "",
                "temperature_2m_mean": "Mean Temp (°C)",
                "city_name": "City",
            },
            template=CHART_TEMPLATE,
        )
        fig_temp.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=11),
            ),
        )
        st.plotly_chart(fig_temp, use_container_width=True)

    with col_right:
        st.markdown(
            "<div class='section-header'>Daily precipitation (mm)</div>",
            unsafe_allow_html=True,
        )
        fig_precip = px.bar(
            filt_daily,
            x="date",
            y="precipitation_sum",
            color="city_name",
            barmode="overlay",
            opacity=0.65,
            color_discrete_sequence=COLOR_SEQ,
            labels={
                "date": "",
                "precipitation_sum": "Precipitation (mm)",
                "city_name": "City",
            },
            template=CHART_TEMPLATE,
        )
        fig_precip.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=11),
            ),
        )
        st.plotly_chart(fig_precip, use_container_width=True)

    st.markdown(
        "<div class='section-header'>Weather flag frequency</div>",
        unsafe_allow_html=True,
    )
    flag_cols_list = [
        "is_comfortable_day", "is_extreme_heat",
        "is_heavy_rain", "is_windy", "is_snow_day",
    ]
    flag_label_map = {
        "is_comfortable_day": "Comfortable Days",
        "is_extreme_heat": "Extreme Heat Days",
        "is_heavy_rain": "Heavy Rain Days",
        "is_windy": "Windy Days",
        "is_snow_day": "Snow Days",
    }
    flag_agg = (
        filt_daily.groupby("city_name")[flag_cols_list]
        .sum()
        .reset_index()
        .rename(columns=flag_label_map)
    )
    flag_melted = flag_agg.melt(
        id_vars=["city_name"], var_name="Flag", value_name="Days"
    )
    fig_flags = px.bar(
        flag_melted,
        x="city_name",
        y="Days",
        color="Flag",
        barmode="group",
        color_discrete_sequence=COLOR_SEQ,
        labels={"city_name": "", "Days": "Days"},
        template=CHART_TEMPLATE,
    )
    fig_flags.update_layout(
        xaxis_tickangle=-20,
        margin=dict(l=0, r=0, t=10, b=0),
        height=310,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11),
        ),
    )
    st.plotly_chart(fig_flags, use_container_width=True)

    st.markdown(
        "<div class='section-header'>Day-by-day detail</div>",
        unsafe_allow_html=True,
    )
    detail_df = (
        filt_daily[[
            "date", "city_name",
            "temperature_2m_max", "temperature_2m_min",
            "temperature_2m_mean", "precipitation_sum",
            "wind_speed_10m_max",
            "is_comfortable_day", "is_extreme_heat", "is_heavy_rain",
        ]]
        .rename(columns={
            "date": "Date",
            "city_name": "City",
            "temperature_2m_max": "Max Temp (°C)",
            "temperature_2m_min": "Min Temp (°C)",
            "temperature_2m_mean": "Mean Temp (°C)",
            "precipitation_sum": "Precip (mm)",
            "wind_speed_10m_max": "Max Wind (km/h)",
            "is_comfortable_day": "Comfortable",
            "is_extreme_heat": "Extreme Heat",
            "is_heavy_rain": "Heavy Rain",
        })
        .sort_values(["City", "Date"])
        .reset_index(drop=True)
    )
    st.dataframe(
        detail_df, hide_index=True, use_container_width=True, height=320
    )


# ── Tab 3: Metric Definitions ────────────────────────────────────────────────
with tab3:
    st.markdown(
        "<div class='section-header'>Holiday type profiles</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "Ideal weather conditions for each holiday type, "
        "as defined in the project specification."
    )
    st.table([
        {
            "Holiday Type": k,
            "Ideal Weather Conditions": v["readme_profile"],
            "Recommended when": v["flag_rule"],
        }
        for k, v in HOLIDAY_TYPES.items()
    ])

    st.markdown(
        "<div class='section-header'>"
        "Daily flags — `marts.fct_city_weather_day` "
        "(one row per city per day)"
        "</div>",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info(
            "**Comfortable Day**  \n"
            "Mean temp **18–25°C**, "
            "precipitation **< 5 mm**, "
            "max wind **< 40 km/h**."
        )
        st.error("**Extreme Heat**  \nMax temp exceeds **35°C**.")
    with c2:
        st.warning(
            "**Heavy Rain**  \n"
            "Daily precipitation exceeds **20 mm**."
        )
        st.info("**Windy Day**  \nMax wind exceeds **50 km/h**.")
    with c3:
        st.info(
            "**Snow Day**  \nAny snowfall recorded (> 0 cm)."
        )

    st.markdown(
        "<div class='section-header'>"
        "Activity scores — `marts.mart_destination_weather_summary` "
        "(one row per city)"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "Scores range **0–100**. "
        "Higher = better weather conditions for that activity."
    )
    for name, meta in HOLIDAY_TYPES.items():
        with st.expander(name):
            st.markdown(meta["score_desc"])

    st.markdown(
        "<div class='section-header'>"
        "European Air Quality Index (AQI)"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "Standardised index combining PM₁₀, PM₂.₅, NO₂, O₃, and SO₂. "
        "Lower = cleaner air.\n\n"
        "| AQI | Category |\n"
        "|-----|----------|\n"
        "| 0–20 | Good |\n"
        "| 20–40 | Fair |\n"
        "| 40–60 | Moderate |\n"
        "| 60–80 | Poor |\n"
        "| 80–100 | Very Poor |\n"
        "| > 100 | Extremely Poor |"
    )
