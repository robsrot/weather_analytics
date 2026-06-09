import duckdb
import pandas as pd
import streamlit as st

# Connect to DuckDB in read-only mode - always read from marts schema
con = duckdb.connect("weather.duckdb", read_only=True)

st.title("Weather Analytics Dashboard")

# TODO: add at least one filter (city, date range, or metric)
# TODO: add at least three charts or tables
# TODO: show clear metric definitions (e.g. what counts as a "comfortable day")
# TODO: state the grain of the main model used

# Example query to get started:
# df = con.execute("select * from marts.mart_city_weather_summary").df()
