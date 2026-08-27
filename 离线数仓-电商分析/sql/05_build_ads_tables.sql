-- ============================================
-- 05_构建ADS层（应用数据层）
-- 面向业务指标的统计报表
-- ============================================

USE ads;

-- ===== 1. 每日GMV =====
CREATE TABLE IF NOT EXISTS ads_gmv_day AS
SELECT 
    dt,
    SUM(sale_amount) AS gmv
FROM dws.dws_product_sale_day
GROUP BY dt
ORDER BY dt;

-- ===== 2. TOP10商品销量 =====
CREATE TABLE IF NOT EXISTS ads_top10_product AS
SELECT 
    product_id,
    SUM(sale_num) AS total_sale
FROM dws.dws_product_sale_day
GROUP BY product_id
ORDER BY total_sale DESC
LIMIT 10;

-- ===== 3. 用户消费金额排行 =====
CREATE TABLE IF NOT EXISTS ads_user_rank AS
SELECT 
    user_id,
    SUM(total_amount) AS amount
FROM dws.dws_user_consume_day
GROUP BY user_id
ORDER BY amount DESC;

-- ===== 4. 商品类目销售排行 =====
CREATE TABLE IF NOT EXISTS ads_category_rank AS
SELECT 
    category,
    SUM(sale_amount) AS amount
FROM dws.dws_category_sale_day
GROUP BY category
ORDER BY amount DESC;

-- 查看ADS层所有表
SHOW TABLES;

-- 验证数据
SELECT 'GMV:' AS indicator, COUNT(*) AS cnt FROM ads_gmv_day
UNION ALL
SELECT 'TOP10:', COUNT(*) FROM ads_top10_product
UNION ALL
SELECT 'UserRank:', COUNT(*) FROM ads_user_rank
UNION ALL
SELECT 'CategoryRank:', COUNT(*) FROM ads_category_rank;
