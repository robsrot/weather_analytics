select
    location_id::integer as location_id,
    city_name::varchar as city_name,
    country_code::varchar as country_code,
    date::date as date,
    temperature_2m_max::double as temperature_2m_max,
    temperature_2m_min::double as temperature_2m_min,
    temperature_2m_mean::double as temperature_2m_mean,
    precipitation_sum::double as precipitation_sum,
    rain_sum::double as rain_sum,
    snowfall_sum::double as snowfall_sum,
    wind_speed_10m_max::double as wind_speed_10m_max,
    extracted_at::timestamp as extracted_at
from {{ source('raw', 'raw_forecast_daily') }}
