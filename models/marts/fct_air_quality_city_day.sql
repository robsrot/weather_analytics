with source as (
    select * from {{ ref('int_air_quality_daily') }}
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key(['location_id', 'date']) }} as air_quality_day_id,
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
    from source
)

select
    air_quality_day_id,
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
from final
