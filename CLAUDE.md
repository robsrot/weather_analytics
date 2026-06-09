# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

This is a **group assignment** for an Analytics Engineering with dbt course. The goal is to build
an end-to-end analytics engineering project using weather data from the Open-Meteo API, ending
in a Streamlit dashboard served from dbt mart models.

**Stack**: DuckDB · dbt Core · Streamlit · Python  
**Team size**: 5 people  
**Submission**: GitHub repository link

---

## Common Commands

> **Windows note**: `DBT_PROFILES_DIR` may be set to another project on this machine.
> Always add `--profiles-dir .` to every dbt command so dbt uses the `profiles.yml` in this folder.

```bash
# Environment setup
uv sync                                      # install Python deps from pyproject.toml
uv run dbt deps                              # install dbt packages (dbt_utils, dbt_expectations)

# Data extraction
uv run python scripts/extract_open_meteo.py                          # default 5 Spanish cities, 30 past days
uv run python scripts/extract_open_meteo.py \
  --cities Madrid Barcelona Paris Berlin Lisbon --past-days 60       # custom run

# Load into DuckDB
uv run python load_db.py                     # writes weather.duckdb from data/raw/open_meteo/*.csv

# dbt
uv run dbt debug --profiles-dir .                                    # verify DuckDB connection
uv run dbt run --profiles-dir .              # build all models
uv run dbt run -s staging --profiles-dir .  # build only staging layer
uv run dbt run -s +mart_city_weather_summary --profiles-dir .  # build a mart and all upstream deps
uv run dbt test --profiles-dir .            # run all tests
uv run dbt build --profiles-dir .           # run + test in DAG order (preferred)

# Dashboard
uv run streamlit run streamlit_app/app.py
```

---

## Architecture

**Four raw sources → Three modeling layers → One dashboard**

```
Open-Meteo API
  └── scripts/extract_open_meteo.py  →  data/raw/open_meteo/*.csv
  └── load_db.py                     →  weather.duckdb (main schema)

Sources (models/sources.yml)
  raw_locations · raw_weather_daily · raw_forecast_daily · raw_air_quality_hourly

Staging  (models/staging/)     → schema: staging
  stg_locations · stg_weather_daily · stg_forecast_daily · stg_air_quality_hourly

Intermediate  (models/intermediate/)   → schema: intermediate
  int_city_day_weather · int_air_quality_daily · int_weather_flags

Marts  (models/marts/)         → schema: marts
  dim_location · fct_city_weather_day · fct_air_quality_city_day · mart_city_weather_summary

Dashboard  (streamlit_app/app.py)  ← reads from marts schema only
```

Schema routing is handled by `macros/generate_schema_name.sql`, which writes each layer into its
own DuckDB schema instead of prefixing with the target schema name.

---

## Raw Sources

The four CSV files extracted by `extract_open_meteo.py` and the tables they map to:

| File | Table | Grain |
|---|---|---|
| `raw_locations.csv` | `main.raw_locations` | one row per city |
| `raw_weather_daily.csv` | `main.raw_weather_daily` | one row per city per day (actuals) |
| `raw_forecast_daily.csv` | `main.raw_forecast_daily` | one row per city per forecast date per extraction run |
| `raw_air_quality_hourly.csv` | `main.raw_air_quality_hourly` | one row per city per hour |

`raw_forecast_daily` includes an `extracted_at` timestamp on every row — this allows you to track
multiple forecast runs over time if the script is run on different days, which enables
forecast-vs-actual accuracy analysis.

---

## Required Models

### Staging (one model per raw source)

Staging models should:
- Rename fields to clear `snake_case` (e.g. `temperature_2m_max` → `temp_max_c`)
- Cast every column to the correct type (`date`, `double`, `integer`, `timestamp`)
- Deduplicate rows if the raw source has any
- Keep the **same grain** as the raw source
- Contain **no business logic** beyond light cleaning

### Intermediate (joins, aggregations, flags)

Examples the grader expects:
- `int_city_day_weather` — join weather actuals with location metadata
- `int_air_quality_daily` — aggregate hourly AQI observations to one row per city per day
- `int_weather_flags` — add boolean columns like `is_extreme_heat`, `is_heavy_rain`, `is_comfortable_day`

### Marts (facts, dimensions, summaries)

Required minimum:
- `dim_location` — one row per city, location dimension
- `fct_city_weather_day` — one row per city per day, weather fact with surrogate key

