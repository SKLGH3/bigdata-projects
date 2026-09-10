"""RAG Demo 配置。

敏感信息只从环境变量读取，不要把真实 API Key 写入或提交到仓库。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATA_PATH = Path(os.getenv("MOVIES_CSV", BASE_DIR / "data" / "movies.csv"))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", BASE_DIR / "chroma_db"))
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "movies_knowledge_base")

# 本地中文向量模型。首次运行会从 Hugging Face 下载模型文件。
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")

# 支持 OpenAI 及其他兼容 OpenAI Chat Completions 接口的模型服务。
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "800"))
LLM_DISABLE_THINKING = os.getenv("LLM_DISABLE_THINKING", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TOP_K = int(os.getenv("TOP_K", "4"))
