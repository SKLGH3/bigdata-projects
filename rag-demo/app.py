"""Streamlit UI for the local movie RAG demo.

Run from this directory with: streamlit run app.py
"""

from __future__ import annotations

import html
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from langchain_core.documents import Document

from config import CHROMA_DIR, OPENAI_API_KEY
from query_rag import (
    COUNTRIES,
    GENRES,
    SORT_LABELS,
    QueryFilters,
    answer_from_documents,
    create_vector_store,
    parse_query_filters,
    retrieve,
)


st.set_page_config(
    page_title="LocalFrame · 电影知识库",
    page_icon=":material/movie:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --bg: #090b0f;
        --panel: #11151b;
        --panel-2: #171c24;
        --line: #272d38;
        --text: #f2f4f7;
        --muted: #9aa4b2;
        --accent: #d8b26e;
        --good: #68c18c;
    }
    .stApp { background: var(--bg); color: var(--text); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] {
        background: #0d1015;
        border-right: 1px solid var(--line);
        min-width: 238px;
        max-width: 238px;
    }
    [data-testid="stSidebar"] > div:first-child { padding-top: 1.4rem; }
    .block-container {
        max-width: 1480px;
        padding-top: 1.35rem;
        padding-bottom: 4rem;
    }
    .brand-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 1px solid var(--line);
        padding: 0 0 .9rem 0;
        margin-bottom: 1.7rem;
    }
    .brand { font-size: .83rem; font-weight: 760; letter-spacing: .16em; color: #f5f0e7; }
    .status { font-size: .76rem; color: var(--muted); letter-spacing: .06em; }
    .status-dot {
        display: inline-block; width: 7px; height: 7px; border-radius: 50%;
        background: var(--good); margin-right: 8px; box-shadow: 0 0 10px rgba(104,193,140,.45);
    }
    .eyebrow { color: var(--accent); font-size: .75rem; letter-spacing: .16em; font-weight: 700; }
    .hero-title {
        font-size: clamp(2.25rem, 4vw, 4.45rem);
        line-height: 1.04; letter-spacing: -.045em; font-weight: 760;
        max-width: 890px; margin: .7rem 0 .9rem;
    }
    .hero-copy { color: var(--muted); max-width: 720px; line-height: 1.75; font-size: .98rem; }
    .pipeline-card {
        background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
        padding: 1.15rem 1.15rem .9rem; margin-top: .15rem;
    }
    .pipeline-title { font-size: .77rem; color: var(--muted); letter-spacing: .12em; margin-bottom: .9rem; }
    .pipeline-step { display: flex; gap: .75rem; align-items: flex-start; padding: .45rem 0; }
    .step-num { color: var(--accent); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .72rem; }
    .step-name { color: #e9edf2; font-size: .84rem; }
    .step-note { color: #727d8b; font-size: .72rem; margin-top: .12rem; }
    .kpi-grid {
        display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
        border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
        margin: 1.35rem 0 1.45rem;
    }
    .kpi { padding: 1rem 1.2rem; border-right: 1px solid var(--line); }
    .kpi:first-child { padding-left: 0; }
    .kpi:last-child { border-right: 0; }
    .kpi-value { font-size: 1.42rem; font-weight: 720; color: #f7f8fa; }
    .kpi-label { font-size: .75rem; color: var(--muted); margin-top: .18rem; }
    .section-label { color: #cbd2dc; font-size: .78rem; letter-spacing: .1em; font-weight: 680; margin: 1.15rem 0 .65rem; }
    .answer-panel {
        background: var(--panel); border-left: 3px solid var(--accent);
        padding: 1.2rem 1.35rem; margin: .45rem 0 1.1rem;
    }
    .answer-kicker { color: var(--accent); font-size: .73rem; letter-spacing: .13em; font-weight: 700; margin-bottom: .7rem; }
    .answer-text { color: #e8ebef; line-height: 1.75; white-space: pre-wrap; }
    .filter-panel {
        background: #0e1218; border: 1px solid var(--line); padding: .9rem 1rem;
        margin: .35rem 0 1rem;
    }
    .filter-row { display: flex; gap: 1.4rem; flex-wrap: wrap; }
    .filter-item { min-width: 130px; }
    .filter-key { color: #747f8e; font-size: .7rem; letter-spacing: .08em; }
    .filter-value { color: #e5e9ee; font-size: .88rem; margin-top: .2rem; }
    .movie-card {
        height: 100%; min-height: 195px; background: var(--panel); border: 1px solid var(--line);
        border-radius: 7px; padding: 1rem 1.05rem; margin-bottom: .9rem;
    }
    .movie-rank { color: var(--accent); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .72rem; }
    .movie-title { color: #f5f6f8; font-size: 1.05rem; font-weight: 690; margin: .35rem 0 .55rem; line-height: 1.3; }
    .movie-meta { color: #a8b1bd; font-size: .78rem; line-height: 1.7; }
    .movie-summary { color: #7f8996; font-size: .76rem; line-height: 1.55; margin-top: .65rem; }
    .source-line { color: #77818e; font-size: .74rem; border-top: 1px solid var(--line); padding-top: .75rem; margin-top: .35rem; }
    .side-logo { font-size: 1rem; font-weight: 750; letter-spacing: .12em; color: #f0e9dc; margin-bottom: .2rem; }
    .side-sub { color: #727d8a; font-size: .72rem; margin-bottom: 1.6rem; }
    .side-section { color: #7e8997; font-size: .69rem; letter-spacing: .12em; margin: 1.1rem 0 .35rem; }
    .side-status { border-top: 1px solid var(--line); margin-top: 1.4rem; padding-top: 1rem; color: #8f99a6; font-size: .73rem; line-height: 1.7; }
    div[data-testid="stTextInput"] input {
        background: #11151b; border: 1px solid #303744; color: #f3f5f7;
        border-radius: 6px; min-height: 50px;
    }
    div[data-testid="stTextInput"] input:focus { border-color: var(--accent); box-shadow: none; }
    .stButton > button, .stFormSubmitButton > button {
        border-radius: 6px; border: 1px solid #343b47; background: #151a21; color: #e7ebef;
        min-height: 44px; font-weight: 600;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover {
        border-color: var(--accent); color: #fff; background: #1a2029;
    }
    div[data-testid="stAlert"] { border-radius: 6px; }
    hr { border-color: var(--line); }
    @media (max-width: 900px) {
        .hero-title { font-size: 2.45rem; }
        .kpi { padding: .8rem .5rem; }
        .block-container { padding-left: 1rem; padding-right: 1rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def load_vector_store(path_text: str):
    return create_vector_store(Path(path_text))


@st.cache_data(show_spinner=False)
def load_dataset_stats(csv_path: str) -> tuple[int, int, int, int]:
    frame = pd.read_csv(csv_path, usecols=["title", "year", "genres", "rating", "summary"])
    frame["title"] = frame["title"].fillna("").astype(str).str.strip()
    frame["summary"] = frame["summary"].fillna("").astype(str).str.strip()
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce")
    frame["rating"] = pd.to_numeric(frame["rating"], errors="coerce")
    frame = frame.dropna(subset=["year", "rating"])
    frame = frame[(frame["title"].str.len() >= 2) & (frame["summary"].str.len() >= 10)]
    frame = frame[frame["rating"].between(0, 10)].drop_duplicates(["title", "year"], keep="last")
    years = frame["year"].astype(int)
    genres = frame["genres"].fillna("").astype(str).str.split("/").str[0]
    return len(frame), int(genres.nunique()), int(years.min()), int(years.max())


def _number(meta: dict[str, Any], key: str, default: float = -1.0) -> float:
    try:
        value = meta.get(key, default)
        return default if value is None else float(value)
    except (TypeError, ValueError):
        return default


def filter_labels(filters: QueryFilters) -> list[tuple[str, str]]:
    labels: list[tuple[str, str]] = []
    if filters.min_rating is not None or filters.max_rating is not None:
        if filters.min_rating is not None and filters.max_rating is not None:
            value = f"{filters.min_rating:g}–{filters.max_rating:g} 分"
        elif filters.min_rating is not None:
            value = f"≥ {filters.min_rating:g} 分"
        else:
            value = f"≤ {filters.max_rating:g} 分"
        labels.append(("评分", value))
    if filters.year_min is not None or filters.year_max is not None:
        if filters.year_min == filters.year_max:
            value = str(filters.year_min)
        elif filters.year_min is None:
            value = f"≤ {filters.year_max}"
        elif filters.year_max is None:
            value = f"≥ {filters.year_min}"
        else:
            value = f"{filters.year_min}–{filters.year_max}"
        labels.append(("年份", value))
    if filters.genres:
        labels.append(("类型", " / ".join(filters.genres)))
    if filters.countries:
        labels.append(("地区", " / ".join(filters.countries)))
    labels.append(("排序", SORT_LABELS[filters.sort_by]))
    return labels


def apply_manual_filters(
    parsed: QueryFilters,
    enabled: bool,
    min_rating: float,
    year_range: tuple[int, int],
    genre: str,
    country: str,
    sort_label: str,
    full_year_range: tuple[int, int],
) -> QueryFilters:
    if not enabled:
        return parsed
    sort_lookup = {"自动识别": parsed.sort_by, **{label: key for key, label in SORT_LABELS.items()}}
    year_min, year_max = (None, None) if year_range == full_year_range else year_range
    return replace(
        parsed,
        min_rating=min_rating if min_rating > 0 else parsed.min_rating,
        genres=(genre,) if genre != "不限" else parsed.genres,
        countries=(country,) if country != "不限" else parsed.countries,
        year_min=year_min if year_min is not None else parsed.year_min,
        year_max=year_max if year_max is not None else parsed.year_max,
        sort_by=sort_lookup[sort_label],
    )


def extract_summary(document: Document) -> str:
    text = document.page_content.replace("\n", " ")
    match = re.search(r"简介：(.+?)(?:数据获取日期：|数据来源：|$)", text)
    summary = match.group(1).strip() if match else text
    return summary[:155] + ("…" if len(summary) > 155 else "")


def money_text(value: object) -> str:
    amount = _number({"value": value}, "value")
    if amount < 0:
        return "票房暂无"
    if amount >= 100_000_000:
        return f"票房 ${amount / 100_000_000:.2f} 亿"
    if amount >= 10_000:
        return f"票房 ${amount / 10_000:.0f} 万"
    return f"票房 ${amount:,.0f}"


def render_movie_card(document: Document, rank: int) -> None:
    meta = document.metadata
    title = html.escape(str(meta.get("title", "未知电影")))
    director = html.escape(str(meta.get("director", "未知")))
    genres = html.escape(str(meta.get("genres", "类型未知")))
    country = html.escape(str(meta.get("country", "地区未知")))
    summary = html.escape(extract_summary(document))
    rating = _number(meta, "rating", 0)
    year = int(_number(meta, "year", 0))
    gross = html.escape(money_text(meta.get("gross_usd")))
    st.markdown(
        f"""
        <div class="movie-card">
          <div class="movie-rank">MATCH {rank:02d}</div>
          <div class="movie-title">{title}</div>
          <div class="movie-meta">{year} · {genres}<br>{country}<br>IMDb {rating:.1f} · {gross}<br>导演 {director}</div>
          <div class="movie-summary">{summary}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def submit_example(question: str) -> None:
    st.session_state["query_input"] = question
    st.session_state["submitted_question"] = question


with st.sidebar:
    st.markdown('<div class="side-logo">LOCALFRAME</div><div class="side-sub">MOVIE KNOWLEDGE SYSTEM</div>', unsafe_allow_html=True)
    st.markdown('<div class="side-section">回答模式</div>', unsafe_allow_html=True)
    mode = st.radio(
        "回答模式",
        ("本地检索（No LLM）", "LLM 增强回答"),
        label_visibility="collapsed",
        help="本地检索无需 API Key；LLM 模式需要在 .env 中配置兼容 OpenAI 的 API。",
    )
    use_llm = mode == "LLM 增强回答"
    st.markdown('<div class="side-section">召回设置</div>', unsafe_allow_html=True)
    top_k = st.slider("返回电影数", 3, 10, 4)
    strict_filter = st.checkbox("严格应用结构化条件", value=True)
    manual_filter = st.checkbox("启用手动筛选", value=False)
    if manual_filter:
        manual_rating = st.slider("最低评分", 0.0, 10.0, 0.0, 0.5)
        manual_years = st.slider("上映年份", 1980, 2020, (1980, 2020))
        manual_genre = st.selectbox("电影类型", ("不限", *GENRES.keys()))
        manual_country = st.selectbox("国家/地区", ("不限", *COUNTRIES.keys()))
        manual_sort = st.selectbox("排序方式", ("自动识别", *SORT_LABELS.values()))
    else:
        manual_rating = 0.0
        manual_years = (1980, 2020)
        manual_genre = manual_country = "不限"
        manual_sort = "自动识别"
    st.caption("自然语言会自动识别评分、年份、类型、地区和排序意图；手动筛选可覆盖自动结果。")
    st.markdown(
        f"""
        <div class="side-status">
          向量模型<br><strong>BGE small zh</strong><br><br>
          生成模型<br><strong>{'API 已配置' if OPENAI_API_KEY else 'API 未配置'}</strong><br><br>
          数据状态<br><strong>7,663 records · local</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


data_path = Path(__file__).resolve().parent / "data" / "movies.csv"
try:
    movie_count, genre_count, first_year, last_year = load_dataset_stats(str(data_path))
except Exception:
    movie_count, genre_count, first_year, last_year = 7663, 19, 1980, 2020

index_ready = CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir())
st.markdown(
    f"""
    <div class="brand-row">
      <div class="brand">LOCALFRAME / RAG DEMO</div>
      <div class="status"><span class="status-dot"></span>{'INDEX READY' if index_ready else 'INDEX NOT FOUND'} · LOCAL CHROMA</div>
    </div>
    """,
    unsafe_allow_html=True,
)

hero_col, pipeline_col = st.columns([3.25, 1.05], gap="large")
with hero_col:
    st.markdown(
        f"""
        <div class="eyebrow">PRIVATE DATA · GROUNDED ANSWERS</div>
        <div class="hero-title">用自然语言，探索本地电影知识库</div>
        <div class="hero-copy">基于 {movie_count:,} 条结构化电影记录进行语义检索，并将评分、年份、类型和地区转换为可解释的筛选条件。答案只来自本地知识库。</div>
        """,
        unsafe_allow_html=True,
    )
with pipeline_col:
    st.markdown(
        """
        <div class="pipeline-card">
          <div class="pipeline-title">DATA PIPELINE</div>
          <div class="pipeline-step"><span class="step-num">01</span><div><div class="step-name">Movies CSV</div><div class="step-note">清洗与字段标准化</div></div></div>
          <div class="pipeline-step"><span class="step-num">02</span><div><div class="step-name">BGE Embedding</div><div class="step-note">中文语义向量化</div></div></div>
          <div class="pipeline-step"><span class="step-num">03</span><div><div class="step-name">Chroma Index</div><div class="step-note">本地相似度检索</div></div></div>
          <div class="pipeline-step"><span class="step-num">04</span><div><div class="step-name">Grounded Answer</div><div class="step-note">检索结果约束生成</div></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    f"""
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-value">{movie_count:,}</div><div class="kpi-label">条有效电影记录</div></div>
      <div class="kpi"><div class="kpi-value">{genre_count}</div><div class="kpi-label">种电影类型</div></div>
      <div class="kpi"><div class="kpi-value">{first_year}–{last_year}</div><div class="kpi-label">数据年份范围</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

if "query_input" not in st.session_state:
    st.session_state["query_input"] = ""
if "submitted_question" not in st.session_state:
    st.session_state["submitted_question"] = ""

with st.form("movie_search", clear_on_submit=False):
    search_col, action_col = st.columns([7, 1])
    with search_col:
        st.text_input(
            "搜索电影知识库",
            key="query_input",
            placeholder="例如：推荐几部 2010 年后评分 8 分以上的科幻电影",
            label_visibility="collapsed",
        )
    with action_col:
        submitted = st.form_submit_button("开始检索", use_container_width=True)
if submitted and st.session_state["query_input"].strip():
    st.session_state["submitted_question"] = st.session_state["query_input"].strip()

st.markdown('<div class="section-label">示例查询</div>', unsafe_allow_html=True)
examples = (
    "推荐几部高分喜剧电影",
    "2010年后评分8分以上的科幻电影",
    "哪些动作电影的全球票房最高",
)
example_cols = st.columns(3, gap="medium")
for column, example in zip(example_cols, examples):
    with column:
        st.button(example, key=f"example_{example}", use_container_width=True, on_click=submit_example, args=(example,))

if not index_ready:
    st.error("未找到本地向量库 chroma_db。请先在 rag-demo 目录构建知识库。")
    st.code("python build_knowledge_base.py\nstreamlit run app.py", language="powershell")
    st.stop()

try:
    with st.spinner("正在加载本地向量模型与 Chroma 索引…"):
        vector_store = load_vector_store(str(CHROMA_DIR))
except Exception as exc:
    st.error("向量库加载失败。索引可能不完整，请删除 chroma_db 后重新构建。")
    with st.expander("查看错误详情"):
        st.exception(exc)
    st.code("Remove-Item -LiteralPath .\\chroma_db -Recurse -Force\npython build_knowledge_base.py", language="powershell")
    st.stop()

question = st.session_state.get("submitted_question", "").strip()
if question:
    st.markdown('<div class="section-label">查询结果</div>', unsafe_allow_html=True)
    parsed_filters = parse_query_filters(question)
    filters = apply_manual_filters(
        parsed_filters,
        manual_filter,
        manual_rating,
        manual_years,
        manual_genre,
        manual_country,
        manual_sort,
        (1980, 2020),
    )

    try:
        with st.spinner("正在进行语义召回与结构化过滤…"):
            result_docs = retrieve(vector_store, question, top_k, filters)
            fell_back = False
            if not result_docs and not strict_filter and filters.active:
                fallback_filters = QueryFilters(sort_by=filters.sort_by)
                result_docs = retrieve(vector_store, question, top_k, fallback_filters)
                fell_back = True
            answer = answer_from_documents(result_docs, question, filters, use_llm=use_llm)
    except Exception as exc:
        st.error("查询失败。请确认 Chroma 索引完整，并检查模型或 API 配置。")
        with st.expander("查看错误详情"):
            st.exception(exc)
        st.stop()

    if use_llm and not OPENAI_API_KEY:
        st.warning("当前未配置 API Key，已由 query_rag.py 自动回退为本地检索回答。")
    if fell_back:
        st.info("没有满足全部结构化条件的结果，已回退到纯语义召回。")

    st.markdown(
        f'<div class="answer-panel"><div class="answer-kicker">GROUNDED ANSWER</div><div class="answer-text">{html.escape(answer)}</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-label">结构化筛选条件</div>', unsafe_allow_html=True)
    items = filter_labels(filters)
    filters_html = "".join(
        f'<div class="filter-item"><div class="filter-key">{html.escape(key)}</div><div class="filter-value">{html.escape(value)}</div></div>'
        for key, value in items
    )
    st.markdown(f'<div class="filter-panel"><div class="filter-row">{filters_html}</div></div>', unsafe_allow_html=True)

    st.markdown(f'<div class="section-label">命中电影 · {len(result_docs)} RESULTS</div>', unsafe_allow_html=True)
    if result_docs:
        for start in range(0, len(result_docs), 2):
            row = st.columns(2, gap="medium")
            for offset, doc in enumerate(result_docs[start : start + 2]):
                with row[offset]:
                    render_movie_card(doc, start + offset + 1)

        sources = sorted({str(doc.metadata.get("source", "本地电影数据集")) for doc in result_docs})
        dates = sorted({str(doc.metadata.get("crawl_date")) for doc in result_docs if doc.metadata.get("crawl_date")})
        st.markdown(
            f'<div class="source-line">数据来源：{html.escape("；".join(sources))}<br>采集日期：{html.escape("、".join(dates) or "未记录")} · 检索索引：本地 Chroma DB</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("知识库中没有同时满足这些条件的电影。可降低评分门槛、放宽年份，或关闭侧栏中的严格过滤。")
else:
    st.caption("选择一个示例，或输入自己的问题开始检索。首次加载向量模型可能需要一些时间。")

