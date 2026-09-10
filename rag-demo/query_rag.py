"""从 Chroma 检索电影资料，并让 LLM 基于本地知识库回答。"""
from __future__ import annotations

import argparse
import math
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_chroma import Chroma
    from langchain_core.documents import Document
else:
    Chroma = Document = Any

try:
    from config import (
        CHROMA_DIR,
        COLLECTION_NAME,
        EMBEDDING_MODEL,
        LLM_MODEL,
        LLM_TIMEOUT,
        LLM_MAX_TOKENS,
        LLM_DISABLE_THINKING,
        OPENAI_API_KEY,
        OPENAI_BASE_URL,
        TOP_K,
    )
except ModuleNotFoundError as exc:
    # 纯单元测试无需安装 LangChain/python-dotenv，也不会访问 Chroma 或网络。
    if exc.name != "dotenv":
        raise
    _BASE = Path(__file__).resolve().parent
    CHROMA_DIR = Path(os.getenv("CHROMA_DIR", _BASE / "chroma_db"))
    COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "movies_knowledge_base")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "800"))
    LLM_DISABLE_THINKING = os.getenv("LLM_DISABLE_THINKING", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
    TOP_K = int(os.getenv("TOP_K", "4"))

SYSTEM_PROMPT = """你是电影知识库助手，只能依据提供的本地知识库片段回答。
推荐时给出片名、评分和理由，事实后标注片段编号，最后注明采集日期；严格遵守程序筛选条件。"""

GENRES = {
    "喜剧": ("喜剧", "comedy"),
    "动作": ("动作", "action"),
    "科幻": ("科幻", "sci-fi", "science fiction"),
    "剧情": ("剧情", "drama"),
    "恐怖": ("恐怖", "horror"),
    "爱情": ("爱情", "romance", "romantic"),
    "动画": ("动画", "animation", "animated"),
    "冒险": ("冒险", "adventure"),
    "犯罪": ("犯罪", "crime"),
    "悬疑": ("悬疑", "mystery", "thriller"),
    "奇幻": ("奇幻", "fantasy"),
    "家庭": ("家庭", "family"),
    "传记": ("传记", "biography"),
    "音乐": ("音乐", "music", "musical"),
    "体育": ("体育", "sport"),
    "历史": ("历史", "history"),
    "西部": ("西部", "western"),
}
COUNTRIES = {
    "中国": ("中国", "china", "chinese", "香港", "hong kong", "台湾", "taiwan"),
    "美国": ("美国", "united states", "usa", "u.s."),
    "日本": ("日本", "japan", "japanese"),
    "韩国": ("韩国", "south korea", "korea", "korean"),
    "英国": ("英国", "united kingdom", "uk", "britain", "british"),
    "法国": ("法国", "france", "french"),
    "印度": ("印度", "india", "indian"),
    "加拿大": ("加拿大", "canada", "canadian"),
    "德国": ("德国", "germany", "german"),
    "澳大利亚": ("澳大利亚", "australia", "australian"),
}
COUNTRY_WORDS = {
    "国产": "中国",
    "中国": "中国",
    "大陆": "中国",
    "华语": "中国",
    "美国": "美国",
    "日本": "日本",
    "韩国": "韩国",
    "英国": "英国",
    "法国": "法国",
    "印度": "印度",
    "加拿大": "加拿大",
    "德国": "德国",
    "澳大利亚": "澳大利亚",
}
SORT_LABELS = {
    "semantic": "语义相关度",
    "rating": "评分从高到低",
    "gross": "全球票房从高到低",
    "year": "上映年份从新到旧",
    "votes": "评分人数从多到少",
}


@dataclass(frozen=True)
class QueryFilters:
    min_rating: float | None = None
    genres: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    year_min: int | None = None
    year_max: int | None = None
    max_rating: float | None = None
    sort_by: str = "semantic"

    @property
    def active(self) -> bool:
        return any(
            (
                self.min_rating is not None,
                self.max_rating is not None,
                self.genres,
                self.countries,
                self.year_min is not None,
                self.year_max is not None,
                self.sort_by != "semantic",
            )
        )

    def descriptions(self) -> list[str]:
        parts: list[str] = []
        if self.min_rating is not None and self.max_rating is not None:
            parts.append(f"评分：{self.min_rating:.1f}–{self.max_rating:.1f}")
        elif self.min_rating is not None:
            parts.append(f"评分 ≥ {self.min_rating:.1f}")
        elif self.max_rating is not None:
            parts.append(f"评分 ≤ {self.max_rating:.1f}")
        if self.genres:
            parts.append(f"类型：{'、'.join(self.genres)}")
        if self.countries:
            parts.append(f"国家/地区：{'、'.join(self.countries)}")
        if self.year_min is not None and self.year_max is not None:
            label = str(self.year_min) if self.year_min == self.year_max else f"{self.year_min}–{self.year_max}"
            parts.append(f"年份：{label}")
        elif self.year_min is not None:
            parts.append(f"年份 ≥ {self.year_min}")
        elif self.year_max is not None:
            parts.append(f"年份 ≤ {self.year_max}")
        if self.sort_by != "semantic":
            parts.append(f"排序：{SORT_LABELS[self.sort_by]}")
        return parts


def parse_query_filters(question: str) -> QueryFilters:
    """从自然语言中解析评分、类型、地区、年份和排序意图。"""
    text = question.lower().strip()
    min_rating = max_rating = None

    above_patterns = (
        r"(?:评分|豆瓣|imdb)?\s*(\d(?:\.\d)?)\s*分?\s*(?:及|或)?以上",
        r"(?:评分|豆瓣|imdb)?\s*(?:不低于|至少|大于等于|>=|≥)\s*(\d(?:\.\d)?)\s*分?",
    )
    below_patterns = (
        r"(?:评分|豆瓣|imdb)?\s*(\d(?:\.\d)?)\s*分?\s*(?:及|或)?以下",
        r"(?:评分|豆瓣|imdb)?\s*(?:不高于|至多|小于等于|<=|≤)\s*(\d(?:\.\d)?)\s*分?",
    )
    for pattern in above_patterns:
        match = re.search(pattern, text, re.I)
        if match and 0 <= float(match.group(1)) <= 10:
            min_rating = float(match.group(1))
            break
    for pattern in below_patterns:
        match = re.search(pattern, text, re.I)
        if match and 0 <= float(match.group(1)) <= 10:
            max_rating = float(match.group(1))
            break
    if min_rating is None and "高分" in text:
        min_rating = 7.0

    genres = tuple(name for name in GENRES if name in text)
    countries: list[str] = []
    for word, name in COUNTRY_WORDS.items():
        if word in text and name not in countries:
            countries.append(name)

    year_min = year_max = None
    match = re.search(r"((?:19|20)\d{2})\s*年?\s*(?:到|至|[-~～—])\s*((?:19|20)\d{2})\s*年?", text)
    if match:
        year_min, year_max = sorted(map(int, match.groups()))
    else:
        match = re.search(r"((?:19|20)?\d{2})\s*年代", text)
        if match:
            raw = match.group(1)
            short = int(raw)
            decade = short if len(raw) == 4 else (2000 + short if short <= 20 else 1900 + short)
            year_min, year_max = decade - decade % 10, decade - decade % 10 + 9
        else:
            after = re.search(r"((?:19|20)\d{2})\s*年?\s*(?:以后|之后|以来|起|及以后|后)", text)
            before = re.search(r"((?:19|20)\d{2})\s*年?\s*(?:以前|之前|及以前|前)", text)
            if after:
                year_min = int(after.group(1))
            if before:
                year_max = int(before.group(1))
            if not after and not before:
                exact = re.search(r"((?:19|20)\d{2})\s*年(?:上映|的|电影|作品)?", text)
                if exact:
                    year_min = year_max = int(exact.group(1))

    if any(word in text for word in ("票房最高", "高票房", "票房排行", "票房排名")):
        sort_by = "gross"
    elif any(word in text for word in ("评分最高", "最高分", "高分")):
        sort_by = "rating"
    elif any(word in text for word in ("最新", "最近上映", "较新")):
        sort_by = "year"
    elif any(word in text for word in ("最热门", "评分人数最多", "最多人评价")):
        sort_by = "votes"
    else:
        sort_by = "semantic"

    return QueryFilters(min_rating, genres, tuple(countries), year_min, year_max, max_rating, sort_by)


def create_vector_store(persist_dir: Path) -> Chroma:
    if not persist_dir.exists():
        raise FileNotFoundError(f"未找到向量库：{persist_dir}\n请先运行 python build_knowledge_base.py")
    # 查询只使用构建知识库时已下载的模型，禁止 Hugging Face 联网探测。
    # 否则 Windows 网络不可达时，每次启动会进行多轮 HEAD 重试，看起来像“没有反应”。
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    from langchain_chroma import Chroma as ChromaStore
    from langchain_huggingface import HuggingFaceEmbeddings

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu", "local_files_only": True},
        encode_kwargs={"normalize_embeddings": True},
    )
    return ChromaStore(
        collection_name=COLLECTION_NAME,
        persist_directory=str(persist_dir),
        embedding_function=embeddings,
    )


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return default


