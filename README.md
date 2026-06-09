# Weather Analytics

An end-to-end analytics engineering project built with dbt, DuckDB, and Streamlit using data from the [Open-Meteo API](https://open-meteo.com).

## Dashboard

> Add your Streamlit Community Cloud link here after deployment.

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
│   ├── sources.yml              # Raw source definitions
│   ├── staging/                 # stg_* models — one per raw source
│   ├── intermediate/            # int_* models — joins, aggregations, flags
│   └── marts/                   # dim_* and fct_* and mart_* models
├── streamlit_app/
│   └── app.py                   # Dashboard
├── macros/
│   └── generate_schema_name.sql # Keeps staging/intermediate/marts in separate schemas
├── dbt_project.yml
├── profiles.yml
├── packages.yml
├── pyproject.toml
├── requirements.txt             # For Streamlit Community Cloud deployment
└── load_db.py                   # Loads CSVs into DuckDB
```

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

Or with pip:

```bash
pip install -r requirements.txt
pip install dbt-core dbt-duckdb
```

### 2. Install dbt packages

```bash
dbt deps
```

### 3. Extract data from the API

Default cities are Madrid, Barcelona, Valencia, Sevilla, Bilbao. You can change them:

```bash
uv run python scripts/extract_open_meteo.py
# or with custom cities:
uv run python scripts/extract_open_meteo.py --cities Madrid Barcelona Paris Berlin Lisbon --past-days 60
```

Output files written to `data/raw/open_meteo/`:
- `raw_locations.csv`
- `raw_weather_daily.csv`
- `raw_forecast_daily.csv`
- `raw_air_quality_hourly.csv`

### 4. Load data into DuckDB

```bash
uv run python load_db.py
```

This creates `weather.duckdb` with the four raw tables in the `main` schema.

### 5. Run dbt

```bash
dbt debug        # verify connection
dbt build        # run all models + tests
```

### 6. Launch the dashboard

```bash
streamlit run streamlit_app/app.py
```

---

## Models

| Layer | Model | Grain | Description |
|---|---|---|---|
| Staging | `stg_locations` | city | Renamed and cast location metadata |
| Staging | `stg_weather_daily` | city × day | Recent daily weather actuals |
| Staging | `stg_forecast_daily` | city × forecast date × run | Daily forecast snapshots |
| Staging | `stg_air_quality_hourly` | city × hour | Hourly AQI and pollutants |
| Intermediate | `int_city_day_weather` | city × day | Weather joined with location metadata |
| Intermediate | `int_air_quality_daily` | city × day | Hourly AQI aggregated to daily |
| Intermediate | `int_weather_flags` | city × day | Boolean condition flags (heat, rain, wind) |
| Marts | `dim_location` | city | Location dimension |
| Marts | `fct_city_weather_day` | city × day | Weather fact with condition flags |
| Marts | `fct_air_quality_city_day` | city × day | Daily air quality fact |
| Marts | `mart_city_weather_summary` | city | Summary metrics over the full period |

The dashboard reads from the mart layer only.

---

## Modeling Decisions

> Fill this in as a team before submission. Examples:
> - Why we chose DuckDB over another warehouse
> - How we handled the hourly → daily aggregation for air quality
> - How comfortable day was defined
> - Any deviations from the suggested structure
