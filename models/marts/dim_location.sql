with source as (
    select * from {{ ref('stg_locations') }}
) ,

final as (
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
        population
    from source
)

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
    population
from final
