select
    location_id::integer as location_id,
    city_name::varchar as city_name,
    country_code::varchar as country_code,
    timestamp::timestamp as timestamp,
    pm10::double as pm10,
    pm2_5::double as pm2_5,
    carbon_monoxide::double as carbon_monoxide,
    nitrogen_dioxide::double as nitrogen_dioxide,
    ozone::double as ozone,
    european_aqi::integer as european_aqi,
    extracted_at::timestamp as extracted_at
from {{ source('raw', 'raw_air_quality_hourly') }}
