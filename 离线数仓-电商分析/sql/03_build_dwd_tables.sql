-- ============================================
-- DWD层 - 订单事实表（分区表改造）
-- 优化前：无分区，全表扫描
-- 优化后：按日期分区，分区裁剪
-- ============================================

USE dwd;

-- 删除旧表（如果存在）
DROP TABLE IF EXISTS dwd_order_detail;

-- 创建分区表
CREATE TABLE IF NOT EXISTS dwd_order_detail (
    order_id BIGINT,
    user_id INT,
    product_id INT,
    product_num INT,
    amount DECIMAL(20,2)
)
PARTITIONED BY (dt STRING)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- 动态分区插入
SET hive.exec.dynamic.partition.mode=nonstrict;

INSERT OVERWRITE TABLE dwd_order_detail PARTITION(dt)
SELECT 
    o.order_id,
    o.user_id,
    d.product_id,
    d.product_num,
    p.price * d.product_num AS amount,
    SUBSTR(o.order_time, 1, 10) AS dt
FROM ods.ods_order_info o
JOIN ods.ods_order_detail d ON o.order_id = d.order_id
JOIN ods.ods_product_info p ON d.product_id = p.product_id;

-- 验证分区
SHOW PARTITIONS dwd_order_detail;
