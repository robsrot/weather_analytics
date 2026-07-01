with source as (
    select * from {{ ref('int_weather_flags') }}
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['location_id', 'date']) }} as weather_day_id,
        location_id,
        city_name,
        country_code,
        country,
        date,
        temperature_2m_max,
        temperature_2m_min,
        temperature_2m_mean,
        precipitation_sum,
        rain_sum,
        snowfall_sum,
        wind_speed_10m_max,
        is_extreme_heat,
        is_heavy_rain,
        is_windy,
        is_snow_day,
        is_comfortable_day
    from source
)

select
    weather_day_id,
    location_id,
    city_name,
    country_code,
    country,
    date,
    temperature_2m_max,
    temperature_2m_min,
    temperature_2m_mean,
    precipitation_sum,
    rain_sum,
    snowfall_sum,
    wind_speed_10m_max,
    is_extreme_heat,
    is_heavy_rain,
    is_windy,
    is_snow_day,
    is_comfortable_day
from final
