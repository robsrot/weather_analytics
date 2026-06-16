with weather as (
    select
        location_id,
        city_name,
        country_code,
        country,
        temperature_2m_max,
        temperature_2m_min,
        temperature_2m_mean,
        precipitation_sum,
        wind_speed_10m_max,
        is_comfortable_day,
        is_extreme_heat,
        is_heavy_rain,
        is_windy,
        is_snow_day
    from {{ ref('int_weather_flags') }}
),

air_quality as (
    select
        location_id,
        avg_european_aqi,
        max_european_aqi
    from {{ ref('int_air_quality_daily') }}
),

weather_summary as (
    select
        location_id,
        city_name,
        country_code,
        country,
        count(*) as total_days,
        round(avg(temperature_2m_mean), 1) as avg_temp_c,
        round(max(temperature_2m_max), 1) as max_temp_c,
        round(min(temperature_2m_min), 1) as min_temp_c,
        round(avg(precipitation_sum), 1) as avg_daily_precipitation_mm,
        round(avg(wind_speed_10m_max), 1) as avg_wind_speed_kmh,
        round(max(wind_speed_10m_max), 1) as max_wind_speed_kmh,
        sum(case when is_comfortable_day then 1 else 0 end) as comfortable_days,
        sum(case when is_extreme_heat then 1 else 0 end) as extreme_heat_days,
        sum(case when is_heavy_rain then 1 else 0 end) as heavy_rain_days,
        sum(case when is_windy then 1 else 0 end) as windy_days,
        sum(case when is_snow_day then 1 else 0 end) as snow_days,
        round(100.0 * sum(case when is_comfortable_day then 1 else 0 end) / count(*), 1) as comfortable_day_pct
    from weather
    group by location_id, city_name, country_code, country
),

aqi_summary as (
    select
        location_id,
        round(avg(avg_european_aqi), 1) as avg_aqi,
        round(max(max_european_aqi), 0) as worst_aqi
    from air_quality
    group by location_id
),

final as (
    select
        weather_summary.location_id,
        weather_summary.city_name,
        weather_summary.country_code,
        weather_summary.country,
        weather_summary.total_days,
        weather_summary.avg_temp_c,
        weather_summary.max_temp_c,
        weather_summary.min_temp_c,
        weather_summary.avg_daily_precipitation_mm,
        weather_summary.avg_wind_speed_kmh,
        weather_summary.max_wind_speed_kmh,
        weather_summary.comfortable_days,
        weather_summary.comfortable_day_pct,
        weather_summary.extreme_heat_days,
        weather_summary.heavy_rain_days,
        weather_summary.windy_days,
        weather_summary.snow_days,
        aqi_summary.avg_aqi,
        aqi_summary.worst_aqi,
        round(least(100, greatest(0,
            least(greatest(weather_summary.avg_temp_c - 15, 0), 20) / 20.0 * 50
            + (1 - weather_summary.heavy_rain_days * 1.0 / weather_summary.total_days) * 30
            + greatest(1 - weather_summary.avg_wind_speed_kmh / 60.0, 0) * 20
        )), 1) as beach_score,
        round(least(100, greatest(0,
            greatest(1 - abs(weather_summary.avg_temp_c - 15) / 20.0, 0) * 50
            + (1 - least(aqi_summary.avg_aqi / 150.0, 1)) * 50
        )), 1) as hiking_score,
        round(least(100, greatest(0,
            weather_summary.comfortable_day_pct / 100.0 * 50
            + (1 - least(aqi_summary.avg_aqi / 100.0, 1)) * 30
            + (1 - weather_summary.heavy_rain_days * 1.0 / weather_summary.total_days) * 20
        )), 1) as city_break_score,
        round(least(100, greatest(0,
            least(weather_summary.avg_wind_speed_kmh / 40.0, 1) * 60
            + least(weather_summary.max_wind_speed_kmh / 80.0, 1) * 40
        )), 1) as extreme_sports_score,
        case
            when weather_summary.avg_temp_c > 22
                and weather_summary.heavy_rain_days * 1.0 / weather_summary.total_days < 0.15
            then true
            else false
        end as is_beach_destination,
        case
            when weather_summary.avg_temp_c between 8 and 18
                and aqi_summary.avg_aqi < 60
            then true
            else false
        end as is_hiking_destination,
        case
            when weather_summary.comfortable_day_pct > 40
                and aqi_summary.avg_aqi < 75
            then true
            else false
        end as is_city_break_destination,
        case
            when weather_summary.avg_wind_speed_kmh > 30
            then true
            else false
        end as is_extreme_sports_destination
    from weather_summary
    left join aqi_summary using (location_id)
)

select
    location_id,
    city_name,
    country_code,
    country,
    total_days,
    avg_temp_c,
    max_temp_c,
    min_temp_c,
    avg_daily_precipitation_mm,
    avg_wind_speed_kmh,
    max_wind_speed_kmh,
    comfortable_days,
    comfortable_day_pct,
    extreme_heat_days,
    heavy_rain_days,
    windy_days,
    snow_days,
    avg_aqi,
    worst_aqi,
    beach_score,
    hiking_score,
    city_break_score,
    extreme_sports_score,
    is_beach_destination,
    is_hiking_destination,
    is_city_break_destination,
    is_extreme_sports_destination
from final