Recommended additions:
- `fct_air_quality_city_day` — one row per city per day, air quality fact
- `mart_city_weather_summary` — one row per city, summary metrics over the full period

Use `{{ dbt_utils.generate_surrogate_key([...]) }}` for fact table surrogate keys.

---

## dbt Tests Required

Every model needs at minimum:
- `unique` + `not_null` on all primary/surrogate keys
- `not_null` on date columns and city name
- `relationships` tests on all foreign keys pointing to `dim_location`

Recommended additions (use `dbt_expectations`):
- `expect_column_values_to_be_between` for temperature (`-50` to `60`) and AQI (`0` to `500`)
- `accepted_values` for `country_code` if you want to lock down the city list

---

## SQL Style Conventions

These are enforced by the course and should be applied consistently:

- **Lowercase** everything: keywords, identifiers, functions, string literals
- **CTEs** over subqueries — always name your intermediate steps
- Standard CTE pattern:
  ```sql
  with source as (
      select * from {{ source('raw', 'raw_locations') }}
  ),

  renamed as (
      select ...
      from source
  )

  select * from renamed
  ```
- **No trailing commas** — commas lead the line (`,  column_name`)
- Alias every column that is cast or computed
- Indent 4 spaces

---

## Naming Conventions

| Pattern | Layer | Example |
|---|---|---|
| `stg_[table]` | Staging | `stg_weather_daily` |
| `int_[description]` | Intermediate | `int_weather_flags` |
| `dim_[entity]` | Mart — dimension | `dim_location` |
| `fct_[grain]` | Mart — fact | `fct_city_weather_day` |
| `mart_[summary]` | Mart — aggregate | `mart_city_weather_summary` |

---

## Materialization Strategy

Configured in `dbt_project.yml`:

| Layer | Materialization | Why |
|---|---|---|
| Staging | `view` | No storage cost; always reflects the raw table |
| Intermediate | `view` | Lightweight joins; no need to persist |
| Marts | `table` | Queried by Streamlit — should be fast and persistent |

---

## Documentation Structure

Each layer should have a YAML docs file:
- `models/staging/docs/staging.yml`
- `models/intermediate/docs/intermediate.yml`
- `models/marts/docs/marts.yml`

Minimum per model: a `description` at the model level and descriptions + tests on all key columns.

---

## Dashboard Requirements

The Streamlit app (`streamlit_app/app.py`) must:
- Read **only from mart models** (not raw CSVs, not staging views)
- Include **at least one filter** (city, date range, or metric)
- Include **at least three charts or tables**
- Show **clear metric definitions** (what does "comfortable day" mean?)
- State the **grain of the main model** used (e.g. "one row per city per day")
- Be runnable locally with `streamlit run streamlit_app/app.py`

Connect to DuckDB in read-only mode:
```python
import duckdb
con = duckdb.connect("weather.duckdb", read_only=True)
df = con.execute("select * from marts.mart_city_weather_summary").df()
```

For Streamlit Community Cloud deployment, the `requirements.txt` in the root lists the needed packages. Note that the DuckDB file must either be committed to the repo or generated at app startup — the simplest approach for deployment is to commit a pre-built `weather.duckdb` (remove it from `.gitignore` temporarily) or use MotherDuck.

---

## Assignment Evaluation Criteria

The grader will look for:

1. Correct extraction from the API
2. Clear source definitions in `sources.yml`
3. Clean staging models (renaming, casting, no business logic)
4. Meaningful intermediate transformations
5. Well-designed fact and dimension models with clear grain
6. dbt tests and column documentation
7. Dashboard usefulness and clarity
8. Reproducibility from the GitHub repository
9. Code organisation and readability

> **Instructor note**: "Focus on a small, well-modeled project rather than a large project with unclear logic."

---

## dbt Profile

`profiles.yml` is in the project root. dbt 1.5+ finds it automatically when commands are run from
this directory. The DuckDB file is `weather.duckdb` in the project root (gitignored — regenerate
with `load_db.py`).

---

## Team Split (reference)

| Person | Responsibility |
|---|---|
| 1 | Repo setup, extraction script, `load_db.py`, `sources.yml` |
| 2 | Staging layer — all 4 `stg_*` models + staging YAML tests/docs |
| 3 | Intermediate layer — `int_city_day_weather`, `int_air_quality_daily`, `int_weather_flags` |
| 4 | Mart layer — `dim_location`, `fct_*`, `mart_*` + mart YAML tests/docs |
| 5 | Streamlit dashboard + final README + deployment |
