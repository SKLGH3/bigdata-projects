"""下载公开电影数据并转换为 RAG 知识库需要的标准 CSV。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import urllib.request
from datetime import date
from pathlib import Path
from typing import Iterable

SOURCE_URL = "https://raw.githubusercontent.com/danielgrijalva/movie-stats/master/movies.csv"
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RAW_PATH = BASE_DIR / "data" / "movies_source.csv"
DEFAULT_OUTPUT_PATH = BASE_DIR / "data" / "movies.csv"

GENRE_ZH = {
    "Action": "动作",
    "Adventure": "冒险",
    "Animation": "动画",
    "Biography": "传记",
    "Comedy": "喜剧",
    "Crime": "犯罪",
    "Drama": "剧情",
    "Family": "家庭",
    "Fantasy": "奇幻",
    "History": "历史",
    "Horror": "恐怖",
    "Music": "音乐",
    "Musical": "歌舞",
    "Mystery": "悬疑",
    "Romance": "爱情",
    "Sci-Fi": "科幻",
    "Sport": "运动",
    "Thriller": "惊悚",
    "Western": "西部",
}

COUNTRY_ZH = {
    "Australia": "澳大利亚",
    "Canada": "加拿大",
    "China": "中国大陆",
    "France": "法国",
    "Germany": "德国",
    "Hong Kong": "中国香港",
    "India": "印度",
    "Italy": "意大利",
    "Japan": "日本",
    "South Korea": "韩国",
    "Spain": "西班牙",
    "Taiwan": "中国台湾",
    "United Kingdom": "英国",
    "United States": "美国",
}

OUTPUT_FIELDS = [
    "title",
    "year",
    "country",
    "genres",
    "rating",
    "votes",
    "content_rating",
    "release_date",
    "director",
    "writer",
    "actors",
    "company",
    "runtime_min",
    "budget_usd",
    "gross_usd",
    "summary",
    "crawl_date",
    "source",
    "source_url",
]


def clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def number(value: str, *, integer: bool = False) -> str:
    value = clean(value)
    if not value:
        return ""
    try:
        parsed = float(value)
    except ValueError:
        return ""
    if integer:
        return str(int(parsed))
    return f"{parsed:.1f}".rstrip("0").rstrip(".")


def bilingual(value: str, mapping: dict[str, str]) -> str:
    value = clean(value)
    translated = mapping.get(value)
    return f"{translated}/{value}" if translated else value


def build_summary(row: dict[str, str]) -> str:
    title = clean(row.get("name"))
    year = number(row.get("year", ""), integer=True)
    country = bilingual(row.get("country", ""), COUNTRY_ZH)
    genre = bilingual(row.get("genre", ""), GENRE_ZH)
    director = clean(row.get("director"))
    writer = clean(row.get("writer"))
    star = clean(row.get("star"))
    score = number(row.get("score", ""))
    votes = number(row.get("votes", ""), integer=True)
    runtime = number(row.get("runtime", ""), integer=True)
    company = clean(row.get("company"))

    sentences = [f"《{title}》是一部{year}年上映的{country}{genre}电影。"]
    credits = []
    if director:
        credits.append(f"由{director}执导")
    if writer:
        credits.append(f"{writer}编剧")
    if star:
        credits.append(f"{star}主演")
    if credits:
        sentences.append("，".join(credits) + "。")
    facts = []
    if score:
        facts.append(f"IMDb 用户评分为 {score} 分")
    if votes:
        facts.append(f"评分票数为 {int(votes):,}")
    if runtime:
        facts.append(f"片长 {runtime} 分钟")
    if facts:
        sentences.append("，".join(facts) + "。")
    if company:
        sentences.append(f"制作公司为 {company}。")
    return "".join(sentences)


def transform(rows: Iterable[dict[str, str]], acquired_on: str) -> tuple[list[dict[str, str]], dict[str, int]]:
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    stats = {"raw": 0, "missing_core": 0, "invalid_score": 0, "duplicate": 0}

    for row in rows:
        stats["raw"] += 1
        title = clean(row.get("name"))
        year = number(row.get("year", ""), integer=True)
        score = number(row.get("score", ""))
        if not title or not year or not score:
            stats["missing_core"] += 1
            continue
        if not 0 <= float(score) <= 10:
            stats["invalid_score"] += 1
            continue
        key = (title.casefold(), year)
        if key in seen:
            stats["duplicate"] += 1
            continue
        seen.add(key)

        output.append(
            {
                "title": title,
                "year": year,
                "country": bilingual(row.get("country", ""), COUNTRY_ZH),
                "genres": bilingual(row.get("genre", ""), GENRE_ZH),
                "rating": score,
                "votes": number(row.get("votes", ""), integer=True),
                "content_rating": clean(row.get("rating")),
                "release_date": clean(row.get("released")),
                "director": clean(row.get("director")),
                "writer": clean(row.get("writer")),
                "actors": clean(row.get("star")),
                "company": clean(row.get("company")),
                "runtime_min": number(row.get("runtime", ""), integer=True),
                "budget_usd": number(row.get("budget", ""), integer=True),
                "gross_usd": number(row.get("gross", ""), integer=True),
                "summary": build_summary(row),
                "crawl_date": acquired_on,
                "source": "movie-stats public dataset (originally collected from IMDb)",
                "source_url": SOURCE_URL,
            }
        )

    stats["valid"] = len(output)
    stats["filtered"] = stats["raw"] - stats["valid"]
    return output, stats


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "bigdata-projects-rag-demo/1.0 (educational portfolio)"},
    )
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as target:
        shutil.copyfileobj(response, target)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="获取并加工电影 RAG 数据集")
    parser.add_argument("--source-url", default=SOURCE_URL, help="公开原始 CSV 地址")
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW_PATH, help="原始数据保存路径")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="清洗后 CSV 路径")
    parser.add_argument("--use-local", action="store_true", help="使用已有原始 CSV，不联网下载")
    parser.add_argument("--date", default=date.today().isoformat(), help="数据获取日期 YYYY-MM-DD")
    args = parser.parse_args()

    if not args.use_local:
        print(f"正在下载：{args.source_url}")
        download(args.source_url, args.raw)
    elif not args.raw.exists():
        raise FileNotFoundError(f"未找到本地原始数据：{args.raw}")

    with args.raw.open("r", encoding="utf-8-sig", newline="") as source:
        rows, stats = transform(csv.DictReader(source), args.date)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print("电影数据加工完成")
    print(f"- 原始记录：{stats['raw']} 条")
    print(f"- 有效记录：{stats['valid']} 条")
    print(f"- 过滤记录：{stats['filtered']} 条")
    print(f"- 原始文件 SHA256：{sha256(args.raw)}")
    print(f"- 输出文件：{args.output}")


if __name__ == "__main__":
    main()
