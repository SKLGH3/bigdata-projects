# 大数据项目合集

---

## 项目一：电商离线数仓

### 技术栈
`Hive(MR优化)` `Sqoop` `DataEase` `DolphinScheduler`

### 数仓架构

ODS (操作数据存储层) → DWD (明细数据层) → DWS (汇总数据层) → ADS (应用数据层)
原始数据 维度建模 预聚合 业务指标

### 核心优化
| 优化项    | 优化前   | 优化后   | 提升      |
| --------- | -------- | -------- | --------- |
| ETL总耗时 | ~90分钟  | ~45分钟  | **50% ↓** |
| 存储空间  | 100%     | 30%      | **70% ↓** |
| 分区查询  | 全表扫描 | 只扫分区 | **3倍 ↑** |

### 优化措施
- **参数调优**：开启 Map 端聚合、数据倾斜优化、向量化执行
- **存储优化**：Parquet+Snappy 列式存储
- **分区设计**：关键事实表按日期分区
- **调度自动化**：DolphinScheduler 编排 DAG 工作流

### 快速启动
```bash
# 执行分层建表
hive -f sql/01_create_database.sql
hive -f sql/02_create_ods_tables.sql
hive -f sql/03_build_dwd_tables.sql
hive -f sql/04_build_dws_tables.sql
hive -f sql/05_build_ads_tables.sql

# 导出ADS层到MySQL
bash scripts/export_ads.sh
```



------

## 项目二：用户行为实时采集

### 技术栈

```
Flume` `HBase` `Phoenix` `Java` `HikariCP
```

### 数据链路

text

```
Python生成JSON日志 → Flume Taildir Source → Memory Channel → 自定义PhoenixSink → Phoenix → HBase存储
```



### 数据模型（8字段）

| 字段       | 类型    | 说明        |
| :--------- | :------ | :---------- |
| id         | VARCHAR | 主键/RowKey |
| user_name  | VARCHAR | 用户名      |
| action     | VARCHAR | 行为类型    |
| event_time | VARCHAR | 事件时间    |
| ip         | VARCHAR | IP地址      |
| device     | VARCHAR | 设备类型    |
| duration   | VARCHAR | 停留时长    |
| page_url   | VARCHAR | 访问页面    |

### 核心优化

| 优化项      | 优化前    | 优化后     | 提升       |
| :---------- | :-------- | :--------- | :--------- |
| 吞吐量(TPS) | ~500条/秒 | ~5000条/秒 | **900% ↑** |
| 平均延迟    | 2ms/条    | 0.2ms/条   | **90% ↓**  |
| 连接管理    | 频繁创建  | 连接池复用 | **稳定**   |

### 快速启动

#### 1. 编译打包
mvn clean package
cp target/flume-phoenix-sink-1.0-SNAPSHOT.jar /opt/module/flume-1.9.0/l

####        2. 启动Flume
bin/flume-ng agent -n a1 -c conf -f conf/hbase.conf -Dflume.root.logger=INFO,console -Xmx1024m

#### 3. 生成测试数据（另一终端）
python3 scripts/gen_data.py

------

## 调度自动化

### DolphinScheduler

- **部署地址**：`http://hadoop142:12345/dolphinscheduler`
- **默认账号**：`admin` / `dolphinscheduler123`
- **工作流**：数仓每日 ETL（凌晨 2 点执行）
- **失败重试**：3 次，间隔 5 分钟

------

## 项目结构

```
bigdata-projects/
├── README.md                           # 项目总说明
├── docs/                               # 文档目录
│   ├── 环境搭建指南.md
│   ├── 性能对比报告.md
│   └── 踩坑记录.md
├── 离线数仓-电商分析/
│   ├── README.md                       # 子项目说明
│   ├── sql/                            # 5个建表SQL
│   │   ├── 01_create_database.sql
│   │   ├── 02_create_ods_tables.sql
│   │   ├── 03_build_dwd_tables.sql
│   │   ├── 04_build_dws_tables.sql
│   │   └── 05_build_ads_tables.sql
│   ├── scripts/                        # 自动化脚本
│   │   └── export_ads.sh
│   └── conf/                           # 配置文件
│       └── hive-site.xml
└── 实时采集-Flume-HBase-Phoenix/
    ├── README.md                       # 子项目说明
    ├── pom.xml                         # Maven依赖
    ├── src/main/java/com/asxy/flume/
    │   └── PhoenixSink.java            # 自定义Sink源码
    ├── conf/
    │   └── hbase.conf                  # Flume配置
    └── scripts/
        └── gen_data.py                 # 数据生成脚本
```



------

## 踩坑记录

详见 [docs/踩坑记录.md](https://docs/踩坑记录.md)

1. **Tez 部署失败** → YARN Classpath 加载问题，改用 MR 参数调优
2. **YARN ResourceManager 位置** → 在 hadoop143 上，正常现象
3. **Phoenix 连接超时** → ZooKeeper 未启动
4. **Flume OOM** → JVM 内存从 20MB 调至 1024MB
5. **DolphinScheduler 数据库** → PostgreSQL 改 MySQL，驱动复制
6. **DolphinScheduler 端口冲突** → 8080 被占用，改 12345
7. **DolphinScheduler ZK 连接** → localhost 改集群地址