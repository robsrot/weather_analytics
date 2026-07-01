with weather as (
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
        wind_speed_10m_max
    from {{ ref('stg_weather_daily') }}
),

locations as (
    select
        location_id,
        country,
        latitude,
        longitude,
        timezone,
        elevation,
        population
    from {{ ref('stg_locations') }}
),

final as (
    select
        weather.location_id,
        weather.city_name,
        weather.country_code,
        locations.country,
        locations.latitude,
        locations.longitude,
        locations.timezone,
        locations.elevation,
        locations.population,
        weather.date,
        weather.temperature_2m_max,
        weather.temperature_2m_min,
        weather.temperature_2m_mean,
        weather.precipitation_sum,
        weather.rain_sum,
        weather.snowfall_sum,
        weather.wind_speed_10m_max
    from weather
    left join locations using (location_id)
)

select
    location_id,
    city_name,
    country_code,
    country,
    latitude,
    longitude,
    timezone,
    elevation,
    population,
    date,
    temperature_2m_max,
    temperature_2m_min,
    temperature_2m_mean,
    precipitation_sum,
    rain_sum,
    snowfall_sum,
    wind_speed_10m_max
from final
