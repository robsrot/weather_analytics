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

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager (replaces pip + venv)
- Python 3.10–3.12 — uv installs the right version automatically
- Git

### 1. Clone the repository

```bash
git clone <repo-url>
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

This pulls data for Madrid, Barcelona, Valencia, Sevilla, and Bilbao and writes four CSV files to `data/raw/open_meteo/`:

- `raw_locations.csv`
- `raw_weather_daily.csv`
- `raw_forecast_daily.csv`
- `raw_air_quality_hourly.csv`

To use different cities or a longer history:

```bash
uv run python scripts/extract_open_meteo.py --cities Madrid Barcelona Paris Berlin Lisbon --past-days 60
```

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
