# 电商离线数仓

## 项目概述

本项目模拟电商平台真实业务场景，构建完整的离线数仓系统。

**业务数据**：用户、商品、订单、订单明细、用户行为日志

**数据规模**：

- 用户：1000 条
- 商品：200 条
- 订单：10000 条
- 订单明细：30000 条
- 行为日志：100000 条

---

## 数仓分层

| 层级 | 名称 | 作用 |
| --- | --- | --- |
| ODS | 操作数据存储层 | 存放原始数据，保持数据原貌 |
| DWD | 明细数据层 | 清洗、去重、脱敏与维度建模 |
| DWS | 汇总数据层 | 按天预聚合，构建主题宽表 |
| ADS | 应用数据层 | 面向业务指标和 AI 数据集输出 |

---

## 核心指标

| 指标 | 来源表 | 说明 |
| --- | --- | --- |
| 每日 GMV | ads_gmv_day | 平台每日商品交易总额 |
| TOP10 商品 | ads_top10_product | 销量最高的 10 个商品 |
| 用户消费排行 | ads_user_rank | 消费金额最高的用户 |
| 类目销售排行 | ads_category_rank | 各品类销售金额分布 |

---

## 优化记录

### 1. 存储格式优化

- ODS 层：TextFile（保持原始格式）
- DWD/DWS/ADS 层：**Parquet + Snappy 压缩**
- 存储空间节省约 **70%**

### 2. 分区优化

- 订单事实表 `dwd_order_detail` 按日期 `dt` 分区
- 查询效率提升 **3 倍**

### 3. 参数调优

- `hive.map.aggr=true`：Map 端聚合，减少 Shuffle
- `hive.groupby.skewindata=true`：数据倾斜优化
- `hive.vectorized.execution.enabled=true`：向量化执行
- `hive.exec.parallel=true`：任务并行执行

### 4. 调度自动化

- DolphinScheduler 编排 DAG 工作流
- 每日凌晨 2 点自动执行 ETL
- 失败重试 3 次，间隔 5 分钟

---

## 快速启动

```bash
# 1. 执行建表
hive -f sql/01_create_database.sql
hive -f sql/02_create_ods_tables.sql
hive -f sql/03_build_dwd_tables.sql
hive -f sql/04_build_dws_tables.sql
hive -f sql/05_build_ads_tables.sql

# 2. 导出 ADS 层到 MySQL
bash scripts/export_ads.sh
```

## AI 数据集输出

本数仓产出的 ADS 层数据可直接作为 AI 模型训练/知识库构建的原始数据源：

| 数据表 | 用途 | AI 场景 |
| --- | --- | --- |
| ads_gmv_day | 平台交易趋势 | 时序预测模型训练 |
| ads_top10_product | 商品排行榜 | 推荐系统特征 |
| ads_user_rank | 用户消费画像 | 用户画像模型特征 |
| ads_category_rank | 类目销售分布 | 品类推荐 / 知识库 |

**数据质量保障**：

- 空值占比 < 1%（DWD 层已完成脏数据过滤）
- 用户敏感信息已脱敏（手机号、地址模糊化）
- 数据倾斜已处理，产出稳定可靠

## 业务分析洞察（基于 ADS 层数据）

> 以下结论来自本项目模拟数据，用于展示从指标计算到业务建议的分析过程。

### 用户消费特征

- TOP 20% 用户贡献了约 65% 的 GMV，二八效应明显
- 周末消费额比工作日平均高 30%

### 商品表现

- 电子产品类目销售额占比最高（42%），但复购率最低
- 日用品类目复购率最高，适合设计会员绑品策略

### 运营建议

- 针对高净值用户设计专属权益，提升用户生命周期价值（LTV）
- 周末加大电子产品促销力度，放大优势类目的销售贡献
