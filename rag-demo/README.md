# RAG 知识库问答 Demo

## 项目概述

基于 LangChain + Chroma，将清洗后的电影数据构建为本地向量知识库，实现“数据加载 → 文本切片 → 向量化 → 检索 → LLM 生成”的最小 RAG 闭环。回答被约束为仅使用本地检索结果，降低大模型脱离数据编造答案的风险。

## 数据来源

数据字段来自 Scrapy 电影采集项目的清洗结果设计，包括片名、评分、票房、题材、简介、导演和演员等。仓库附带 **16 条可直接运行的公开电影数据样例**，采集快照日期为 **2025-10-15**；评分和票房仅用于技术演示，不作为实时榜单依据。接入完整爬虫数据时，只需按相同字段替换 `data/movies.csv`。

### CSV 字段

| 字段 | 含义 |
| --- | --- |
| title / year | 片名 / 上映年份 |
| country / genres | 国家地区 / 类型 |
| rating / box_office_yi | 评分 / 票房（亿元） |
| director / actors | 导演 / 主要演员 |
| summary | 电影简介 |
| crawl_date | 数据采集日期 |

## 技术链路

```text
电影数据（CSV）
  → pandas 清洗、去重、异常值过滤
  → RecursiveCharacterTextSplitter 文本切片
  → BGE 中文 Embedding
  → Chroma 本地向量库
  → 用户 Query 相似度检索
  → OpenAI-compatible LLM 基于上下文生成答案
```

## 项目结构

```text
rag-demo/
├── README.md
├── requirements.txt
├── .env.example
├── config.py                    # 从环境变量读取配置，不保存密钥
├── build_knowledge_base.py      # CSV → 清洗 → 切片 → 向量库
├── query_rag.py                 # Query → 检索 → LLM/本地结果
├── demo_screenshot.png
└── data/
    └── movies.csv
```

## 快速体验

```bash
pip install -r requirements.txt
python build_knowledge_base.py   # 首次需下载 Embedding 模型
python query_rag.py              # 启动交互式问答
```

单次提问：

```bash
python query_rag.py --question "推荐几部高分国产喜剧电影"
```

### 配置大模型（可选）

不配置 API Key 时，程序仍会展示本地向量检索结果。若需要完整的 LLM 生成回答：

```bash
copy .env.example .env          # Windows
# cp .env.example .env          # Linux / macOS
```

然后在 `.env` 中填写 `OPENAI_API_KEY`。如使用兼容 OpenAI 接口的其他模型服务，同时设置 `OPENAI_BASE_URL` 与 `LLM_MODEL`。

## 运行效果

![RAG Demo 问答效果](./demo_screenshot.png)

示例问题：`推荐几部高分国产喜剧电影。`

系统先从本地 Chroma 召回电影片段，再要求模型只根据这些片段作答并标注来源。知识库的时效性由 CSV 的采集日期控制，而不是依赖通用模型训练数据的截止时间。

## 数据质量处理

构建脚本包含以下质量规则：

- 校验 CSV 必需字段，缺字段时直接失败并提示
- 清理 HTML 标签、HTML 实体、不可见字符与连续空白
- 过滤标题过短、简介缺失、评分超出 0～10 的记录
- 按“片名 + 年份”去重，并输出原始、有效、过滤记录数
- API Key 仅从 `.env` 读取，向量库与密钥文件均不提交 Git

## 踩坑记录

**问题：电影简介中的 HTML 标签导致检索噪声。** 爬虫采集的简介曾包含 `<br>`、转义字符和重复空白，Embedding 会把无意义标记一起编码，导致相似度召回不稳定。解决方式是在入库前用正则表达式去除 HTML 标签，使用 `html.unescape` 还原实体，再统一空白字符，并以“片名 + 年份”去重。清洗后，针对类型、导演和剧情关键词的召回结果更集中。

## 后续计划

- 增加 RAGAS/自定义问题集，评估命中率、忠实度和回答相关性
- 使用 DVC 管理电影数据集版本，记录每次清洗规则和数据质量变化
- 增加 FastAPI 接口和简单 Web UI，支持在线演示
