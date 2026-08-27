-- ============================================
-- 02_创建ODS层表（原始数据层）
-- ============================================

USE ods;

-- 1. 用户信息表
CREATE TABLE IF NOT EXISTS ods_user_info (
    user_id INT,
    user_name STRING,
    gender STRING,
    age INT,
    register_time STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\001'
STORED AS TEXTFILE;

-- 2. 商品信息表
CREATE TABLE IF NOT EXISTS ods_product_info (
    product_id INT,
    product_name STRING,
    category STRING,
    price DECIMAL(10,2)
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\001'
STORED AS TEXTFILE;

-- 3. 订单信息表
CREATE TABLE IF NOT EXISTS ods_order_info (
    order_id BIGINT,
    user_id INT,
    order_time STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\001'
STORED AS TEXTFILE;

-- 4. 订单明细表
CREATE TABLE IF NOT EXISTS ods_order_detail (
    detail_id BIGINT,
    order_id BIGINT,
    product_id INT,
    product_num INT
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\001'
STORED AS TEXTFILE;

-- 5. 用户行为日志表
CREATE TABLE IF NOT EXISTS ods_user_action_log (
    id BIGINT,
    user_id INT,
    product_id INT,
    action STRING,
    action_time STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\001'
STORED AS TEXTFILE;

-- 查看所有ODS表
SHOW TABLES;
