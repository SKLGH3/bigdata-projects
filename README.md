# 大数据项目合集

> 💡 **项目定位**：本仓库包含从原始业务数据到 AI 可用数据集的完整加工链路，涵盖离线数仓建模、实时特征采集、数据清洗脱敏、样本质量监控等数据工程能力。

## 项目导航

| 项目 | 技术栈 | 一句话说明 | 适合场景 |
| --- | --- | --- | --- |
| [离线数仓](./离线数仓-电商分析) | Hive + Sqoop + DolphinScheduler | 四层数仓建模，产出业务指标 + AI 数据集 | 离线分析 / 模型训练数据准备 |
| [实时采集](./实时采集-Flume-HBase-Phoenix) | Flume + HBase + Phoenix + Java | 用户行为实时入库，支撑在线特征查询 | 实时特征库 / 模型推理数据源 |
| [RAG 知识库问答](./rag-demo) | LangChain + Chroma + OpenAI-compatible API | 将 7,665 条清洗后的电影数据构建为本地向量知识库 | AI 应用开发 / RAG 最小闭环 |


## 项目亮点

- **离线数仓**：四层建模 + Hive MR 参数调优，ETL 耗时从 90 分钟降至 45 分钟
- **实时采集**：自定义 PhoenixSink，吞吐量从 500 条/秒提升至 5000 条/秒
- **RAG Demo**：实现从 CSV 清洗、向量化、检索到 LLM 生成的完整闭环，支持本地运行
- **踩坑记录**：沉淀 4 个实战问题及解决方案，覆盖数仓、调度、实时采集与 RAG，体现故障排查能力

---

## 项目一：电商离线数仓

### 技术栈

`Hive（MR 优化）` `Sqoop` `DataEase` `DolphinScheduler`

### 数仓架构

```text
ODS（操作数据存储层） → DWD（明细数据层） → DWS（汇总数据层） → ADS（应用数据层）
原始数据              清洗/维度建模       预聚合             业务指标/AI 数据集
```

### 核心优化

| 优化项 | 优化前 | 优化后 | 提升 |
| --- | --- | --- | --- |
| ETL 总耗时 | ~90 分钟 | ~45 分钟 | **50% ↓** |
| 存储空间 | 100% | 30% | **70% ↓** |
| 分区查询 | 全表扫描 | 只扫描目标分区 | **3 倍 ↑** |

### 优化措施

- **参数调优**：开启 Map 端聚合、数据倾斜优化、向量化执行
- **存储优化**：使用 Parquet + Snappy 列式存储
- **分区设计**：关键事实表按日期分区
- **调度自动化**：使用 DolphinScheduler 编排 DAG 工作流

### 快速启动

```bash
cd 离线数仓-电商分析
hive -f sql/01_create_database.sql
hive -f sql/02_create_ods_tables.sql
hive -f sql/03_build_dwd_tables.sql
hive -f sql/04_build_dws_tables.sql
hive -f sql/05_build_ads_tables.sql
bash scripts/export_ads.sh
```

详见：[离线数仓项目说明](./离线数仓-电商分析/README.md)

---

## 项目二：用户行为实时采集

### 技术栈

`Flume` `HBase` `Phoenix` `Java` `HikariCP`

### 数据链路

```text
Python 生成 JSON 日志 → Flume Taildir Source → Memory Channel
→ 自定义 PhoenixSink → Phoenix → HBase 存储
```

### 数据模型（8 字段）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | VARCHAR | 主键 / RowKey |
| user_name | VARCHAR | 用户名 |
| action | VARCHAR | 行为类型 |
| event_time | VARCHAR | 事件时间 |
| ip | VARCHAR | IP 地址 |
| device | VARCHAR | 设备类型 |
| duration | VARCHAR | 停留时长 |
| page_url | VARCHAR | 访问页面 |

### 核心优化

| 优化项 | 优化前 | 优化后 | 提升 |
| --- | --- | --- | --- |
| 吞吐量（TPS） | ~500 条/秒 | ~5000 条/秒 | **900% ↑** |
| 平均延迟 | 2 ms/条 | 0.2 ms/条 | **90% ↓** |
| 连接管理 | 频繁创建 | 连接池复用 | **稳定** |

详见：[实时采集项目说明](./实时采集-Flume-HBase-Phoenix/README.md)

---

## 项目三：RAG 电影知识库问答

将电影 CSV 数据经过清洗、文本切片和 Embedding 后写入 Chroma，本地检索相关电影资料，再由大模型基于检索上下文生成可追溯回答；未配置 API Key 时也可运行检索演示。

```bash
cd rag-demo
pip install -r requirements.txt
python build_knowledge_base.py
python query_rag.py
```

详见：[RAG Demo 项目说明](./rag-demo/README.md)

---

## 调度自动化

### DolphinScheduler

- **部署地址**：`http://hadoop142:12345/dolphinscheduler`
- **默认账号**：`admin` / `dolphinscheduler123`
- **工作流**：数仓每日 ETL（凌晨 2 点执行）
- **失败重试**：3 次，间隔 5 分钟

---

## 项目结构

```text
bigdata-projects/
├── README.md
├── docs/
│   ├── AI数据集加工规范.md
│   ├── 环境搭建指南.md
│   ├── 性能对比报告.md
│   └── 踩坑记录.md
├── 离线数仓-电商分析/
│   ├── README.md
│   ├── sql/
│   ├── scripts/
│   └── conf/
├── 实时采集-Flume-HBase-Phoenix/
│   ├── README.md
│   ├── pom.xml
│   ├── src/
│   ├── conf/
│   └── scripts/
└── rag-demo/
    ├── README.md
    ├── requirements.txt
    ├── config.py
    ├── build_knowledge_base.py
    ├── query_rag.py
    ├── demo_screenshot.png
    └── data/movies.csv
```

---

## 踩坑记录

详见 [docs/踩坑记录.md](./docs/踩坑记录.md)。

1. **Tez 部署失败** → YARN Classpath 加载问题，改用 MR 参数调优
2. **Phoenix 连接超时** → 检查 ZooKeeper 服务与连接地址
3. **Flume OOM** → JVM 堆内存从 20 MB 调至 1024 MB
4. **RAG 检索噪声** → 清洗 HTML 标签、空白字符并按标题与年份去重

## 项目状态

- ✅ 离线数仓：已完成，含四层建模、ADS 数据集输出与业务分析
- ✅ 实时采集：已完成，含自定义 Sink 与性能调优
- ✅ RAG Demo：已完成最小闭环，支持本地向量检索与可选 LLM 生成
