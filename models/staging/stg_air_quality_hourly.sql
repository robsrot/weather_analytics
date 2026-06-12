select
    location_id,
    city_name,
    country_code,
    timestamp,
    pm10,
    pm2_5,
    carbon_monoxide,
    nitrogen_dioxide,
    ozone,
    european_aqi,
    extracted_at
from {{ source('raw', 'raw_air_quality_hourly') }}
