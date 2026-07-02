# `mart_destination_weather_summary` — Field Reference

One row per city, summarising weather and air quality over the full extraction period (31 days in the example below). This sheet shows one real row, then explains how every derived column was built.

## Example row — Dubrovnik

| Column | Value |
|---|---|
| `location_id` | 3201047 |
| `city_name` | Dubrovnik |
| `country_code` | HR |
| `country` | Croatia |
| `total_days` | 31 |
| `avg_temp_c` | 26.0 |
| `max_temp_c` | 34.8 |
| `min_temp_c` | 16.8 |
| `avg_daily_precipitation_mm` | 1.2 |
| `avg_wind_speed_kmh` | 13.1 |
| `max_wind_speed_kmh` | 28.7 |
| `comfortable_days` | 14 |
| `comfortable_day_pct` | 45.2 |
| `extreme_heat_days` | 0 |
| `heavy_rain_days` | 1 |
| `windy_days` | 0 |
| `snow_days` | 0 |
| `avg_aqi` | 32.7 |
| `worst_aqi` | 58 |
| `beach_score` | 72.2 |
| `hiking_score` | 61.6 |
| `city_break_score` | 62.1 |
| `extreme_sports_score` | 34.0 |
| `cultural_score` | 63.1 |
| `wellness_score` | 55.4 |
| `is_beach_destination` | True |
| `is_hiking_destination` | False |
| `is_city_break_destination` | True |
| `is_extreme_sports_destination` | False |
| `is_cultural_destination` | True |
| `is_wellness_destination` | True |

---

## Daily flags — created in `int_weather_flags`

These are computed once per city per day (grain: city × day), then rolled up into the day-counts (`comfortable_days`, `extreme_heat_days`, etc.) seen in the mart row above via `sum(case when flag then 1 else 0 end)` in `mart_destination_weather_summary`.

| Flag | How it's created |
|---|---|
| `is_extreme_heat` | `true` when `temperature_2m_max > 35`°C that day |
| `is_heavy_rain` | `true` when `precipitation_sum > 20`mm that day |
| `is_windy` | `true` when `wind_speed_10m_max > 50` km/h that day |
| `is_snow_day` | `true` when `snowfall_sum > 0` that day (any snowfall at all) |
| `is_comfortable_day` | `true` when **all three** hold simultaneously: `temperature_2m_mean` between 18–25°C, `precipitation_sum < 5`mm, and `wind_speed_10m_max < 40` km/h |

All five are simple threshold `case when` expressions over `int_city_day_weather` — no joins, no aggregation at this step. `is_comfortable_day` is the only compound one (AND of three conditions); the rest are single-threshold checks.

---

## Appendix: Score Calc — generated in `mart_destination_weather_summary`

Each score adds up a few weather "ingredients" (temperature, rain, wind, air quality), where each ingredient is worth some points, and a city gets more or fewer of those points depending on how good its weather is for that ingredient. The method is always the same three steps:

1. **Set a "good" range or target** — fixed in advance (e.g. "beach temperature is worst at 15°C and best at 35°C").
2. **Turn the city's actual number into a percentage of that range.**
3. **Multiply that percentage by the points the ingredient is worth.**

Every score is built from the city-level aggregates (`weather_summary` + `aqi_summary` CTEs), not the raw daily rows, and every total is clamped to 0–100 so nothing can go negative or overshoot. All worked examples below use the real **Dubrovnik** row from the mart (`avg_temp_c = 26.0`, `avg_daily_precipitation_mm = 1.2`, `heavy_rain_days = 1` of `total_days = 31`, `avg_wind_speed_kmh = 13.1`, `max_wind_speed_kmh = 28.7`, `avg_aqi = 32.7`, `comfortable_day_pct = 45.2`).

### `beach_score` — 50 / 30 / 20

| Ingredient | Worth | Dubrovnik got | Why |
|---|---|---|---|
| Warm temperature | 50 pts | 27.5 | Warm (26°C), but not maxed out |
| Low rain | 30 pts | 29.0 | Almost no heavy-rain days |
| Calm wind | 20 pts | 15.6 | Fairly calm |
| **Total** | **100** | **72.1 → 72.2** | |

**Temperature example** (worst point 15°C, best point 35°C):
1. How far is 26°C above the worst point (15°C)? → `26 − 15 = 11` degrees
2. How wide is the whole good range (15°C to 35°C)? → `35 − 15 = 20` degrees
3. What fraction of the way through the range is that? → `11 ÷ 20 = 0.55 → 55%`
4. Multiply by the points available: → `55% of 50 = 27.5 points`

### `hiking_score` — 50 / 50

| Ingredient | Worth | Dubrovnik got | Why |
|---|---|---|---|
| Mild temperature | 50 pts | 22.5 | Warmer than the 15°C ideal, but within tolerance |
| Clean air | 50 pts | 39.1 | Low AQI (32.7), well under the 150 ceiling |
| **Total** | **100** | **61.6** | |

**Temperature example** (ideal 15°C, tolerance ±20°C — zero points once 20°C away in *either* direction):
1. How far is 26°C from the ideal (15°C)? → `|26 − 15| = 11` degrees
2. How wide is the tolerance before it hits zero? → `20` degrees
3. What fraction of the tolerance is left? → `1 − (11 ÷ 20) = 1 − 0.55 = 0.45 → 45%`
4. Multiply by the points available: → `45% of 50 = 22.5 points`

### `city_break_score` — 50 / 30 / 20

