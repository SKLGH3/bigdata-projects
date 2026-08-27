-- ============================================
-- 01_创建数仓分层数据库
-- ============================================
-- 删除已存在的数据库（如需重建）
DROP DATABASE IF EXISTS ods CASCADE;
DROP DATABASE IF EXISTS dwd CASCADE;
DROP DATABASE IF EXISTS dws CASCADE;
DROP DATABASE IF EXISTS ads CASCADE;

-- 创建四层数据库
CREATE DATABASE ods;
CREATE DATABASE dwd;
CREATE DATABASE dws;
CREATE DATABASE ads;

-- 查看所有数据库
SHOW DATABASES;
