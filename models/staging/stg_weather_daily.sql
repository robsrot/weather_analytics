select
    location_id,
    city_name,
    country_code,
    date,
    temperature_2m_max,
    temperature_2m_min,
    temperature_2m_mean,
    precipitation_sum,
    rain_sum,
    snowfall_sum,
    wind_speed_10m_max,
    extracted_at
from {{ source('raw', 'raw_weather_daily') }}
