-- ============================================
-- DWS层 - 汇总表（分区+列式存储）
-- ============================================

USE dws;

-- 1. 用户消费日汇总表
DROP TABLE IF EXISTS dws_user_consume_day;
CREATE TABLE IF NOT EXISTS dws_user_consume_day (
    user_id INT,
    total_amount DECIMAL(20,2),
    order_cnt INT
)
PARTITIONED BY (dt STRING)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression'='SNAPPY');

SET hive.exec.dynamic.partition.mode=nonstrict;
INSERT OVERWRITE TABLE dws_user_consume_day PARTITION(dt)
SELECT 
    user_id,
    SUM(amount) AS total_amount,
    COUNT(DISTINCT order_id) AS order_cnt,
    dt
FROM dwd.dwd_order_detail
GROUP BY dt, user_id;

-- 2. 商品销售日汇总表
DROP TABLE IF EXISTS dws_product_sale_day;
CREATE TABLE IF NOT EXISTS dws_product_sale_day (
    product_id INT,
    sale_num INT,
    sale_amount DECIMAL(20,2)
)
PARTITIONED BY (dt STRING)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression'='SNAPPY');

INSERT OVERWRITE TABLE dws_product_sale_day PARTITION(dt)
SELECT 
    product_id,
    SUM(product_num) AS sale_num,
    SUM(amount) AS sale_amount,
    dt
FROM dwd.dwd_order_detail
GROUP BY dt, product_id;
