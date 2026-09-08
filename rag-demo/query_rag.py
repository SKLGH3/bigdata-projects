"""从 Chroma 检索电影资料，并让 LLM 基于本地知识库回答。"""

from __future__ import annotations

import argparse
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

from config import (
    CHROMA_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    LLM_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    TOP_K,
)

SYSTEM_PROMPT = """你是电影知识库助手。只能依据提供的本地知识库片段回答：
1. 不使用片段之外的事实，不确定时明确说“知识库中没有足够信息”；
2. 推荐电影时给出片名、评分和推荐理由；
3. 在事实后用 [1]、[2] 标注对应片段编号；
4. 最后注明知识库数据的采集日期。"""


def create_vector_store(persist_dir: Path) -> Chroma:
    if not persist_dir.exists():
        raise FileNotFoundError(
            f"未找到向量库：{persist_dir}\n请先运行 python build_knowledge_base.py"
        )
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    return Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(persist_dir),
        embedding_function=embeddings,
    )


def retrieve(vector_store: Chroma, question: str, top_k: int) -> list[Document]:
    return vector_store.similarity_search(question, k=top_k)


def format_context(documents: list[Document]) -> str:
    return "\n\n".join(
        f"[{index}]\n{document.page_content}"
        for index, document in enumerate(documents, start=1)
    )


def format_retrieval_results(documents: list[Document], reason: str) -> str:
    """输出纯检索结果，不调用 LLM。"""
    if not documents:
        return "知识库中没有检索到相关电影。"
    lines = [f"{reason}，当前展示本地向量检索结果："]
    crawl_dates: set[str] = set()
    for index, document in enumerate(documents, start=1):
        meta = document.metadata
        box_office = meta.get("box_office_yi", -1)
        box_text = (
            "暂无票房数据"
            if box_office is None or float(box_office) < 0
            else f"票房约 {float(box_office):.2f} 亿元"
        )
        lines.append(
            f"{index}. 《{meta.get('title', '未知')}》：评分 {float(meta.get('rating', 0)):.1f}，"
            f"导演 {meta.get('director', '未知')}，{box_text}。[{index}]"
        )
        if meta.get("crawl_date"):
            crawl_dates.add(str(meta["crawl_date"]))
    if crawl_dates:
        lines.append(f"知识库采集日期：{', '.join(sorted(crawl_dates))}")
    return "\n".join(lines)


def answer_question(
    vector_store: Chroma,
    question: str,
    top_k: int = TOP_K,
    use_llm: bool = True,
) -> str:
    documents = retrieve(vector_store, question, top_k)
    if not documents:
        return "知识库中没有足够信息。"
    if not use_llm:
        return format_retrieval_results(documents, "已启用 --no-llm")
    if not OPENAI_API_KEY:
        return format_retrieval_results(documents, "未配置 API Key")

    kwargs = {
        "model": LLM_MODEL,
        "api_key": OPENAI_API_KEY,
        "temperature": 0,
    }
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    llm = ChatOpenAI(**kwargs)

    context = format_context(documents)
    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"知识库片段：\n{context}\n\n用户问题：{question}"),
        ]
    )
    return str(response.content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="电影知识库 RAG 问答")
    parser.add_argument("--question", help="单次提问；不传则进入交互模式")
    parser.add_argument("--top-k", type=int, default=TOP_K, help="召回片段数量")
    parser.add_argument("--persist-dir", type=Path, default=CHROMA_DIR, help="Chroma 目录")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="仅输出向量检索结果，不调用大模型 API",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    vector_store = create_vector_store(args.persist_dir)

    if args.question:
        print(
            answer_question(
                vector_store,
                args.question,
                args.top_k,
                use_llm=not args.no_llm,
            )
        )
        return

    print("电影知识库已加载。输入问题开始问答，输入 exit 退出。")
    while True:
        try:
            question = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            break
        if question.lower() in {"exit", "quit", "q"}:
            print("已退出。")
            break
        if not question:
            continue
        try:
            answer = answer_question(
                vector_store,
                question,
                args.top_k,
                use_llm=not args.no_llm,
            )
            print(f"\n助手：{answer}")
        except Exception as exc:
            print(f"\n问答失败：{exc}")


if __name__ == "__main__":
    main()
