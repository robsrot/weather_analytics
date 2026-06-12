select
    location_id,
    city_name,
    country,
    country_code,
    admin1,
    latitude,
    longitude,
    timezone,
    elevation,
    population,
    extracted_at
from {{ source('raw', 'raw_locations') }}
