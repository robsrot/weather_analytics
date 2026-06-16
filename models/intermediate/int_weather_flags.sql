with city_weather as (
    select
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
        wind_speed_10m_max
    from {{ ref('int_city_day_weather') }}
),

final as (
    select
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
        case
            when temperature_2m_max > 35 then true
            else false
        end as is_extreme_heat,
        case
            when precipitation_sum > 20 then true
            else false
        end as is_heavy_rain,
        case
            when wind_speed_10m_max > 50 then true
            else false
        end as is_windy,
        case
            when snowfall_sum > 0 then true
            else false
        end as is_snow_day,
        case
            when temperature_2m_mean between 18 and 25
                and precipitation_sum < 5
                and wind_speed_10m_max < 40
            then true
            else false
        end as is_comfortable_day
    from city_weather
)

select
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
