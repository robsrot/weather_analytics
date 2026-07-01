# Weather Holiday Recommender

An end-to-end analytics engineering project built with dbt, DuckDB, and Streamlit using weather data from the [Open-Meteo API](https://open-meteo.com).

**Business question**: *Based on weather, which European destination is best for your type of holiday?*

## Dashboard

> [Streamlit App](https://robsrot-weather-analytics-streamlit-appapp-ew6ilb.streamlit.app/)

---

## Project Concept

The dashboard scores 12 European cities across 6 holiday types using 30 days of real weather data. Users can filter by holiday type, sort by a specific weather attribute (warmest, driest, calmest, etc.), or browse by country/city. Only one filter is active at a time.

### Holiday Types & Scoring

Each holiday type produces a **score (0–100)** and a **binary recommendation flag**. The score is a weighted formula; the flag is a stricter pass/fail gate.

| Type | Key scoring factors | Flag condition |
|---|---|---|
| Beach & Sun | Temp (50 pts), low rain (30 pts), low wind (20 pts) | avg temp > 22°C AND < 15% rainy days |
| Nature & Hiking | Mild temp ~15°C (50 pts), clean air AQI (50 pts) | temp 8–18°C AND AQI < 60 |
| City Break | Comfortable days % (50 pts), AQI (30 pts), low rain (20 pts) | > 40% comfortable days AND AQI < 75 |
| Extreme Sports | Avg wind (60 pts), peak wind (40 pts) | avg wind > 30 km/h |
| Cultural & Sightseeing | Mild temp ~20°C (40 pts), dry (25 pts), AQI (20 pts), calm (15 pts) | temp 14–26°C AND rain < 8 mm AND AQI < 50 AND wind < 30 km/h |
| Wellness & Slow Travel | Precise temp ~21.5°C (35 pts), dry (25 pts), pristine air (25 pts), calm (15 pts) | temp 17–26°C AND rain < 8 mm AND AQI < 35 AND wind < 25 km/h |

### Destinations

12 cities across 4 climate zones, chosen to produce maximally different metric profiles:

| City | Country | Climate Zone | Primary Types |
|---|---|---|---|
| Tenerife | Spain | Canary Islands | Beach, Wellness |
| Tarifa | Spain | Mediterranean coast | Extreme Sports, Beach |
| Barcelona | Spain | Mediterranean | Beach, City Break |
| Lisbon | Portugal | Atlantic coast | City Break, Cultural, Wellness |
| Dubrovnik | Croatia | Adriatic coast | Beach, Cultural |
| Rhodes | Greece | Eastern Mediterranean | Beach, Cultural |
| Nice | France | French Riviera | Beach, City Break |
| Chamonix | France | Alpine | Nature, Extreme Sports |
| Bergen | Norway | Nordic fjords | Nature, Wellness |
| Reykjavik | Iceland | Subarctic | Extreme Sports, Nature |
| Prague | Czech Republic | Continental | City Break, Cultural |
| Amsterdam | Netherlands | Northern European | City Break |

---

## Project Structure

```
.
├── data/
│   └── raw/
│       └── open_meteo/          # CSV files written by extract_open_meteo.py (gitignored)
├── scripts/
│   └── extract_open_meteo.py    # Pulls data from the Open-Meteo API
├── models/
│   ├── sources.yml              # Raw source definitions with column descriptions
│   ├── staging/                 # stg_* models — one per raw source
│   ├── intermediate/            # int_* models — joins, aggregations, flags
│   └── marts/                   # dim_* and fct_* and mart_* models
├── streamlit_app/
│   ├── app.py                   # Holiday recommender dashboard
│   └── assets/
│       └── cities/              # City photos (committed) + ATTRIBUTIONS.md
├── macros/
│   └── generate_schema_name.sql # Routes each layer into its own DuckDB schema
├── dbt_project.yml
├── profiles.yml
├── packages.yml
├── pyproject.toml
├── requirements.txt             # For Streamlit Community Cloud deployment
├── weather.duckdb               # Pre-built database (committed for deployment)
└── load_db.py                   # Loads CSVs into DuckDB
```

---

## Setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager (replaces pip + venv)
- Python 3.10–3.12 — uv installs the right version automatically
- Git

### 1. Clone the repository

```bash
git clone https://github.com/robsrot/weather_analytics.git
cd weather_analytics
```

### 2. Install Python dependencies

```bash
uv sync
```

This creates a `.venv` and installs everything from `pyproject.toml` (dbt, DuckDB, Streamlit, Pandas, Plotly).

> **No uv?** Use pip instead:
> ```bash
> pip install -r requirements.txt
> pip install dbt-core dbt-duckdb
> ```

### 3. Install dbt packages

```bash
uv run dbt deps --profiles-dir .
```

This installs `dbt_utils` and `dbt_expectations` into `dbt_packages/`.

### 4. Verify the dbt connection

```bash
uv run dbt debug --profiles-dir .
```

You should see `All checks passed!` at the end. If not, check that you are running the command from inside the `weather_analytics/` folder.

### 5. Launch the dashboard (using committed database)

```bash
uv run streamlit run streamlit_app/app.py
```

`weather.duckdb` is committed to the repo — no extraction or dbt build needed just to view the dashboard. The data covers the period it was last extracted.

### Refresh the data (optional)

To pull fresh weather data and rebuild the database:

```bash
uv run python scripts/extract_open_meteo.py   # call API → write 4 CSV files
uv run python load_db.py                       # load CSVs → weather.duckdb raw tables
uv run dbt build --profiles-dir .             # run + test all models
```

---

## Models

| Layer | Model | Grain | Description |
|---|---|---|---|
| Staging | `stg_locations` | city | Renamed and cast location metadata |
| Staging | `stg_weather_daily` | city × day | Historical weather actuals |
| Staging | `stg_forecast_daily` | city × forecast date × run | Daily forecast snapshots (one per extraction run) |
| Staging | `stg_air_quality_hourly` | city × hour | Hourly AQI and pollutant readings |
| Intermediate | `int_city_day_weather` | city × day | Weather joined with location metadata |
| Intermediate | `int_air_quality_daily` | city × day | Hourly AQI aggregated to daily averages |
| Intermediate | `int_weather_flags` | city × day | Boolean flags: `is_comfortable_day`, `is_extreme_heat`, `is_heavy_rain`, `is_windy`, `is_snow_day` |
| Marts | `dim_location` | city | Location dimension (coordinates, country, timezone) |
| Marts | `fct_city_weather_day` | city × day | Daily weather fact with surrogate key and condition flags |
| Marts | `fct_air_quality_city_day` | city × day | Daily air quality fact |
| Marts | `mart_destination_weather_summary` | city | One row per city: summary stats, 6 scores, 6 recommendation flags |

The dashboard reads from the mart layer only.

---

## Data Notes

**`sunshine_duration` is in seconds**
The API returns seconds per day, not hours. Divide by 3600 for hours.

**`raw_air_quality_hourly` mixes historical and modelled rows**
The extraction pulls `past_days` of history plus a forward forecast window in the same API call. Future dates have modelled AQI values, not sensor readings.

**Re-running the extraction overwrites the CSVs**
`extract_open_meteo.py` always writes fresh files — it does not append. Each run is a new snapshot. `raw_forecast_daily` includes `extracted_at` to track multiple forecast runs.

**`raw_weather_daily` and `raw_forecast_daily` share the same columns**
Both tables have identical column structures. They are kept as separate sources and separate staging models deliberately.

**Actual temperature, not apparent temperature**
Scoring uses `temperature_2m_mean` (actual measured temperature at 2m height), not `apparent_temperature_mean`. The "feels like" columns are extracted but not used in downstream transformations.

**`location_id` is the join key**
All four raw tables carry `location_id` from the Geocoding API. Use this — not `city_name` — as the foreign key when joining to `dim_location`.
