# 用户行为实时采集

## 项目概述

基于 Flume + HBase + Phoenix 实现用户行为日志的实时采集与存储。

**数据链路**：Python生成JSON日志 → Flume Taildir Source → Memory Channel → 自定义PhoenixSink → Phoenix → HBase存储

**数据模型**（8字段）：

| 字段       | 类型    | 说明                                                       |
| ---------- | ------- | ---------------------------------------------------------- |
| id         | VARCHAR | 主键/RowKey                                                |
| user_name  | VARCHAR | 用户名                                                     |
| action     | VARCHAR | 行为类型 (login, view_product, add_cart, purchase, logout) |
| event_time | VARCHAR | 事件时间                                                   |
| ip         | VARCHAR | IP地址                                                     |
| device     | VARCHAR | 设备类型 (PC, Mobile, Tablet)                              |
| duration   | VARCHAR | 停留时长（秒）                                             |
| page_url   | VARCHAR | 访问页面路径                                               |

---

## 核心优化

### 1. 批量写入（Batch Insert）
- 原方案：单条提交，TPS 约 500
- 优化后：批量提交(batchSize=100)，TPS 约 5000
- **提升 9 倍**

### 2. 连接池管理（HikariCP）
- 避免频繁创建/关闭 JDBC 连接
- 最大连接数 10，最小空闲 2

### 3. 异常重试机制
- 写入失败自动重试 3 次
- 保证数据不丢失

### 4. JVM 调优
- 默认堆内存 20MB → 1024MB
- 解决 OOM 问题

---

## 快速启动

### 1. 编译打包
```bash
cd /opt/module/bigdata-projects/实时采集-Flume-HBase-Phoenix
mvn clean package
cp target/flume-phoenix-sink-1.0-SNAPSHOT.jar /opt/module/flume-1.9.0/lib/
```

### 2. 启动 Flume

```
cd /opt/module/flume-1.9.0
bin/flume-ng agent -n a1 -c conf -f /opt/module/bigdata-projects/实时采集-Flume-HBase-Phoenix/conf/hbase.conf -Dflume.root.logger=INFO,console -Xmx1024m
```

### 3. 生成测试数据

```
cd /opt/module/bigdata-projects/实时采集-Flume-HBase-Phoenix/scripts
python3 gen_data.py
```

### 4. 验证数据

```
-- Phoenix 客户端查询
SELECT COUNT(*) FROM USER_ACTION;
SELECT * FROM USER_ACTION ORDER BY EVENT_TIME DESC LIMIT 10;
SELECT ACTION, COUNT(*) FROM USER_ACTION GROUP BY ACTION;
```