def _has(value: Any, aliases: tuple[str, ...]) -> bool:
    text = str(value or "").lower()
    return any(alias.lower() in text for alias in aliases)


def document_matches_filters(document: Document, filters: QueryFilters) -> bool:
    meta = document.metadata
    rating = _float(meta.get("rating"), -1)
    if filters.min_rating is not None and rating < filters.min_rating:
        return False
    if filters.max_rating is not None and rating > filters.max_rating:
        return False
    # 当前数据每部电影只有一个主类型，多类型查询按“任一类型”匹配。
    if filters.genres and not any(_has(meta.get("genres"), GENRES[genre]) for genre in filters.genres):
        return False
    if filters.countries and not any(_has(meta.get("country"), COUNTRIES[country]) for country in filters.countries):
        return False
    year = _int(meta.get("year"), -1)
    if filters.year_min is not None and year < filters.year_min:
        return False
    if filters.year_max is not None and year > filters.year_max:
        return False
    return True


def _dedupe(documents: list[Document]) -> list[Document]:
    seen: set[tuple[str, int]] = set()
    result: list[Document] = []
    for document in documents:
        key = (
            str(document.metadata.get("title", "")).strip().casefold(),
            _int(document.metadata.get("year"), -1),
        )
        if key not in seen:
            seen.add(key)
            result.append(document)
    return result


