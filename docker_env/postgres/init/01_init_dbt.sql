-- PostgreSQL 初始化脚本
-- 创建 dbt 用户和数据库，以及示例数据

-- 创建 dbt 用户
CREATE USER dbt_user WITH PASSWORD 'dbt_password';

-- 创建 dbt 数据库
CREATE DATABASE dbt_demo;

-- 连接到 dbt_demo 数据库
\c dbt_demo

-- 创建 schema
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

-- 授权
GRANT ALL PRIVILEGES ON DATABASE dbt_demo TO dbt_user;
GRANT ALL ON SCHEMA raw TO dbt_user;
GRANT ALL ON SCHEMA staging TO dbt_user;
GRANT ALL ON SCHEMA marts TO dbt_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA raw TO dbt_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA staging TO dbt_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA marts TO dbt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA raw GRANT ALL ON TABLES TO dbt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging GRANT ALL ON TABLES TO dbt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT ALL ON TABLES TO dbt_user;

-- 创建原始表 (raw schema)
CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id INT PRIMARY KEY,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.orders (
    order_id INT PRIMARY KEY,
    customer_id INT,
    order_date DATE,
    status VARCHAR(20),
    total_amount DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.products (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(100),
    category VARCHAR(50),
    price DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.order_items (
    order_item_id INT PRIMARY KEY,
    order_id INT,
    product_id INT,
    quantity INT,
    unit_price DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入示例数据
INSERT INTO raw.customers (customer_id, first_name, last_name, email) VALUES
(1, 'John', 'Doe', 'john@example.com'),
(2, 'Jane', 'Smith', 'jane@example.com'),
(3, 'Bob', 'Johnson', 'bob@example.com'),
(4, 'Alice', 'Williams', 'alice@example.com'),
(5, 'Charlie', 'Brown', 'charlie@example.com')
ON CONFLICT (customer_id) DO NOTHING;

INSERT INTO raw.products (product_id, product_name, category, price) VALUES
(1, 'Laptop', 'Electronics', 999.99),
(2, 'Mouse', 'Electronics', 29.99),
(3, 'Keyboard', 'Electronics', 79.99),
(4, 'Monitor', 'Electronics', 299.99),
(5, 'USB Cable', 'Accessories', 9.99)
ON CONFLICT (product_id) DO NOTHING;

INSERT INTO raw.orders (order_id, customer_id, order_date, status, total_amount) VALUES
(1, 1, '2024-01-15', 'completed', 1029.98),
(2, 2, '2024-01-16', 'completed', 29.99),
(3, 3, '2024-01-17', 'pending', 379.98),
(4, 1, '2024-01-18', 'completed', 299.99),
(5, 4, '2024-01-19', 'shipped', 9.99),
(6, 2, '2024-01-20', 'completed', 1079.98),
(7, 5, '2024-01-21', 'pending', 999.99),
(8, 3, '2024-01-22', 'completed', 59.98),
(9, 4, '2024-01-23', 'shipped', 29.99),
(10, 1, '2024-01-24', 'completed', 9.99)
ON CONFLICT (order_id) DO NOTHING;

INSERT INTO raw.order_items (order_item_id, order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 1, 999.99),
(2, 1, 2, 1, 29.99),
(3, 2, 2, 1, 29.99),
(4, 3, 3, 1, 79.99),
(5, 3, 4, 1, 299.99),
(6, 4, 4, 1, 299.99),
(7, 5, 5, 1, 9.99),
(8, 6, 1, 1, 999.99),
(9, 6, 3, 1, 79.99),
(10, 7, 1, 1, 999.99)
ON CONFLICT (order_item_id) DO NOTHING;
