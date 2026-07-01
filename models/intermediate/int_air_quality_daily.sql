with source as (
    select
        location_id,
        city_name,
        country_code,
        cast(timestamp as date) as date,
        pm10,
        pm2_5,
        carbon_monoxide,
        nitrogen_dioxide,
        ozone,
        european_aqi
    from {{ ref('stg_air_quality_hourly') }}
),

daily as (
    select
        location_id,
        city_name,
        country_code,
        date,
        avg(pm10)             as avg_pm10,
        avg(pm2_5)            as avg_pm2_5,
        avg(carbon_monoxide)  as avg_carbon_monoxide,
        avg(nitrogen_dioxide) as avg_nitrogen_dioxide,
        avg(ozone)            as avg_ozone,
        avg(european_aqi)     as avg_european_aqi,
        max(european_aqi)     as max_european_aqi
    from source
    group by location_id, city_name, country_code, date
)

select
    location_id,
    city_name,
    country_code,
    date,
    avg_pm10,
    avg_pm2_5,
    avg_carbon_monoxide,
    avg_nitrogen_dioxide,
    avg_ozone,
    avg_european_aqi,
    max_european_aqi
from daily
