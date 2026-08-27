#!/bin/bash
# ============================================
# ADS层数据导出脚本
# 功能：将Hive ADS层数据导出到MySQL
# 优化：使用INSERT OVERWRITE DIRECTORY + Sqoop
# ============================================

set -e  # 遇错即停

# 日期变量
DT=$(date +%Y-%m-%d)
LOG="/opt/module/logs/ads_export_${DT}.log"
mkdir -p /opt/module/logs
exec >> $LOG 2>&1

echo "========== $(date) 开始导出ADS层数据 =========="

# HDFS临时导出目录
EXPORT_BASE="/tmp/sqoop_export/${DT}"

# MySQL连接信息
MYSQL_URL="jdbc:mysql://hadoop142:3306/ecommerce_dw?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&characterEncoding=UTF-8"
MYSQL_USER="root"
MYSQL_PWD="123456"

# ============================================
# 定义导出函数
# 参数1: MySQL表名
# 参数2: Hive表名(含库名)
# ============================================
do_export() {
    local table=$1
    local hive_table=$2
    local export_dir="${EXPORT_BASE}/${table}"
    
    echo "[$(date)] 导出 ${hive_table} -> ${table}"
    
    # 1. 使用INSERT OVERWRITE DIRECTORY导出为Text格式（解决Parquet兼容问题）
    hive -e "
    INSERT OVERWRITE DIRECTORY '${export_dir}'
    ROW FORMAT DELIMITED FIELDS TERMINATED BY '\001'
    SELECT * FROM ${hive_table};
    " 2>&1 | tee -a $LOG
    
    # 检查Hive导出是否成功
    if [ $? -ne 0 ]; then
        echo "ERROR: Hive导出失败: ${hive_table}"
        exit 1
    fi
    
    # 2. Sqoop导出到MySQL
    sqoop export \
    --connect "${MYSQL_URL}" \
    --username ${MYSQL_USER} \
    --password ${MYSQL_PWD} \
    --table ${table} \
    --export-dir "${export_dir}" \
    --input-fields-terminated-by '\001' \
    --input-null-string '\\N' \
    --input-null-non-string '\\N' \
    --batch \
    --num-mappers 1 2>&1 | tee -a $LOG
    
    # 检查Sqoop导出是否成功
    if [ $? -ne 0 ]; then
        echo "ERROR: Sqoop导出失败: ${table}"
        exit 1
    fi
    
    # 3. 清理HDFS临时目录
    hdfs dfs -rm -r "${export_dir}" 2>/dev/null || true
    
    echo "[$(date)] 导出成功: ${table}"
}

# ============================================
# 执行导出4张ADS表
# ============================================
do_export "ads_gmv_day" "ads.ads_gmv_day"
do_export "ads_top10_product" "ads.ads_top10_product"
do_export "ads_user_rank" "ads.ads_user_rank"
do_export "ads_category_rank" "ads.ads_category_rank"

# 清理根目录
hdfs dfs -rm -r "${EXPORT_BASE}" 2>/dev/null || true

echo "========== $(date) 所有ADS表导出完成！ =========="