def _scored_search(store: Chroma, question: str, k: int) -> list[tuple[Document, float]]:
    method = getattr(store, "similarity_search_with_relevance_scores", None)
    if callable(method):
        try:
            return [(doc, _float(score)) for doc, score in method(question, k=k)]
        except (AttributeError, NotImplementedError):
            pass
    documents = store.similarity_search(question, k=k)
    total = max(len(documents), 1)
    return [(doc, 1 - rank / total) for rank, doc in enumerate(documents)]


def _all_documents(store: Chroma) -> list[Document]:
    """读取本地集合全部元数据；用于票房/评分/年份等全局排序。"""
    get_method = getattr(store, "get", None)
    if not callable(get_method):
        return []
    raw = get_method(include=["documents", "metadatas"])
    texts = raw.get("documents") or []
    metadatas = raw.get("metadatas") or []
    try:
        from langchain_core.documents import Document as DocumentClass
    except ModuleNotFoundError:
        @dataclass
        class DocumentClass:  # type: ignore[no-redef]
            page_content: str
            metadata: dict[str, Any]

    return [
        DocumentClass(page_content=text or "", metadata=metadata or {})
        for text, metadata in zip(texts, metadatas)
    ]


def _quality_rank(document: Document, similarity: float) -> float:
    rating = min(max(_float(document.metadata.get("rating")) / 10, 0), 1)
    votes = min(math.log10(max(_float(document.metadata.get("votes")), 0) + 1) / 7, 1)
    similarity = min(max(similarity, 0), 1)
    return similarity * 0.55 + rating * 0.30 + votes * 0.15


def _sort_documents(
    items: list[tuple[Document, float]], filters: QueryFilters
) -> list[Document]:
    if filters.sort_by == "gross":
        items.sort(key=lambda item: (_float(item[0].metadata.get("gross_usd"), -1), _float(item[0].metadata.get("rating"))), reverse=True)
    elif filters.sort_by == "rating":
        items.sort(key=lambda item: (_float(item[0].metadata.get("rating"), -1), _float(item[0].metadata.get("votes"))), reverse=True)
    elif filters.sort_by == "year":
        items.sort(key=lambda item: (_int(item[0].metadata.get("year"), -1), _float(item[0].metadata.get("rating"))), reverse=True)
    elif filters.sort_by == "votes":
        items.sort(key=lambda item: (_float(item[0].metadata.get("votes"), -1), _float(item[0].metadata.get("rating"))), reverse=True)
    else:
        items.sort(key=lambda item: (_quality_rank(item[0], item[1]), item[1]), reverse=True)
    return _dedupe([document for document, _ in items])


def retrieve(
    vector_store: Chroma,
    question: str,
    top_k: int,
    filters: QueryFilters | None = None,
) -> list[Document]:
    """语义召回后执行结构化过滤；显式排行问题在全库范围内精确排序。"""
    if top_k <= 0:
        return []
    filters = filters or parse_query_filters(question)

    # “票房最高/评分最高/最新”等问题必须扫描全部元数据，否则只会在少量语义候选中排序。
    if filters.sort_by != "semantic":
        all_documents = _all_documents(vector_store)
        if all_documents:
            matches = [(doc, 0.0) for doc in all_documents if document_matches_filters(doc, filters)]
            return _sort_documents(matches, filters)[:top_k]

    if not filters.active:
        return _dedupe(vector_store.similarity_search(question, k=max(top_k * 3, top_k)))[:top_k]

    candidate_k = min(max(120, top_k * 40), 400)
    candidates = _scored_search(vector_store, question, candidate_k)
    matches = [(doc, score) for doc, score in candidates if document_matches_filters(doc, filters)]

    # 语义候选没有命中时，再扫描元数据兜底，避免严格条件被小候选池漏掉。
    if not matches:
        all_documents = _all_documents(vector_store)
        matches = [(doc, 0.0) for doc in all_documents if document_matches_filters(doc, filters)]
    return _sort_documents(matches, filters)[:top_k]


