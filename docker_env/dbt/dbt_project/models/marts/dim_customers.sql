with customers as (
    select * from {{ ref('stg_customers') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
),

customer_orders as (
    select
        customer_id,
        count(order_id) as total_orders,
        sum(total_amount) as total_spent,
        min(order_date) as first_order_date,
        max(order_date) as last_order_date
    from orders
    group by 1
),

final as (
    select
        c.customer_id,
        c.first_name,
        c.last_name,
        c.email,
        coalesce(co.total_orders, 0) as total_orders,
        coalesce(co.total_spent, 0) as total_spent,
        co.first_order_date,
        co.last_order_date,
        c.created_at
    from customers c
    left join customer_orders co on c.customer_id = co.customer_id
)

select * from final
