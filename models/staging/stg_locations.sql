select
    location_id::integer as location_id,
    city_name::varchar as city_name,
    country::varchar as country,
    country_code::varchar as country_code,
    admin1::varchar as admin1,
    latitude::double as latitude,
    longitude::double as longitude,
    timezone::varchar as timezone,
    elevation::double as elevation,
    population::integer as population,
    extracted_at::timestamp as extracted_at
from {{ source('raw', 'raw_locations') }}