def format_context(documents: list[Document]) -> str:
    return "\n\n".join(f"[{index}]\n{document.page_content}" for index, document in enumerate(documents, 1))


def format_filter_summary(filters: QueryFilters) -> str:
    if filters.active:
        return f"已应用筛选：{'；'.join(filters.descriptions())}"
    return "未应用结构化筛选，结果按语义相关度检索"


def format_retrieval_results(
    documents: list[Document],
    reason: str,
    filters: QueryFilters | None = None,
) -> str:
    summary = format_filter_summary(filters or QueryFilters())
    if not documents:
        return f"{summary}。知识库中没有检索到符合条件的电影。"
    lines = [f"{reason}；{summary}："]
    dates: set[str] = set()
    for index, document in enumerate(documents, 1):
        meta = document.metadata
        gross = _float(meta.get("gross_usd"), -1)
        box_office = "暂无票房数据" if gross < 0 else f"全球票房约 {gross:,.0f} 美元"
        lines.append(
            f"{index}. 《{meta.get('title', '未知')}》（{_int(meta.get('year')) or '年份未知'}）："
            f"评分 {_float(meta.get('rating')):.1f}，导演 {meta.get('director', '未知')}，{box_office}。[{index}]"
        )
        if meta.get("crawl_date"):
            dates.add(str(meta["crawl_date"]))
    if dates:
        lines.append(f"知识库采集日期：{', '.join(sorted(dates))}")
    return "\n".join(lines)


def answer_from_documents(
    documents: list[Document],
    question: str,
    filters: QueryFilters,
    use_llm: bool = True,
) -> str:
    """基于已检索文档回答，供 CLI 与 UI 复用，避免 UI 重复检索。"""
    summary = format_filter_summary(filters)
    if not documents:
        return f"{summary}。知识库中没有足够信息。"
    if not use_llm:
        return format_retrieval_results(documents, "本地向量检索结果", filters)
    if not OPENAI_API_KEY:
        return format_retrieval_results(documents, "未配置 API Key，已回退到本地检索", filters)

    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = {
        "model": LLM_MODEL,
        "api_key": OPENAI_API_KEY,
        "temperature": 0,
        "timeout": LLM_TIMEOUT,
        "max_retries": 1,
        "max_tokens": LLM_MAX_TOKENS,
    }
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    if LLM_DISABLE_THINKING and "deepseek.com" in OPENAI_BASE_URL.lower():
        # DeepSeek V4 默认启用思考模式。RAG 展示更重视响应速度，默认关闭，
        # 避免短问题长时间停留在“正在回答”。可通过 .env 重新开启。
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    response = ChatOpenAI(**kwargs).invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"程序筛选说明：{summary}\n\n"
                    f"知识库片段：\n{format_context(documents)}\n\n"
                    f"用户问题：{question}"
                )
            ),
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)
    if not content.strip():
        raise RuntimeError("大模型返回内容为空，请检查模型名称或将 LLM_DISABLE_THINKING 设为 true。")
    return f"{summary}。\n\n{content}"


def answer_question(
    vector_store: Chroma,
    question: str,
    top_k: int = TOP_K,
    use_llm: bool = True,
    filters: QueryFilters | None = None,
) -> str:
    """检索并回答；保留原调用方式，同时允许 UI 传入手动筛选条件。"""
    resolved_filters = filters or parse_query_filters(question)
    documents = retrieve(vector_store, question, top_k, resolved_filters)
    return answer_from_documents(documents, question, resolved_filters, use_llm)


def with_sort(filters: QueryFilters, sort_by: str) -> QueryFilters:
    """为 UI 提供不可变筛选对象的排序覆盖。"""
    return replace(filters, sort_by=sort_by)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="电影知识库 RAG 问答")
    parser.add_argument("--question", help="单次提问；不传则进入交互模式")
    parser.add_argument("--top-k", type=int, default=TOP_K, help="返回电影数量")
    parser.add_argument("--persist-dir", type=Path, default=CHROMA_DIR, help="Chroma 目录")
    parser.add_argument("--no-llm", action="store_true", help="仅输出本地检索结果，不调用大模型 API")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store = create_vector_store(args.persist_dir)
    if args.question:
        print(answer_question(store, args.question, args.top_k, not args.no_llm))
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
            print(f"\n助手：{answer_question(store, question, args.top_k, not args.no_llm)}")
        except Exception as exc:
            print(f"\n问答失败：{exc}")


if __name__ == "__main__":
    main()
