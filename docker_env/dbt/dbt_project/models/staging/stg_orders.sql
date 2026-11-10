with source as (
    select * from {{ source('raw', 'orders') }}
),

renamed as (
    select
        order_id,
        customer_id,
        order_date,
        status,
        total_amount,
        created_at
    from source
)

select * from renamed
