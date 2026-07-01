# Weather Holiday Recommender

An end-to-end analytics engineering project built with dbt, DuckDB, and Streamlit using weather data from the [Open-Meteo API](https://open-meteo.com).

**Business question**: *Based on weather, which destination is best for your type of holiday?*

## Dashboard

> Add your Streamlit Community Cloud link here after deployment.

---

## Project Concept

The dashboard lets a user select a **holiday type** and optionally filter by country or city to see which destinations had the best weather conditions for that style of travel.

### Holiday Types

| Type | Weather Profile |
|---|---|
| Beach & Sun | Apparent temp > 27°C, rain < 5 mm, wind < 30 km/h |
| Nature & Hiking | Temp 10–22°C, rain < 15 mm, AQI < 30 |
| City Break | Temp 15–28°C, rain < 10 mm, AQI < 50 |
| Cultural & Sightseeing | Temp 15–25°C, rain < 8 mm, AQI < 40, wind < 25 km/h |
| Wellness & Slow Travel | Temp 18–25°C, rain < 8 mm, AQI < 25, wind < 20 km/h |
| Extreme Sports | Wind > 30 km/h, rain < 10 mm (wind is the feature) |

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
│   └── app.py                   # Holiday recommender dashboard
├── macros/
│   └── generate_schema_name.sql # Routes each layer into its own DuckDB schema
├── dbt_project.yml
├── profiles.yml
├── packages.yml
├── pyproject.toml
├── requirements.txt             # For Streamlit Community Cloud deployment
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

### 5. Extract data from the API

```bash
uv run python scripts/extract_open_meteo.py
```

This pulls 30 days of weather history + 7-day forecast + historical air quality for all 12 destinations and writes four CSV files to `data/raw/open_meteo/`:

- `raw_locations.csv` — 12 rows, one per city
- `raw_weather_daily.csv` — ~372 rows, one per city per day
- `raw_forecast_daily.csv` — ~84 rows, one per city per forecast day
- `raw_air_quality_hourly.csv` — ~10,080 rows, one per city per hour

### 6. Load data into DuckDB

```bash
uv run python load_db.py
```

This creates `weather.duckdb` in the project root with all four raw tables in the `main` schema.

### 7. Build all dbt models

```bash
uv run dbt build --profiles-dir .
```

This runs and tests every model in DAG order (staging → intermediate → marts).

### 8. Launch the dashboard

```bash
uv run streamlit run streamlit_app/app.py
```

> **Note**: `weather.duckdb` and the raw CSV files are gitignored. Every teammate must run steps 5 and 6 locally to generate them.

---

## Models

| Layer | Model | Grain | Description |
|---|---|---|---|
| Staging | `stg_locations` | city | Renamed and cast location metadata |
| Staging | `stg_weather_daily` | city × day | Weather actuals with apparent temp and sunshine hours |
| Staging | `stg_forecast_daily` | city × forecast date × run | Daily forecast snapshots |
| Staging | `stg_air_quality_hourly` | city × hour | Hourly AQI and pollutants |
| Intermediate | `int_city_day_weather` | city × day | Weather joined with location metadata |
| Intermediate | `int_air_quality_daily` | city × day | Hourly AQI aggregated to daily |
| Intermediate | `int_weather_flags` | city × day | Boolean flags per holiday type (is_good_beach_day, is_good_nature_day, etc.) |
| Marts | `dim_location` | city | Location dimension with holiday type tags |
| Marts | `fct_city_weather_day` | city × day | Weather fact with per-holiday-type condition flags |
| Marts | `fct_air_quality_city_day` | city × day | Daily air quality fact |
| Marts | `mart_city_weather_summary` | city | % of good days per holiday type over the full period |

The dashboard reads from the mart layer only.

---

## Data Notes for Model Builders

Things you will hit when writing staging and intermediate models — read before you start.

**`sunshine_duration` is in seconds**
The API returns seconds per day, not hours. Convert in staging:
```sql
sunshine_duration / 3600.0 as sunshine_hours
```

**`raw_air_quality_hourly` mixes historical and forecast rows**
The extraction pulls `past_days` of history plus a forward forecast window in the same API call. Both land in the same table with no flag distinguishing them. When aggregating to daily in `int_air_quality_daily`, be aware that future dates have modelled AQI values, not sensor readings.

**Re-running the extraction overwrites the CSVs**
`extract_open_meteo.py` always writes fresh files — it does not append. Each run is a new snapshot. `raw_forecast_daily` includes `extracted_at` precisely to track multiple runs if you run the script on different days.

**`raw_weather_daily` and `raw_forecast_daily` share the same columns**
Both tables have identical column structures (same weather variables, same grain). The `source_name` column distinguishes them (`recent_weather` vs `forecast`). They are kept as separate sources deliberately — staging models should be separate too.

**Apparent temperature vs actual temperature**
Use `apparent_temperature_mean` (feels-like) rather than `temperature_2m_mean` for comfort-based holiday flags. It accounts for wind chill and humidity, which matters when comparing Reykjavik (cold + wind) against Tenerife (warm + calm).

**`location_id` is the join key**
All four raw tables carry `location_id` from the Geocoding API. Use this — not `city_name` — as the foreign key when joining to `dim_location`.
