"""Load extracted Open-Meteo CSVs into DuckDB."""

from pathlib import Path
import duckdb

DB_PATH = "weather.duckdb"
RAW_DIR = Path("data/raw/open_meteo")

TABLES = {
    "raw_locations": "raw_locations.csv",
    "raw_weather_daily": "raw_weather_daily.csv",
    "raw_forecast_daily": "raw_forecast_daily.csv",
    "raw_air_quality_hourly": "raw_air_quality_hourly.csv",
}


def main() -> None:
    con = duckdb.connect(DB_PATH)
    con.execute("create schema if not exists main")

    for table_name, filename in TABLES.items():
        csv_path = RAW_DIR / filename
        if not csv_path.exists():
            print(f"Skipping {table_name}: {csv_path} not found")
            continue

        con.execute(f"drop table if exists main.{table_name}")
        con.execute(
            f"create table main.{table_name} as "
            f"select * from read_csv_auto('{csv_path.as_posix()}')"
        )
        count = con.execute(f"select count(*) from main.{table_name}").fetchone()[0]
        print(f"  {table_name}: {count:,} rows")

    con.close()
    print(f"\nDatabase written to {DB_PATH}")


if __name__ == "__main__":
    main()
