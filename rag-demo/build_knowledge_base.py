"""读取电影 CSV，完成清洗、切片、向量化并写入 Chroma。"""

from __future__ import annotations

import argparse
import html
import re
import shutil
from pathlib import Path

import pandas as pd
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHROMA_DIR, COLLECTION_NAME, DATA_PATH, EMBEDDING_MODEL

CHROMA_WRITE_BATCH_SIZE = 500
CHROMA_SYNC_THRESHOLD = 100_000

REQUIRED_COLUMNS = {
    "title",
    "year",
    "country",
    "genres",
    "rating",
    "director",
    "actors",
    "summary",
    "crawl_date",
}


def clean_text(value: object) -> str:
    """清理 HTML、不可见字符和连续空白。"""
    if pd.isna(value):
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[\u200b-\u200f\ufeff]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def load_and_clean_movies(csv_path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    """读取并清洗电影数据，返回清洗结果及质量统计。"""
    frame = pd.read_csv(csv_path, encoding="utf-8-sig")
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"CSV 缺少字段：{', '.join(sorted(missing))}")

    original_rows = len(frame)
    for column in frame.columns:
        if frame[column].dtype == "object":
            frame[column] = frame[column].map(clean_text)

    frame["rating"] = pd.to_numeric(frame["rating"], errors="coerce")
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
    for numeric_column in ["votes", "runtime_min", "budget_usd", "gross_usd", "box_office_yi"]:
        if numeric_column in frame.columns:
            frame[numeric_column] = pd.to_numeric(frame[numeric_column], errors="coerce")

    frame = frame.dropna(subset=["title", "year", "rating"])
    frame = frame[(frame["title"].str.len() >= 2) & (frame["summary"].str.len() >= 10)]
    frame = frame[(frame["rating"] >= 0) & (frame["rating"] <= 10)]
    frame = frame.drop_duplicates(subset=["title", "year"], keep="last").reset_index(drop=True)

    stats = {
        "original_rows": original_rows,
        "valid_rows": len(frame),
        "filtered_rows": original_rows - len(frame),
    }
    return frame, stats


def movie_to_document(row: pd.Series) -> Document:
    """把一条结构化电影记录转换为适合检索的文本。"""
    def value(name: str, default: str = "暂无") -> str:
        if name not in row or pd.isna(row[name]) or str(row[name]).strip() == "":
            return default
        return str(row[name]).strip()

    def numeric(name: str, suffix: str = "", default: str = "暂无") -> str:
        if name not in row or pd.isna(row[name]):
            return default
        number = float(row[name])
        rendered = f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}"
        return f"{rendered}{suffix}"

    if "gross_usd" in row:
        box_office = numeric("gross_usd", " 美元")
    else:
        box_office = numeric("box_office_yi", " 亿元")

    fields = [
        f"片名：{value('title')}",
        f"上映年份：{int(row['year'])}",
        f"国家/地区：{value('country')}",
        f"类型：{value('genres')}",
        f"IMDb 用户评分：{float(row['rating']):.1f}",
        f"评分人数：{numeric('votes')}",
        f"票房：{box_office}",
        f"预算：{numeric('budget_usd', ' 美元')}",
        f"导演：{value('director')}",
        f"编剧：{value('writer')}",
        f"主演：{value('actors')}",
        f"制作公司：{value('company')}",
        f"片长：{numeric('runtime_min', ' 分钟')}",
        f"简介：{value('summary')}",
        f"数据获取日期：{value('crawl_date')}",
        f"数据来源：{value('source')}",
    ]
    content = "\n".join(fields)
    metadata = {
        "title": value("title", ""),
        "year": int(row["year"]),
        "country": value("country", ""),
        "genres": value("genres", ""),
        "rating": float(row["rating"]),
        "votes": -1 if "votes" not in row or pd.isna(row["votes"]) else int(row["votes"]),
        "gross_usd": -1.0 if "gross_usd" not in row or pd.isna(row["gross_usd"]) else float(row["gross_usd"]),
        "director": value("director", ""),
        "actors": value("actors", ""),
        "crawl_date": value("crawl_date", ""),
        "source": value("source", ""),
    }
    return Document(page_content=content, metadata=metadata)

def build_knowledge_base(csv_path: Path, persist_dir: Path, reset: bool = True) -> None:
    frame, stats = load_and_clean_movies(csv_path)
    if frame.empty:
        raise ValueError("清洗后没有有效数据，请检查 CSV 内容和过滤规则。")

    documents = [movie_to_document(row) for _, row in frame.iterrows()]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=60,
        separators=["\n", "。", "；", "，", " "],
    )
    chunks = splitter.split_documents(documents)

    if reset and persist_dir.exists():
        shutil.rmtree(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    # Chroma 1.x 在 Windows 上一次性写入大量向量时，可能只生成
    # index_metadata.pickle 而没有完整 HNSW 文件。显式创建集合并分批写入，
    # 同时提高同步阈值，避免下次进程启动时加载到半成品索引。
    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(persist_dir),
        embedding_function=embeddings,
        collection_configuration={
            "hnsw": {
                "space": "cosine",
                "sync_threshold": CHROMA_SYNC_THRESHOLD,
            }
        },
    )
    for start in range(0, len(chunks), CHROMA_WRITE_BATCH_SIZE):
        batch = chunks[start : start + CHROMA_WRITE_BATCH_SIZE]
        vector_store.add_documents(
            documents=batch,
            ids=[f"movie-{index}" for index in range(start, start + len(batch))],
        )
        print(f"- 向量写入进度：{min(start + len(batch), len(chunks))}/{len(chunks)}")

    # 在构建进程退出前触发一次检索，确保索引可以被实际读取。
    if not vector_store.similarity_search("电影", k=1):
        raise RuntimeError("向量库构建后验证失败：未能检索到任何文档。")

    print("知识库构建完成并通过检索验证")
    print(f"- 原始记录：{stats['original_rows']} 条")
    print(f"- 有效记录：{stats['valid_rows']} 条")
    print(f"- 过滤记录：{stats['filtered_rows']} 条")
    print(f"- 文本切片：{len(chunks)} 个")
    print(f"- 向量库目录：{persist_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建电影 RAG 向量知识库")
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="电影 CSV 路径")
    parser.add_argument("--persist-dir", type=Path, default=CHROMA_DIR, help="Chroma 持久化目录")
    parser.add_argument("--no-reset", action="store_true", help="不删除已有向量库")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_knowledge_base(args.data, args.persist_dir, reset=not args.no_reset)
