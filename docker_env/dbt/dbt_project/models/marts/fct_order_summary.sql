with orders as (
    select * from {{ ref('stg_orders') }}
),

order_items as (
    select * from {{ ref('stg_order_items') }}
),

products as (
    select * from {{ ref('stg_products') }}
),

order_summary as (
    select
        o.order_id,
        o.customer_id,
        o.order_date,
        o.status,
        o.total_amount,
        count(oi.order_item_id) as total_items,
        sum(oi.quantity) as total_quantity
    from orders o
    left join order_items oi on o.order_id = oi.order_id
    group by 1, 2, 3, 4, 5
),

final as (
    select *
    from order_summary
)

select * from final