| Ingredient | Worth | Dubrovnik got | Why |
|---|---|---|---|
| Comfortable days | 50 pts | 22.6 | 45.2% of days were "comfortable" |
| Air quality | 30 pts | 20.2 | AQI 32.7, well under the 100 ceiling |
| Low rain | 20 pts | 19.4 | Almost no heavy-rain days |
| **Total** | **100** | **62.1** | |

**Comfortable-days example** (this ingredient reuses `comfortable_day_pct` directly, no range needed):
1. What percentage of days were comfortable? → `45.2%`
2. Turn that into a fraction: → `45.2 ÷ 100 = 0.452`
3. Multiply by the points available: → `0.452 × 50 = 22.6 points`

### `extreme_sports_score` — 60 / 40

| Ingredient | Worth | Dubrovnik got | Why |
|---|---|---|---|
| Average wind | 60 pts | 19.7 | 13.1 km/h avg — modest for this ingredient |
| Peak wind | 40 pts | 14.4 | 28.7 km/h max gust — well under the 80 km/h ceiling |
| **Total** | **100** | **34.0** | No temperature or rain ingredient at all — the only score that's purely wind-driven |

**Average-wind example** (worst point 0 km/h, best point 40 km/h — full points once ≥40):
1. How far is 13.1 km/h above the worst point (0)? → `13.1` km/h
2. How wide is the whole good range (0 to 40 km/h)? → `40` km/h
3. What fraction of the way through is that? → `13.1 ÷ 40 = 0.3275 → 32.75%`
4. Multiply by the points available: → `32.75% of 60 = 19.65 points`

### `cultural_score` — 40 / 25 / 20 / 15

| Ingredient | Worth | Dubrovnik got | Why |
|---|---|---|---|
| Mild temperature | 40 pts | 16.0 | 6°C above the 20°C ideal, ±10°C tolerance |
| Low rain | 25 pts | 24.2 | Almost no heavy-rain days |
| Air quality | 20 pts | 11.8 | AQI 32.7 against a stricter 80 ceiling |
| Calm wind | 15 pts | 11.1 | Fairly calm against a 50 km/h ceiling |
| **Total** | **100** | **63.1** | |

**Temperature example** (ideal 20°C, tolerance ±10°C):
1. How far is 26°C from the ideal (20°C)? → `|26 − 20| = 6` degrees
2. How wide is the tolerance before it hits zero? → `10` degrees
3. What fraction of the tolerance is left? → `1 − (6 ÷ 10) = 1 − 0.6 = 0.4 → 40%`
4. Multiply by the points available: → `40% of 40 = 16.0 points`

### `wellness_score` — 35 / 25 / 25 / 15

| Ingredient | Worth | Dubrovnik got | Why |
|---|---|---|---|
| Precise temperature | 35 pts | 12.5 | 4.5°C above the 21.5°C ideal, the tightest ±7°C tolerance of any score |
| Low rain | 25 pts | 24.2 | Almost no heavy-rain days |
| Pristine air | 25 pts | 8.7 | AQI 32.7 against the strictest 50 ceiling of any score |
| Calm wind | 15 pts | 10.1 | Fairly calm against a 40 km/h ceiling |
| **Total** | **100** | **55.5 → 55.4** | |

**Temperature example** (ideal 21.5°C, tolerance ±7°C — the narrowest band of all six scores):
1. How far is 26°C from the ideal (21.5°C)? → `|26 − 21.5| = 4.5` degrees
2. How wide is the tolerance before it hits zero? → `7` degrees
3. What fraction of the tolerance is left? → `1 − (4.5 ÷ 7) = 1 − 0.643 = 0.357 → 35.7%`
4. Multiply by the points available: → `35.7% of 35 = 12.5 points`

---

## Destination flags — also generated in `mart_destination_weather_summary`

Unlike the scores above (smooth weighted blends), these are hard pass/fail AND-gates computed directly from the same city-level aggregates. A city can score well on a holiday type's smooth score while still failing its corresponding flag, if any single hard condition misses its cutoff.

| Flag | Condition (all must hold) |
|---|---|
| `is_beach_destination` | `avg_temp_c > 22` AND `heavy_rain_days / total_days < 0.15` |
| `is_hiking_destination` | `avg_temp_c` between 8–18°C AND `avg_aqi < 60` |
| `is_city_break_destination` | `comfortable_day_pct > 40` AND `avg_aqi < 75` |
| `is_extreme_sports_destination` | `avg_wind_speed_kmh > 30` |
| `is_cultural_destination` | `avg_temp_c` between 14–26°C AND `avg_daily_precipitation_mm < 8` AND `avg_aqi < 50` AND `avg_wind_speed_kmh < 30` |
| `is_wellness_destination` | `avg_temp_c` between 17–26°C AND `avg_daily_precipitation_mm < 8` AND `avg_aqi < 35` AND `avg_wind_speed_kmh < 25` |

**Dubrovnik example above**: `avg_temp_c = 26.0` (>22, so clears Beach), `heavy_rain_days / total_days = 1/31 ≈ 0.032` (<0.15, also clears Beach) → `is_beach_destination = True`. `comfortable_day_pct = 45.2` (>40) and `avg_aqi = 32.7` (<75) → `is_city_break_destination = True`. Both the Cultural gate (14–26°C, <8mm, <50 AQI, <30 km/h) and the stricter Wellness gate (17–26°C, <8mm, <35 AQI, <25 km/h) are cleared too, so `is_cultural_destination` and `is_wellness_destination` both read `True`. It fails Hiking (26°C is outside the 8–18°C band) and Extreme Sports (13.1 km/h avg wind is nowhere near the >30 km/h cutoff) — matching the `False`/`False` seen in the example row above.
